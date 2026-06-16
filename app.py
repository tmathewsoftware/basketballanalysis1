import streamlit as st
from basketball_ranker import fetch_upcoming_games, build_ranked_list
from datetime import datetime
import zoneinfo
import os
from bulkreport import generate_all_reports

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

        .rank-badge {
            display: inline-block;
            background: #e8ff00;
            color: #0d0d0d;
            font-family: 'Bebas Neue', sans-serif;
            font-size: 0.85rem;
            padding: 1px 7px;
            border-radius: 3px;
            margin-right: 8px;
            letter-spacing: 0.05em;
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
tomorrow_str = datetime.now(melbourne_tz).strftime("Tomorrow — %A, %d %b %Y")
st.markdown(f'<div class="subtitle">Ranked games for {tomorrow_str}</div>', unsafe_allow_html=True)


# ── Excel generation helper ───────────────────────────────────────────────────
def generate_excel_bytes(build_fn, *args):
    tmp_path = "_tmp_report.xlsx"
    build_fn(*args, output_path=tmp_path)
    if not os.path.exists(tmp_path):
        raise Exception("Report could not be generated — team may not be found in Highlightly database.")
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

# ── Bulk Report Button ────────────────────────────────────────────────────────
if ranked_games:
    col_left, col_right = st.columns([3, 1])
    with col_right:
        bulkreport = st.button("📦 Analyse All Games", key="analyse_all")
else:
    bulkreport = False

# When the button is clicked:
if bulkreport:
    progress = st.progress(0, text="Starting...")
    
    def update_progress(idx, total, name):
        progress.progress(idx / total, text=f"Generating {name}...")
    
    zip_buffer, date_str, errors = generate_all_reports(ranked_games, update_progress)
    
    progress.progress(1.0, text="Done!")
    
    for err in errors:
        st.warning(err)
    
    st.download_button(
        label="📥 Download All Reports",
        data=zip_buffer,
        file_name=f"Analysed Games {date_str}.zip",
        mime="application/zip",
        key="download_all"
    )

# ── Game buttons ──────────────────────────────────────────────────────────────
if not ranked_games:
    st.warning("No games found with spread and totals data for tomorrow.")
else:
    st.markdown(f"**{len(ranked_games)} games ranked** — click a game to generate Excel reports.")
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    for game in ranked_games:
        label = (
            f"#{game['rank']}  ·  {game['home']} vs {game['away']}  "
            f"·  Spread: {game['spread']}  ·  Total: {game['total']}  "
            f"·  {game['league']}"
        )

        if st.button(label, key=f"game_{game['event_id']}"):
            home = game['home']
            away = game['away']
            date_str = datetime.now(melbourne_tz).strftime("%d %b %Y")

            st.markdown(f"### {home} vs {away}")

            from h2hgames import build_h2h_excel
            from recentgames import build_recent_games_excel

            h2h_bytes = None
            rg_bytes = None

            with st.spinner("Generating reports..."):
                try:
                    h2h_bytes = generate_excel_bytes(build_h2h_excel, home, away)
                except Exception as e:
                    st.warning(f"H2H report failed: {e}")

                try:
                    rg_bytes = generate_excel_bytes(build_recent_games_excel, home, away)
                except Exception as e:
                    st.warning(f"Recent Games report failed: {e}")

            if h2h_bytes or rg_bytes:
                col1, col2 = st.columns(2)
                if h2h_bytes:
                    with col1:
                        st.download_button(
                            label="📥 Download H2H Report",
                            data=h2h_bytes,
                            file_name=f"H2H — {home} vs {away} — {date_str}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"h2h_{game['event_id']}"
                        )
                if rg_bytes:
                    with col2:
                        st.download_button(
                            label="📥 Download Recent Games Report",
                            data=rg_bytes,
                            file_name=f"Recent Games — {home} vs {away} — {date_str}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"rg_{game['event_id']}"
                        )