from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from google.oauth2 import service_account
from googleapiclient.discovery import build

_SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsExportError(RuntimeError):
    pass


def _normalize_video_url_key(value: str) -> str:
    """
    Normalize URL for stable duplicate matching across sync runs.

    We intentionally keep identity query keys (e.g. youtube v/list),
    but drop tracking params that frequently vary between runs.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except Exception:
        return raw.rstrip("/")

    if not parts.scheme or not parts.netloc:
        return raw.rstrip("/")

    scheme = "https"
    netloc = (parts.netloc or "").lower()
    path = (parts.path or "").rstrip("/")

    # Drop unstable tracker params, keep identity params.
    allowed_keys = {"v", "list", "id", "video", "video_id", "clip"}
    tracker_prefixes = ("utm_",)
    tracker_keys = {"fbclid", "gclid", "yclid", "si", "feature", "ref", "source"}
    kept_pairs: list[tuple[str, str]] = []
    for key, val in parse_qsl(parts.query, keep_blank_values=False):
        k = str(key or "").strip().lower()
        if not k:
            continue
        if k in allowed_keys:
            kept_pairs.append((k, val))
            continue
        if any(k.startswith(prefix) for prefix in tracker_prefixes):
            continue
        if k in tracker_keys:
            continue
    query = urlencode(kept_pairs, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def _sheet_start_column() -> str:
    # Business template expects data block to start at column B
    # (B=title, C=url, D=social_network, ...).
    raw = str(os.getenv("CONTENT_FACTORY_GOOGLE_START_COLUMN", "B")).strip().upper()
    if not raw:
        return "B"
    if not raw.isalpha():
        return "B"
    return raw


def _load_service_account_info() -> dict[str, Any]:
    raw_json = str(os.getenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON", "")).strip()
    if raw_json:
        try:
            payload = json.loads(raw_json)
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            raise GoogleSheetsExportError("Invalid GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON") from exc

    raw_b64 = str(os.getenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON_B64", "")).strip()
    if raw_b64:
        try:
            decoded = base64.b64decode(raw_b64).decode("utf-8")
            payload = json.loads(decoded)
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            raise GoogleSheetsExportError("Invalid GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON_B64") from exc

    file_path = str(os.getenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", "")).strip()
    if file_path:
        try:
            text = Path(file_path).read_text(encoding="utf-8")
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            raise GoogleSheetsExportError("Cannot read GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE") from exc

    raise GoogleSheetsExportError(
        "Google Sheets writer is not configured. Set one of: "
        "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON, GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON_B64, GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE"
    )


def _build_sheets_service():
    info = _load_service_account_info()
    credentials = service_account.Credentials.from_service_account_info(info, scopes=_SHEETS_SCOPE)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _sheet_range(sheet_name: str) -> str:
    cleaned = (sheet_name or "Content Factory Export").strip() or "Content Factory Export"
    escaped = cleaned.replace("'", "''")
    start_col = _sheet_start_column()
    return f"'{escaped}'!{start_col}1"


def _sheet_row_range(sheet_name: str, row: int) -> str:
    cleaned = (sheet_name or "Content Factory Export").strip() or "Content Factory Export"
    escaped = cleaned.replace("'", "''")
    start_col = _sheet_start_column()
    return f"'{escaped}'!{start_col}{row}:ZZ{row}"


def _sheet_data_range_from_row(sheet_name: str, row: int) -> str:
    cleaned = (sheet_name or "Content Factory Export").strip() or "Content Factory Export"
    escaped = cleaned.replace("'", "''")
    start_col = _sheet_start_column()
    return f"'{escaped}'!{start_col}{row}:ZZ"


def _column_letter(index_1_based: int) -> str:
    if index_1_based <= 0:
        raise ValueError("index_1_based must be > 0")
    result = ""
    n = index_1_based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _normalize_header_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    normalized = "".join(ch for ch in raw if ch.isalnum())

    alias_to_key = {
        "videoid": "video_id",
        "idvideo": "video_id",
        "channelid": "channel_id",
        "projectname": "project_name",
        "project": "project_name",
        "socialnetwork": "social_network",
        "network": "social_network",
        "platform": "social_network",
        "соцсеть": "social_network",
        "социальнаясеть": "social_network",
        "channeltitle": "channel_title",
        "канал": "channel_title",
        "channelurl": "channel_url",
        "videourl": "video_url",
        "ссылканавидео": "video_url",
        "ссылка": "video_url",
        "videoexternalid": "video_external_id",
        "title": "title",
        "название": "title",
        "названиевидео": "title",
        "publishedat": "published_at",
        "датапубликации": "published_at",
        "дата": "published_at",
        "capturedat": "captured_at",
        "views": "views",
        "просмотры": "views",
        "likes": "likes",
        "лайки": "likes",
        "comments": "comments",
        "комментарии": "comments",
        "shares": "shares",
        "репосты": "shares",
        "saves": "saves",
        "сохранения": "saves",
        "durationseconds": "duration_seconds",
        "длительность": "duration_seconds",
        "isshort": "is_short",
        "short": "is_short",
        "тип": "video_type",
        "типвидео": "video_type",
        "modstatus": "moderation_status",
        "moderationstatus": "moderation_status",
        "source": "source",
        "recoveryapplied": "recovery_applied",
        "recoverysource": "recovery_source",
        "recoveredfields": "recovered_fields",
    }
    return alias_to_key.get(normalized, normalized)


def _header(include_provenance: bool) -> list[str]:
    base = [
        "video_id",
        "channel_id",
        "project_name",
        "social_network",
        "channel_title",
        "channel_url",
        "video_url",
        "video_external_id",
        "title",
        "published_at",
        "captured_at",
        "views",
        "likes",
        "comments",
        "shares",
        "saves",
        "duration_seconds",
        "is_short",
        "moderation_status",
    ]
    if include_provenance:
        base.extend([
            "source",
            "recovery_applied",
            "recovery_source",
            "recovered_fields",
        ])
    return base


def _template_bootstrap_headers() -> list[str]:
    """Headers for user-facing sheet templates (B40 layout)."""
    return [
        "Название видео",
        "Ссылка на видео",
        "Социальная сеть",
        "Просмотры",
        "Дата",
        "Тип видео",
    ]


def _bootstrap_headers(include_provenance: bool) -> list[str]:
    mode = str(os.getenv("CONTENT_FACTORY_GOOGLE_BOOTSTRAP_MODE", "template")).strip().lower()
    if mode in {"template", "simple", "business"}:
        return _template_bootstrap_headers()
    return _header(include_provenance)


def _row_values(row: dict[str, Any], include_provenance: bool) -> list[Any]:
    published_raw = str(row.get("published_at") or "").strip()
    published_at = published_raw.split("T", 1)[0] if "T" in published_raw else published_raw

    values: list[Any] = [
        int(row.get("video_id") or 0),
        int(row.get("channel_id") or 0),
        str(row.get("project_name") or ""),
        str(row.get("social_network") or ""),
        str(row.get("channel_title") or ""),
        str(row.get("channel_url") or ""),
        str(row.get("video_url") or ""),
        str(row.get("video_external_id") or ""),
        str(row.get("title") or ""),
        published_at,
        str(row.get("captured_at") or ""),
        int(row.get("views") or 0),
        int(row.get("likes") or 0),
        int(row.get("comments") or 0),
        int(row.get("shares") or 0),
        int(row.get("saves") or 0),
        int(row.get("duration_seconds") or 0) if row.get("duration_seconds") is not None else "",
        bool(row.get("is_short")),
        str(row.get("moderation_status") or ""),
    ]
    if include_provenance:
        recovered_fields = row.get("recovered_fields")
        if isinstance(recovered_fields, list):
            recovered_fields_text = ", ".join(str(item) for item in recovered_fields if str(item).strip())
        else:
            recovered_fields_text = ""
        values.extend([
            str(row.get("source") or ""),
            bool(row.get("recovery_applied")),
            str(row.get("recovery_source") or ""),
            recovered_fields_text,
        ])
    return values


def _ensure_sheet_exists(*, spreadsheet_id: str, sheet_name: str) -> str:
    """Ensure the sheet exists in the spreadsheet. Returns the sheet ID."""
    service = _build_sheets_service()
    
    # Get spreadsheet metadata to see existing sheets
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties(sheetId,title)"
    ).execute()
    
    for sheet in spreadsheet.get("sheets", []):
        if sheet["properties"]["title"] == sheet_name:
            return str(sheet["properties"]["sheetId"])
    
    # Sheet doesn't exist, create it
    requests = [
        {
            "addSheet": {
                "properties": {
                    "title": sheet_name,
                    "gridProperties": {
                        "rowCount": 10000,
                        "columnCount": 50
                    }
                }
            }
        }
    ]
    
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()
    
    sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
    return str(sheet_id)


def export_rows_to_google_sheets(
    *,
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[dict[str, Any]],
    include_provenance: bool,
    clear_sheet: bool,
) -> dict[str, Any]:
    if not str(spreadsheet_id or "").strip():
        raise GoogleSheetsExportError("spreadsheet_id is required")

    # Ensure sheet exists before trying to write
    _ensure_sheet_exists(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name)
    
    service = _build_sheets_service()
    values = [_header(include_provenance)] + [_row_values(row, include_provenance) for row in rows]
    target_range = _sheet_range(sheet_name)

    if clear_sheet:
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=target_range,
            body={},
        ).execute()

    response = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=target_range,
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    return {
        "rows_written": max(0, len(values) - 1),
        "updated_range": str(response.get("updatedRange") or target_range),
        "updated_rows": int(response.get("updatedRows") or 0),
    }


def append_rows_to_google_sheets(
    *,
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[dict[str, Any]],
    header_row: int,
    include_provenance: bool,
    prevent_duplicates: bool,
    duplicate_key: str,
    update_existing: bool = True,
) -> dict[str, Any]:
    if not str(spreadsheet_id or "").strip():
        raise GoogleSheetsExportError("spreadsheet_id is required")
    if header_row < 1:
        raise GoogleSheetsExportError("header_row must be >= 1")

    # Ensure sheet exists before trying to write
    _ensure_sheet_exists(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name)

    service = _build_sheets_service()
    header_range = _sheet_row_range(sheet_name, header_row)
    header_resp = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=header_range,
    ).execute()
    header_values = (header_resp.get("values") or [])
    if not header_values or not header_values[0]:
        # Bootstrap headers on an empty sheet so append mode works out-of-the-box.
        header_payload = _bootstrap_headers(include_provenance)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=header_range,
            valueInputOption="RAW",
            body={"values": [header_payload]},
        ).execute()
        header_values = [header_payload]

    raw_headers = [str(item).strip() for item in header_values[0]]
    normalized_headers = [_normalize_header_name(item) for item in raw_headers]

    duplicate_key_normalized = _normalize_header_name(duplicate_key)
    duplicate_col_idx = -1
    if prevent_duplicates and duplicate_key_normalized in normalized_headers:
        duplicate_col_idx = normalized_headers.index(duplicate_key_normalized)

    existing_resp = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=_sheet_data_range_from_row(sheet_name, header_row + 1),
    ).execute()
    existing_rows = existing_resp.get("values") or []

    existing_keys: set[str] = set()
    existing_key_to_rownum: dict[str, int] = {}
    if prevent_duplicates and duplicate_col_idx >= 0:
        for idx, existing_row in enumerate(existing_rows, start=header_row + 1):
            if duplicate_col_idx < len(existing_row):
                value = str(existing_row[duplicate_col_idx] or "").strip()
                if value:
                    existing_keys.add(value)
                    existing_key_to_rownum[value] = idx
                    if duplicate_key_normalized == "video_url":
                        normalized = _normalize_video_url_key(value)
                        if normalized:
                            existing_keys.add(normalized)
                            existing_key_to_rownum[normalized] = idx

    data_rows_to_append: list[list[Any]] = []
    # Each entry: (row_num_1based, row_values_aligned_with_headers)
    data_row_updates: list[tuple[int, list[Any]]] = []
    duplicates_skipped = 0
    for row in rows:
        if include_provenance:
            candidate = _row_values(row, include_provenance=True)
        else:
            candidate = _row_values(row, include_provenance=False)

        # Build map by canonical keys using known export order.
        canonical_values = {
            "video_id": candidate[0],
            "channel_id": candidate[1],
            "project_name": candidate[2],
            "social_network": candidate[3],
            "channel_title": candidate[4],
            "channel_url": candidate[5],
            "video_url": candidate[6],
            "video_external_id": candidate[7],
            "title": candidate[8],
            "published_at": candidate[9],
            "captured_at": candidate[10],
            "views": candidate[11],
            "likes": candidate[12],
            "comments": candidate[13],
            "shares": candidate[14],
            "saves": candidate[15],
            "duration_seconds": candidate[16],
            "is_short": candidate[17],
            "video_type": "Шортс" if bool(candidate[17]) else "Горизонтальное",
            "moderation_status": candidate[18],
        }
        if include_provenance and len(candidate) >= 23:
            canonical_values.update(
                {
                    "source": candidate[19],
                    "recovery_applied": candidate[20],
                    "recovery_source": candidate[21],
                    "recovered_fields": candidate[22],
                }
            )

        if prevent_duplicates:
            key_value = str(canonical_values.get(duplicate_key_normalized) or "").strip()
            match_key = key_value
            if duplicate_key_normalized == "video_url" and key_value:
                normalized_key = _normalize_video_url_key(key_value)
                if normalized_key and normalized_key in existing_keys:
                    match_key = normalized_key
            if key_value and (match_key in existing_keys or key_value in existing_keys):
                target_key = match_key if match_key in existing_key_to_rownum else key_value
                if update_existing and target_key in existing_key_to_rownum:
                    # Refresh full row so stale template columns (for example
                    # social_network in column D) are corrected on re-export.
                    row_update: list[Any] = []
                    for header_key in normalized_headers:
                        row_update.append(canonical_values.get(header_key, ""))
                    data_row_updates.append((existing_key_to_rownum[target_key], row_update))
                else:
                    duplicates_skipped += 1
                continue
            if key_value:
                existing_keys.add(key_value)
                if duplicate_key_normalized == "video_url":
                    normalized_key = _normalize_video_url_key(key_value)
                    if normalized_key:
                        existing_keys.add(normalized_key)

        row_out: list[Any] = []
        for header_key in normalized_headers:
            row_out.append(canonical_values.get(header_key, ""))
        data_rows_to_append.append(row_out)

    updated_rows_count = 0
    updated_ranges: list[str] = []
    if data_row_updates:
        batch_data: list[dict] = []
        for row_num, row_values in data_row_updates:
            batch_data.append(
                {
                    "range": _sheet_row_range(sheet_name, row_num),
                    "values": [row_values],
                }
            )
        if batch_data:
            batch_resp = service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "RAW", "data": batch_data},
            ).execute()
            updated_rows_count = len(data_row_updates)
            responses = batch_resp.get("responses") or []
            for item in responses:
                if isinstance(item, dict):
                    updated_ranges.append(str(item.get("updatedRange") or ""))

    if not data_rows_to_append:
        return {
            "rows_written": updated_rows_count,
            "updated_range": _sheet_data_range_from_row(sheet_name, header_row + 1),
            "updated_rows": updated_rows_count,
            "rows_appended": 0,
            "rows_updated": updated_rows_count,
            "duplicates_skipped": duplicates_skipped,
            "updated_ranges": updated_ranges,
        }

    append_start_row = header_row + 1 + len(existing_rows)
    append_range = _sheet_data_range_from_row(sheet_name, append_start_row)
    update_resp = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=append_range,
        valueInputOption="RAW",
        body={"values": data_rows_to_append},
    ).execute()

    appended_rows_count = int(update_resp.get("updatedRows") or 0)
    return {
        "rows_written": appended_rows_count + updated_rows_count,
        "updated_range": str(update_resp.get("updatedRange") or append_range),
        "updated_rows": appended_rows_count + updated_rows_count,
        "rows_appended": appended_rows_count,
        "rows_updated": updated_rows_count,
        "duplicates_skipped": duplicates_skipped,
        "updated_ranges": updated_ranges,
    }


# ---------------------------------------------------------------------------
# Per-network sheet export
# Writes to named sheets (YOUTUBE, INST, TIKTOK, VK, ODNOKLASSNIKI, LIKE,
# DZEN, RUTUBE) with columns B-G starting from row 27:
#   B = Название видео
#   C = Ссылка на видео
#   D = Социальная сеть
#   E = Дата
#   F = Просмотры
#   G = Тип видео  (Шортс / Горизонтальное)
# Existing rows are matched by video URL (column C) and only metrics/dates
# are refreshed; new rows are appended below the last used row.
# ---------------------------------------------------------------------------

_NETWORK_TO_SHEET: dict[str, str] = {
    "youtube": "YOUTUBE",
    "instagram": "INST",
    "tiktok": "TIKTOK",
    "vk": "VK",
    "ok": "ODNOKLASSNIKI",
    "likee": "LIKE",
    "dzen": "DZEN",
    "rutube": "RUTUBE",
}

# Fixed layout: columns B(2)..G(7), data starts at row 27
_PNS_START_ROW = 27
_PNS_COL_TITLE = 2   # B
_PNS_COL_URL   = 3   # C
_PNS_COL_SOCIAL = 4  # D
_PNS_COL_DATE   = 5  # E
_PNS_COL_VIEWS  = 6  # F
_PNS_COL_TYPE   = 7  # G


def _pns_range(sheet_name: str, from_row: int, col_start: int, col_end: int) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'!{_column_letter(col_start)}{from_row}:{_column_letter(col_end)}"


def write_per_network_sheets(
    *,
    spreadsheet_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write rows to per-network sheets in columns B:G starting at row 27.

    Existing rows (matched by video URL in column C) are refreshed in full;
    new rows are appended after the last used row.
    """
    if not str(spreadsheet_id or "").strip():
        raise GoogleSheetsExportError("spreadsheet_id is required")

    service = _build_sheets_service()

    # Group rows by social_network
    by_network: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        net = str(row.get("social_network") or "").strip().lower()
        sheet_name = _NETWORK_TO_SHEET.get(net)
        if not sheet_name:
            continue
        by_network.setdefault(sheet_name, []).append(row)

    total_appended = 0
    total_updated = 0
    summary: dict[str, Any] = {}

    for sheet_name, sheet_rows in by_network.items():
        _ensure_sheet_exists(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name)

        # Read existing data from B27:G downward
        read_range = _pns_range(sheet_name, _PNS_START_ROW, _PNS_COL_TITLE, _PNS_COL_TYPE)
        existing_resp = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=read_range,
        ).execute()
        existing_data: list[list[str]] = existing_resp.get("values") or []

        # Build URL → row number map (column C = index 1 in B:G slice)
        url_to_rownum: dict[str, int] = {}
        for idx, existing_row in enumerate(existing_data):
            if len(existing_row) >= 2:
                url_val = str(existing_row[1] or "").strip()
                if url_val:
                    url_to_rownum[url_val] = _PNS_START_ROW + idx
                    normalized_url = _normalize_video_url_key(url_val)
                    if normalized_url:
                        url_to_rownum[normalized_url] = _PNS_START_ROW + idx

        rows_to_append: list[list[Any]] = []
        row_updates: list[dict[str, Any]] = []

        for row in sheet_rows:
            published_raw = str(row.get("published_at") or "").strip()
            date_str = published_raw.split("T", 1)[0] if "T" in published_raw else published_raw
            is_short = bool(row.get("is_short"))
            video_type = "Шортс" if is_short else "Горизонтальное"
            title = str(row.get("title") or "")
            url = str(row.get("video_url") or "")
            social_network = str(row.get("social_network") or "")
            views = int(row.get("views") or 0)
            row_values = [[title, url, social_network, date_str, views, video_type]]

            match_url = url
            if url:
                normalized_url = _normalize_video_url_key(url)
                if normalized_url and normalized_url in url_to_rownum:
                    match_url = normalized_url

            if url and match_url in url_to_rownum:
                # Refresh the entire row so the sheet stays in sync.
                existing_row_num = url_to_rownum[match_url]
                row_updates.append({
                    "range": _pns_range(sheet_name, existing_row_num, _PNS_COL_TITLE, _PNS_COL_TYPE),
                    "values": row_values,
                })
            else:
                rows_to_append.append(row_values[0])
                if url:
                    # Pre-register so duplicate input rows don't double-append
                    next_row = _PNS_START_ROW + len(existing_data) + len(rows_to_append) - 1
                    url_to_rownum[url] = next_row

        if row_updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                # USER_ENTERED lets Sheets parse dates/numbers, which is critical
                # for dashboard formulas (e.g. summary cells like J26).
                body={"valueInputOption": "USER_ENTERED", "data": row_updates},
            ).execute()
            total_updated += len(row_updates)

        # Append new rows
        if rows_to_append:
            next_empty_row = _PNS_START_ROW + len(existing_data)
            append_range = _pns_range(sheet_name, next_empty_row, _PNS_COL_TITLE, _PNS_COL_TYPE)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=append_range,
                # Keep values typed by Sheets engine (dates, numbers) instead of raw text.
                valueInputOption="USER_ENTERED",
                body={"values": rows_to_append},
            ).execute()
            total_appended += len(rows_to_append)

        summary[sheet_name] = {
            "appended": len(rows_to_append),
            "updated": len(row_updates),
        }

    return {
        "total_appended": total_appended,
        "total_updated": total_updated,
        "by_sheet": summary,
    }
