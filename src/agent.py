"""Mimir MemoryAgent -- persistent AI memory on Qwen Cloud.

Loop: recall -> reason -> remember -> (periodic) groom.

Deep Qwen Cloud integration:
  * Reasoning over recalled context with qwen-max-longcontext
  * Memory writes via Qwen native function calling (store_memories tool)
  * Hybrid recall (FTS5 + Qwen text-embedding-v3 cosine similarity)
"""

import os
import sys
import json
import textwrap
from datetime import datetime, timezone

from mimir_bridge import MimirBridge
from qwen_client import QwenClient


SYSTEM_PROMPT = textwrap.dedent("""\
    You are Mimir MemoryAgent -- a persistent-memory assistant powered by Qwen
    Cloud and a SQLite-backed memory store.

    Relevant memories from past sessions are provided before each message. Use
    them to give informed, personalized answers. When you recall something from
    a previous session, say so explicitly. When you are unsure, ask.

    Memory categories: user_preference, project_fact, decision, correction, insight.
    """)

# Qwen function-calling schema: the model decides what (if anything) to persist.
STORE_TOOL = [{
    "type": "function",
    "function": {
        "name": "store_memories",
        "description": (
            "Persist genuinely new facts, preferences, decisions, corrections, "
            "or insights learned from the latest exchange. Omit anything already "
            "known or trivial. Call with an empty list if nothing is worth saving."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["user_preference", "project_fact",
                                         "decision", "correction", "insight"],
                            },
                            "key": {
                                "type": "string",
                                "description": "short hyphenated-lowercase id",
                            },
                            "content": {"type": "string"},
                            "importance": {
                                "type": "number",
                                "description": "0.0-1.0; 1.0 = critical, never forget",
                            },
                        },
                        "required": ["category", "key", "content", "importance"],
                    },
                }
            },
            "required": ["items"],
        },
    },
}]

DEFAULT_MODEL = os.environ.get("QWEN_MODEL", "qwen-max-longcontext")
TOOL_MODEL = os.environ.get("QWEN_TOOL_MODEL", "qwen-max")
DEFAULT_DB = os.environ.get("MIMIR_DB_PATH", "./mimir.db")


class MemoryAgent:
    """Persistent-memory AI agent: Qwen Cloud reasoning + embedded Mimir store."""

    def __init__(self, api_key=None, model=DEFAULT_MODEL, mimir_db=DEFAULT_DB,
                 tool_model=TOOL_MODEL):
        self.mimir_db = mimir_db
        self.model = model
        self.tool_model = tool_model
        self.turn_count = 0
        self.session_start = datetime.now(timezone.utc)
        self.qwen = QwenClient(api_key=api_key, model=model)
        self.mimir = MimirBridge(db_path=mimir_db, embed_fn=self.qwen.embed)
        self.history = []
        self.memories_stored = 0
        self.memories_recalled = 0

    def process(self, user_message):
        self.turn_count += 1
        memories = self._recall_memories(user_message)
        memory_context = self._format_memories(memories)
        messages = self._build_messages(user_message, memory_context)
        response = self.qwen.chat(messages=messages, system=SYSTEM_PROMPT,
                                  temperature=0.7)
        self._store_new_memories(user_message, response)
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": response})
        if self.turn_count % 10 == 0:
            self._groom_memory()
        return response

    def _recall_memories(self, query):
        results = self.mimir.recall(query=query, limit=8, mode="hybrid")
        seen = {(r["category"], r["key"]) for r in results}
        for category in ("user_preference", "project_fact"):
            for r in self.mimir.recall(query=query, limit=3, category=category,
                                       mode="hybrid"):
                k = (r["category"], r["key"])
                if k not in seen:
                    seen.add(k)
                    results.append(r)
        self.memories_recalled += len(results)
        return results[:10]

    def _format_memories(self, memories):
        if not memories:
            return "(No relevant memories from past sessions yet.)"
        lines = ["[Memories from past sessions]"]
        for m in memories:
            lines.append(f"  [{m['category']}] {m['key']}: {m['content']}")
        return "\n".join(lines)

    def _build_messages(self, user_message, memory_context):
        recent = self.history[-20:] if self.history else []
        messages = list(recent)
        messages.append({
            "role": "user",
            "content": f"{memory_context}\n\n---\n\nCurrent message: {user_message}",
        })
        return messages

    def _store_new_memories(self, user_message, assistant_response):
        """Let Qwen decide what to remember via native function calling."""
        try:
            msg = self.qwen.chat_with_tools(
                messages=[{
                    "role": "user",
                    "content": (
                        "Decide what (if anything) to remember from this exchange.\n\n"
                        f"User: {user_message}\nAssistant: {assistant_response}"
                    ),
                }],
                tools=STORE_TOOL,
                tool_choice={"type": "function",
                             "function": {"name": "store_memories"}},
                model=self.tool_model,
            )
        except Exception as e:
            print(f"[memory extraction skipped: {e}]", file=sys.stderr)
            return

        if not getattr(msg, "tool_calls", None):
            return
        try:
            args = json.loads(msg.tool_calls[0].function.arguments)
        except (json.JSONDecodeError, AttributeError, IndexError):
            return
        for item in args.get("items", []):
            if not isinstance(item, dict) or not item.get("content"):
                continue
            self.mimir.remember(
                category=item.get("category", "insight"),
                key=item.get("key", f"mem-{self.turn_count}"),
                content=item["content"],
                importance=float(item.get("importance", 0.5)),
            )
            self.memories_stored += 1

    def _groom_memory(self):
        try:
            self.mimir.cohere()
            print("[memory grooming complete]", file=sys.stderr)
        except Exception as e:
            print(f"[grooming note: {e}]", file=sys.stderr)

    def get_stats(self):
        return {
            "session_start": self.session_start.isoformat(),
            "turn_count": self.turn_count,
            "memories_stored": self.memories_stored,
            "memories_recalled": self.memories_recalled,
            "model": self.model,
            "tool_model": self.tool_model,
        }

    def get_mimir_stats(self):
        return self.mimir.stats()


def ask(question, api_key=None):
    """Quick single-turn query with memory."""
    return MemoryAgent(api_key=api_key).process(question)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Mimir MemoryAgent -- persistent AI memory on Qwen Cloud"
    )
    parser.add_argument("--api-key", default=os.environ.get("QWEN_CLOUD_API_KEY", ""))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--mimir-db", default=DEFAULT_DB)
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("message", nargs="*")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: QWEN_CLOUD_API_KEY required (export it or pass --api-key).",
              file=sys.stderr)
        sys.exit(1)

    agent = MemoryAgent(api_key=args.api_key, model=args.model, mimir_db=args.mimir_db)

    if args.interactive:
        print("Mimir MemoryAgent -- type /stats, /exit, or your message")
        print(f"Model: {args.model} | Tool model: {agent.tool_model} | DB: {args.mimir_db}")
        print("-" * 60)
        try:
            while True:
                user_input = input("\nYou: ").strip()
                if not user_input:
                    continue
                if user_input == "/exit":
                    break
                if user_input == "/stats":
                    print(json.dumps(agent.get_stats(), indent=2))
                    print(json.dumps(agent.get_mimir_stats(), indent=2))
                    continue
                print("\nAgent: ", end="", flush=True)
                print(agent.process(user_input))
        except (KeyboardInterrupt, EOFError):
            print()
    else:
        message = " ".join(args.message)
        if not message:
            print("Enter a message or use --interactive", file=sys.stderr)
            sys.exit(1)
        print(agent.process(message))
