# GDL V2 candidate instructions

These instructions apply to the entire repository for bounded V2 work units.
GDL v0.2 remains **Current**. V2 is a productionization **candidate**, not Current.
Phase 0–4 entry points are historical canary surfaces; the reusable candidate is
`scripts/gdl_v2_work_unit.py` and `.github/workflows/gdl-v2-work-unit.yml`.

## Canonical task and evidence

- Treat the linked GitHub Issue as the instruction canonical for the bounded work unit.
- Treat the Draft Pull Request, its current head SHA, actual diff, and test/CI results as the result/evidence canonical.
- Do not treat a chat summary or an agent's own completion message as proof that acceptance criteria are satisfied.

## Safety boundary

- Do not merge or enable auto-merge.
- Do not write directly to main or another default branch.
- Do not close issues or pull requests.
- Do not release, deploy, publish packages, or cut over production automation.
- Do not disable or delete the current GDL v0.2 / legacy path.
- Do not expose, print, commit, or request secret values.
- Do not use consumer-UI automation, session cookies, hidden/private endpoints, or undocumented fallback paths.
- Live Agents API execution requires a bounded authorized Issue contract, an exact work-unit run marker on its deterministic branch, duplicate-trigger checks, and an explicit caller `--live` flag. The OpenAI API key remains in the caller environment, outside source and sandbox input. Never request or use credentials inside Codex.
- Codex must not receive GitHub write credentials. Remote GitHub write-back is a separate ChatGPT/GitHub caller action after independent artifact verification.

## Model routing

- The orchestrator must choose an explicit route. Never silently rely on an unspecified/default model for a V2 task.
- Validate the route with `codex_config_guard.gdl_v2_router` before execution wiring uses it.
- Minimum candidate routes are:
  - routine/focused: `gpt-6-luna` with `max`
  - standard coding/professional: `gpt-6.1-sol` with `high`
  - hardest/high-impact: `gpt-6-astra` with `high`
- Upward escalation is allowed when needed for first-pass success; silent downgrade below the task-class floor is not.

## Editing and tests

- Make the smallest complete change needed for the Issue.
- Avoid unrelated refactors, format churn, and dependency changes.
- Prefer standard library and existing dependencies.
- Validate schema-v1 work-unit contracts with `codex_config_guard.gdl_v2_work_unit`.
- Clone the exact contract source SHA; caller contract/trigger files are not source inputs.
- Edit only explicit allowed file/directory scopes and respect the changed-file limit.
- This gate supports regular LF text create/modify patches only: no file deletion,
  rename/copy, binary files, symlinks/submodules, or mode changes.
- Run the allowlisted `unit` profile; do not accept arbitrary test shell from contracts.
- Run the existing repository unit tests plus any targeted tests added for the V2 change.
- Record actual commands and results in the Draft PR.
- If a required test cannot run, state exactly what is unverified instead of claiming PASS.

## Candidate completion and recovery

Codex completes only after actual tests pass and `/workspace/outputs/change.patch`
and `/workspace/outputs/result.json` are written, re-read, and checked. The caller
must independently validate scope/count, work unit/Issue, route, source/test metadata,
no remote-write attempt, and the SHA-256 of the exact patch bytes. A completion marker
alone is insufficient. Authorized GitHub control-plane write-back is separate from
Codex execution and requires verified artifacts, exact-head CI, and head-bound audit.

Use exactly one `gdl-v2/work/<work_unit>` branch and one exact
`[gdl-v2-run:<work_unit>]` trigger commit. Do not duplicate a marker or retry an
unknown live outcome on another branch. Reconcile original branch/head and Agents
session/turn evidence first; Actions reruns are blocked from paid execution.
See `docs/gdl-v2-productionization.md` for cutover and rollback rules. Stop before
merge, release, deploy, Issue/PR closure, or promotion of V2 to Current.
