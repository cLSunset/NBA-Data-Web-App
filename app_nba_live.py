"""
NBA Stats Explorer — Live Data Edition
----------------------------------------
A Streamlit app backed by REAL NBA data, pulled live from stats.nba.com via
the open-source `nba_api` package (no API key or signup required).

Run with:
    pip install -r requirements.txt
    streamlit run app_nba_live.py

Note: stats.nba.com occasionally blocks requests from cloud/datacenter IPs.
If data fails to load, try again in a moment, or run this from a normal
home/office internet connection rather than a cloud server.
"""

import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from nba_api.stats.endpoints import (
    leaguedashplayerstats,
    leaguedashteamstats,
    leaguestandingsv3,
)
from nba_api.stats.static import teams as static_teams

st.set_page_config(
    page_title="NBA Stats Explorer",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

REQUEST_TIMEOUT = 30  # seconds, per call to stats.nba.com

# Most recent season first
SEASONS = [f"{y}-{str(y + 1)[-2:]}" for y in range(2005, 2026)][::-1]

# ----------------------------------------------------------------------------
# Data fetchers (cached — each hits stats.nba.com once per hour per args)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_teams_df() -> pd.DataFrame:
    """Static team directory — no network call."""
    return pd.DataFrame(static_teams.get_teams())


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_standings(season: str) -> pd.DataFrame | None:
    try:
        df = leaguestandingsv3.LeagueStandingsV3(
            season=season, timeout=REQUEST_TIMEOUT
        ).get_data_frames()[0]
        for col in ["WINS", "LOSSES", "WinPCT", "PointsPG", "OppPointsPG", "DiffPointsPG"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_team_stats(season: str, per_mode: str) -> pd.DataFrame | None:
    try:
        df = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            per_mode_detailed=per_mode,
            timeout=REQUEST_TIMEOUT,
        ).get_data_frames()[0]
        return df
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_player_stats(season: str, per_mode: str) -> pd.DataFrame | None:
    try:
        df = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            per_mode_detailed=per_mode,
            timeout=REQUEST_TIMEOUT,
        ).get_data_frames()[0]
        return df
    except Exception:
        return None


def fetch_trend(team_id: int, seasons: list[str], per_mode: str) -> pd.DataFrame:
    """Build a multi-season trend for one team by reusing the cached
    per-season league-wide team stats (so repeated teams cost nothing extra)."""
    rows = []
    for season in seasons:
        df = fetch_team_stats(season, per_mode)
        if df is None:
            continue
        row = df[df["TEAM_ID"] == team_id]
        if not row.empty:
            r = row.iloc[0]
            rows.append(
                {
                    "Season": season,
                    "W": r.get("W"),
                    "L": r.get("L"),
                    "W_PCT": r.get("W_PCT"),
                    "PTS": r.get("PTS"),
                    "REB": r.get("REB"),
                    "AST": r.get("AST"),
                }
            )
        time.sleep(0.3)  # be polite to stats.nba.com between calls
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("🏀 NBA Stats Explorer")
st.sidebar.caption("Live data from stats.nba.com via `nba_api` — no API key needed.")

season = st.sidebar.selectbox("Season", SEASONS, index=0)
per_mode = st.sidebar.radio("Stat mode", ["PerGame", "Totals"], horizontal=True)

if st.sidebar.button("🔄 Refresh data (clear cache)"):
    st.cache_data.clear()
    st.rerun()

teams_df = get_teams_df()
team_names = sorted(teams_df["full_name"].tolist())

st.sidebar.markdown("---")
st.sidebar.caption(
    "If data doesn't load, stats.nba.com may be rate-limiting or blocking "
    "your network. Wait a moment and hit Refresh, or try from a different "
    "connection."
)

st.title("NBA Stats Explorer")
st.caption(f"Season {season} · {per_mode}")

# ----------------------------------------------------------------------------
# Fetch core data once
# ----------------------------------------------------------------------------
with st.spinner("Loading live NBA data..."):
    standings = fetch_standings(season)
    team_stats = fetch_team_stats(season, per_mode)
    player_stats = fetch_player_stats(season, per_mode)

if standings is None and team_stats is None and player_stats is None:
    st.error(
        "Couldn't reach stats.nba.com right now. This endpoint sometimes "
        "blocks cloud or shared IP addresses. Try the Refresh button in the "
        "sidebar in a minute, or run this app from a regular home/office "
        "network connection."
    )
    st.stop()

# ----------------------------------------------------------------------------
# Header metrics
# ----------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
if standings is not None and not standings.empty:
    top = standings.sort_values("WinPCT", ascending=False).iloc[0]
    best_off = standings.sort_values("PointsPG", ascending=False).iloc[0]
    best_def = standings.sort_values("OppPointsPG", ascending=True).iloc[0]
    col1.metric("Best record", f"{top['TeamCity']} {top['TeamName']}", f"{top['WINS']:.0f}-{top['LOSSES']:.0f}")
    col2.metric("Best offense", f"{best_off['TeamCity']} {best_off['TeamName']}", f"{best_off['PointsPG']:.1f} PPG")
    col3.metric("Best defense", f"{best_def['TeamCity']} {best_def['TeamName']}", f"{best_def['OppPointsPG']:.1f} PPG allowed")
    col4.metric("Teams", f"{standings['TeamID'].nunique()}")
else:
    st.warning("Standings unavailable for this season/right now.")

st.markdown("---")

tab_standings, tab_teams, tab_players, tab_compare = st.tabs(
    ["📊 Standings", "📈 Team Stats & Trends", "🧑‍🤝‍🧑 Player Leaderboard", "⚔️ Head-to-Head"]
)

