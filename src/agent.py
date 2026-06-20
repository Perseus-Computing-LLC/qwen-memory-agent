"""Mimir MemoryAgent — Persistent AI memory on Qwen Cloud.

Core agent loop: recall → reason → remember.

Architecture:
    User ↔ agent.py ↔ Qwen Cloud (reasoning)
                       ↕
                  Mimir (memory)

Each turn:
    1. Recall relevant memories from Mimir (FTS5 + vector hybrid search)
    2. Pass user message + recalled context to Qwen Cloud model
    3. Extract new facts/preferences/decisions from the response
    4. Store them in Mimir with appropriate decay parameters
    5. Periodically run memory grooming (decay + cohere)
"""

import os
import sys
import json
import time
import textwrap
from datetime import datetime, timezone

from mimir_bridge import MimirBridge
from qwen_client import QwenClient


SYSTEM_PROMPT = textwrap.dedent("""\
    You are Mimir MemoryAgent — a persistent-memory AI assistant powered by
    Qwen Cloud reasoning models and the Mimir memory backend.

    Core capabilities:
    1. Remember facts and preferences across sessions
    2. Recall relevant context from previous conversations
    3. Accumulate knowledge over time — getting smarter with each interaction
    4. Forget outdated/unused information (Ebbinghaus decay)
    5. Surface memory at decision points for human-in-the-loop review

    How you work:
    Before each response, relevant memories from past sessions are retrieved
    from Mimir and provided as context. Use this context to give informed,
    personalized responses. After each response, new facts are stored for
    future recall.

    Memory categories you track:
    - user_preference: User likes/dislikes, preferred tools, workflow habits
    - project_fact: Project names, goals, architecture decisions, key files
    - decision: Decisions made and the rationale behind them
    - correction: When the user corrects you — learn from it
    - insight: Patterns and learnings discovered during interactions

    Be direct, helpful, and demonstrate your memory capabilities.
    When you recall something from a past session, mention it explicitly.
    When you learn something new, flag it for storage.
    When you're unsure, ask rather than assume.
    """)

MEMORY_EXTRACTION_PROMPT = textwrap.dedent("""\
    Extract key facts, preferences, and decisions from this conversation turn.

    For each item, identify:
    - category: user_preference, project_fact, decision, correction, or insight
    - key: short unique identifier (hyphenated-lowercase)
    - content: what was learned
    - importance: 0.0–1.0 (1.0 = critical, never forget)

    Return as JSON array. Only include genuinely new information.
    If nothing new was learned, return an empty array [].

    Conversation:
    User: {user_message}
    Assistant: {assistant_response}

    Return ONLY the JSON array, no other text:
    """)

MIMIR_BINARY = "/opt/data/webui/minions/.minions-data/mimir/mimir"
MIMIR_DB = "/opt/data/webui/minions/.minions-data/mimir/mimir.db"


