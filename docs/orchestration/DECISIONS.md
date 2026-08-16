# DECISIONS

Append-only log. Newest first.

## Template

### YYYY-MM-DD — title
- Context:
- Options:
- Decision:
- Owner:
- Consequences:

---

### 2026-08-16 — default multi-agent roles
- Context: User asked for orchestrator across Pi, Claude, Codex, Gemini, Grok.
- Options: single mega-agent vs role-specialized orchestra on Orca.
- Decision: Role-specialized defaults — Claude architect/review, Codex implement, Pi ops, Gemini research/docs, Grok explore/red-team, Orca/markdown as bus.
- Owner: orchestration defaults
- Consequences: docs/orchestration/* is the contract; Level-1 markdown orchestra before building a heavy router service.
