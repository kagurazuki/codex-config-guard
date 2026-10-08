# GDL V2 canary instructions

These instructions apply to the entire repository while working on the GDL V2 canary.

## Canonical task and evidence

- Treat the linked GitHub Issue as the instruction canonical for the bounded work unit.
- Treat the Draft Pull Request, its current head SHA, actual diff, and test/CI results as the result/evidence canonical.
- Do not treat a chat summary or an agent's own completion message as proof that acceptance criteria are satisfied.

## Safety boundary

- Do not merge or enable auto-merge.
- Do not close issues or pull requests.
- Do not release, deploy, publish packages, or cut over production automation.
- Do not disable or delete the current GDL v0.2 / legacy path.
- Do not expose, print, commit, or request secret values.
- Do not use consumer-UI automation, session cookies, hidden/private endpoints, or undocumented fallback paths.
- Live Agents API execution is disabled for this Phase 0 canary unless the task explicitly states that the credential/runtime boundary has already been validated and authorizes that exact execution.

## Model routing

- The orchestrator must choose an explicit route. Never silently rely on an unspecified/default model for a V2 task.
- Validate the route with `codex_config_guard.gdl_v2_router` before execution wiring uses it.
- Minimum canary routes are:
  - routine/focused: `gpt-6-luna` with `max`
  - standard coding/professional: `gpt-6.1-sol` with `high`
  - hardest/high-impact: `gpt-6-astra` with `high`
- Upward escalation is allowed when needed for first-pass success; silent downgrade below the task-class floor is not.

## Editing and tests

- Make the smallest complete change needed for the Issue.
- Avoid unrelated refactors, format churn, and dependency changes.
- Prefer standard library and existing dependencies during this canary.
- Run the existing repository unit tests plus any targeted tests added for the V2 change.
- Record actual commands and results in the Draft PR.
- If a required test cannot run, state exactly what is unverified instead of claiming PASS.

## Stop condition

For Phase 0, stop when the architecture/spec, deterministic route guard, tests, and Draft PR evidence are complete. Do not cross into live Agents API execution or production promotion.