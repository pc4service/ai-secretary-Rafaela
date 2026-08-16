# Playbooks

## P1 — New feature

1. Orchestrator: write PLAN.md (goal, constraints, acceptance).
2. Grok: optional 3 approaches + risks (short).
3. Claude: choose approach, file plan, risks.
4. User go if required.
5. Codex: implement on one worktree.
6. Pi: run health/docker/tests in scope.
7. Claude: review P0 concerns.
8. Orchestrator: STATUS done + summary for user.

## P2 — Bug

1. Pi: reproduce, capture logs, isolate layer (env vs app).
2. If app bug: Codex patch from minimal repro.
3. Pi: verify fix.
4. Claude: root-cause note only if recurring or security-related.

## P3 — Professional audit

1. Claude: audit-only report (P0/P1/P2), no code.
2. Gemini: check docs/roadmap gaps against code.
3. Grok: customer/DPO/adversarial questions.
4. Orchestrator: merged backlog in PLAN.md.
5. Stop until user says go.
6. Implement only approved P0 slice.

## P4 — Ops / “won’t launch”

1. Pi only first (PATH, terminal profile, compose, ports, OAuth URIs).
2. If IDE extension issue: Pi adjusts settings; user restarts app.
3. Escalate to Claude only if product code must change.

## P5 — Knowledge / RAG content

1. Gemini or human: draft knowledge/*.md templates.
2. Pi: index/status endpoints, compose/qdrant health.
3. Codex: wire tools/API if missing.
4. Claude: prompt/tool-policy review.
5. Demo chat: follow-up template question must call search_knowledge.

## P6 — OAuth connect (Microsoft / Google)

1. Pi: redirect URIs, .env keys present (redacted check), callback routes.
2. Codex/Claude: code path only if mismatch in app routes.
3. Pi: live authorize URL check (no AADSTS50011 / Google redirect errors).
4. Smoke: settings shows connected; one read tool works.

## Stop and ask user when

- Need secret values (API keys, client secrets)
- Destructive prod action
- Ambiguous product choice with business impact
- Two agents would edit the same files concurrently
