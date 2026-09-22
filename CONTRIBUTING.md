# Contributing

Thanks for helping improve Codex Config Guard.

## Ground rules

- Keep the default behavior read-only.
- Do not add telemetry, account requirements, secret collection, or config-value reporting.
- Prefer deterministic checks backed by Codex schema/source/docs evidence.
- Do not infer that a removed setting is safe to delete merely because it disappeared from a schema.
- New findings should use stable rule IDs and include tests.

## Development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
```

## Pull requests

Please include:

1. the problem being solved;
2. the evidence source for Codex-specific behavior;
3. tests for new logic;
4. whether the change affects privacy, config mutation, networking, or evidence labels.

Changes that auto-edit `config.toml`, expose secret values, execute Codex/MCP/project code, or weaken evidence labeling need separate design review before implementation.
