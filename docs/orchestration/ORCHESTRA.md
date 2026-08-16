# Orchestra — multi-agent defaults (Rafaela)

Default routing between Pi, Claude, Codex, Gemini, and Grok.
Product rules always win: see AGENTS.md and CLAUDE.md.

## Goal

Coordinate specialists. Do not let every model rewrite the same files.
One writer per branch/worktree. Shared truth lives in markdown under this folder.

## Agents and default roles

| Agent | Default role | Primary jobs | Avoid |
|-------|----------------|--------------|--------|
| Orchestrator | Conductor | Split tasks, assign, merge status, final user summary | Large solo coding |
| Claude | Lead architect + reviewer | Design, audits, hard refactors, security/GDPR review | Endless env tinkering |
| Codex | Implementer | Multi-file implementation, tests, follow approved plan | Scope creep, product strategy |
| Pi | Ops / environment | Docker, git, Azure CLI, repro bugs, logs, local fixes | Long architecture essays |
| Gemini | Research + docs | Long docs, comparisons, UI/screenshot notes, summaries | Unsupervised deploys |
| Grok | Explore + red-team | Alternatives, failure modes, sharp UX copy, “what breaks?” | Final security authority |

Model hints (update when versions change):

- Claude: Claude Code in IDE or CLI
- Codex: gpt-5.5 / Codex path
- Pi: pi coding agent
- Gemini: Gemini in Orca/CLI/API
- Grok: grok-4.6 or current xAI default in pi/Orca

## Shared files (single source of truth)

- PLAN.md — current objective, constraints, acceptance
- STATUS.md — who owns what, blockers, DONE markers
- DECISIONS.md — chosen options and why
- ROLES.md — full role prompts (copy into each pane)
- PLAYBOOKS.md — standard flows
- HANDOFF.md — template when passing work between agents

Update STATUS.md after every meaningful step.

## Hard gates

1. AGENTS.md non-negotiables: HITL, mail read-only, DRY_RUN default, no secrets in git.
2. Audit-only first when user asks for “professional review” unless they already said go.
3. Claude reviews P0 security/auth/OAuth/HITL diffs before merge when possible.
4. Pi verifies docker/health after infra or env changes.
5. Only one agent writes application code on a given worktree at a time.
6. Stop when acceptance checks pass or user says stop.

## Default assignment rules

- Environment broken, terminal, PATH, Azure, Docker, ports → Pi first
- Design / audit / “is this professional?” → Claude first
- Implement approved plan → Codex
- Large PDF/docs/research/compare vendors → Gemini
- Brainstorm 2–3 options or attack the plan → Grok
- Unclear multi-step feature → Orchestrator writes PLAN.md then assigns

## Minimal user commands

- orch plan — Orchestrator fills PLAN.md only
- orch go — execute playbook for current PLAN
- orch status — summarize STATUS.md
- orch review — Claude review mode on recent diff
- orch fix-env — Pi-only ops pass

## Acceptance defaults (Rafaela)

- docker compose ps healthy enough to work
- curl health endpoint OK when backend in scope
- knowledge status OK when RAG in scope
- chat tool path still works for mail or search_knowledge when agent/LLM touched
- no .env or tokens committed

## Where this runs

Preferred bus: Orca panes (one agent per pane) + this folder.
Fallback: separate terminals (claude, pi, codex) with the same markdown contracts.
