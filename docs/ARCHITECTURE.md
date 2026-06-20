# Architecture — Mimir MemoryAgent

## System Overview

```
┌─────────────┐       ┌─────────────────┐       ┌────────────────┐
│   User      │──────▶│  MemoryAgent    │──────▶│  Qwen Cloud    │
│   (CLI)     │◀──────│  (Python)       │◀──────│  (Reasoning)   │
└─────────────┘       │                 │       └────────────────┘
                      │  ┌───────────┐  │
                      │  │  Mimir    │  │
                      │  │  Bridge   │──┼──────▶┌────────────────┐
                      │  └───────────┘  │       │  Mimir (Rust)  │
                      └─────────────────┘       │  ┌───────────┐ │
                                                │  │ SQLite DB │ │
                                                │  │ (AES-256) │ │
                                                │  └───────────┘ │
                                                └────────────────┘
```

## Components

### 1. MemoryAgent (`src/agent.py`)
Orchestration layer. Implements the core loop:
- **Recall** facts from Mimir before each response
- **Reason** using Qwen Cloud models with recalled context
- **Remember** new facts extracted from the conversation
- **Groom** memory periodically (decay + coherence)

### 2. Mimir Bridge (`src/mimir_bridge.py`)
Client for the Mimir persistent memory server. Wraps:
- `remember()` — store structured entities
- `recall()` — FTS5 keyword search + vector hybrid
- `decay()` — Ebbinghaus-based forgetting
- `stats()` — database statistics
- `forget()` — soft-delete entities

### 3. Qwen Client (`src/qwen_client.py`)
OpenAI-compatible wrapper for Qwen Cloud:
- Base URL: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- Models: qwen-max (default), qwen-max-longcontext, qwen-plus

## Memory Model

Mimir stores entities as:
```json
{
  "category": "user_preference | project_fact | decision | correction | insight",
  "key": "unique-identifier",
  "body_json": {
    "content": "Full text content",
    "summary": "Short summary for recall"
  },
  "importance": 0.0-1.0,
  "decay_score": 0.0-1.0
}
```

### Decay (Ebbinghaus Forgetting Curve)
- Every entity has a `decay_score` that decreases over time
- High-importance entities (1.0) resist decay
- Unaccessed entities naturally fade below recall threshold (0.05)
- `mimir_decay` recalculates scores; `mimir_compact` archives stale entities

### Search (Hybrid FTS5 + Vector)
- **FTS5**: Fast keyword search with Porter stemming
- **Vector**: Semantic similarity via Ollama embeddings
- **Hybrid**: Reciprocal Rank Fusion (RRF) combines both

## Data Flow

### Session Start
1. Agent loads → Mimir health check
2. User sends message
3. `mimir_recall()` searches for relevant memories
4. Memories formatted as context block
5. Qwen Cloud receives: system prompt + memory context + user message

### Per-Turn Loop
```
User message
  → recall(query, limit=10)
  → format as context
  → qwen_client.chat(messages + context)
  → extract new facts from response
  → mimir_bridge.remember(...) for each fact
  → return response to user
```

### Grooming (every 10 turns)
```
mimir_bridge.decay()    # Recalculate all decay scores
mimir_bridge.cohere()   # Auto-link related entities
```

## Security

- **AES-256-GCM**: All memories encrypted at rest
- **API keys**: Never stored in code; environment variables only
- **No telemetry**: Mimir runs fully local

## Trade-offs

| Decision | Rationale |
|----------|-----------|
| CLI over web UI | Simpler, faster to demo, production agent has 27 MCP tools |
| Python over Rust for orchestration | Faster iteration, Qwen Cloud SDK is Python-first |
| OpenAI-compatible API | Qwen Cloud's official API; no custom SDK needed |
| SQLite over PostgreSQL | Zero-config, single-file, perfect for agent memory |
| Ebbinghaus over LRU | Mimics human memory; time-based decay is more intuitive for demos |

## Future Extensions

- **Web dashboard** — memory browsing, entity graph visualization
- **Multi-agent memory** — shared memory pool across agent society
- **Memory compression** — LLM-based summarization of old entities
- **Cross-workspace federation** — share memories between projects
