from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    path: str = "$"
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
