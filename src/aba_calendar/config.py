from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config.toml"


@dataclass(frozen=True)
class Config:
    source_url: str
    csv_path: Path
    timezone: str
    default_duration_minutes: int
    calendar_name: str
    calendar_description: str
    teams: tuple[str, ...]

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        config_path = path or DEFAULT_CONFIG
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        csv_path = Path(data["csv_path"])
        if not csv_path.is_absolute():
            csv_path = ROOT / csv_path
        return cls(
            source_url=data["source_url"],
            csv_path=csv_path,
            timezone=data.get("timezone", "Europe/Ljubljana"),
            default_duration_minutes=int(data.get("default_duration_minutes", 120)),
            calendar_name=data["calendar_name"],
            calendar_description=data["calendar_description"],
            teams=tuple(data.get("teams") or ()),
        )
