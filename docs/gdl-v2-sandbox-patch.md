# GDL V2 Phase 2 — managed sandbox patch-artifact canary

Status: **PHASE 2 PASS / MANAGED SANDBOX PATCH+TEST ARTIFACTS VERIFIED / CODEX HAS NO GITHUB WRITE CREDENTIAL**

Linked work unit: GitHub Issue #7. Depends on Phase 1 Issue #5 / Draft PR #6 PASS.

## Purpose

Prove the next V2 boundary without giving Codex any GitHub write credential:

1. launch a managed Codex turn in an OpenAI-hosted sandbox;
2. clone an exact public GitHub revision under a restricted network policy;
3. make one bounded synthetic change inside the sandbox;
4. run the repository unit suite;
5. publish a patch and structured result under `/workspace/outputs`;
6. download those published artifacts through the Agents session Artifacts API;
7. independently validate the patch and result in the GitHub Actions caller.

A model completion message is not sufficient evidence. PASS requires caller-side artifact validation.

## Exact source and change contract

- repository: `https://github.com/kagurazuki/codex-config-guard.git`
- source SHA: `b6d18dffcfad5016f2f21ee760372a2cf0ab2bdc`
- only intended source-tree change: `docs/gdl-v2-managed-agent-canary.txt`
- exact file payload: `GDL_V2_MANAGED_AGENT_CANARY` plus one trailing newline
- required test: `python -m unittest discover -s tests -v`
- required published artifacts:
  - `/workspace/outputs/change.patch`
  - `/workspace/outputs/result.json`

`result.json` must exactly report the pinned source SHA, expected changed path and marker, PASS test state, and `remote_write_attempted: false`.

## OpenAI-hosted environment boundary

The verified canary uses:

- `environment.type=openai_hosted`
- `container_size=small`
- `network.access=restricted`
- runtime allowlist: `github.com` only
- hosted Python package setup for `hatchling>=1.25` and `jsonschema>=4.23,<5`
- normal local project installation with `python -m pip install . --no-build-isolation --no-deps`

No GitHub token, GitHub App credential, vault credential, deployment credential, or other third-party secret is supplied to the sandbox.

Official references:
- https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted
- https://developers.openai.com/api/docs/guides/agents-api/environments/security
- https://developers.openai.com/api/docs/guides/agents-api/environments/files
- https://developers.openai.com/api/docs/guides/agents-api/sessions

## Artifact verification

After the root turn completes, the caller lists `GET /v1/agents/sessions/{session_id}/artifacts` and selects only artifacts matching both the completed root `turn_id` and required absolute path. It then downloads each artifact's `/content` endpoint.

The caller rejects:

- missing required artifacts;
- artifacts from a different turn;
- a patch that changes any path other than the expected canary file;
- unexpected added content;
- a result with the wrong source SHA/path/marker/test state;
- any result claiming `remote_write_attempted: true`;
- malformed JSON or incomplete evidence.

Verified local copies are preserved as a short-retention GitHub Actions artifact for audit.

## Verified live evidence

Final live head: `d767201f58e10b741860d907c5696bd3cbeeb584`

GitHub Actions run `37786369894` completed successfully:

- guard job: PASS
- hosted sandbox job: PASS
- session: `sess_07104de971deb74e006ac79da3471881a3bbb1527da5f37e74`
- root turn: `turn_07104de971deb74e006ac79da9210881a3927e4db8559e40ed`
- root turn status: `completed`
- exact final output: `GDL_V2_SANDBOX_OK`
- source SHA: `b6d18dffcfad5016f2f21ee760372a2cf0ab2bdc`
- changed path: `docs/gdl-v2-managed-agent-canary.txt`
- test status: `pass`
- `patch_verified: true`
- `result_verified: true`

GitHub Actions evidence artifact:

- name: `gdl-v2-sandbox-patch-evidence`
- ID: `11554472587`
- digest: `sha256:3a63c7a51b89ca64017e162d32258ddfc278718da3a3a9ea9a7f94f9075f8347`
- contents: exactly `change.patch` and `result.json`

The downloaded ZIP was re-read independently. `change.patch` adds only the expected marker file, and `result.json` matches the exact source/path/marker/test/no-remote-write contract.

## Retained failure evidence

Phase 2 attempts 1-3 remain recorded in Issue #7. They exposed, in order:

1. the cloned package had not been installed before tests;
2. editable installation introduced an unnecessary `editables` dependency;
3. the caller incorrectly concatenated progress output items with the final Agents output item.

Each defect was repaired without widening GitHub credentials or runtime network access.

## Phase 2 verdict and next boundary

**PHASE 2 PASS.** Managed Codex can produce a bounded tested patch artifact in an OpenAI-hosted sandbox, and the caller can independently verify that evidence while Codex has no GitHub write credential.

The generated patch is still **not** written back to GitHub automatically in Phase 2. Phase 3 is the separate controlled-write boundary: the ChatGPT/GitHub side may apply an already verified bounded patch to a dedicated branch, create a Draft PR, run CI, and audit the resulting head. Merge/release/deploy remain outside that authority. GDL v0.2 remains Current until later V2 promotion gates pass.
