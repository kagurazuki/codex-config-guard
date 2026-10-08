# GDL V2 productionization, Current, and rollback

Status: **V2 CANDIDATE / NOT CURRENT / NO PRODUCTION CUTOVER**.
Canonical productionization work unit: GitHub Issue #16, implemented from
`8adf1f8fbd4a13437657e5e177d8e0defcc8f213`. **GDL v0.2 remains Current.**

The reusable entry is `scripts/gdl_v2_work_unit.py` with
`.github/workflows/gdl-v2-work-unit.yml`. This is the future Current surface only
after a separately authorized cutover. It now supports bounded real source,
test, and documentation work, using the existing router and managed sandbox.

## Surfaces and authority

| Surface | Status and purpose |
| --- | --- |
| GDL v0.2 / legacy GitHub loop | Current; retain through candidate validation and rollback |
| Phase 0 foundation / `docs/gdl-v2-new-cloud.md` | Historical canary design and route evidence |
| `gdl-v2-agents-connectivity.yml` / Phase 1 | Historical connectivity canary |
| `gdl-v2-sandbox-patch.yml` / Phase 2 | Historical one-file sandbox canary |
| Phase 3 caller write-back / `docs/gdl-v2-sandbox-patch.md` | Historical controlled handoff evidence |
| `gdl-v2-orchestrated-handoff.yml` / Phase 4 | Historical marker-file orchestration canary |
| `gdl-v2-work-unit.yml` / generic CLI | Reusable candidate; future Current entry after cutover |

Historical code/tests/workflows are preserved for evidence and regression checks.
Their old branch names and marker strings are not generic production triggers.
Do not use their earlier phase plans as authorization for new live tasks.

The Issue is the instruction canonical. The Draft PR, exact head, actual diff,
tests/CI, and independent audit are the result canonical. Chat completion text
and self-reported PASS are insufficient for write-back or cutover.

## Schema-v1 contract

The caller places one JSON contract at `.gdl/work-unit.json` on the work branch.
The file is control-plane input, not a patch change to inject into the sandbox.
Example contract for an authorized source + test + docs task:

```json
{
  "schema_version": 1,
  "work_unit": "issue-16-productionization",
  "issue_number": 16,
  "task_class": "standard",
  "source_sha": "8adf1f8fbd4a13437657e5e177d8e0defcc8f213",
  "summary": "Implement the bounded V2 productionization gate",
  "instructions": "Implement Issue #16 acceptance criteria within these scopes. Preserve Phase 0-4 code/tests and GDL v0.2 Current.",
  "allowed_paths": [
    "src/codex_config_guard/gdl_v2_work_unit.py",
    "src/codex_config_guard/gdl_v2_production.py",
    "scripts/gdl_v2_work_unit.py",
    "tests/test_gdl_v2_work_unit.py",
    "tests/test_gdl_v2_production.py",
    ".github/workflows/gdl-v2-work-unit.yml",
    "docs/gdl-v2-productionization.md",
    "AGENTS.md"
  ],
  "max_changed_files": 8,
  "test_profile": "unit",
  "route": {"model": "gpt-6.1-sol", "reasoning_effort": "high"}
}
```

For later tasks, pin a reviewed source commit containing the candidate, replace
the Issue/instructions, and use the smallest complete scopes. For example,
`["src/codex_config_guard/", "tests/", "docs/", "README.md"]` permits multi-file
real-code work. A trailing `/` means descendants of that directory; other values
mean exact files. `src/` does not authorize `src-other/`. No glob expansion occurs.

Validation rejects unknown/missing keys, duplicate JSON keys, non-object roots,
non-finite numbers, invalid types (including booleans used as integers), controls,
traversal, absolute paths, `.git` components, empty/root/glob scopes, and unsafe
path characters. Bounds: 32 KiB JSON, 3–64 character lowercase alphanumeric/hyphen
work-unit IDs (no repeated/trailing hyphen), 240-byte summary, 12,000-byte detail,
1–32 scopes, 240-character paths with 64-character components, 1–64 changed files,
and positive signed-32-bit Issue numbers. SHAs are full lowercase 40-hex commit
identities, excluding all-zero. `schema_version` must be integer `1`.

`route` is optional; defaults are explicit and deterministic. Partial or invalid
requests fail. The existing guard rejects model/effort downgrades; upgrades remain
allowed: routine Luna/max, standard Sol/high, critical Astra/high. Neither payload
nor metadata depends on an unspecified provider model default.

Only `unit` is currently allowlisted, mapping to
`python -m unittest discover -s tests -v`. Contracts cannot supply test shell.
New profiles require a reviewed code change to the allowlist.

## Execution and verification

Prepare locally without credentials or network execution:

```sh
python scripts/gdl_v2_work_unit.py /path/to/contract.json
```

On the exact clean work-branch checkout, preflight includes Git evidence:

```sh
python scripts/gdl_v2_work_unit.py .gdl/work-unit.json --check-trigger
```

Live execution additionally requires an explicit `--live` and `OPENAI_API_KEY`
already present in the caller environment. Never request, log, or commit keys.
The workflow uses only the existing `GDL_V2_OPENAI_API_KEY` secret in the live
caller step. Repository permissions are `contents: read`; checkout does not persist
its credential. No GitHub token, caller environment, cookie, or secret is included
in agent input, environment, or metadata. This bootstrap performs no live calls.

