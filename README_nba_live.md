# NBA Stats Explorer — Live Data Edition

A Streamlit app backed by **real NBA data**, pulled live from stats.nba.com
using the open-source [`nba_api`](https://github.com/swar/nba_api) package.
No API key, no signup, no account required.

## Why `nba_api` instead of a "sports API"

I checked the usual free options as of September 2026:

- **balldontlie.io** now requires a free account/API key for every request
  (its old fully-keyless endpoints were retired). Its free tier also
  doesn't include standings or season averages.
- **TheSportsDB**'s free test key ("123") is a demo key — it returns
  canned sample data (English Premier League / Arsenal) regardless of what
  you actually query, so it's not usable for real NBA data.
- **`nba_api`** wraps the same JSON endpoints NBA.com's own site uses
  internally. It's open source, actively maintained, needs no key, and
  covers standings, team stats, and player stats in depth — so it's the
  best fit for "real data, no key."

## Setup

```bash
pip install -r requirements_nba_live.txt
streamlit run app_nba_live.py
```

## Features

- **Standings** — live conference standings, win%, streaks
- **Team Stats & Trends** — sortable team stat rankings, plus a
  multi-season win% trend for any team
- **Player Leaderboard** — rank players by points/rebounds/assists/etc,
  filterable by minimum games played
- **Head-to-Head** — radar chart comparing two teams' season stats

Use the sidebar to pick a season (defaults to the most recent) and switch
between Per-Game and Totals stat modes.

## Important: a known `nba_api` quirk

`stats.nba.com` sometimes blocks or times out requests from **cloud or
shared datacenter IP addresses** (this affects things like Streamlit
Community Cloud, some VPS providers, etc. — not because of anything wrong
with your code). It generally works fine from a normal home or office
internet connection.

If the app shows a "couldn't reach stats.nba.com" error:

1. Wait a few seconds and click **🔄 Refresh data** in the sidebar.
2. If it persists, try running the app from a different network.
3. As a fallback, the earlier `balldontlie.io` API works reliably from
   cloud hosts too — it just now requires a free API key from
   [app.balldontlie.io](https://app.balldontlie.io) (free tier covers
   Teams/Players/Games; standings and season averages need a paid tier).

## Notes on the data

- Data is cached for 1 hour (`st.cache_data(ttl=3600)`) so repeated
  interactions with the same season don't re-hit the API every time.
- The "Load trend" button in the Team Stats tab makes one request per
  season shown — it's deliberately behind a button (not automatic) to
  avoid hammering the API, and includes a short delay between requests.
- Only NBA teams/seasons are covered. `nba_api` also exposes WNBA and
  G-League data if you want to extend this (see its docs).
