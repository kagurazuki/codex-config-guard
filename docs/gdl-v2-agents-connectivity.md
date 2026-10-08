# GDL V2 Phase 1 — Agents API connectivity canary

Status: **PHASE 1 PASS / MANAGED CODEX ROOT-TURN CONNECTIVITY VERIFIED / NO REPOSITORY WRITE CAPABILITY**

Linked work unit: GitHub Issue #5. Depends on Phase 0 Draft PR #4.

## Purpose

Prove that the GDL V2 application can run one managed Codex/Agents API turn with the explicit route selected by the Phase 0 model guard and verify the turn's actual terminal outcome and final output.

This phase deliberately does **not** give the managed agent a repository filesystem, GitHub write token, deployment credentials, or any other external-system capability. The canary uses `environment.type=none` and asks for one exact text response.

## Required OpenAI application-key permissions

The Agents API application key is restricted to the required session/inference permissions:

- `api.agents.read`
- `api.agents.write`
- `api.responses.write`

The restricted key is stored outside source control as GitHub repository secret `GDL_V2_OPENAI_API_KEY`. The workflow maps that secret to `OPENAI_API_KEY` only for the guarded live job. Never put the key in Issue/PR text, committed files, command arguments, or logs.

Official references:
- https://developers.openai.com/api/docs/guides/agents-api/quickstart
- https://developers.openai.com/api/docs/guides/agents-api/sessions
- https://developers.openai.com/api/docs/guides/agents-api/sessions/events
- https://developers.openai.com/api/docs/guides/agents-api/environments/security

## Dry run

After installing the repository package, run:

```bash
python scripts/gdl_v2_agents_connectivity.py --task-class routine
```

Dry run is the default. It prints the endpoint, required permission names, and the non-secret request payload. It does not read or require `OPENAI_API_KEY` and does not make a network call.

For an explicit upgraded route:

```bash
python scripts/gdl_v2_agents_connectivity.py \
  --task-class routine \
  --model gpt-6.1-sol \
  --reasoning-effort high
```

The Phase 0 validator rejects unsupported or under-floor routes before any live request can be created.

## Live connectivity run

Live mode is intentionally opt-in:

```bash
python scripts/gdl_v2_agents_connectivity.py --task-class routine --live
```

The command fails closed unless `OPENAI_API_KEY` is present. The key is used only in the HTTP `Authorization` header and is not included in the JSON payload or printed output.

The live canary POSTs to `/v1/agents/sessions` with `stream: true` and:

- explicit model from the route guard
- explicit `reasoning.effort`
- `environment.type=none`
- no tools
- a non-destructive instruction to return exactly `GDL_V2_CONNECTIVITY_OK`

## PASS contract

Session creation or `agent.session.idle` alone is not success. The live run consumes the Agents API event stream and PASS requires all of the following:

1. A session identity is observed.
2. The root turn emits `agent.session.turn.completed`.
3. The final `agent.session.turn.output_text.done` text resolves exactly to `GDL_V2_CONNECTIVITY_OK`.
4. No root-turn failure/cancellation, session/environment failure, or unexpected required action occurs.

The command fails closed if the stream closes before root-turn completion, if output differs, if the stream is malformed, or if the session identity is missing.

## GitHub Actions guard

The branch-scoped workflow runs only on `gdl-v2-agents-connectivity-canary`.

- Ordinary pushes run the guard job but skip the paid connectivity job.
- The paid live job runs only when the commit message contains exact marker `[gdl-v2-live]`.
- Workflow permission is `contents: read` only.
- No merge, release, deploy, or repository-write path exists in this phase.

## Verified evidence

Completion-aware implementation CI run `37782130880` / #82 passed on Python 3.11, 3.12, and 3.13.

Completion-verified live run `37782192796` on head `a83021127a39cbc014d08434475804951f1a0a60` passed with:

- session `sess_0863c517b99af96d006ac7962e21e8819c9f1f8181452a2d19`
- root turn `turn_0863c517b99af96d006ac79632018c819ca2745873db93474c`
- root turn status `completed`
- exact output `GDL_V2_CONNECTIVITY_OK`
- `verified_output: true`

The GitHub Actions log kept `OPENAI_API_KEY` masked and exposed only `contents: read` plus metadata-read permissions for the workflow token.

## Phase 1 verdict and boundary

**PHASE 1 PASS.** Managed Codex can be launched through the Agents API with the explicit V2 route and its root-turn outcome can be verified deterministically.

Phase 1 still grants no repository-write capability. Phase 2 must separately validate an OpenAI-hosted sandbox that produces bounded patch/test artifacts before any write-back path is considered. GDL v0.2 remains Current until later V2 promotion gates pass.
