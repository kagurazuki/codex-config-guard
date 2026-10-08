# GDL V2 Phase 4 — ChatGPT-orchestrated handoff canary

Status: **CANDIDATE / ISSUE #11 / NOT CURRENT / NO MERGE OR CUTOVER**

This phase proves the complete bounded path that a normal user request is intended to use:

```text
user intent
  -> ChatGPT Issue/task contract + explicit route
  -> managed Codex in OpenAI-hosted sandbox
  -> patch + structured result artifacts
  -> ChatGPT independent artifact verification
  -> ChatGPT/GitHub controlled write-back
  -> Draft PR + CI
  -> head-bound audit
```

The managed Codex sandbox never receives GitHub write credentials. The repository write is a separate caller-side action performed only after the completed root turn and both published artifacts have been independently verified.

## Canary request

The contract is `.gdl/phase4-orchestrated-canary.json`.

It pins:
- work unit `issue-11-phase4`
- task class `routine`
- source SHA `b6d18dffcfad5016f2f21ee760372a2cf0ab2bdc`
- one added file: `docs/gdl-v2-orchestrated-handoff-canary.txt`
- exact content: `GDL_V2_ORCHESTRATED_HANDOFF_CANARY` plus one trailing newline

The only accepted route for this canary is the existing routine floor, `gpt-6-luna` with reasoning effort `max`.

## Contract safety

The Phase 4 handoff contract is intentionally narrower than a general coding task. It accepts only:
- one exact 40-character lowercase Git SHA;
- one `docs/*.txt` added path with no traversal;
- one uppercase ASCII marker line plus its trailing newline;
- one of the three existing V2 task classes;
- the repository's fixed unit-test command.

There is no arbitrary command field. Runtime network remains restricted to `github.com`, while build/runtime packages are provisioned by the hosted environment before the turn.

## Evidence boundary

A model completion message is never sufficient. PASS requires:
1. completed root turn and exact final output;
2. artifacts published by that exact root turn;
3. caller-side patch validation against the contract;
4. caller-side structured-result validation, including exact model and reasoning route;
5. `remote_write_attempted: false`;
6. re-read of `main` before write-back;
7. exact GitHub branch file read-back and actual PR diff;
8. CI green on the exact audited PR head;
9. Draft/open/unmerged state.

Any mismatch fails closed.

## Promotion boundary

Phase 4 does not make V2 Current. GDL v0.2 remains Current. A separate promotion gate must reconcile the stacked V2 implementation, rollback path, current model/platform facts, and a final representative end-to-end audit before any cutover is considered.
