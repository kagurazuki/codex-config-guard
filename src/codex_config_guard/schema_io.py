from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import __version__

OFFICIAL_SCHEMA_URL = "https://developers.openai.com/codex/config-schema.json"


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def load_json_source(source: str, timeout: float = 10.0) -> dict[str, Any]:
    if _is_url(source):
        req = Request(source, headers={"User-Agent": f"codex-config-guard/{__version__}"})
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - user-selected URL is intentional
            payload = response.read().decode("utf-8")
    else:
        payload = Path(source).read_text(encoding="utf-8")

    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Schema source must contain a JSON object")
    return data


def top_level_properties(schema: dict[str, Any]) -> set[str]:
    props = schema.get("properties", {})
    return set(props) if isinstance(props, dict) else set()


def feature_properties(schema: dict[str, Any]) -> set[str]:
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return set()
    features = props.get("features")
    if not isinstance(features, dict):
        return set()

    # Most generated schemas expose features directly or through allOf/$ref.
    direct = features.get("properties")
    if isinstance(direct, dict):
        return set(direct)

    for entry in features.get("allOf", []):
        if isinstance(entry, dict) and isinstance(entry.get("properties"), dict):
            return set(entry["properties"])
        ref = entry.get("$ref") if isinstance(entry, dict) else None
        if isinstance(ref, str) and ref.startswith("#/definitions/"):
            name = ref.split("/")[-1]
            defs = schema.get("definitions", {})
            target = defs.get(name) if isinstance(defs, dict) else None
            if isinstance(target, dict) and isinstance(target.get("properties"), dict):
                return set(target["properties"])
    return set()
