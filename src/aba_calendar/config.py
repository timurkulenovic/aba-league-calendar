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
    ics_output_dir: Path
    ics_subdir: str
    pages_base_url: str

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        config_path = path or DEFAULT_CONFIG
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        csv_path = Path(data["csv_path"])
        if not csv_path.is_absolute():
            csv_path = ROOT / csv_path
        ics_output_dir = Path(data.get("ics_output_dir", "docs"))
        if not ics_output_dir.is_absolute():
            ics_output_dir = ROOT / ics_output_dir
        return cls(
            source_url=data["source_url"],
            csv_path=csv_path,
            timezone=data.get("timezone", "Europe/Ljubljana"),
            default_duration_minutes=int(data.get("default_duration_minutes", 120)),
            calendar_name=data.get("calendar_name", ""),
            calendar_description=data.get("calendar_description", ""),
            teams=tuple(data.get("teams") or ()),
            ics_output_dir=ics_output_dir,
            ics_subdir=data.get("ics_subdir", "ics"),
            pages_base_url=data.get(
                "pages_base_url",
                "https://timurkulenovic.github.io/aba-league-calendar",
            ),
        )