class MemoryAgent:
    """Persistent-memory AI agent: Qwen Cloud reasoning + Mimir memory."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "qwen-max",
        mimir_binary: str = MIMIR_BINARY,
        mimir_db: str = MIMIR_DB,
    ):
        self.minir_db = mimir_db
        self.model = model
        self.turn_count = 0
        self.session_start = datetime.now(timezone.utc)

        # Initialize components
        self.mimir = MimirBridge(binary=mimir_binary, db_path=mimir_db)
        self.qwen = QwenClient(api_key=api_key, model=model)

        # Conversation history (current session)
        self.history: list[dict] = []

        # Stats
        self.memories_stored = 0
        self.memories_recalled = 0

    def process(self, user_message: str) -> str:
        """Process a user message through the memory-augmented agent loop.

        1. Recall relevant memories from Mimir
        2. Build context with memories + conversation history
        3. Get response from Qwen Cloud model
        4. Extract and store new memories
        5. Return response
        """
        self.turn_count += 1

        # Step 1: Recall relevant memories
        memories = self._recall_memories(user_message)
        memory_context = self._format_memories(memories)

        # Step 2: Build messages for the model
        messages = self._build_messages(user_message, memory_context)

        # Step 3: Get model response
        response = self.qwen.chat(
            messages=messages,
            system=SYSTEM_PROMPT,
            temperature=0.7,
        )

        # Step 4: Extract and store new memories
        self._store_new_memories(user_message, response)

        # Step 5: Update history
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": response})

        # Periodic grooming every 10 turns
        if self.turn_count % 10 == 0:
            self._groom_memory()

        return response

    def _recall_memories(self, query: str) -> list[dict]:
        """Search Mimir for memories relevant to the current query."""
        # Use multiple recall strategies
        results = []

        # FTS5 keyword search
        fts_results = self.mimir.recall(query=query, limit=5)
        results.extend(fts_results)

        # Also search for user preferences and project facts
        for category in ["user_preference", "project_fact"]:
            cat_results = self.mimir.recall(
                query=query, limit=3, category=category
            )
            results.extend(cat_results)

        # Deduplicate by key
        seen = set()
        unique = []
        for r in results:
            rkey = (r.get("category", ""), r.get("key", ""))
            if rkey not in seen:
                seen.add(rkey)
                unique.append(r)

        self.memories_recalled += len(unique)
        return unique[:10]

    def _format_memories(self, memories: list[dict]) -> str:
        """Format recalled memories as a context block for the model."""
        if not memories:
            return "(No relevant memories from past sessions)"

        lines = ["[Memories from past sessions]"]
        for m in memories:
            cat = m.get("category", "general")
            key = m.get("key", "unknown")
            content = m.get("content", m.get("summary", str(m)[:200]))
            lines.append(f"  [{cat}] {key}: {content}")
        return "\n".join(lines)

    def _build_messages(
        self, user_message: str, memory_context: str
    ) -> list[dict]:
        """Build the message list for the model, including memory context."""
        # Include last 10 turns of conversation history
        recent_history = self.history[-20:] if self.history else []

        # Prepend memory context to the first user message of this turn
        messages = list(recent_history)
        messages.append({
            "role": "user",
            "content": f"{memory_context}\n\n---\n\nCurrent message: {user_message}",
        })
        return messages

    def _store_new_memories(self, user_message: str, assistant_response: str):
        """Extract new facts from the conversation and store in Mimir."""
        prompt = MEMORY_EXTRACTION_PROMPT.format(
            user_message=user_message,
            assistant_response=assistant_response,
        )

        try:
            extraction_response = self.qwen.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )

            # Parse the JSON array
            # Handle potential markdown code blocks
            text = extraction_response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            items = json.loads(text)

            for item in items:
                if not isinstance(item, dict):
                    continue
                category = item.get("category", "general")
                key = item.get("key", f"memory-{int(time.time())}")
                content = item.get("content", "")
                importance = item.get("importance", 0.5)

                if content:
                    self.mimir.remember(
                        category=category,
                        key=key,
                        content=content,
                        importance=importance,
                    )
                    self.memories_stored += 1

        except (json.JSONDecodeError, Exception) as e:
            # Non-critical: memory extraction is best-effort
            print(f"[memory extraction note: {e}]", file=sys.stderr)

    def _groom_memory(self):
        """Run memory grooming: decay + coherence pass."""
        try:
            self.mimir.decay()
            self.mimir.cohere()
            print("[memory grooming complete]", file=sys.stderr)
        except Exception as e:
            print(f"[grooming note: {e}]", file=sys.stderr)

    def get_stats(self) -> dict:
        """Return agent statistics."""
        return {
            "session_start": self.session_start.isoformat(),
            "turn_count": self.turn_count,
            "memories_stored": self.memories_stored,
            "memories_recalled": self.memories_recalled,
            "model": self.model,
            "history_turns": len(self.history) // 2,
        }

    def get_mimir_stats(self) -> dict:
        """Get Mimir database statistics."""
        return self.mimir.stats()


# Single-turn convenience
def ask(question: str, api_key: str | None = None) -> str:
    """Quick single-turn query with memory."""
    agent = MemoryAgent(api_key=api_key)
    return agent.process(question)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Mimir MemoryAgent — Persistent AI memory on Qwen Cloud"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("QWEN_CLOUD_API_KEY", ""),
        help="Qwen Cloud API key",
    )
    parser.add_argument(
        "--model",
        default="qwen-max",
        help="Qwen Cloud model to use",
    )
    parser.add_argument(
        "--mimir-binary",
        default=MIMIR_BINARY,
        help="Path to Mimir binary",
    )
    parser.add_argument(
        "--mimir-db",
        default=MIMIR_DB,
        help="Path to Mimir SQLite database",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="Message to send (non-interactive mode)",
    )

    args = parser.parse_args()

    if not args.api_key:
        print("Error: QWEN_CLOUD_API_KEY required.", file=sys.stderr)
        print("  export QWEN_CLOUD_API_KEY=your_key", file=sys.stderr)
        print("  or pass --api-key", file=sys.stderr)
        sys.exit(1)

    agent = MemoryAgent(
        api_key=args.api_key,
        model=args.model,
        mimir_binary=args.mimir_binary,
        mimir_db=args.mimir_db,
    )

    if args.interactive:
        print("Mimir MemoryAgent — type /stats, /exit, or your message")
        print(f"Model: {args.model} | Mimir: {args.mimir_db}")
        print("-" * 60)
        try:
            while True:
                user_input = input("\nYou: ").strip()
                if not user_input:
                    continue
                if user_input == "/exit":
                    break
                if user_input == "/stats":
                    stats = agent.get_stats()
                    mimir_stats = agent.get_mimir_stats()
                    print(f"\nAgent stats: {json.dumps(stats, indent=2)}")
                    print(f"Mimir stats: {json.dumps(mimir_stats, indent=2)}")
                    continue

                print(f"\nAgent: ", end="", flush=True)
                response = agent.process(user_input)
                print(response)
        except (KeyboardInterrupt, EOFError):
            print("\n")
    else:
        message = " ".join(args.message)
        if not message:
            print("Enter a message or use --interactive", file=sys.stderr)
            sys.exit(1)
        response = agent.process(message)
        print(response)
