# Codex instructions — ORIÓN JARVIS scope

Applies only to files under `jarvis-staging/`. Inherit and obey the root `AGENTS.md`; when policies differ, follow the more restrictive rule.

## Mission and source of truth
- Read `jarvis-staging/ROADMAP_ENTREGA.md` first, especially **JARVIS Trust & Time Intelligence**.
- Then read `jarvis-staging/CODEX_TARGET_9.md`: the 9/10 goal is a target with measurable exit gates, **not** a claim about current quality.
- Prioritize actual end-to-end functionality over adding more isolated intent regex tests or cosmetic changes.

## Non-negotiable constraints
- Work in a focused feature branch based on `orion-jarvis-staging`; propose a PR for human review. No direct production deployment or merges.
- Do not enable `ENABLE_MODEL_REQUESTS`, invoke billed models/APIs, modify pricing plans, create paid resources, rotate or expose secrets, or alter production infrastructure.
- Do not log or commit credentials, `.env` values, private messages, or real user data. Use synthetic fixtures.
- Preserve Supabase auth, session isolation and RLS; avoid destructive migrations or data mutations. Do not weaken security boundaries without approval.
- Never represent fabricated calendars, events, tasks, saved reminders, actions, locations, ETA or traffic as confirmed.
- For recommended departure times require authorized calendar information, verified origin/destination, time zone and an authorized traffic-aware routing source; otherwise say it cannot be calculated.
- Safari/iPhone microphone, background audio, wake-word and interrupted speech capabilities need physical-device validation; do not claim they are proven from desktop or simulation.
- Leave existing scheduled automations untouched.

## Verification protocol
1. State the baseline repo commit, changed paths, and exact commands executed.
2. Investigate the actual project structure and supported runtimes; do not infer working commands from file names alone.
3. First attempt existing tests; capture pass/fail/skipped counts and failure excerpts with redaction.
4. For changed JS tests, investigate `node --test jarvis-staging/tests/*.test.mjs` with the installed Node version, documenting any module/version constraints. For root Python use root `AGENTS.md` commands when the environment permits.
5. Prefer fixing failing existing behavior and adding integrated tests over duplicative narrow coverage. Never claim unexecuted tests passed.
6. After edits rerun impacted tests, inspect the diff for secrets, document residual risks and provide rollback notes.
7. For every PR include: problem, evidence, exact changed files, commands/results, security review, blockers, out-of-scope work, rollback and next proposed increment.

## Expected first Codex deliverable
A verified status matrix: roadmap requirement -> implementation path -> test evidence -> gap -> priority. Then fix one demonstrable P0 issue with a small reviewed PR if a safe fix is available. Distinguish code staged, deployed and personally tested on iPhone.
