# GDL V2 Phase 1 — Agents API connectivity canary

Status: **CANDIDATE / PREPARED / LIVE RUN BLOCKED UNTIL RESTRICTED APPLICATION KEY EXISTS**

Linked work unit: GitHub Issue #5. Depends on Phase 0 Draft PR #4.

## Purpose

Prove only that the GDL V2 application can create a managed Codex/Agents API session with the explicit route selected by the Phase 0 model guard.

This phase deliberately does **not** give the managed agent a repository filesystem, GitHub write token, deployment credentials, or any other external-system capability. The canary uses `environment.type=none` and asks for one exact text response.

## Required OpenAI application-key permissions

The current Agents API quickstart requires a project application API key with:

- `api.agents.read`
- `api.agents.write`
- `api.responses.write`

Store the key outside source control as `OPENAI_API_KEY`. Never put it in Issue/PR text, committed files, command arguments, or logs.

Official references:
- https://developers.openai.com/api/docs/guides/agents-api/quickstart
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

The live canary creates a session at `/v1/agents/sessions` with:

- explicit model from the route guard
- explicit `reasoning.effort`
- `environment.type=none`
- no tools
- a non-destructive instruction to return exactly `GDL_V2_CONNECTIVITY_OK`

This phase records only non-secret response metadata such as session ID/status. It does not claim full success merely because session creation returned; a later live validation must reconcile the session/turn outcome before promoting the path.

## Current stop boundary

Do not run live until the restricted application key has been created and stored outside the repository. Do not add GitHub/repository write capability in Phase 1. The next phase will design a bounded code-change transport separately so the model never needs a broad GitHub credential merely to edit code.