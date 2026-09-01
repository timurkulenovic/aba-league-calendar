from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aba_calendar.config import Config
from aba_calendar.scrape import fetch_html, parse_matches, read_csv, write_csv
from aba_calendar.sync import sync_matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scrape ABA Liga dates, save CSV, and sync selected teams to macOS Calendar."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.toml",
    )
    sub = parser.add_subparsers(dest="command")

    fetch_parser = sub.add_parser("fetch", help="Download the calendar and write CSV")
    fetch_parser.add_argument("--url", help="Override source URL")

    sync_parser = sub.add_parser(
        "sync", help="Add filtered team matches from CSV into Personal Calendar"
    )
    sync_parser.add_argument(
        "--teams",
        help="Comma-separated team name filters (overrides config)",
    )
    sync_parser.add_argument(
        "--csv",
        type=Path,
        help="CSV to read (defaults to config csv_path)",
    )

    all_parser = sub.add_parser("all", help="Fetch CSV then sync filtered teams")
    all_parser.add_argument("--teams", help="Comma-separated team name filters")

    args = parser.parse_args(argv)
    config = Config.load(args.config)

    command = args.command or "all"
    if command == "fetch":
        return cmd_fetch(config, url=args.url)
    if command == "sync":
        teams = _teams(config, getattr(args, "teams", None))
        csv_path = args.csv or config.csv_path
        return cmd_sync(config, csv_path, teams)
    teams = _teams(config, getattr(args, "teams", None))
    status = cmd_fetch(config)
    if status != 0:
        return status
    return cmd_sync(config, config.csv_path, teams)


def cmd_fetch(config: Config, url: str | None = None) -> int:
    source = url or config.source_url
    print(f"Fetching {source}")
    html = fetch_html(source)
    matches = parse_matches(html, config.timezone)
    write_csv(matches, config.csv_path)
    print(f"Wrote {len(matches)} matches to {config.csv_path}")
    return 0


def cmd_sync(config: Config, csv_path: Path, teams: tuple[str, ...]) -> int:
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}. Run fetch first.", file=sys.stderr)
        return 1
    matches = [m for m in read_csv(csv_path) if m.involves_any(teams)]
    print(f"Syncing {len(matches)} matches for teams: {', '.join(teams)}")
    print(f"Calendar: {config.calendar_name} ({config.calendar_description})")
    result = sync_matches(matches, config)
    print(
        f"Created {result['created']} events, "
        f"skipped {result['skipped']} already present."
    )
    return 0


def _teams(config: Config, override: str | None) -> tuple[str, ...]:
    if override:
        return tuple(part.strip() for part in override.split(",") if part.strip())
    return config.teams


if __name__ == "__main__":
    raise SystemExit(main())
