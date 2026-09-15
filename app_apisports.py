"""
NBA Stats Explorer — API-Sports Edition
------------------------------------------
Same app, different data source: pulls from api-sports.io's NBA API
instead of stats.nba.com, because stats.nba.com blocks cloud-hosted IPs
(including Streamlit Community Cloud) and there's no clean fix for that.

api-sports.io's free tier gives 100 requests/day. This app is deliberately
conservative with calls:
  - Standings loads by default (1 call, cached for hours, shared by everyone
    who visits while the cache is warm).
  - Team profile / head-to-head data only loads when you pick a team and
    click a button, and is cached per team+season afterwards.
  - There's no full-league player leaderboard here — api-sports.io's free
    tier has no "season averages" endpoint, and getting every player's
    stats would mean ~30 calls (one per team), which would blow the daily
    quota almost immediately. Instead there's a per-team roster view.

Setup:
    1. Get a free key at https://api-sports.io/sports/nba
    2. Put it in Streamlit secrets as:  api_sports_key = "your-key"
       (Settings -> Secrets, on share.streamlit.io — NOT GitHub secrets)
    3. pip install -r requirements_apisports.txt
    4. streamlit run app_apisports.py

Note: I built this against api-sports.io's published documentation, not
live testing (no outbound network access in the environment I built this
in). If a field is named slightly differently than expected, most tables
below fall back to showing the raw data so the app won't hard-crash — but
if you hit an error, paste it back and I'll patch the exact field name.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="NBA Stats Explorer",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_URL = "https://v2.nba.api-sports.io"
REQUEST_TIMEOUT = 15
SEASONS = list(range(2018, 2026))[::-1]  # most recent first


def get_api_key() -> str | None:
    try:
        return st.secrets["api_sports_key"]
    except Exception:
        return st.sidebar.text_input(
            "API-Sports key (no secret found — paste for local testing)",
            type="password",
        ) or None


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def api_get(endpoint: str, params: dict, api_key: str) -> pd.DataFrame | None:
    """Generic cached GET against api-sports.io. Returns a flattened
    DataFrame of the 'response' list, or None on any failure."""
    try:
        r = requests.get(
            f"{BASE_URL}/{endpoint}",
            headers={"x-apisports-key": api_key},
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        response = data.get("response", [])
        if not response:
            return pd.DataFrame()
        return pd.json_normalize(response)
    except Exception as e:
        st.session_state["last_api_error"] = str(e)
        return None


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("🏀 NBA Stats Explorer")
st.sidebar.caption("Data via api-sports.io — 100 free requests/day, cached heavily.")

api_key = get_api_key()
season = st.sidebar.selectbox("Season (start year)", SEASONS, index=0)

if not api_key:
    st.warning("Add your API-Sports key in Streamlit secrets (see the top of this file for instructions) to load data.")
    st.stop()

view = st.sidebar.radio(
    "View",
    ["📊 Standings", "🏀 Team Profile", "⚔️ Head-to-Head"],
)

if st.sidebar.button("🔄 Clear cache"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
if "last_api_error" in st.session_state:
    st.sidebar.caption(f"Last API error: {st.session_state['last_api_error']}")

st.title("NBA Stats Explorer")
st.caption(f"Season {season}-{str(season + 1)[-2:]}")
st.markdown("---")

teams_df = api_get("teams", {"league": "standard"}, api_key)
if teams_df is None or teams_df.empty:
    st.error("Couldn't load the team list. Check your API key and quota, then hit 'Clear cache' and reload.")
    st.stop()

name_col = "name" if "name" in teams_df.columns else teams_df.columns[1]
id_col = "id" if "id" in teams_df.columns else teams_df.columns[0]
team_names = sorted(teams_df[name_col].dropna().tolist())

# ----------------------------------------------------------------------------
# Standings
# ----------------------------------------------------------------------------
if view == "📊 Standings":
    with st.spinner("Loading standings..."):
        standings = api_get("standings", {"league": "standard", "season": season}, api_key)

    if standings is None or standings.empty:
        st.error("Standings unavailable — check the sidebar for the last API error, or your daily quota may be used up.")
    else:
        st.dataframe(standings, use_container_width=True)

        # Try to build a clean chart if the expected columns are present
        win_col = next((c for c in standings.columns if c.endswith("win.percentage")), None)
        team_name_col = next((c for c in standings.columns if c == "team.name"), None)
        if win_col and team_name_col:
            standings[win_col] = pd.to_numeric(standings[win_col], errors="coerce")
            fig = px.bar(
                standings.sort_values(win_col, ascending=False),
                x=team_name_col, y=win_col,
                title=f"Win% by team — {season}-{str(season + 1)[-2:]}",
            )
            fig.update_layout(xaxis_tickangle=-40)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Showing raw standings data — column names differ from what I expected, but everything is here.")

# ----------------------------------------------------------------------------
# Team profile
# ----------------------------------------------------------------------------
elif view == "🏀 Team Profile":
    team_name = st.selectbox("Team", team_names)
    team_id = int(teams_df.loc[teams_df[name_col] == team_name, id_col].iloc[0])

    if st.button("Load team data"):
        with st.spinner("Loading team stats and roster..."):
            team_stats = api_get("teams/statistics", {"id": team_id, "season": season}, api_key)
            roster = api_get("players", {"team": team_id, "season": season}, api_key)
            games = api_get("games", {"team": team_id, "season": season}, api_key)

        st.subheader(f"{team_name} — season stats")
        if team_stats is None or team_stats.empty:
            st.warning("Team stats unavailable right now.")
        else:
            st.dataframe(team_stats, use_container_width=True)

        st.subheader("Roster")
        if roster is None or roster.empty:
            st.warning("Roster unavailable right now.")
        else:
            name_cols = [c for c in roster.columns if "name" in c.lower() or "position" in c.lower() or "height" in c.lower()]
            st.dataframe(roster[name_cols] if name_cols else roster, use_container_width=True)

        st.subheader("Recent games")
        if games is None or games.empty:
            st.warning("Game results unavailable right now.")
        else:
            score_cols = [c for c in games.columns if "score" in c.lower() or "team" in c.lower() or "date" in c.lower()]
            st.dataframe(games[score_cols] if score_cols else games, use_container_width=True)
    else:
        st.info("Pick a team and click **Load team data** — this makes a few live API calls, so it's behind a button rather than automatic.")

# ----------------------------------------------------------------------------
# Head-to-head
# ----------------------------------------------------------------------------
else:
    c1, c2 = st.columns(2)
    team_a = c1.selectbox("Team A", team_names, index=0)
    team_b = c2.selectbox("Team B", team_names, index=1 if len(team_names) > 1 else 0)

    if st.button("Compare"):
        id_a = int(teams_df.loc[teams_df[name_col] == team_a, id_col].iloc[0])
        id_b = int(teams_df.loc[teams_df[name_col] == team_b, id_col].iloc[0])

        with st.spinner("Loading both teams' stats..."):
            stats_a = api_get("teams/statistics", {"id": id_a, "season": season}, api_key)
            stats_b = api_get("teams/statistics", {"id": id_b, "season": season}, api_key)

        if stats_a is None or stats_b is None or stats_a.empty or stats_b.empty:
            st.warning("Couldn't load stats for one or both teams right now.")
        else:
            combined = pd.concat([stats_a.assign(Team=team_a), stats_b.assign(Team=team_b)], ignore_index=True)
            st.dataframe(combined, use_container_width=True)

            numeric_cols = [c for c in ["points", "assists", "totReb", "steals", "blocks"] if c in combined.columns]
            if numeric_cols:
                fig = go.Figure()
                for _, row in combined.iterrows():
                    fig.add_trace(go.Scatterpolar(
                        r=[row[c] for c in numeric_cols], theta=numeric_cols,
                        fill="toself", name=row["Team"],
                    ))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True)), title=f"{team_a} vs {team_b}")
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Pick two teams and click **Compare**.")

st.markdown("---")
st.caption("Data: api-sports.io NBA API. Free tier: 100 requests/day, cached for 6 hours to stretch the quota.")
