# GDL V2 productionization, Current, and rollback

Status: **GDL V2 CURRENT**.

The Current execution surface is `scripts/gdl_v2_work_unit.py` with
`.github/workflows/gdl-v2-work-unit.yml`. GDL v0.2 is preserved intact as the
rollback path and historical predecessor; it is no longer the Current execution
surface after the Issue #22 cutover merge.

Productionization history remains auditable:

- Productionization Gate #16 built the reusable work-unit layer.
- Real-code generic proof #18 exercised the managed path on actual Python source and tests.
- Promotion Gate #20 returned `PROMOTION_READY` for exact integrated head
  `6eb36800dd00ccba107da275343b57337c9aa3a3`.
- Current cutover authority is GitHub Issue #22.
- Recovery Issue #23 records the one-time control-plane finalization used after the
  Issue #22 R3 managed turn was reconciled to a terminal provider
  `usage_limit_exceeded` failure with no implementation artifacts. That recovery is
  historical cutover evidence, not a general bypass around the managed work-unit path.
- Final audited merge/main evidence and `CURRENT_CUTOVER_PASS` are recorded in Issue #22.
- Issue #25 temporarily changes the active routing preference to Astra/high for every
  task class. Its single managed Astra/high attempt failed terminally with
  `usage_limit_exceeded` and no implementation artifacts; Recovery Issue #26 records
  the bounded control-plane finalization. This recovery is specific to that routing
  configuration change and is not a general managed-execution bypass.

## Surfaces and authority

| Surface | Status and purpose |
| --- | --- |
| GDL v0.2 / legacy GitHub loop | Preserved rollback path and historical predecessor |
| Phase 0 foundation / `docs/gdl-v2-new-cloud.md` | Historical canary design and route evidence |
| `gdl-v2-agents-connectivity.yml` / Phase 1 | Historical connectivity canary |
| `gdl-v2-sandbox-patch.yml` / Phase 2 | Historical one-file sandbox canary |
| Phase 3 caller write-back / `docs/gdl-v2-sandbox-patch.md` | Historical controlled handoff evidence |
| `gdl-v2-orchestrated-handoff.yml` / Phase 4 | Historical marker-file orchestration canary |
| `gdl-v2-work-unit.yml` / generic CLI | **Current** bounded coding entry surface |

Historical code/tests/workflows are preserved for evidence and regression checks.
Their old branch names and marker strings are not generic Current triggers. Earlier
candidate/canary plans are evidence, not authority for new live tasks.

The GitHub Issue is the instruction canonical. The Draft PR, exact head, actual diff,
tests/CI, and independent audit are the result canonical. Chat completion text and
self-reported PASS are insufficient for write-back, merge, or other remote actions.

## Schema-v1 contract

The trusted ChatGPT/GitHub control plane places one JSON contract at
`.gdl/work-unit.json` on the deterministic work branch. The file is control-plane
input, not a patch change to inject into the sandbox. A typical Current contract is:

```json
{
  "schema_version": 1,
  "work_unit": "issue-42-example",
  "issue_number": 42,
  "task_class": "standard",
  "source_sha": "0123456789abcdef0123456789abcdef01234567",
  "summary": "Implement one bounded repository change",
  "instructions": "Implement the linked Issue within the reviewed scopes and preserve all Current safety boundaries.",
  "allowed_paths": [
    "src/codex_config_guard/example.py",
    "tests/test_example.py"
  ],
  "max_changed_files": 2,
  "test_profile": "unit",
  "route": {"model": "gpt-6-astra", "reasoning_effort": "high"}
}
```

For each new task, pin a reviewed source commit containing Current V2, bind the
canonical Issue/instructions, and use the smallest complete path scopes. A trailing
`/` means descendants of that directory; other values mean exact files. `src/` does
not authorize `src-other/`. No glob expansion occurs. Overlapping/redundant directory
authority is rejected so a broad scope cannot silently duplicate a narrower one.

Validation rejects unknown/missing keys, duplicate JSON keys, non-object roots,
non-finite numbers, invalid types including booleans used as integers, controls,
traversal, absolute paths, `.git` components, empty/root/glob scopes, unsafe path
characters, duplicate scopes, and overlapping/redundant directory scopes. Bounds:
32 KiB JSON, 3–64 character lowercase alphanumeric/hyphen work-unit IDs with no
repeated/trailing hyphen, 240-byte summary, 12,000-byte detail, 1–32 scopes,
240-character paths with 64-character components, 1–64 changed files, and positive
signed-32-bit Issue numbers. SHAs are full lowercase 40-hex identities excluding
all-zero. `schema_version` must be integer `1`.

