# GDL V2 cutover-authority instructions

These instructions apply to the entire repository for bounded V2 work units.
GDL v0.2 remains **Current until the Issue #22 cutover merge succeeds**. Promotion
Gate #20 returned `PROMOTION_READY`, and the user has now explicitly authorized the
separate Current cutover/merge. Issue #22 is the canonical cutover authority.
Phase 0–4 entry points are historical canary surfaces; the reusable V2 surface is
`scripts/gdl_v2_work_unit.py` and `.github/workflows/gdl-v2-work-unit.yml`.

For **Issue #22 only**, Codex may prepare the bounded repository patch that changes
this generic V2 surface from candidate wording/state to final Current wording/state,
including this file, provided the exact Issue contract allows each changed path.
This authority does not let Codex write to GitHub or perform the merge. Current only
changes when the independently verified cutover patch passes exact-head CI/audit and
the authorized ChatGPT/GitHub control plane merges the exact audited head to `main`.
After that merge, GDL v0.2 remains preserved as the rollback path, not Current.

## Canonical task and evidence

- Treat the linked GitHub Issue as the instruction canonical for the bounded work unit.
- Treat the Draft Pull Request, its current head SHA, actual diff, and test/CI results as the result/evidence canonical.
- Do not treat a chat summary or an agent's own completion message as proof that acceptance criteria are satisfied.
- For the cutover, require Issue #22 plus the exact Promotion Gate #20 `PROMOTION_READY` source as entry authority; unrelated Issues cannot reuse this exception.

## Safety boundary

- Codex must not merge or enable auto-merge.
- Codex must not write directly to main or another default branch.
- Codex must not close issues or pull requests.
- Codex must not release, deploy, publish packages, or mutate production/remote systems.
- Do not disable or delete GDL v0.2; preserve it as the rollback path through and after cutover.
- Do not expose, print, commit, or request secret values.
- Do not use consumer-UI automation, session cookies, hidden/private endpoints, or undocumented fallback paths.
- Live Agents API execution requires a bounded authorized Issue contract, an exact work-unit run marker on its deterministic branch, duplicate-trigger checks, and an explicit caller `--live` flag. The OpenAI API key remains in the caller environment, outside source and sandbox input. Never request or use credentials inside Codex.
- Codex must not receive GitHub write credentials. Remote GitHub write-back is a separate ChatGPT/GitHub caller action after independent artifact verification.
- Issue #22 authorizes only preparation of the final Current-state patch. GitHub write-back, exact-head audit, and merge remain caller-side steps.

## Model routing

- The orchestrator must choose an explicit route. Never silently rely on an unspecified/default model for a V2 task.
- Validate the route with `codex_config_guard.gdl_v2_router` before execution wiring uses it.
- Minimum routes are:
  - routine/focused: `gpt-6-luna` with `max`
  - standard coding/professional: `gpt-6.1-sol` with `high`
  - hardest/high-impact: `gpt-6-astra` with `high`
- Upward escalation is allowed when needed for first-pass success; silent downgrade below the task-class floor is not.
- Issue #22 Current cutover preparation is `critical` and must use at least `gpt-6-astra` / `high`.

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
- For Issue #22, the final patch must remove obsolete operational claims that GDL v0.2 is Current or V2 is merely a candidate, while retaining historical statements only when clearly labeled as pre-cutover evidence.

## Completion and recovery

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
See `docs/gdl-v2-productionization.md` for cutover and rollback rules.

For Issue #22, successful artifact preparation is not itself the cutover. Stop Codex
before any GitHub remote mutation. The caller may proceed only through independent
artifact verification, controlled write-back, Draft PR, exact-head CI, and a fresh
cutover audit. The user authorization in Issue #22 permits the control plane to merge
the exact audited cutover head after those checks pass. No release/deploy/package
publish or manual Issue closure is authorized by this cutover.