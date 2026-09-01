# ABA Liga calendar

Scrapes match dates from the [ABA Liga calendar](https://www.aba-liga.com/calendar/26/1/), saves every game to CSV, and adds selected teams to the macOS **Personal** calendar on `timur@kulenovic.si`.

Default team filter: **Cedevita Olimpija** and **Ilirija** (matches `Perspektiva Ilirija`).

## Setup

Python 3.11+ is required (stdlib only).

## Usage

Refresh everything (scrape + sync filtered teams) — the one command you'll use:

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

Add filtered team games to Personal Calendar (Kulenovic.si) only:

```bash
python3 aba.py sync
```

Fetch and sync in one step:

```bash
python3 aba.py all
```

Change teams without editing config:

```bash
python3 aba.py sync --teams "Cedevita Olimpija,Ilirija,Krka"
```

Team names are substring filters (case-insensitive) against home and away.

## Config

Edit `config.toml` to change the source URL, CSV path, calendar identity, or default teams.

Events are tagged with `UID: aba-liga-match-<id>`. Synced IDs are stored in `data/synced_uids.txt` so re-running `sync` does not create duplicates. Delete that file if you want a full re-import. Games with a published tip-off time are 2-hour timed events in `Europe/Ljubljana`; games without a time are all-day events.