`route` is optional but resolves to an explicit deterministic route. Partial or
invalid requests fail. The router always enforces the active model/effort floor and
never relies on an unspecified provider model default.

### Temporary Astra/high routing policy

`src/codex_config_guard/gdl_v2_router.py` currently has:

```python
ACTIVE_ROUTE_POLICY = "astra-high-temporary"
```

While that selector is active, every task class defaults to and is floored at:

- routine/focused: `gpt-6-astra` / `high`
- standard coding/professional: `gpt-6-astra` / `high`
- hardest/high-impact: `gpt-6-astra` / `high`

Therefore Luna or Sol requests for routine/standard tasks fail route validation
instead of silently using a lower-capability model.

The prior balanced policy is preserved intact in the same module:

- routine/focused: `gpt-6-luna` / `max`
- standard coding/professional: `gpt-6.1-sol` / `high`
- hardest/high-impact: `gpt-6-astra` / `high`

To restore the previous balanced behavior, change only the selector to:

```python
ACTIVE_ROUTE_POLICY = "balanced"
```

Do not reconstruct the old mapping or weaken route validation. Tests cover both
policy definitions so the rollback is a selector change rather than a routing rewrite.

Only `unit` is currently allowlisted, mapping to
`python -m unittest discover -s tests -v`. Contracts cannot supply arbitrary test
shell. New profiles require a reviewed code change to the allowlist.

## Current execution and credential boundary

Prepare a contract without live execution:

```sh
python scripts/gdl_v2_work_unit.py /path/to/contract.json
```

On the exact clean work-branch checkout, preflight includes Git evidence:

```sh
python scripts/gdl_v2_work_unit.py .gdl/work-unit.json --check-trigger
```

Live execution additionally requires explicit `--live` and `OPENAI_API_KEY` already
present in the caller environment. Never request, log, or commit keys. The GitHub
workflow exposes only `GDL_V2_OPENAI_API_KEY` to the caller live step. Repository
permissions are `contents: read`; checkout uses `persist-credentials: false`.
No GitHub token, caller environment, cookie, or secret is copied into agent input,
environment, or metadata. Codex receives no GitHub write credential.

The agent clones the public fixed repository from `github.com`, checks out the exact
contract source SHA, installs with `--no-build-isolation --no-deps`, requires a clean
tree, implements the bounded work, and runs the allowlisted profile with fixed
`PYTHONPATH=/workspace/repo/src` so tests exercise edited source. The hosted runtime
network is restricted to `github.com`. The agent stages intended changes locally
without committing and writes `/workspace/outputs/change.patch` plus
`/workspace/outputs/result.json`. It re-reads them and emits only
`GDL_V2_SANDBOX_OK` after successful checks.

The caller downloads artifacts belonging to the completed session's exact root turn.
It parses the complete patch, enforces matching old/new paths, scope semantics, file
count and supported text operations, and checks exact result metadata: schema,
work unit, Issue, task class, model/effort, source, test profile/command/PASS,
`remote_write_attempted: false`, sorted changed paths, canonical contract SHA-256,
and SHA-256 of the exact patch bytes. The completion marker alone is never enough.
Result JSON is bounded at 32 KiB and patches at 2 MiB.

Current artifact verification accepts regular LF UTF-8 text create/modify patches
with nonempty new files. File deletion, rename/copy, binary diffs, quoted or
space-containing paths, mode changes, symlinks/submodules, empty new files, and
unexplained patch syntax fail closed. Line removal within a modified file is
supported. Broader operations require a separately reviewed parser/test change.

After verification, an independently authorized ChatGPT/GitHub control-plane caller
may apply only the verified patch to the reviewed source/work branch and prepare a
Draft PR. Reconcile the actual diff, run required tests, and check the current
branch/head before write-back. The CLI, workflow, and Codex do not perform remote
GitHub write-back. Exact-head CI and a head-bound audit are required before a merge
or other high-impact action.

## Deterministic trigger and duplicate protection

