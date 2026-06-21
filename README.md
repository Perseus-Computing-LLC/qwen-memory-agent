# Mimir MemoryAgent — Persistent AI Memory on Qwen Cloud

**Every AI agent forgets everything between sessions. Mimir fixes that.**

Mimir MemoryAgent is a persistent-memory AI agent built on **Qwen Cloud**. It
remembers facts, preferences, and decisions across sessions, recalls them with
hybrid search, and lets stale memories fade with Ebbinghaus-style decay — so the
agent gets more useful the more you talk to it.

Built for **Track 1: MemoryAgent** of the [Qwen Cloud Global AI Hackathon 2026](https://qwencloud-hackathon.devpost.com/).

▶️ **[Watch the demo](https://devpost.com/software/mimir-memoryagent-persistent-ai-memory-on-qwen-cloud)** · 📜 [Demo script](docs/demo_script.md)

## The problem

LLMs are stateless. Every conversation starts from zero. They can't remember
what you're building, the stack you prefer, the decision you made last week, or
that you already tried an approach that failed. Developers paper over this with
context-stuffing and endless repetition.

## What it does

```
Session 1: "I'm building Perseus — a live context engine for AI agents."
  → stores  project_fact/perseus

Session 2 (days later): "What was I working on?"
  → recalls "You're building Perseus, a live context engine for AI agents."

Session 3: "I prefer TypeScript over Python for new services."
  → stores  user_preference/lang-typescript

Session 4: "Scaffold me a new service."
  → recalls the preference and scaffolds in TypeScript, unprompted

Session 5 (weeks later): unused small-talk has decayed and no longer clutters
  context — while high-importance facts persist.
```

## Deep Qwen Cloud integration

Mimir doesn't just call an LLM — it uses three distinct Qwen Cloud capabilities:

| Capability | Qwen feature | Where |
|---|---|---|
| Reasoning over long multi-session context | `qwen-max-longcontext` | every turn |
| Deciding what to remember | **native function calling** (`store_memories` tool) | after every turn |
| Semantic recall | `text-embedding-v3` embeddings (hybrid with FTS5) | every recall |

The agent never hand-parses JSON out of prose: Qwen's function calling returns a
structured `store_memories` call, so memory writes are reliable by construction.

## Architecture

```
User ↔ agent.py ──(reasoning)─▶ Qwen Cloud  qwen-max-longcontext
           │  ▲
   recall  │  │ remember (Qwen function calling)
           ▼  │
        mimir_bridge.py ─ SQLite + FTS5 + Qwen embeddings + Ebbinghaus decay

Each turn:
  1. RECALL    hybrid search (FTS5 keyword + Qwen-embedding cosine), decay-weighted
  2. REASON    user message + recalled memories → qwen-max-longcontext
  3. REMEMBER  Qwen function-calls store_memories(...) → persisted to SQLite
  4. GROOM     every 10 turns: Ebbinghaus decay + dedupe
```

## Memory backend

`src/mimir_bridge.py` is a **self-contained, stdlib-only** persistent store — no
external daemon, no setup. It implements the same model as Perseus Computing's
production [Mimir](https://perseus.observer) system:

- **Structured entities** — `category / key / content / importance`
- **FTS5 full-text search** (with a `LIKE` fallback if FTS5 isn't compiled in)
- **Hybrid recall** — keyword + Qwen-embedding semantic similarity, score-fused
- **Ebbinghaus decay** — unused memories fade; recall reinforces; important ones persist
- **Cross-session persistence** — one SQLite file, survives reboots

> The production Mimir backend adds a Rust core, AES-256-GCM encryption at rest,
> 27 MCP tools, and cross-workspace federation. This repo ships a compact,
> auditable version so you can run the whole thing in under a minute.

## Quickstart

```bash
git clone https://github.com/Perseus-Computing-LLC/qwen-memory-agent.git
cd qwen-memory-agent
pip install -r requirements.txt

export QWEN_CLOUD_API_KEY=your_key_here   # or: cp .env.example .env && edit

python src/agent.py --interactive
```

The SQLite memory DB is created automatically at `./mimir.db`. Quit, re-run
later, and the agent still remembers. Type `/stats` to inspect the store.

## Run the multi-session demo

Follow [docs/demo_script.md](docs/demo_script.md) to reproduce the five-session
memory-accumulation-and-decay walkthrough from the video.

## Built with

- **Qwen Cloud** — `qwen-max-longcontext` reasoning, native function calling, `text-embedding-v3`
- **Python** — agent orchestration via the `openai` SDK against Qwen's OpenAI-compatible API
- **SQLite + FTS5** — embedded persistent memory

## License

MIT © Perseus Computing LLC