The agent clones the public fixed repository from `github.com`, checks out the
exact source SHA, installs with `--no-build-isolation --no-deps`, requires a clean
tree, implements bounded work, and runs the allowlisted profile with the fixed
test-process `PYTHONPATH=/workspace/repo/src` so imports exercise edited source
rather than the pre-edit wheel. Hosted setup
supplies the existing build/runtime dependencies. Runtime network allows only
`github.com`. The agent stages intended changes locally without committing and
writes `/workspace/outputs/change.patch` and `/workspace/outputs/result.json`.
It re-reads them and emits only `GDL_V2_SANDBOX_OK` after success.

The caller downloads artifacts belonging to the completed session's exact root
turn. It parses the entire patch, including hunk counts and matching old/new
path headers, enforces identical scope semantics and file count, and checks
exact result metadata: schema, work unit, Issue, task class, model/effort, source,
test profile/command/PASS, `remote_write_attempted: false`, sorted changed paths,
canonical contract SHA-256, and SHA-256 of exact patch bytes. It rejects malformed,
ambiguous, oversized, or mismatched evidence. Result JSON is bounded at 32 KiB;
patches are bounded at 2 MiB.

This gate accepts regular LF UTF-8 text create/modify patches with nonempty new
files. File deletion, rename/copy, binary diffs, quoted/space-containing paths,
mode changes, symlinks/submodules, empty new files, and unexplained patch syntax
fail closed. Line removal within a modified file is supported. These limitations
keep verification predictable; broaden only with reviewed parser/tests.

After verification, an independently authorized ChatGPT/GitHub control-plane
caller may apply the patch to the original work branch and prepare a Draft PR.
First check applicability against a clean exact-source checkout with
`git apply --check`, inspect the actual diff, run required tests, and reconcile
current branch/head to prevent stale write-back. Keep contract/trigger bookkeeping
outside the implementation diff. No remote write-back is performed by the CLI,
workflow, or Codex. Require exact-head CI and head-bound audit before any decision.

## Deterministic trigger and duplicate protection

Every work unit maps injectively to exactly `gdl-v2/work/<work_unit>`; route,
attempt number, time, Issue edits, and retries never create another branch identity.
The authorized GitHub control plane creates that branch from the reviewed source
and commits `.gdl/work-unit.json` with this entire commit message:

```text
[gdl-v2-run:issue-16-productionization]
```

That commit is the one paid trigger. The push workflow's preliminary string filter
does not grant authorization: preflight checks the exact whole message, same work
unit/branch, original event HEAD, committed contract equality, source ancestry
(the source must precede the trigger head),
clean checkout, full non-shallow reachable history, and exactly one occurrence of
the work-unit marker in that history. Mismatched marker, duplicate occurrence,
wrong branch/contract, and Actions `GITHUB_RUN_ATTEMPT != 1` fail before dispatch.
Subsequent implementation/audit commits have ordinary messages without a marker.
Do not force-push away trigger history; retain it as durable evidence.

Branch concurrency serializes runs without canceling active work. This protects
against duplicate trigger commits and ordinary Actions reruns, not all possible
provider/network delivery ambiguity. There is no claim of distributed exactly-once
API execution. A local exclusive `dispatch.json` receipt also blocks repeats into
the same output directory; moving/deleting it is not permission to retry.

## Unknown outcome reconciliation

On a timeout, stream interruption, missing artifact, or failed verification, stop.
Do not duplicate the marker, rerun paid execution, make a retry branch, or rename
the work unit to evade the guard. Preserve workflow run/event SHA, deterministic
branch and its current head, contract digest, logs, and `dispatch.json`.
Artifacts/evidence upload runs even after failure.

The receipt is written before POST (`dispatch_pending`), then records Agents
session ID, root turn ID, completion and verification state before/after download.
A transport failure before completion may leave no session identity locally:
reconcile provider session/turn evidence using the original dispatch timing and
work-unit/contract metadata. Missing identity means the outcome remains unknown,
not that dispatch did not happen. Do not automatically issue another POST.

Read the existing Agents session/turn and its published artifacts when identities
are known. Match the original work unit, contract, source, selected route, event
head, and patch digest. If execution completed, recover and verify that turn's
artifacts without creating a new session; check whether caller write-back already
advanced the original branch/head. If state remains ambiguous, keep the work unit
blocked for explicit audit. Authorized caller repairs and audits stay on the
original branch. This gate offers no automatic paid retry for an existing work
unit; a future retry capability needs a separately reviewed protocol. A second
branch must never be used to hide an unknown result.

## Cutover and rollback

Cutover requires separate explicit authorization after successful real bounded
work: inspect verified contract/patch evidence, no-secret/no-remote-write behavior,
exact-head CI, and audit; exercise duplicate and unknown-outcome handling; recheck
supported model IDs/reasoning and Agents API semantics. Record the reviewed caller
version, workflow/source SHA, route defaults, cutover authority, and rollback target.
Only then may the generic work-unit surface be labeled Current. This Issue grants
no merge, close, release, deploy, secret change, or production cutover authority.

Roll back by stopping new generic V2 triggers and routing new work through Current
GDL v0.2. Preserve branches, receipts, sessions, artifacts, Draft PRs, and audits;
reconcile every in-flight/unknown V2 task before resuming overlapping work. Do not
delete the legacy path, hide failures, create replacement branches, or weaken
guards. Re-enable V2 only after a reviewed fix and separately authorized validation.
