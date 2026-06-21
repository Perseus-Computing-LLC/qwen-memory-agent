# Mimir MemoryAgent — 5-Session Demo Script

This reproduces the demo video: an agent that accumulates memory across
sessions, recalls it, and lets unused facts decay. Each "session" is a fresh
run of the CLI — the agent only knows what it persisted to `./mimir.db`.

Prereqs:

```bash
export QWEN_CLOUD_API_KEY=your_key_here
pip install -r requirements.txt
```

> Each block below is a separate process. Quit with `/exit` between sessions to
> prove memory survives across runs — nothing is held in RAM.

## Session 1 — teach it your project

```
python src/agent.py --interactive
You: I'm building Perseus, a live context engine for AI agents.
You: The backend is Rust and the memory layer is called Mimir.
You: /stats        # see the project_fact entries that were stored
You: /exit
```

## Session 2 — recall across a fresh run

```
python src/agent.py --interactive
You: What am I working on?
# → recalls Perseus + the Rust / Mimir details from Session 1
You: /exit
```

## Session 3 — teach it a preference

```
python src/agent.py --interactive
You: I prefer TypeScript over Python for new services.
You: /exit
```

## Session 4 — act on the preference

```
python src/agent.py --interactive
You: Scaffold a new service for me.
# → recalls the TypeScript preference and uses it without being asked
You: /exit
```

## Session 5 — decay in action

```
python src/agent.py --interactive
You: /stats
# Untouched, low-importance memories show a falling decay_score; after enough
# idle time they archive automatically. High-importance facts (Perseus, the
# TypeScript preference) persist and stay top-ranked on recall.
You: Remember my project?
# → still recalls Perseus; trivial small-talk from earlier has faded.
```

## What to point the judges at

- **Function calling** — memory writes go through Qwen's `store_memories` tool;
  see `_store_new_memories` in `src/agent.py`.
- **Hybrid recall** — FTS5 + Qwen `text-embedding-v3` cosine, fused and
  decay-weighted; see `recall()` in `src/mimir_bridge.py`.
- **Persistence** — kill the process, re-run, memory is still there (`./mimir.db`).
