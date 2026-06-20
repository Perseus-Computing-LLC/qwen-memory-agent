# Mimir MemoryAgent — Persistent AI Memory on Qwen Cloud

**Every AI agent forgets everything between sessions. Mimir fixes that.**

Mimir is a persistent-memory backend for AI agents. It remembers facts, preferences, and decisions across sessions — and forgets what's stale. Powered by Qwen Cloud reasoning models.

Built for **Track 1: MemoryAgent** of the [Qwen Cloud Global AI Hackathon 2026](https://qwencloud-hackathon.devpost.com/).

## The problem

LLMs are stateless. Every conversation starts from zero. They can't remember:

- What project you're working on
- That you prefer DeepSeek over Claude
- The architecture decision you made last week
- That you already tried approach X and it failed

Developers work around this with context stuffing, long system prompts, and
repeating themselves endlessly. It's wasteful and frustrating.

## What Mimir does

```
Session 1: "I'm building Perseus — a context engine for AI agents."
  → Mimir stores: project_fact/perseus-context-engine

Session 2 (days later): "What was I working on?"
  → Mimir recalls: "You're building Perseus, a context engine for AI agents"
  → Agent responds with full context, no repetition needed

Session 3: "I prefer DeepSeek V4 over Claude."
  → Mimir stores: user_preference/prefers-deepseek

Session 4: "Which model should I use for this task?"
  → Mimir recalls the preference
  → Agent recommends DeepSeek based on stored preference

Session 5 (weeks later): "Remember that project?"
  → Old, unused memories have decayed — they don't clutter context
  → Critical facts (stored with high importance) persist
```

## Architecture

```
User ↔ MemoryAgent (Python) ↔ Qwen Cloud API (reasoning)
                                ↕
                           Mimir (memory backend)

Memory Agent loop:
  1. RECALL  — Search Mimir for relevant memories (FTS5 + vector hybrid)
  2. REASON  — Pass user message + recalled context to Qwen Cloud model
  3. REMEMBER — Extract new facts from the response, store in Mimir
  4. GROOM   — Periodically run decay + coherence (Ebbinghaus-based)
```

## Why Mimir wins the MemoryAgent track

Mimir isn't a hackathon prototype — it's a **production memory system** with:

- **Structured entities** — category, key, body_json model for clean organization
- **FTS5 + vector hybrid search** — fast keyword search + semantic similarity
- **Ebbinghaus decay** — memories lose relevance over time, mimicking human forgetting
- **AES-256-GCM encryption** — all memories encrypted at rest
- **Cross-session persistence** — SQLite-backed, survives reboots
- **27 MCP tools** — remember, recall, recall_when, embed, decay, cohere, synthesize...

Competitors are building memory from scratch. We're integrating a production system.

## Quickstart

```bash
# 1. Clone
git clone https://github.com/Perseus-Computing-LLC/qwen-memory-agent.git
cd qwen-memory-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Qwen Cloud API key
export QWEN_CLOUD_API_KEY=your_key_here

# 4. Start Mimir (persistent memory server)
/opt/data/webui/minions/.minions-data/mimir/mimir serve --db mimir.db &

# 5. Run the agent
python src/agent.py --interactive
```

## Demo

Watch the [demo video](docs/demo_script.md) showing 5 sessions of memory accumulation across time — the agent remembers your project, your preferences, and forgets what's stale.

## Built with

- **Qwen Cloud** — reasoning models (OpenAI-compatible API)
- **Mimir** — persistent memory backend (27 MCP tools, FTS5 + vector search)
- **Python** — agent orchestration layer

## License

MIT — Perseus Computing LLC

---

Built for the Qwen Cloud Global AI Hackathon 2026 · Track 1: MemoryAgent
