import os
import zipfile
import io
from datetime import datetime
import zoneinfo
from h2hgames import build_h2h_excel
from recentgames import build_recent_games_excel


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

    progress_callback: optional function(idx, total, game_name) for progress updates
    """
    melbourne_tz = zoneinfo.ZoneInfo("Australia/Melbourne")
    date_str = datetime.now(melbourne_tz).strftime("%d %b %Y")

    zip_buffer = io.BytesIO()
    total = len(ranked_games)
    errors = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, game in enumerate(ranked_games):
            home = game['home']
            away = game['away']
            folder = f"Analysed Games {date_str}/{home} vs {away}"

            if progress_callback:
                progress_callback(idx, total, f"{home} vs {away}")

            # H2H report
            try:
                h2h_bytes = generate_excel_bytes(build_h2h_excel, home, away)
                zf.writestr(f"{folder}/H2H — {home} vs {away} — {date_str}.xlsx", h2h_bytes)
            except Exception as e:
                errors.append(f"H2H failed for {home} vs {away}: {e}")

            # Recent Games report
            try:
                rg_bytes = generate_excel_bytes(build_recent_games_excel, home, away)
                zf.writestr(f"{folder}/Recent Games — {home} vs {away} — {date_str}.xlsx", rg_bytes)
            except Exception as e:
                errors.append(f"Recent Games failed for {home} vs {away}: {e}")

    zip_buffer.seek(0)
    return zip_buffer, date_str, errors