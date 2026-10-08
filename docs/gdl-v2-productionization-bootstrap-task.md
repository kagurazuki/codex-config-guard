# GDL V2 productionization bootstrap task

Canonical work unit: GitHub Issue #16.

Implement the Productionization Gate on top of exact source SHA `8adf1f8fbd4a13437657e5e177d8e0defcc8f213`.

The implementation must turn the proven canary stack into a reusable **candidate** for real bounded coding work without claiming Current or modifying remote GitHub state.

## Required implementation

1. Add a reusable work-unit contract module with strict validation. The contract must include schema version, stable work-unit id, GitHub issue number, task class, exact source SHA, summary, detailed instructions, explicit allowed path scopes, maximum changed-file count, and an allowlisted test profile. Reject traversal, `.git`, empty/unbounded scopes, invalid SHA/task class, unsafe/oversized values, and invalid route requests.
2. Add generic managed-Codex payload/instruction construction using the existing route guard and OpenAI-hosted sandbox primitives. Codex receives no GitHub credential. It clones the exact source SHA, edits only allowed scopes, runs an allowlisted test profile, writes `/workspace/outputs/change.patch` and `/workspace/outputs/result.json`, re-reads them, and returns only `GDL_V2_SANDBOX_OK` on success.
3. Add caller-side verification that parses changed paths from the patch and enforces allowed scopes + max file count, validates result metadata including work unit / issue / model / reasoning / source SHA / test profile / test PASS / `remote_write_attempted: false`, and binds integrity to a patch SHA-256.
4. Add a generic executable script/CLI for one work-unit contract. It must be dry-run-first and require an explicit live flag plus `OPENAI_API_KEY` from the environment.
5. Add a generic GitHub Actions entry surface for deterministic V2 work branches, using read-only repository permission and the existing `GDL_V2_OPENAI_API_KEY` secret only in the caller process. It must never pass a GitHub credential into the agent payload.
6. Add deterministic branch naming and duplicate-trigger protection. The same `work_unit` must map to exactly one branch identity. Validate an exact run marker bound to the same work unit and fail closed if the same branch history contains that trigger more than once. Document unknown-outcome reconciliation using branch/head + Agents session/turn evidence instead of creating a second branch.
7. Update `AGENTS.md` from Phase-4-only canary instructions to reusable V2 candidate instructions. Keep all no-merge/no-close/no-release/no-secret/no-direct-main/no-Codex-GitHub-write boundaries.
8. Add a productionization/current/rollback document that clearly marks old Phase 0-4 workflows as historical canary surfaces, identifies the generic work-unit entry as the future Current surface, keeps GDL v0.2 Current for now, and gives rollback/cutover rules.
9. Preserve existing Phase 0-4 code/tests. Avoid unnecessary dependency changes.

## Design constraints

- This repository is public and source clone uses only `github.com` network access at runtime.
- Prefer standard library plus existing dependencies.
- Test execution must use an allowlisted profile, not arbitrary shell from the contract. At minimum support the repository unit profile `python -m unittest discover -s tests -v`.
- Path scopes should be expressive enough for real source+test+docs work while remaining bounded. Exact files and/or directory prefixes are acceptable if validation is strict and caller-side patch verification uses the same semantics.
- Generic contracts may permit create/modify/delete only if verification can reliably constrain the resulting patch. If deletion support complicates safety, create/modify-only is acceptable for this gate and must be documented.
- The generic workflow must be invokable by the ChatGPT/GitHub control plane through deterministic branch + contract commit semantics, without consumer UI automation.
- Do not merge, push, open PRs, close issues, release, deploy, or mutate any remote system from the sandbox.

## Required tests

Add tests for:
- valid multi-path real-code contract
- invalid traversal / `.git` / unbounded scopes / invalid SHA / invalid task class / size bounds
- route selection and silent downgrade rejection
- payload/instruction construction
- changed-path extraction from multi-file patches
- allowed-scope and max-file enforcement
- result metadata + patch digest verification
- deterministic branch naming
- exact work-unit run-marker validation and duplicate-trigger rejection

Run the complete repository suite: `python -m unittest discover -s tests -v`.

## Output contract for this bootstrap producer

When implementation and tests pass, create exactly:
- `/workspace/outputs/change.patch` containing the complete git diff from source SHA to the productionization implementation
- `/workspace/outputs/result.json` containing JSON with at least: `issue_number: 16`, `source_sha`, `test_command`, `test_status`, `remote_write_attempted: false`, and `changed_paths`

Then re-read both files and return exactly `GDL_V2_SANDBOX_OK` and nothing else.

If any required check fails, do not fabricate PASS evidence and do not return the success marker.