# --- Standings ---------------------------------------------------------------
with tab_standings:
    if standings is None or standings.empty:
        st.warning("Standings data isn't available right now.")
    else:
        conf = st.radio("Conference", ["Both", "East", "West"], horizontal=True, key="conf_filter")
        view = standings.copy()
        if conf != "Both":
            view = view[view["Conference"] == conf]
        view = view.sort_values(["Conference", "PlayoffRank"])
        view["Team"] = view["TeamCity"] + " " + view["TeamName"]
        display_cols = ["Team", "Conference", "WINS", "LOSSES", "WinPCT", "Record", "L10", "CurrentStreak", "strCurrentStreak"]
        display_cols = [c for c in display_cols if c in view.columns]
        st.dataframe(view[display_cols].reset_index(drop=True), use_container_width=True)

        fig = px.bar(
            view.sort_values("WinPCT", ascending=False),
            x="Team",
            y="WinPCT",
            color="Conference",
            title=f"Win% by team — {season}",
        )
        fig.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)

# --- Team stats & trends -------------------------------------------------------
with tab_teams:
    if team_stats is None or team_stats.empty:
        st.warning("Team stats unavailable right now.")
    else:
        stat_options = [c for c in ["PTS", "REB", "AST", "STL", "BLK", "FG_PCT", "FG3_PCT", "TOV"] if c in team_stats.columns]
        stat_choice = st.selectbox("Rank teams by", stat_options, index=0)
        ranked = team_stats.sort_values(stat_choice, ascending=False)
        fig = px.bar(ranked, x="TEAM_NAME", y=stat_choice, title=f"{stat_choice} by team — {season} ({per_mode})")
        fig.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            ranked[["TEAM_NAME", "W", "L", "W_PCT"] + stat_options].reset_index(drop=True),
            use_container_width=True,
        )

        st.markdown("##### Multi-season trend for one team")
        trend_team = st.selectbox("Team", team_names, key="trend_team")
        n_seasons = st.slider("How many past seasons", 2, 10, 5)
        trend_seasons = SEASONS[SEASONS.index(season): SEASONS.index(season) + n_seasons]
        team_id = int(teams_df.loc[teams_df["full_name"] == trend_team, "id"].iloc[0])

        if st.button("Load trend (multiple requests — may take a few seconds)"):
            with st.spinner("Fetching season-by-season data..."):
                trend_df = fetch_trend(team_id, trend_seasons, per_mode)
            if trend_df.empty:
                st.warning("Couldn't fetch trend data right now.")
            else:
                trend_df = trend_df.sort_values("Season")
                fig2 = px.line(trend_df, x="Season", y="W_PCT", markers=True, title=f"{trend_team} — Win% by season")
                st.plotly_chart(fig2, use_container_width=True)
                st.dataframe(trend_df.reset_index(drop=True), use_container_width=True)

# --- Player leaderboard ---------------------------------------------------------
with tab_players:
    if player_stats is None or player_stats.empty:
        st.warning("Player stats unavailable right now.")
    else:
        stat_options = [c for c in ["PTS", "REB", "AST", "STL", "BLK", "FG3M", "TOV"] if c in player_stats.columns]
        stat_choice = st.selectbox("Rank players by", stat_options, index=0, key="player_stat")
        min_gp = st.slider("Minimum games played", 0, 82, 20)
        top_n = st.slider("Show top N", 5, 50, 15, key="player_top_n")

        filtered = player_stats[player_stats["GP"] >= min_gp]
        leaderboard = filtered.sort_values(stat_choice, ascending=False).head(top_n)

        fig = px.bar(
            leaderboard, x="PLAYER_NAME", y=stat_choice, color="TEAM_ABBREVIATION",
            title=f"Top {top_n} players by {stat_choice} — {season} ({per_mode}, min {min_gp} GP)",
        )
        fig.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            leaderboard[["PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN"] + stat_options].reset_index(drop=True),
            use_container_width=True,
        )

# --- Head-to-head -----------------------------------------------------------
with tab_compare:
    if team_stats is None or team_stats.empty:
        st.warning("Team stats unavailable right now.")
    else:
        c1, c2 = st.columns(2)
        team_a = c1.selectbox("Team A", team_names, index=0)
        team_b = c2.selectbox("Team B", team_names, index=1 if len(team_names) > 1 else 0)

        sub = team_stats[team_stats["TEAM_NAME"].isin(
            [team_a.split(" ")[-1], team_b.split(" ")[-1]]
        )]
        # TEAM_NAME in this endpoint is usually just the nickname (e.g. "Lakers")
        sub = team_stats[team_stats["TEAM_NAME"].apply(lambda n: n in team_a or n in team_b)]

        if sub.empty:
            st.warning("Couldn't match those teams in this season's data.")
        else:
            categories = [c for c in ["PTS", "REB", "AST", "STL", "BLK"] if c in sub.columns]
            fig = go.Figure()
            for _, row in sub.iterrows():
                fig.add_trace(
                    go.Scatterpolar(
                        r=[row[c] for c in categories],
                        theta=categories,
                        fill="toself",
                        name=row["TEAM_NAME"],
                    )
                )
            fig.update_layout(polar=dict(radialaxis=dict(visible=True)), title=f"{team_a} vs {team_b} — {season}")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                sub[["TEAM_NAME", "W", "L", "W_PCT"] + categories].reset_index(drop=True),
                use_container_width=True,
            )

st.markdown("---")
st.caption("Data: stats.nba.com via the open-source `nba_api` package. No API key required.")
