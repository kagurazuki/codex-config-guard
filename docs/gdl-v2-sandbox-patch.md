# GDL V2 Phase 2 — managed sandbox patch-artifact canary

Status: **CANDIDATE / PREPARED / LIVE SANDBOX CANARY NOT YET RUN**

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

The canary uses:

- `environment.type=openai_hosted`
- `container_size=small`
- `network.access=restricted`
- initial runtime allowlist: `github.com` only
- hosted Python package setup for the repository's existing `jsonschema>=4.23,<5` dependency

No GitHub token, GitHub App credential, vault credential, deployment credential, or other third-party secret is supplied to the sandbox.

OpenAI's Agents API documentation states that an `openai_hosted` sandbox provides a Linux workspace, supports restricted network host allowlists, and publishes files under `/workspace/outputs` as immutable session artifacts when a turn completes.

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

Verified local copies are then preserved as a short-retention GitHub Actions artifact for audit.

## GitHub Actions gate

Workflow: `.github/workflows/gdl-v2-sandbox-patch.yml`

- branch-scoped to `gdl-v2-sandbox-patch-canary`;
- GitHub token permission is `contents: read` only;
- ordinary pushes run only the guard job;
- paid hosted-sandbox execution requires exact commit marker `[gdl-v2-sandbox-live]`;
- no push, PR creation/update, merge, release, deploy, or production cutover exists in this phase.

## Promotion boundary

Phase 2 may be marked PASS only after green repository CI and one bounded live sandbox run whose published artifacts pass caller-side verification.

Even after Phase 2 PASS, the generated patch must **not** be written back to GitHub automatically in this phase. A controlled write-back path is a separate Phase 3 boundary. GDL v0.2 remains Current until later V2 promotion gates pass.
