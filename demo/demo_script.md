# Mneme MemoryAgent — Demo Script

**Duration:** ~2:50 | **Format:** Terminal simulation with HTML/CSS

## Scene 1 — Setup & Introduction (0:00–0:30)

```
$ python src/agent.py --interactive
Mneme MemoryAgent — type /stats, /exit, or your message
Model: qwen-max | Mneme: /opt/data/webui/minions/.minions-data/mimir/mimir.db
------------------------------------------------------------

You: Hello! I'm Thomas. I'm building Perseus — a context engine for AI agents.

Agent: Hello Thomas! Great to meet you. Perseus sounds interesting — a context
engine for AI agents. I'll remember this. What does Perseus use for its context
rendering engine?

You: It's Python-based, using Jinja2 templates with live system state injection.
It renders AGENTS.md files that get injected into the AI agent's system prompt.

Agent: I've stored that. Perseus — Python, Jinja2 templates, live system state
injection into AGENTS.md. I'm tracking this as a project fact. What's next on
your roadmap?
```

## Scene 2 — Cross-Session Memory (0:30–1:00)

```
[NEW SESSION — days later]

$ python src/agent.py --interactive
Mneme MemoryAgent — type /stats, /exit, or your message
Model: qwen-max | Mneme: /opt/data/webui/minions/.minions-data/mimir/mimir.db
------------------------------------------------------------

You: What was I working on last time?

Agent: Let me check my memory...
[Recalling: project_fact/perseus-context-engine, project_fact/perseus-tech-stack]

Based on our previous session, you're building Perseus — a context engine for
AI agents. It's Python-based, using Jinja2 templates with live system state
injection to render AGENTS.md files. You mentioned working on the roadmap next.
```

## Scene 3 — Preferences (1:00–1:30)

```
You: I prefer DeepSeek V4 Pro over Claude for reasoning tasks. Much faster.

Agent: Noted. I'll remember that: DeepSeek V4 Pro > Claude for reasoning. Do
you have a preference for coding tasks as well?

You: Claude for code, DeepSeek for reasoning. And I never want to use GPT-5.

Agent: Stored. Three preferences locked in:
  • DeepSeek V4 Pro — reasoning tasks
  • Claude — coding tasks
  • GPT-5 — never use

You: What model should I use for reviewing architecture docs?

Agent: Based on your preferences: for architecture docs, that's a reasoning task,
so DeepSeek V4 Pro would be my recommendation. You've consistently preferred it
for analysis and review work.
```

## Scene 4 — Decay & Forgetting (1:30–2:10)

```
You: /stats

Agent stats:
{
  "session_start": "2026-07-01T10:00:00Z",
  "turn_count": 5,
  "memories_stored": 12,
  "memories_recalled": 18,
  "model": "qwen-max",
  "history_turns": 5
}

Mneme stats:
{
  "total_entities": 45,
  "categories": {
    "project_fact": 8,
    "user_preference": 6,
    "decision": 12,
    "insight": 19
  },
  "decay_archived": 3,
  "database_size_mb": 0.2
}

You: Do you remember that random Python script I mentioned 3 weeks ago?

Agent: [Searching memory...]
I don't have a clear memory of that. My memory system uses Ebbinghaus decay —
information that's never accessed naturally fades over time. The Python script
must have decayed below the recall threshold. But all your project decisions
and preferences are still fresh — those have high importance scores.
```

## Scene 5 — Decision Support (2:10–2:50)

```
You: I need to decide: should Perseus use MCP or REST for its API surface?

Agent: [Recalling 6 related memories...]
This is a significant architecture decision. Let me surface what I know:

From memory:
  • You standardized on MCP for Mneme's API (June 2026 — decision/mimir-mcp-api)
  • You chose JSON-RPC 2.0 over gRPC for simplicity (decision/jsonrpc-over-grpc)
  • Your preference for "strip to essentials" (user_preference/minimalist-stack)

Based on your track record: MCP aligns with your existing Mneme architecture
and keeps the stack consistent. REST would mean maintaining two API surfaces.
My recommendation: MCP, consistent with Mneme.

But I want your call — this is a human-in-the-loop decision. What do you think?

You: MCP it is. Good recall.

Agent: Decision stored: Perseus API surface = MCP (June 2026). Rationale:
consistent with Mneme, avoids dual API surfaces, aligns with minimalist
preference. I'll reference this if similar API questions come up.
```