Every work unit maps injectively to exactly `gdl-v2/work/<work_unit>`; route, time,
Issue edits, and retries never create a second identity. The authorized GitHub
control plane creates that branch from the reviewed source and commits the canonical
contract with this entire commit message:

```text
[gdl-v2-run:<work_unit>]
```

That commit is the one paid trigger. The push workflow's preliminary string filter
does not grant authority. Preflight checks the exact whole message, matching work
unit/branch, original event HEAD, committed contract equality, source ancestry,
clean checkout, full non-shallow reachable history, and exactly one occurrence of
the work-unit marker. Mismatched marker, duplicate occurrence, wrong branch/contract,
and Actions `GITHUB_RUN_ATTEMPT != 1` fail before dispatch. Later implementation or
audit commits use ordinary messages without a marker. Do not force-push away trigger
history.

Branch concurrency serializes runs without canceling active work. This protects
against duplicate trigger commits and ordinary Actions reruns, not every possible
provider/network ambiguity. There is no claim of distributed exactly-once API
execution. A local exclusive `dispatch.json` receipt is written before the POST and
blocks repeat dispatch from the same output state; deleting or moving it is not
permission to retry.

## Unknown-outcome reconciliation

On a timeout, stream interruption, missing artifact, failed verification, or another
post-dispatch transport error, stop. Do not duplicate the marker, rerun paid
execution, make a retry branch, or rename the work unit to evade the guard. Preserve
the workflow run/event SHA, deterministic branch/head, contract digest, logs, and
`dispatch.json`. Evidence upload runs even after failure.

The receipt begins as `dispatch_pending`, then records Agents session/root-turn and
verification state when available. A transport failure can leave no local session
identity even though the POST reached the provider. Reconcile provider session/turn
evidence using original dispatch timing plus work-unit/contract/source/route metadata.
Missing local identity means unknown outcome, not proof of no dispatch.

When provider session/turn identities are found, inspect the existing turn and its
artifacts read-only. If it completed, recover and verify that exact turn rather than
creating a new session. If it failed terminally, record the exact provider outcome
and artifact state. If ambiguity remains, keep the work unit blocked. Never create a
second branch merely to hide an unknown result.

A fresh paid retry after a confirmed terminal failure is not automatic. It requires
a separately reviewed recovery protocol that states why reuse/retry is safe and how
the original identity remains auditable. Issue #23 is historical evidence of one
such protocol for the Current cutover governance transition after R3 failed with
`usage_limit_exceeded`. Issue #26 separately records the Issue #25 routing-policy
recovery after its single Astra/high attempt failed with the same provider code and
no artifacts. Neither recovery grants ordinary tasks a general control-plane
implementation bypass.

## Current status and rollback

Current cutover was separately authorized by Issue #22 after Promotion Gate #20
returned `PROMOTION_READY` for exact integrated source
`6eb36800dd00ccba107da275343b57337c9aa3a3`. The cutover changes status/governance
wording and Current metadata without weakening the already-proven managed execution,
credential, routing, patch-verification, duplicate, or recovery architecture.
No release, deploy, package publication, secret change, or automatic Issue closure
is implied by Current status.

There are two distinct rollback actions:

1. **Routing-policy rollback:** if only the temporary Astra/high preference should be
   removed, change `ACTIVE_ROUTE_POLICY` in `gdl_v2_router.py` from
   `"astra-high-temporary"` to `"balanced"`. This restores the preserved Luna/Sol/Astra
   balanced mapping without disabling GDL V2 Current.
2. **Execution-surface rollback:** if Current V2 itself must be stopped, follow the
   fail-safe sequence below and route new bounded development through preserved GDL v0.2.

Execution-surface rollback remains fail-safe and preserves evidence:

1. Stop creation of new generic V2 Current triggers.
2. Reconcile every in-flight or unknown V2 work unit before overlapping work resumes.
3. Route new bounded development through the preserved GDL v0.2 rollback path while
   the V2 issue is repaired.
4. Preserve V2 branches, receipts, sessions, artifacts, Draft PRs, audits, and the
   failing exact heads. Do not rewrite history to hide a failure.
5. Do not delete or weaken either V2 safety guards or the v0.2 rollback path.
6. Restore V2 as the active Current path only after a reviewed fix, green exact-head
   CI, and a separately authorized validation/audit.

The authoritative cutover merge SHA and post-merge `main` verification are recorded
in Issue #22 so the repository code does not need a self-referential merge identifier.
