from __future__ import annotations

import csv
import html.parser
import re
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DATETIME_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*"
    r"(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})"
    r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<tz>CET|CEST)?)?",
    re.IGNORECASE,
)
CSV_FIELDS = (
    "match_id",
    "round",
    "group",
    "date",
    "time",
    "datetime_iso",
    "all_day",
    "home",
    "away",
    "result",
    "url",
    "datetime_raw",
)


@dataclass(frozen=True)
class Match:
    match_id: str
    round: str
    group: str
    date: str
    time: str
    datetime_iso: str
    all_day: bool
    home: str
    away: str
    result: str
    url: str
    datetime_raw: str

    def involves_team(self, needle: str) -> bool:
        needle = needle.casefold()
        return needle in self.home.casefold() or needle in self.away.casefold()

    def involves_any(self, teams: tuple[str, ...]) -> bool:
        return any(self.involves_team(team) for team in teams)


class CalendarParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.matches: list[dict[str, str]] = []
        self._in_heading = False
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._prefer_hidden_xs = False
        self._skip_visible_xs = False
        self._round = ""
        self._cell_index = -1
        self._cell_text: list[str] = []
        self._cell_href = ""
        self._row: dict[str, str] = {}
        self._capture_round = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = _class_set(attrs)
        if tag == "h4" and "panel-title" in classes:
            self._in_heading = True
            self._capture_round = True
            self._round = ""
        if tag == "table" and "league_calendar_table" in classes:
            self._in_table = True
        if not self._in_table:
            return
        if tag == "tr":
            self._in_row = True
            self._cell_index = -1
            self._row = {
                "round": self._round,
                "href": "",
                "game": "",
                "result": "",
                "datetime": "",
                "group": "",
            }
        if tag == "td" and self._in_row:
            self._in_cell = True
            self._cell_index += 1
            self._cell_text = []
            self._cell_href = ""
            self._prefer_hidden_xs = False
            self._skip_visible_xs = False
        if tag == "p" and self._in_cell and self._cell_index == 0:
            if "visible-xs" in classes:
                self._skip_visible_xs = True
            if "hidden-xs" in classes:
                self._prefer_hidden_xs = True
                self._skip_visible_xs = False
        if tag == "a" and self._in_cell and self._cell_index == 0 and not self._skip_visible_xs:
            href = dict(attrs).get("href") or ""
            if href:
                self._cell_href = href

    def handle_endtag(self, tag: str) -> None:
        if tag == "h4" and self._in_heading:
            self._in_heading = False
            self._capture_round = False
            self._round = _clean(self._round)
        if tag == "p" and self._in_cell:
            self._skip_visible_xs = False
        if tag == "td" and self._in_cell:
            text = _clean("".join(self._cell_text))
            if self._cell_index == 0:
                self._row["game"] = text
                self._row["href"] = self._cell_href
            elif self._cell_index == 1:
                self._row["result"] = text
            elif self._cell_index == 2:
                self._row["datetime"] = text
            elif self._cell_index == 4:
                self._row["group"] = text
            self._in_cell = False
        if tag == "tr" and self._in_row:
            self._in_row = False
            if self._row.get("game") and self._row.get("href"):
                self.matches.append(self._row)
        if tag == "table" and self._in_table:
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._capture_round:
            self._round += data
        elif self._in_cell and not self._skip_visible_xs:
            self._cell_text.append(data)


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_matches(html: str, timezone: str) -> list[Match]:
    parser = CalendarParser()
    parser.feed(html)
    tz = ZoneInfo(timezone)
    matches: list[Match] = []
    seen: set[str] = set()
    for raw in parser.matches:
        round_name = raw["round"]
        if "ROUND" not in round_name.upper():
            continue
        url = raw["href"]
        match_id = _match_id_from_url(url)
        if not match_id or match_id in seen:
            continue
        seen.add(match_id)
        home, away = _split_teams(raw["game"])
        date, time, datetime_iso, all_day = _parse_datetime(raw["datetime"], tz)
        matches.append(
            Match(
                match_id=match_id,
                round=round_name,
                group=raw["group"],
                date=date,
                time=time,
                datetime_iso=datetime_iso,
                all_day=all_day,
                home=home,
                away=away,
                result=raw["result"],
                url=url,
                datetime_raw=raw["datetime"],
            )
        )
    return matches


def write_csv(matches: list[Match], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for match in matches:
            row = asdict(match)
            row["all_day"] = "true" if match.all_day else "false"
            writer.writerow(row)


def read_csv(path: Path) -> list[Match]:
    matches: list[Match] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            matches.append(
                Match(
                    match_id=row["match_id"],
                    round=row["round"],
                    group=row["group"],
                    date=row["date"],
                    time=row["time"],
                    datetime_iso=row["datetime_iso"],
                    all_day=row["all_day"].lower() == "true",
                    home=row["home"],
                    away=row["away"],
                    result=row["result"],
                    url=row["url"],
                    datetime_raw=row["datetime_raw"],
                )
            )
    return matches


def _class_set(attrs: list[tuple[str, str | None]]) -> set[str]:
    value = dict(attrs).get("class") or ""
    return set(value.split())


def _clean(text: str) -> str:
    text = text.replace("\uf107", "").replace("\uf105", "")
    return re.sub(r"\s+", " ", text).strip()


def _split_teams(game: str) -> tuple[str, str]:
    parts = re.split(r"\s+:\s+", game, maxsplit=1)
    if len(parts) != 2:
        return game, ""
    return parts[0].strip(), parts[1].strip()


def _match_id_from_url(url: str) -> str:
    found = re.search(r"/match/(\d+)/", url)
    return found.group(1) if found else ""


def _parse_datetime(raw: str, tz: ZoneInfo) -> tuple[str, str, str, bool]:
    parsed = DATETIME_RE.search(raw)
    if parsed is None:
        return "", "", "", True
    year = int(parsed.group("year"))
    month = int(parsed.group("month"))
    day = int(parsed.group("day"))
    date = f"{year:04d}-{month:02d}-{day:02d}"
    if parsed.group("hour") is None:
        start = datetime(year, month, day, tzinfo=tz)
        return date, "", start.date().isoformat(), True
    hour = int(parsed.group("hour"))
    minute = int(parsed.group("minute"))
    start = datetime(year, month, day, hour, minute, tzinfo=tz)
    return date, f"{hour:02d}:{minute:02d}", start.isoformat(), False
