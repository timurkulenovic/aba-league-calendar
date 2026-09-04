from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aba_calendar.config import Config
from aba_calendar.ical import write_ics_feeds
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

    ics_parser = sub.add_parser(
        "ics", help="Generate subscribable .ics feeds + index.html into the Pages dir"
    )
    ics_parser.add_argument(
        "--csv",
        type=Path,
        help="CSV to read (defaults to config csv_path)",
    )

    args = parser.parse_args(argv)
    config = Config.load(args.config)

    command = args.command or "all"
    if command == "fetch":
        return cmd_fetch(config, url=args.url)
    if command == "sync":
        teams = _teams(config, getattr(args, "teams", None))
        csv_path = args.csv or config.csv_path
        return cmd_sync(config, csv_path, teams)
    if command == "ics":
        csv_path = args.csv or config.csv_path
        return cmd_ics(config, csv_path)
    teams = _teams(config, getattr(args, "teams", None))
    status = cmd_fetch(config)
    if status != 0:
        return status
    if config.calendar_name:
        cmd_sync(config, config.csv_path, teams)
    return cmd_ics(config, config.csv_path)


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


def cmd_ics(config: Config, csv_path: Path) -> int:
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}. Run fetch first.", file=sys.stderr)
        return 1
    matches = read_csv(csv_path)
    result = write_ics_feeds(
        matches=matches,
        output_dir=config.ics_output_dir,
        base_url=config.pages_base_url,
        ics_subdir=config.ics_subdir,
        tz_name=config.timezone,
        duration_minutes=config.default_duration_minutes,
    )
    print(
        f"Wrote {result['teams']} team feeds + all.ics ({result['matches']} matches) "
        f"to {config.ics_output_dir / config.ics_subdir}"
    )
    print(f"Index page: {config.ics_output_dir / 'index.html'}")
    print(f"Subscribe URL base: {config.pages_base_url.rstrip('/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
