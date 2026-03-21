
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import calendar
from config import SHEET_JSON, SHEET_ID
from ai_helpers import update_client_memory

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

def get_gspread_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(SHEET_JSON, SCOPES)
    client = gspread.authorize(creds)
    return client

def fetch_sheet_dataframe(worksheet_name="Sheet1"):
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    ws = spreadsheet.worksheet(worksheet_name)
    all_records = ws.get_all_records()
    df = pd.DataFrame(all_records)
    return df

def summarize_year_to_date():
    df = fetch_sheet_dataframe()
    df["ParsedDate"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    start = pd.Timestamp(year=2026, month=1, day=1)
    end = pd.Timestamp.now()
    mask = (df["ParsedDate"] >= start) & (df["ParsedDate"] <= end)
    df_filtered = df.loc[mask].copy()

    total_records = len(df_filtered)
    df_filtered["Service Type"] = df_filtered["Service Type"].fillna("Unknown")
    service_counts = df_filtered["Service Type"].value_counts().to_dict()
    df_filtered["On time / Late"] = df_filtered["On time / Late"].fillna("Unknown")
    otl_counts = df_filtered["On time / Late"].value_counts().to_dict()

    lines = []
    lines.append(f"📊 *Ringkasan Nafas (01-Jan-2026 s/d {end.strftime('%d-%b-%Y')}):*")
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
        lines.append(f"  – {client_terakhir} di {tanggal_terakhir} ({service_terakhir}, Teknisi: {tek_terakhir})")

        df_latest = df_filtered.sort_values("ParsedDate", ascending=True).drop_duplicates("Client Name", keep="last")
        for _, row in df_latest.iterrows():
            client_name = row.get("Client Name", "").strip()
            location = row.get("Location", "").strip() or row.get("Address", "").strip()
            parsed_dt = row["ParsedDate"]
            last_service = parsed_dt.strftime("%d-%b-%Y %H:%M") if not pd.isna(parsed_dt) else ""
            service_type = row.get("Service Type", "").strip()
            technician = row.get("Technician", "").strip()
            device = row.get("Devices", "").strip()
            issue = row.get("Issue", "").strip()
            solution = row.get("Solution", "").strip()
            client_type = row.get("Client Type", "").strip()
            notes = row.get("Notes", "").strip()

            if client_name:
                update_client_memory(
                    client_name=client_name,
                    address=location,
                    last_service=last_service,
                    service_type=service_type,
                    technician=technician,
                    device=device,
                    issue=issue,
                    solution=solution,
                    client_type=client_type,
                    notes=notes
                )
    else:
        lines.append("• *Tidak ada data di rentang waktu ini.*")

    return "\n".join(lines)

def summarize_month(month_index: int, year: int = 2026):
    df = fetch_sheet_dataframe()
    df["ParsedDate"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    start = pd.Timestamp(year=year, month=month_index, day=1)
    last_day = calendar.monthrange(year, month_index)[1]
    end = pd.Timestamp(year=year, month=month_index, day=last_day, hour=23, minute=59, second=59)

    mask = (df["ParsedDate"] >= start) & (df["ParsedDate"] <= end)
    df_filtered = df.loc[mask].copy()
    total_records = len(df_filtered)
    df_filtered["Service Type"] = df_filtered["Service Type"].fillna("Unknown")
    service_counts = df_filtered["Service Type"].value_counts().to_dict()
    df_filtered["On time / Late"] = df_filtered["On time / Late"].fillna("Unknown")
    otl_counts = df_filtered["On time / Late"].value_counts().to_dict()

    NAMA_BULAN_ID = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    nama_bulan = NAMA_BULAN_ID.get(month_index, f"Month-{month_index}")

    lines = []
    lines.append(f"📊 *Ringkasan Nafas ({nama_bulan} {year}):*")
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
        lines.append("• *Layanan Terakhir di Bulan Ini:*")
        lines.append(f"  – {client_terakhir} di {tanggal_terakhir} ({service_terakhir}, Teknisi: {tek_terakhir})")

        df_latest = df_filtered.sort_values("ParsedDate", ascending=True).drop_duplicates("Client Name", keep="last")
        for _, row in df_latest.iterrows():
            client_name = row.get("Client Name", "").strip()
            location = row.get("Location", "").strip() or row.get("Address", "").strip()
            parsed_dt = row["ParsedDate"]
            last_service = parsed_dt.strftime("%d-%b-%Y %H:%M") if not pd.isna(parsed_dt) else ""
            service_type = row.get("Service Type", "").strip()
            technician = row.get("Technician", "").strip()
            device = row.get("Devices", "").strip()
            issue = row.get("Issue", "").strip()
            solution = row.get("Solution", "").strip()
            client_type = row.get("Client Type", "").strip()
            notes = row.get("Notes", "").strip()

            if client_name:
                update_client_memory(
                    client_name=client_name,
                    address=location,
                    last_service=last_service,
                    service_type=service_type,
                    technician=technician,
                    device=device,
                    issue=issue,
                    solution=solution,
                    client_type=client_type,
                    notes=notes
                )
    else:
        lines.append("• *Tidak ada data di bulan ini.*")

    return "\n".join(lines)
