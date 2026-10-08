# GDL V2 Current instructions

These instructions apply to the entire repository for bounded GDL V2 work units.
The generic V2 work-unit surface is **Current**. GDL v0.2 is retained intact as the
rollback path and historical predecessor; it is not the Current execution surface.
Phase 0–4 entry points and the productionization/promotion branches remain historical
evidence. The Current entry is `scripts/gdl_v2_work_unit.py` with
`.github/workflows/gdl-v2-work-unit.yml`.

Current cutover authority is GitHub Issue #22, following Promotion Gate #20
`PROMOTION_READY`. Recovery Issue #23 records the one-time control-plane cutover
finalization after the R3 provider turn was reconciled to a terminal
`usage_limit_exceeded` failure with no published implementation artifacts. That
recovery is historical cutover evidence, not a general alternative execution path.

## Canonical task and evidence

- Treat the linked GitHub Issue as the instruction canonical for each bounded work unit.
- Treat the Draft Pull Request, its exact current head SHA, actual diff, and test/CI results as the result/evidence canonical.
- Do not treat chat summaries, completion text, or an agent's self-reported PASS as proof that acceptance criteria are satisfied.
- Bind every decision to the exact source/head under review; a moved head requires a fresh audit.

## Safety boundary

- Codex must not merge or enable auto-merge.
- Codex must not write directly to `main` or another default branch.
- Codex must not close issues or pull requests.
- Codex must not release, deploy, publish packages, or mutate production systems.
- Do not disable or delete GDL v0.2; preserve it as the rollback path.
- Do not expose, print, commit, or request secret values.
- Do not use consumer-UI automation, session cookies, hidden/private endpoints, or undocumented fallback paths.
- Live Agents API execution requires a bounded authorized Issue contract, an exact work-unit run marker on its deterministic branch, duplicate-trigger checks, and an explicit caller `--live` flag.
- The OpenAI API key remains in the caller environment, outside source and sandbox input. Never request or use credentials inside Codex.
- Codex must not receive GitHub write credentials. Remote GitHub write-back is a separate trusted ChatGPT/GitHub control-plane action after independent artifact verification.
- The normal Current workflow keeps GitHub permissions read-only and checkout credentials non-persistent.

## Model routing

- The orchestrator must choose an explicit route. Never silently rely on an unspecified/default model for a V2 task.
- Validate the route with `codex_config_guard.gdl_v2_router` before execution wiring uses it.
- Minimum Current routes are:
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
- Current artifact verification supports regular LF text create/modify patches only: no file deletion, rename/copy, binary files, symlinks/submodules, or mode changes.
- Run the allowlisted `unit` profile; contracts must not supply arbitrary test shell.
- Run the existing repository unit tests plus any targeted tests added for the work unit.
- Record actual commands and results in the Draft PR.
- If a required test cannot run, state exactly what is unverified instead of claiming PASS.

## Completion and recovery

Codex completes only after actual tests pass and `/workspace/outputs/change.patch`
and `/workspace/outputs/result.json` are written, re-read, and checked. The caller
must independently validate scope/count, work unit/Issue, route, source/test metadata,
`remote_write_attempted: false`, and the SHA-256 of the exact patch bytes. A completion
marker alone is insufficient. Authorized GitHub control-plane write-back remains
separate from Codex execution and requires verified artifacts, exact-head CI, and a
head-bound audit.

Use exactly one `gdl-v2/work/<work_unit>` branch and one exact
`[gdl-v2-run:<work_unit>]` trigger commit. Do not duplicate a marker or automatically
retry an unknown live outcome. Reconcile the original branch/head and Agents
session/turn evidence first; ordinary Actions reruns are blocked from paid execution.
A confirmed terminal provider failure may only be retried through a separately
reviewed recovery protocol. Never create a second branch merely to hide an unknown
result.

See `docs/gdl-v2-productionization.md` for the Current contract, recovery rules, and
rollback procedure. GDL v0.2 remains available for rollback if Current V2 must be
stopped. Normal work still stops before merge, release, deploy, Issue/PR closure, or
other remote actions unless the controlling Issue and user explicitly authorize that
separate control-plane action.