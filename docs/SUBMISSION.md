# Devpost Submission — Mneme MemoryAgent

## Project Name
Mneme MemoryAgent — Persistent AI Memory on Qwen Cloud

## Elevator Pitch (200 chars)
Mneme gives AI agents persistent, searchable memory across sessions — remembering facts, forgetting what's stale, and surfacing context that makes agents smarter over time. Powered by Qwen Cloud.

## Track
Track 1: MemoryAgent

## What it does
Mneme MemoryAgent solves the fundamental problem of AI amnesia. Every LLM conversation starts from zero — no memory of past projects, preferences, decisions, or corrections. Mneme fixes this by wrapping a production-grade persistent memory backend (27 MCP tools, FTS5+vector hybrid search, AES-256-GCM encryption, Ebbinghaus decay) with Qwen Cloud reasoning models.

The agent demonstrates:
1. **Persistent memory across sessions** — remembers projects, facts, preferences
2. **Cross-session context accumulation** — gets smarter as memory grows
3. **Timely forgetting** — Ebbinghaus decay removes stale/unused memories
4. **Critical memory recall** — retrieves relevant context without dumping everything
5. **Human-in-the-loop surfacing** — surfaces what it remembers at decision points

## How we built it
- **Memory backend**: Mneme (Rust) — production persistent memory with SQLite, FTS5, vector search, and Ebbinghaus decay
- **Reasoning**: Qwen Cloud via OpenAI-compatible API (qwen-max model)
- **Orchestration**: Python agent loop: recall → reason → remember → groom
- **Architecture**: 3-layer — MemoryAgent Python orchestrator, MimirBridge (mimir_bridge.py) for memory operations, QwenClient for reasoning

## Why Qwen Cloud
Qwen Cloud's OpenAI-compatible API made integration seamless. We used qwen-max for its strong reasoning capabilities — the agent needs to both recall relevant context AND extract new facts from responses. The 1M-token context window on qwen-max-longcontext enables rich memory context without truncation, which is critical for the MemoryAgent track's cross-session requirements.

## GitHub Repo
https://github.com/Perseus-Computing-LLC/qwen-memory-agent

## Demo Video
[YouTube link — will be added after recording]

## Architecture Diagram
See `assets/architecture-diagram.html` in the repo.

## Try it out
```bash
git clone https://github.com/Perseus-Computing-LLC/qwen-memory-agent.git
cd qwen-memory-agent
pip install -r requirements.txt
export QWEN_CLOUD_API_KEY=your_key
python src/agent.py --interactive
```

## Challenges we ran into
- Qwen Cloud's hackathon voucher system requires separate application — built the agent to work with any OpenAI-compatible endpoint as fallback
- Mneme's MCP stdio protocol requires persistent process management — used direct CLI subprocess calls for hackathon simplicity
- Memory extraction (identifying what to store) is itself an LLM task — used a second Qwen Cloud call with a structured extraction prompt

## Accomplishments
- Full agent loop working end-to-end in under 4 hours
- Demo shows clear progression across 5 sessions: introduction → recall → preferences → decay → decision support
- Architecture diagram and documentation in the repo are ready for production use
- Not a toy — Mneme is a real memory system with 27 MCP tools, used in production agents

## What we learned
- Persistent memory transforms the agent experience — users don't need to repeat themselves
- Ebbinghaus decay is more intuitive than LRU for demonstrating "natural forgetting"
- Structured entity model (category, key, body_json) is the right abstraction for agent memory
- Qwen Cloud's API is reliable and fast for the recall→reason→remember loop

## What's next
- Web dashboard for memory browsing and graph visualization
- Multi-agent shared memory pools (Agent Society track)
- LLM-based memory compression for long-term storage
- Cross-workspace memory federation

## Built with
- qwen-cloud
- python
- mimir
- sqlite
- mcp
