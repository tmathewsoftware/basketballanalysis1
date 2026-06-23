import streamlit as st
from basketball_ranker import fetch_upcoming_games, build_ranked_list
from datetime import datetime, timedelta
from teamselector import resolve_team, confirm_team_selection
import zoneinfo
import os

st.set_page_config(page_title="Basketball Ranker", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
            background-color: #0d0d0d;
            color: #f0f0f0;
        }

        .title {
            font-family: 'Bebas Neue', sans-serif;
            font-size: 3.5rem;
            letter-spacing: 0.08em;
            color: #f0f0f0;
            line-height: 1;
        }

        .subtitle {
            font-size: 0.9rem;
            color: #888;
            margin-top: -0.5rem;
            margin-bottom: 2rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .stButton > button {
            width: 100%;
            background-color: #1a1a1a;
            color: #f0f0f0;
            border: 1px solid #2e2e2e;
            border-radius: 6px;
            padding: 0.75rem 1.2rem;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.95rem;
            text-align: left;
            transition: all 0.15s ease;
        }

        .stButton > button:hover {
            background-color: #222;
            border-color: #e8ff00;
            color: #e8ff00;
        }

        .divider {
            border-top: 1px solid #1e1e1e;
            margin: 1.5rem 0;
        }
    </style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="title">🏀 Basketball Ranker</div>', unsafe_allow_html=True)

melbourne_tz = zoneinfo.ZoneInfo("Australia/Melbourne")
st.markdown(f'<div class="subtitle">All available ranked games — today, tomorrow & beyond</div>', unsafe_allow_html=True)


# ── Excel generation helper ───────────────────────────────────────────────────
def generate_excel_bytes(build_fn, *args):
    tmp_path = "_tmp_report.xlsx"
    build_fn(*args, output_path=tmp_path)
    if not os.path.exists(tmp_path):
        raise Exception("Report could not be generated.")
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.remove(tmp_path)
    return data


# ── Load games ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_games():
    events = fetch_upcoming_games()
    return build_ranked_list(events)


with st.spinner("Fetching games and odds..."):
    ranked_games = load_games()

# ── Game buttons ──────────────────────────────────────────────────────────────
if not ranked_games:
    st.warning("No games found with spread and totals data.")
else:
    date_str = datetime.now(melbourne_tz).strftime("%d %b %Y")

    col_left, col_mid, col_right = st.columns([3, 1, 1])
    with col_left:
        st.markdown(f"**{len(ranked_games)} games ranked** — click a game to generate Excel reports.")
    with col_mid:
        precheck = st.button("🔍 Check All Teams", key="precheck_all")
    with col_right:
        bulkreport = st.button("📦 Analyse All Games", key="analyse_all")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── Precheck all teams ───────────────────────────────────────────────────────
    if precheck:
        st.session_state["precheck_active"] = True

    if st.session_state.get("precheck_active"):
        st.markdown("### 🔍 Team Check")

        unresolved = []
        resolved_count = 0

        for game in ranked_games:
            for side, team_name in [("home", game["home"]), ("away", game["away"])]:
                cache_key = f"precheck_{side}_{game['event_id']}"
                if cache_key not in st.session_state:
                    team_id, result, status = resolve_team(team_name, game["league"])
                    if status == "auto":
                        st.session_state[cache_key] = {"id": team_id, "name": result}
                    else:
                        st.session_state[cache_key] = {"id": None, "candidates": result}

                state = st.session_state[cache_key]
                if state["id"] is None:
                    unresolved.append((game, side, team_name, state["candidates"]))
                else:
                    resolved_count += 1

        total_teams = len(ranked_games) * 2
        st.markdown(f"**{resolved_count} / {total_teams} teams resolved.**")

        if unresolved:
            st.warning(f"{len(unresolved)} teams need manual selection:")
            for game, side, team_name, candidates in unresolved:
                cache_key = f"precheck_{side}_{game['event_id']}"
                st.markdown(f"**{team_name}** ({game['league']}) — {game['home']} vs {game['away']}")
                for i, candidate in enumerate(candidates):
                    from teamselector import get_team_league
                    cand_league = get_team_league(candidate["id"])
                    cand_label = candidate['name']
                    if cand_league:
                        cand_label += f"  —  {cand_league}"
                    if candidate.get('score') is not None:
                        cand_label += f"  (score: {candidate['score']:.0f})"
                    if st.button(cand_label, key=f"precheck_candidate_{cache_key}_{i}_{candidate['id']}"):
                        confirm_team_selection(team_name, candidate["name"], candidate["id"])
                        st.session_state[cache_key] = {"id": candidate["id"], "name": candidate["name"]}
                        st.rerun()
                st.markdown("---")
        else:
            st.success("✅ All teams resolved! Ready to run Analyse All Games.")

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── Bulk report ───────────────────────────────────────────────────────────
    if bulkreport:
        from bulkreport import generate_all_reports
        progress = st.progress(0, text="Starting...")

        def update_progress(idx, total, name):
            progress.progress(idx / total, text=f"Generating {name}...")

        zip_buffer, date_str_zip, errors = generate_all_reports(ranked_games, update_progress)
        progress.progress(1.0, text="Done!")

        for err in errors:
            st.warning(err)

        st.download_button(
            label="📥 Download All Reports",
            data=zip_buffer,
            file_name=f"Analysed Games {date_str_zip}.zip",
            mime="application/zip",
            key="download_all"
        )

    # ── Individual game buttons ───────────────────────────────────────────────
    if "active_game" not in st.session_state:
        st.session_state["active_game"] = None

    date_colors = {
        "today": "#e74c3c",      # red
        "tomorrow": "#3498db",   # blue
        "later": "#888888"       # standard grey
    }

    for game in ranked_games:
        date_category = game.get("date_category", "later")
        date_str = game.get("date_str", "")
        time_str = game.get("time_str", "")
        color = date_colors.get(date_category, "#888888")

        col_badge, col_btn = st.columns([1, 9])
        with col_badge:
            st.markdown(
                f'<div style="background-color:{color}; color:white; '
                f'border-radius:4px; padding:4px 8px; text-align:center; '
                f'font-size:0.75rem; font-weight:bold; margin-top:6px;">'
                f'{date_category.upper()}<br>{date_str}<br>{time_str}</div>',
                unsafe_allow_html=True
            )
        with col_btn:
            label = (
                f"#{game['rank']}  ·  {game['home']} vs {game['away']}  "
                f"·  Spread: {game['spread']}  ·  Total: {game['total']}  "
                f"·  {game['league']}"
            )

            if st.button(label, key=f"game_{game['event_id']}"):
                st.session_state["active_game"] = game['event_id']

        # Render the team resolution / report section if this game is active
        if st.session_state["active_game"] == game['event_id']:
            home = game['home']
            away = game['away']

            st.markdown(f"### {home} vs {away}")

            # ── Resolve team names ────────────────────────────────────────────
            key_home = f"resolved_home_{game['event_id']}"
            key_away = f"resolved_away_{game['event_id']}"

            if key_home not in st.session_state:
                home_id, home_result, home_status = resolve_team(home, game['league'])
                if home_status == "auto":
                    st.session_state[key_home] = {"id": home_id, "name": home_result}
                else:
                    st.session_state[key_home] = {"id": None, "candidates": home_result}

            if key_away not in st.session_state:
                away_id, away_result, away_status = resolve_team(away, game['league'])
                if away_status == "auto":
                    st.session_state[key_away] = {"id": away_id, "name": away_result}
                else:
                    st.session_state[key_away] = {"id": None, "candidates": away_result}

            home_state = st.session_state[key_home]
            away_state = st.session_state[key_away]

            # ── Show selectors if needed ──────────────────────────────────────
            if home_state["id"] is None:
                st.warning(f"Could not auto-match **{home}** — please select the correct team:")
                for i, candidate in enumerate(home_state["candidates"]):
                    from teamselector import get_team_league
                    cand_league = get_team_league(candidate["id"])
                    cand_label = candidate['name']
                    if cand_league:
                        cand_label += f"  —  {cand_league}"
                    if candidate.get('score') is not None:
                        cand_label += f"  (score: {candidate['score']:.0f})"
                    if st.button(cand_label, key=f"home_candidate_{game['event_id']}_{i}_{candidate['id']}"):
                        confirm_team_selection(home, candidate["name"], candidate["id"])
                        st.session_state[key_home] = {"id": candidate["id"], "name": candidate["name"]}
                        st.rerun()

            if away_state["id"] is None:
                st.warning(f"Could not auto-match **{away}** — please select the correct team:")
                for i, candidate in enumerate(away_state["candidates"]):
                    from teamselector import get_team_league
                    cand_league = get_team_league(candidate["id"])
                    cand_label = candidate['name']
                    if cand_league:
                        cand_label += f"  —  {cand_league}"
                    if candidate.get('score') is not None:
                        cand_label += f"  (score: {candidate['score']:.0f})"
                    if st.button(cand_label, key=f"away_candidate_{game['event_id']}_{i}_{candidate['id']}"):
                        confirm_team_selection(away, candidate["name"], candidate["id"])
                        st.session_state[key_away] = {"id": candidate["id"], "name": candidate["name"]}
                        st.rerun()

            # ── Generate reports once both teams confirmed ────────────────────
            if home_state["id"] and away_state["id"]:
                home_matched = home_state["name"]
                away_matched = away_state["name"]

                st.success(f"✅ {home} → {home_matched}  |  {away} → {away_matched}")

                from h2hgames import build_h2h_excel
                from recentgames import build_recent_games_excel

                h2h_bytes = None
                rg_bytes = None

                with st.spinner("Generating reports..."):
                    try:
                        h2h_bytes = generate_excel_bytes(build_h2h_excel, home_matched, away_matched)
                    except Exception as e:
                        st.warning(f"H2H report failed: {e}")

                    try:
                        rg_bytes = generate_excel_bytes(build_recent_games_excel, home_matched, away_matched)
                    except Exception as e:
                        st.warning(f"Recent Games report failed: {e}")

                if h2h_bytes or rg_bytes:
                    col1, col2 = st.columns(2)
                    if h2h_bytes:
                        with col1:
                            st.download_button(
                                label="📥 Download H2H Report",
                                data=h2h_bytes,
                                file_name=f"H2H — {home_matched} vs {away_matched} — {date_str}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"h2h_{game['event_id']}"
                            )
                    if rg_bytes:
                        with col2:
                            st.download_button(
                                label="📥 Download Recent Games Report",
                                data=rg_bytes,
                                file_name=f"Recent Games — {home_matched} vs {away_matched} — {date_str}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"rg_{game['event_id']}"
                            )