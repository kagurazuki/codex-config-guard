# GitHub Development Loop V2 — new-cloud canary

Status: **CANDIDATE / PHASE 0 CANARY / NOT CURRENT / NO PRODUCTION CUTOVER**

Linked work unit: GitHub Issue #3.

## Outcome

The user should only need to tell ChatGPT what they want built. ChatGPT remains the planner/auditor, GitHub remains the durable control/evidence plane, and Codex runs through a new-cloud managed harness path with an explicit model route instead of relying on an unspecified/default model.

Target flow:

```text
User request
  -> ChatGPT planner/auditor
  -> bounded GitHub Issue
  -> explicit model + reasoning route
  -> managed Codex / Agents API execution
  -> dedicated branch + Draft PR
  -> tests / CI
  -> ChatGPT diff-and-evidence audit
  -> user-only boundary for merge/release/deploy when required
```

## Why V2 exists

The current GDL v0.2 is already a verified GitHub-centered loop, but its existing GitHub `@codex` trigger path is tied to the legacy Codex Cloud integration and does not give the planner a dependable per-task model-routing contract. V2 preserves the proven Issue/PR evidence structure while replacing only the execution adapter.

## Authority and rollback

- GDL v0.2 remains Current while V2 is being tested.
- V2 does not delete, disable, or rewrite the existing runtime.
- V2 is an execution-adapter candidate, not a new source of truth for task state.
- GitHub Issue remains the instruction canonical.
- Draft PR + current head SHA + actual diff + test/CI evidence remain the result canonical.
- If V2 fails, disable/ignore the V2 adapter and continue using the existing GDL path.

## Model routing contract

ChatGPT selects a task class before handing work to the execution adapter. The repository guard validates the route so the runtime cannot silently downgrade below the current floor.

| Task class | Default route | Typical work |
| --- | --- | --- |
| `routine` | `gpt-6-luna` / `max` | Focused, bounded, low-ambiguity changes |
| `standard` | `gpt-6.1-sol` / `high` | Normal coding, debugging, multi-file professional work |
| `critical` | `gpt-6-astra` / `high` | Hardest/high-impact design, debugging, migration or complex reasoning |

Upward escalation is allowed. Silent downgrade below either the task-class model floor or the chosen model's reasoning floor is rejected.

The current model IDs and supported reasoning levels must be rechecked against OpenAI's current model documentation before V2 is promoted beyond canary status.

## Phase plan

### Phase 0 — foundation, current scope

Build and verify only the non-live parts:

1. Bounded Issue contract.
2. Dedicated canary branch.
3. Repo-local `AGENTS.md` safety boundary.
4. Deterministic model route validator.
5. Unit tests and existing CI.
6. Draft PR with evidence.

**Stop before live Agents API execution.**

### Phase 1 — managed harness connectivity

After Phase 0 passes:

- Validate the supported Agents API session creation path using the managed Codex harness.
- Keep the OpenAI API key outside source control.
- Validate required API-key permissions and the exact execution environment.
- Use a synthetic/read-only or otherwise bounded canary first.
- Record direct evidence of selected model, reasoning route, task/session identity, and completion state.

### Phase 2 — GitHub write canary

Only after Phase 1 passes:

- Give the managed execution path access to one canary repo/branch only.
- Implement a tiny bounded change from Issue -> branch -> Draft PR.
- Require current-head reconciliation and targeted tests.
- Do not merge.

### Phase 3 — ChatGPT-orchestrated handoff

After the execution adapter is proven:

- ChatGPT converts the user's natural-language request into the Issue contract.
- ChatGPT selects task class/model route using the current user quality/cost rules.
- V2 launches the managed Codex task.
- ChatGPT audits Issue + current PR diff + tests/CI.
- Repairs stay on the same PR branch when safe.

At that point the intended user experience is: **tell ChatGPT what to build; the implementation plumbing stays behind the curtain.**

## Live execution prerequisites

Before enabling the Agents API step, all of the following must be true:

- A supported OpenAI API credential exists with only the required permissions.
- No secret value is stored in GitHub content, Issue/PR text, logs, or committed configuration.
- The exact repository access method is documented and can be revoked independently.
- The execution environment is explicit and reproducible.
- Unknown outcomes can be reconciled using task/session ID + repo + branch/head SHA.
- Duplicate execution cannot create a second uncontrolled branch/PR for the same work unit.
- Merge/release/deploy remain outside the canary's authority.

## Official platform basis checked for this canary

OpenAI's current Agents API documentation describes a managed Codex harness where the application explicitly supplies the agent model and execution environment. The current model catalog lists `gpt-6-luna`, `gpt-6.1-sol`, and `gpt-6-astra`, including high/xhigh/max reasoning options as applicable. These are current external platform facts and must be revalidated at promotion time.

References:
- https://developers.openai.com/api/docs/guides/agents-api/overview
- https://developers.openai.com/api/docs/guides/agents-api/quickstart
- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/guides/deployment-checklist

## Phase 0 done condition

Phase 0 is complete only when the branch contains this spec, `AGENTS.md`, the deterministic route guard, and tests; a Draft PR exists; and CI is green. Completion of Phase 0 does **not** authorize live Agents API execution or V2 adoption.