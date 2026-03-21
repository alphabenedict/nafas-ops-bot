import logging
import time
import json
import calendar
from datetime import datetime

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from config import SHEET_JSON, SHEET_ID
from ai_helpers import update_client_memory

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

REQUIRED_COLUMNS = {"Timestamp", "Client Name", "Service Type"}

NAMA_BULAN_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

# ── Google Sheets client ─────────────────────────────────────────────

def get_gspread_client():
    """Authenticate with Google Sheets using google-auth (replaces deprecated oauth2client)."""
    if SHEET_JSON and SHEET_JSON.strip().startswith("{"):
        creds_dict = json.loads(SHEET_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(SHEET_JSON, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client


# ── Caching ──────────────────────────────────────────────────────────

_CACHE = {}
CACHE_TTL = 300  # 5 minutes


def fetch_sheet_dataframe(worksheet_name="Sheet1"):
    """Fetch Google Sheet as a DataFrame with TTL caching."""
    now = time.time()
    if worksheet_name in _CACHE:
        cached_time, cached_df = _CACHE[worksheet_name]
        if now - cached_time < CACHE_TTL:
            return cached_df

    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    ws = spreadsheet.worksheet(worksheet_name)
    all_records = ws.get_all_records()
    df = pd.DataFrame(all_records)

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Google Sheet is missing required columns: {', '.join(sorted(missing))}. "
            f"Found columns: {df.columns.tolist()}"
        )

    _CACHE[worksheet_name] = (now, df)
    return df


# ── Shared helpers ───────────────────────────────────────────────────

def _filter_by_date_range(df, start, end):
    """Parse Timestamp column and filter to a date range. Returns filtered copy."""
    df = df.copy()
    df["ParsedDate"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    mask = (df["ParsedDate"] >= start) & (df["ParsedDate"] <= end)
    return df.loc[mask].copy()


def _build_summary_lines(df_filtered, title):
    """Build human-readable summary lines from a filtered DataFrame."""
    total_records = len(df_filtered)

    df_filtered["Service Type"] = df_filtered["Service Type"].fillna("Unknown")
    service_counts = df_filtered["Service Type"].value_counts().to_dict()

    df_filtered["On time / Late"] = df_filtered["On time / Late"].fillna("Unknown")
    otl_counts = df_filtered["On time / Late"].value_counts().to_dict()

    lines = []
    lines.append(f"📊 *{title}:*")
    lines.append(f"• Total Record: *{total_records}*")
    lines.append("")
    lines.append("• *Jumlah per Service Type:*")
    for svc, count in service_counts.items():
        lines.append(f"  – {svc}: {count}")
    lines.append("")
    lines.append("• *On time vs Late:*")
    for status, count in otl_counts.items():
        lines.append(f"  – {status}: {count}")
    lines.append("")

    if total_records > 0:
        last_row = df_filtered.sort_values("ParsedDate", ascending=False).iloc[0]
        client_terakhir = last_row.get("Client Name", "N/A")
        tanggal_terakhir = last_row["ParsedDate"].strftime("%d-%b-%Y %H:%M")
        service_terakhir = last_row.get("Service Type", "N/A")
        tek_terakhir = last_row.get("Technician", "N/A")
        lines.append("• *Layanan Terakhir:*")
        lines.append(
            f"  – {client_terakhir} di {tanggal_terakhir} "
            f"({service_terakhir}, Teknisi: {tek_terakhir})"
        )
    else:
        lines.append("• *Tidak ada data di rentang waktu ini.*")

    return "\n".join(lines)


def _sync_memory_from_df(df_filtered):
    """Sync the latest record per client from a filtered DataFrame into memory."""
    df_latest = (
        df_filtered
        .sort_values("ParsedDate", ascending=True)
        .drop_duplicates("Client Name", keep="last")
    )
    synced = 0
    for _, row in df_latest.iterrows():
        client_name = str(row.get("Client Name", "")).strip()
        if not client_name:
            continue

        parsed_dt = row["ParsedDate"]
        last_service = parsed_dt.strftime("%d-%b-%Y %H:%M") if not pd.isna(parsed_dt) else ""

        update_client_memory(
            client_name=client_name,
            address=str(row.get("Location", "") or row.get("Address", "")).strip(),
            last_service=last_service,
            service_type=str(row.get("Service Type", "")).strip(),
            technician=str(row.get("Technician", "")).strip(),
            device=str(row.get("Devices", "")).strip(),
            issue=str(row.get("Issue", "")).strip(),
            solution=str(row.get("Solution", "")).strip(),
            client_type=str(row.get("Client Type", "")).strip(),
            notes=str(row.get("Notes", "")).strip(),
        )
        synced += 1

    logger.info("Synced %d client records to memory", synced)
    return synced


# ── Public API ───────────────────────────────────────────────────────

def sync_memory():
    """Sync all client data from the sheet into local memory. Called by /sync."""
    df = fetch_sheet_dataframe()
    now = datetime.now()
    start = pd.Timestamp(year=now.year, month=1, day=1)
    end = pd.Timestamp.now()
    df_filtered = _filter_by_date_range(df, start, end)
    count = _sync_memory_from_df(df_filtered)
    return f"✅ Synced {count} client records to memory."


def summarize_year_to_date():
    """Build a year-to-date summary. Uses dynamic current year."""
    df = fetch_sheet_dataframe()
    now = datetime.now()
    start = pd.Timestamp(year=now.year, month=1, day=1)
    end = pd.Timestamp.now()
    df_filtered = _filter_by_date_range(df, start, end)

    title = f"Ringkasan Nafas (01-Jan-{now.year} s/d {end.strftime('%d-%b-%Y')})"
    return _build_summary_lines(df_filtered, title)


def summarize_month(month_index: int, year: int = None):
    """Build a monthly summary. Defaults to current year if not specified."""
    if year is None:
        year = datetime.now().year

    df = fetch_sheet_dataframe()
    start = pd.Timestamp(year=year, month=month_index, day=1)
    last_day = calendar.monthrange(year, month_index)[1]
    end = pd.Timestamp(year=year, month=month_index, day=last_day, hour=23, minute=59, second=59)
    df_filtered = _filter_by_date_range(df, start, end)

    nama_bulan = NAMA_BULAN_ID.get(month_index, f"Month-{month_index}")
    title = f"Ringkasan Nafas ({nama_bulan} {year})"
    return _build_summary_lines(df_filtered, title)
