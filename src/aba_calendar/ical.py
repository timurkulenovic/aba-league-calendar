"""Generate subscribable iCalendar (.ics) feeds and a team-picker index page.

Produces one calendar per team plus an "all matches" calendar, all written to a
static output directory (intended for GitHub Pages). UIDs are stable so calendar
apps treat re-runs as updates rather than new events.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from aba_calendar.scrape import Match

PRODID = "-//aba-league-calendar//ABA Liga//EN"
UID_SUFFIX = "@aba-league-calendar"
ALL_CALENDAR_NAME = "ABA Liga (all matches)"


# --- team slug helpers -----------------------------------------------------


def slugify(name: str) -> str:
    """Lowercase, alphanumerics and dashes only, collapsed and trimmed."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "team"


def all_teams(matches: list[Match]) -> list[str]:
    """Distinct team names in first-seen order."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for m in matches:
        for team in (m.home, m.away):
            if team and team not in seen_set:
                seen_set.add(team)
                seen.append(team)
    return seen


# --- iCalendar escaping & folding ------------------------------------------


def escape_text(value: str) -> str:
    """Escape text values per RFC 5545."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def fold_line(line: str) -> str:
    """Fold long lines at 75 octets with CRLF + space continuation."""
    encoded = line.encode("utf-8")
    out: list[str] = []
    while len(encoded) > 75:
        out.append(encoded[:75].decode("utf-8", errors="ignore"))
        encoded = b" " + encoded[75:]
    out.append(encoded.decode("utf-8", errors="ignore"))
    return "\r\n".join(out)


def _dtstamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fmt_date(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def _fmt_local(d: datetime) -> str:
    return d.strftime("%Y%m%dT%H%M%S")


# --- event rendering --------------------------------------------------------


def event_lines(match: Match, tz: ZoneInfo, duration_minutes: int) -> list[str]:
    uid = f"aba-liga-match-{match.match_id}{UID_SUFFIX}"
    summary = escape_text(f"{match.home} vs {match.away}")
    description_parts = [match.round]
    if match.group:
        description_parts.append(f"Group {match.group}")
    if match.result:
        description_parts.append(f"Result: {match.result}")
    description_parts.append(match.url)
    description = escape_text(" · ".join(description_parts))

    if match.all_day or not match.datetime_iso:
        start = datetime.fromisoformat(match.date).replace(tzinfo=tz)
        end = start + timedelta(days=1)
        dtstart = f"DTSTART;VALUE=DATE:{_fmt_date(start)}"
        dtend = f"DTEND;VALUE=DATE:{_fmt_date(end)}"
    else:
        start = datetime.fromisoformat(match.datetime_iso).astimezone(tz)
        end = start + timedelta(minutes=duration_minutes)
        dtstart = f"DTSTART;TZID={tz.key}: {_fmt_local(start)}".replace(" ", "")
        dtend = f"DTEND;TZID={tz.key}: {_fmt_local(end)}".replace(" ", "")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_dtstamp()}",
        dtstart,
        dtend,
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        f"URL:{match.url}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]
    return lines


def render_calendar(
    matches: list[Match],
    tz: ZoneInfo,
    duration_minutes: int,
    calendar_name: str,
) -> str:
    body: list[str] = []
    for m in sorted(matches, key=lambda x: (x.date, x.time or "")):
        body.extend(event_lines(m, tz, duration_minutes))

    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{escape_text(calendar_name)}",
        "X-WR-TIMEZONE:" + tz.key,
    ]
    footer = ["END:VCALENDAR"]
    all_lines = header + body + footer
    folded = [fold_line(line) for line in all_lines]
    return "\r\n".join(folded) + "\r\n"


# --- index.html picker ------------------------------------------------------


_INDEX_CSS = """
:root {
  --bg: #0f172a; --card: #1e293b; --accent: #38bdf8; --accent2: #818cf8;
  --text: #e2e8f0; --muted: #94a3b8; --border: #334155;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: linear-gradient(180deg, #0b1120 0%, #0f172a 100%); color: var(--text);
  min-height: 100vh;
}
.wrap { max-width: 920px; margin: 0 auto; padding: 48px 24px 80px; }
h1 { font-size: 2.2rem; margin: 0 0 8px; letter-spacing: -0.02em; }
h1 .grad {
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.sub { color: var(--muted); font-size: 1.05rem; margin: 0 0 8px; }
.hint { color: var(--muted); font-size: 0.9rem; margin: 0 0 28px; }
.toolbar {
  display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  margin-bottom: 24px; padding: 14px 16px; background: var(--card);
  border: 1px solid var(--border); border-radius: 12px;
}
.toolbar .count { color: var(--muted); font-size: 0.9rem; margin-right: auto; }
button, .btn {
  border: 0; cursor: pointer; font-size: 0.9rem; font-weight: 600;
  padding: 9px 14px; border-radius: 8px; transition: transform .08s, background .15s;
}
button:active { transform: scale(0.97); }
.btn-sub { background: var(--accent); color: #00121f; }
.btn-sub:hover { background: #7dd3fc; }
.btn-sec { background: #334155; color: var(--text); }
.btn-sec:hover { background: #475569; }
a.btn { text-decoration: none; text-align: center; display: inline-flex; align-items: center; justify-content: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 14px;
  padding: 16px 18px; display: flex; flex-direction: column; gap: 10px;
}
.card label { display: flex; align-items: center; gap: 10px; font-weight: 600; cursor: pointer; }
.card input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--accent); }
.card .name { font-size: 1.05rem; }
.card .meta { color: var(--muted); font-size: 0.82rem; }
.card .row { display: flex; gap: 8px; flex-wrap: wrap; }
.card .row > * { flex: 1; min-width: 0; padding: 8px 10px; font-size: 0.82rem; }
.all-card { border-color: var(--accent); }
footer { margin-top: 40px; color: var(--muted); font-size: 0.82rem; text-align: center; }
a { color: var(--accent); }
code { background: #0b1120; padding: 1px 5px; border-radius: 4px; font-size: 0.85em; color: var(--accent); }
"""


def _team_card(team: str, ics_url: str, webcal_url: str, gcal_url: str, n: int) -> str:
    name = html.escape(team)
    return f"""      <div class="card" data-team="{html.escape(slugify(team))}" data-webcal="{webcal_url}" data-gcal="{gcal_url}">
        <label><input type="checkbox" data-team="{name}"> <span class="name">{name}</span></label>
        <div class="meta">{n} matches</div>
        <div class="row">
          <a class="btn btn-sub" href="{gcal_url}" target="_blank" rel="noopener">Google</a>
          <a class="btn btn-sub" href="{webcal_url}">Apple</a>
          <button class="btn-sec" onclick="copy('{ics_url}', this)">Copy</button>
        </div>
      </div>"""


def render_index(
    teams: list[tuple[str, int]],
    all_count: int,
    base_url: str,
    ics_dir: str,
) -> str:
    """Render the team-picker index page."""
    norm_base = base_url.rstrip("/")
    rel = ics_dir.strip("/")

    def ics_path(slug: str) -> str:
        return f"{norm_base}/{rel}/{slug}.ics"

    def webcal(slug: str) -> str:
        return ics_path(slug).replace("https://", "webcal://").replace("http://", "webcal://")

    def gcal(slug: str) -> str:
        # Google Calendar's cid= endpoint rejects https:// URLs but accepts
        # webcal:// (URL-encoded) — it signals "subscribe to external feed".
        return f"https://calendar.google.com/calendar/render?cid={quote(webcal(slug), safe='')}"

    all_ics = ics_path("all")
    all_webcal = webcal("all")
    all_gcal = gcal("all")

    cards = [
        f"""      <div class="card all-card" data-team="__all__" data-webcal="{all_webcal}" data-gcal="{all_gcal}">
        <label><input type="checkbox" data-team="__all__"> <span class="name">All matches</span></label>
        <div class="meta">{all_count} matches · every team</div>
        <div class="row">
          <a class="btn btn-sub" href="{all_gcal}" target="_blank" rel="noopener">Google</a>
          <a class="btn btn-sub" href="{all_webcal}">Apple</a>
          <button class="btn-sec" onclick="copy('{all_ics}', this)">Copy</button>
        </div>
      </div>"""
    ]
    for team, n in teams:
        slug = slugify(team)
        cards.append(_team_card(team, ics_path(slug), webcal(slug), gcal(slug), n))

    cards_html = "\n".join(cards)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ABA Liga — subscribable calendars</title>
<style>{_INDEX_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1><span class="grad">ABA Liga</span> calendars</h1>
  <p class="sub">Subscribable iCalendar feeds for the 2026/27 ABA Liga season.</p>
  <p class="hint">Pick the teams you care about and subscribe to each feed once — your calendar app pulls updates automatically. Use <b>Google</b> or <b>Apple</b> to subscribe directly, or <b>Copy</b> the URL and add it via “subscribe from URL” in any other calendar app.</p>
  <p class="hint"><b>Google not working?</b> Google’s one-click is flaky. If it says “unable to open calendar”, open Google Calendar → Settings → Add calendar → From URL → paste the copied <code>https://…/*.ics</code> link. That always works.</p>

  <div class="toolbar">
    <span class="count" id="count">0 selected</span>
    <button class="btn-sub" onclick="subscribeSelected('gcal')">Subscribe selected · Google</button>
    <button class="btn-sub" onclick="subscribeSelected('webcal')">Subscribe selected · Apple</button>
    <button class="btn-sec" onclick="toggleAll(this)">Select all teams</button>
  </div>

  <div class="grid">
{cards_html}
  </div>

  <footer>
    Feeds are regenerated daily by a GitHub Action scraping
    <a href="https://www.aba-liga.com/calendar/26/1/" target="_blank" rel="noopener">aba-liga.com</a>.
    Source: <a href="https://github.com/timurkulenovic/aba-league-calendar" target="_blank" rel="noopener">timurkulenovic/aba-league-calendar</a>.
  </footer>
</div>
<script>
  const boxes = () => document.querySelectorAll('input[type=checkbox][data-team]');
  function updateCount() {{
    const n = [...boxes()].filter(b => b.checked).length;
    document.getElementById('count').textContent = n + ' selected';
  }}
  document.addEventListener('change', e => {{ if (e.target.matches('[data-team]')) updateCount(); }});
  function toggleAll(btn) {{
    const all = [...boxes()]; const anyUnchecked = all.some(b => !b.checked);
    all.forEach(b => b.checked = anyUnchecked);
    btn.textContent = anyUnchecked ? 'Clear selection' : 'Select all teams';
    updateCount();
  }}
  function subscribeSelected(kind) {{
    const sel = [...boxes()].filter(b => b.checked).map(b => b.closest('.card'));
    if (!sel.length) {{ alert('Pick at least one team first.'); return; }}
    if (sel.length > 5 && !confirm('This will open ' + sel.length + ' calendar subscriptions. Continue?')) return;
    const attr = kind === 'gcal' ? 'data-gcal' : 'data-webcal';
    sel.forEach(card => {{
      const url = card.getAttribute(attr);
      window.open(url, '_blank');
    }});
  }}
  function copy(url, btn) {{
    navigator.clipboard.writeText(url).then(() => {{
      const t = btn.textContent; btn.textContent = 'Copied!';
      setTimeout(() => btn.textContent = t, 1200);
    }}).catch(() => alert(url));
  }}
</script>
</body>
</html>
"""


# --- top-level: write everything --------------------------------------------


def write_ics_feeds(
    matches: list[Match],
    output_dir: Path,
    base_url: str,
    ics_subdir: str,
    tz_name: str,
    duration_minutes: int,
) -> dict[str, int]:
    """Write per-team + all .ics files and the index.html picker page."""
    tz = ZoneInfo(tz_name)
    ics_dir = output_dir / ics_subdir.strip("/")
    ics_dir.mkdir(parents=True, exist_ok=True)

    # all.ics
    all_path = ics_dir / "all.ics"
    all_path.write_text(
        render_calendar(matches, tz, duration_minutes, ALL_CALENDAR_NAME),
        encoding="utf-8",
    )

    # per-team
    team_counts: list[tuple[str, int]] = []
    for team in all_teams(matches):
        team_matches = [m for m in matches if m.involves_team(team)]
        team_counts.append((team, len(team_matches)))
        slug = slugify(team)
        cal_name = f"ABA Liga — {team}"
        (ics_dir / f"{slug}.ics").write_text(
            render_calendar(team_matches, tz, duration_minutes, cal_name),
            encoding="utf-8",
        )

    # index.html
    index_path = output_dir / "index.html"
    index_path.write_text(
        render_index(team_counts, len(matches), base_url, ics_subdir),
        encoding="utf-8",
    )

    return {"teams": len(team_counts), "matches": len(matches)}
