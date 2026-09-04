# ABA Liga calendar

Scrapes match dates from the [ABA Liga calendar](https://www.aba-liga.com/calendar/26/1/), saves every game to CSV, and publishes **subscribable iCalendar feeds** for each team via GitHub Pages.

A GitHub Action scrapes the source daily and regenerates the feeds, so subscribers always see the latest schedule without doing anything.

## Subscribable calendars

Each team has its own `.ics` feed. Subscribe to the ones you care about — your calendar app pulls updates automatically (typically every few hours to a day).

- **Picker page:** <https://timurkulenovic.github.io/aba-league-calendar/>
- **All matches:** `webcal://timurkulenovic.github.io/aba-league-calendar/ics/all.ics`
- **Per team:** `webcal://timurkulenovic.github.io/aba-league-calendar/ics/<team-slug>.ics`
  - e.g. `cedevita-olimpija.ics`, `perspektiva-ilirija.ics`, `partizan-mozzart-bet.ics`

| App | How to subscribe |
|---|---|
| Apple Calendar | Click the **Apple** button on the picker page, or paste the `webcal://…` URL into File → New Calendar Subscription |
| Google Calendar | Click **Google** on the picker page, or Other calendars → + → From URL → paste the `https://…/team.ics` URL |
| Outlook | Add calendar → Subscribe from web → paste the URL |

Open the picker page, tick the teams you want, and hit **Subscribe selected (Apple)** to add each feed in one go.

## Setup

Python 3.11+ (stdlib only — no dependencies).

## Usage

Refresh everything (scrape + generate feeds) — the one command you'll use:

```bash
./refresh.sh
```

Or equivalently:

```bash
python3 aba.py
```

Fetch all dates into `data/aba_liga_calendar.csv` only:

```bash
python3 aba.py fetch
```

Generate subscribable `.ics` feeds + `index.html` into `docs/`:

```bash
python3 aba.py ics
```

Sync filtered team games to the local macOS Personal calendar (Kulenovic.si) only:

```bash
python3 aba.py sync
```

Change the local-sync team filter without editing config:

```bash
python3 aba.py sync --teams "Cedevita Olimpija,Ilirija,Krka"
```

Team names are substring filters (case-insensitive) against home and away.

## Config

Edit `config.toml` to change the source URL, CSV path, calendar identity, default teams, or the Pages base URL used to build subscribe links.

## How it works

- `fetch` downloads and parses the ABA Liga calendar HTML (stdlib `html.parser`) into `data/aba_liga_calendar.csv` (180 matches, rounds 1–18).
- `ics` renders one `.ics` per team plus `all.ics` into `docs/ics/`, and a team-picker `index.html` into `docs/`. UIDs are stable (`aba-liga-match-<id>@aba-league-calendar`) so re-runs update events in place instead of duplicating them. Timed games use `TZID=Europe/Ljubljana`; games without a published tip-off are all-day.
- `sync` (optional, macOS only) writes filtered games to the local Calendar app via AppleScript. Synced IDs are tracked in `data/synced_uids.txt` to avoid duplicates; delete that file for a full re-import.
- `.github/workflows/scrape.yml` runs `fetch` + `ics` daily and commits any changes back to `main`, which triggers a GitHub Pages rebuild.

## Enable GitHub Pages (one-time)

Repo Settings → Pages → Source: **Deploy from a branch** → Branch: `main` / `/docs` → Save. The picker page and feeds go live at the `pages_base_url` in `config.toml`.
