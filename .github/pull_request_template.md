## What changed

Describe the change and why it is needed.

## Evidence

Link the Codex schema/source/docs/issue/discussion or other evidence that justifies Codex-specific behavior.

## Validation

- [ ] `python -m unittest discover -s tests -v`
- [ ] New behavior has tests
- [ ] No real secrets/config values were added to tests or docs
- [ ] Read-only default is preserved
- [ ] Markdown support output does not expose config values

## Risk notes

Call out any change involving networking, paths, parsing, privacy, mutation, or execution.
