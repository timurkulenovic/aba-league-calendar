from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aba_calendar.config import ROOT, Config
from aba_calendar.scrape import Match

UID_PREFIX = "aba-liga-match"
LEDGER_PATH = ROOT / "data" / "synced_uids.txt"


def apple_script_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def event_uid(match: Match) -> str:
    return f"{UID_PREFIX}-{match.match_id}"


def event_summary(match: Match) -> str:
    return f"{match.home} vs {match.away}"


def event_notes(match: Match) -> str:
    lines = [
        f"{match.round} · Group {match.group}" if match.group else match.round,
        f"UID: {event_uid(match)}",
        match.url,
    ]
    if match.result:
        lines.insert(1, f"Result: {match.result}")
    return "\n".join(lines)


def sync_matches(matches: list[Match], config: Config) -> dict[str, int]:
    existing = load_ledger()
    created = 0
    skipped = 0
    for match in matches:
        uid = event_uid(match)
        if uid in existing:
            skipped += 1
            print(f"  skip {event_summary(match)} ({match.date})")
            continue
        print(f"  add  {event_summary(match)} ({match.date} {match.time or 'all-day'})")
        create_event(match, config)
        append_ledger(uid)
        existing.add(uid)
        created += 1
    return {"created": created, "skipped": skipped, "total": len(matches)}


def load_ledger() -> set[str]:
    if not LEDGER_PATH.exists():
        return set()
    return {
        line.strip()
        for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def append_ledger(uid: str) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", encoding="utf-8") as handle:
        handle.write(uid + "\n")


def create_event(match: Match, config: Config) -> None:
    tz = ZoneInfo(config.timezone)
    start = _start_datetime(match, tz)
    if match.all_day:
        end = start + timedelta(days=1)
        all_day_line = "set allday event of theEvent to true"
    else:
        end = start + timedelta(minutes=config.default_duration_minutes)
        all_day_line = "set allday event of theEvent to false"

    notes = apple_script_escape(event_notes(match))
    script = f'''
tell application "Calendar"
  set theCal to first calendar whose name is "{apple_script_escape(config.calendar_name)}" and description is "{apple_script_escape(config.calendar_description)}"
  set startDate to current date
  set year of startDate to {start.year}
  set month of startDate to {start.month}
  set day of startDate to {start.day}
  set hours of startDate to {start.hour}
  set minutes of startDate to {start.minute}
  set seconds of startDate to 0
  set endDate to current date
  set year of endDate to {end.year}
  set month of endDate to {end.month}
  set day of endDate to {end.day}
  set hours of endDate to {end.hour}
  set minutes of endDate to {end.minute}
  set seconds of endDate to 0
  set theEvent to make new event at end of events of theCal with properties {{summary:"{apple_script_escape(event_summary(match))}", start date:startDate, end date:endDate, description:"{notes}", url:"{apple_script_escape(match.url)}"}}
  {all_day_line}
end tell
'''
    _run_osascript(script)


def _start_datetime(match: Match, tz: ZoneInfo) -> datetime:
    if match.all_day:
        return datetime.fromisoformat(match.date).replace(tzinfo=tz)
    return datetime.fromisoformat(match.datetime_iso).astimezone(tz)


def _run_osascript(script: str) -> str:
    completed = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout
