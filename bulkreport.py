import os
import zipfile
import io
import base64
import requests
from datetime import datetime
import zoneinfo
from h2hgames import build_h2h_excel
from recentgames import build_recent_games_excel
from teamselector import resolve_team

SKIPPED_LOG_FILE = "skipped_games_log.txt"
GITHUB_API_BASE = "https://api.github.com"


def _get_github_config():
    """Read GitHub token and repo from Streamlit secrets, if available."""
    try:
        import streamlit as st
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO")
        if token and repo:
            return token, repo
    except Exception:
        pass
    return None, None


def _github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }


def github_load_log():
    """Load skipped_games_log.txt content from GitHub. Returns string or None."""
    token, repo = _get_github_config()
    if not token or not repo:
        return None

    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{SKIPPED_LOG_FILE}"
    try:
        response = requests.get(url, headers=_github_headers(token))
        if response.status_code != 200:
            return None
        data = response.json()
        return base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return None


def github_save_log(content):
    """Push updated skipped_games_log.txt content to GitHub."""
    token, repo = _get_github_config()
    if not token or not repo:
        return False

    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{SKIPPED_LOG_FILE}"

    sha = None
    try:
        get_resp = requests.get(url, headers=_github_headers(token))
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
    except Exception:
        pass

    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": "Update skipped_games_log.txt via app",
        "content": content_b64,
    }
    if sha:
        payload["sha"] = sha

    try:
        put_resp = requests.put(url, headers=_github_headers(token), json=payload)
        return put_resp.status_code in (200, 201)
    except Exception:
        return False


def log_skipped_games_batch(new_lines):
    """
    Append multiple skipped game lines to the persistent log in one batch.
    Loads current log from GitHub (or local fallback), appends, and saves back once.
    """
    # Try to load existing content from GitHub first
    existing = github_load_log()
    if existing is None:
        # Fall back to local file
        if os.path.exists(SKIPPED_LOG_FILE):
            with open(SKIPPED_LOG_FILE, "r", encoding="utf-8") as f:
                existing = f.read()
        else:
            existing = ""

    updated_content = existing + "".join(new_lines)

    # Save locally
    with open(SKIPPED_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(updated_content)

    # Save to GitHub for persistence (single write for the whole batch)
    github_save_log(updated_content)


def generate_excel_bytes(build_fn, *args):
    tmp_path = "_tmp_report.xlsx"
    build_fn(*args, output_path=tmp_path)
    if not os.path.exists(tmp_path):
        raise Exception("Report could not be generated — team may not be found in Highlightly database.")
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.remove(tmp_path)
    return data


def generate_all_reports(ranked_games, progress_callback=None):
    """
    Generate H2H and Recent Games reports for all ranked games.
    Returns a zip file as bytes.
    Subfolders are named by league, with numbering if repeated.
    Any game where both reports fail is logged to skipped_games_log.txt
    in a single batched update at the end of the run.
    """
    melbourne_tz = zoneinfo.ZoneInfo("Australia/Melbourne")
    date_str = datetime.now(melbourne_tz).strftime("%d %b %Y")

    zip_buffer = io.BytesIO()
    total = len(ranked_games)
    errors = []
    skipped_lines = []

    # Track how many times each league appears
    league_counts = {}

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, game in enumerate(ranked_games):
            home = game['home']
            away = game['away']
            league = game['league']

            # Build unique folder name per league
            if league not in league_counts:
                league_counts[league] = 1
                folder_name = league
            else:
                league_counts[league] += 1
                folder_name = f"{league} {league_counts[league]}"

            folder = f"Analysed Games {date_str}/{folder_name}"

            if progress_callback:
                progress_callback(idx, total, f"{home} vs {away}")

            # Resolve team names using teamselector's cache (populated by precheck)
            # This ensures WNBA abbreviations and other manually-confirmed mappings are used
            home_id, home_result, home_status = resolve_team(home, league)
            away_id, away_result, away_status = resolve_team(away, league)

            if home_status != "auto" or away_status != "auto":
                # Team not resolved (not yet confirmed via precheck) — skip and log
                unresolved_names = []
                if home_status != "auto":
                    unresolved_names.append(home)
                if away_status != "auto":
                    unresolved_names.append(away)
                timestamp = datetime.now(melbourne_tz).strftime("%d %b %Y %H:%M")
                reason = f"Unresolved team(s): {', '.join(unresolved_names)} — run 'Check All Teams' first"
                skipped_lines.append(f"[{timestamp}] {home} vs {away} ({league}) — {reason}\n")
                continue

            home_matched = home_result
            away_matched = away_result

            h2h_failed = False
            rg_failed = False
            last_error = ""

            # H2H report
            try:
                h2h_bytes = generate_excel_bytes(build_h2h_excel, home_matched, away_matched)
                zf.writestr(f"{folder}/H2H — {home} vs {away} — {date_str}.xlsx", h2h_bytes)
            except Exception as e:
                h2h_failed = True
                last_error = str(e)
                errors.append(f"H2H failed for {home} vs {away}: {e}")

            # Recent Games report
            try:
                rg_bytes = generate_excel_bytes(build_recent_games_excel, home_matched, away_matched)
                zf.writestr(f"{folder}/Recent Games — {home} vs {away} — {date_str}.xlsx", rg_bytes)
            except Exception as e:
                rg_failed = True
                last_error = str(e)
                errors.append(f"Recent Games failed for {home} vs {away}: {e}")

            # Collect skipped games (both reports failed) for batched logging
            if h2h_failed and rg_failed:
                timestamp = datetime.now(melbourne_tz).strftime("%d %b %Y %H:%M")
                skipped_lines.append(f"[{timestamp}] {home} vs {away} ({league}) — {last_error}\n")

    # Batch-write all skipped games from this run in one GitHub update
    if skipped_lines:
        log_skipped_games_batch(skipped_lines)

    zip_buffer.seek(0)
    return zip_buffer, date_str, errors