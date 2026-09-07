"""Fetch and parse a published Google Sheet for Awqaat MT."""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date, datetime
from urllib.parse import parse_qs, urlparse

import aiohttp

_LOGGER = logging.getLogger(__name__)

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y")
_TIME_FORMATS = ("%H:%M:%S", "%H:%M")


class SheetError(Exception):
    """Raised when the sheet can't be fetched or parsed."""


class SheetAuthError(SheetError):
    """Raised when the sheet isn't published / publicly reachable."""


def normalize_to_csv_url(raw_url: str) -> str:
    """Turn a pubhtml / regular Google Sheets link into a CSV export link.

    Accepts:
    - .../pub?output=csv&gid=... (used as-is)
    - .../pubhtml?gid=...&single=true (converted to pub?output=csv)
    - .../d/e/<pub-id>/pubhtml (converted)
    Raises SheetError if the URL doesn't look like a Google Sheets publish link.
    """
    raw_url = raw_url.strip()
    parsed = urlparse(raw_url)

    if "docs.google.com" not in parsed.netloc:
        raise SheetError(
            "That doesn't look like a Google Sheets link. Use File > Share > "
            "Publish to web, and paste the link it gives you."
        )

    query = parse_qs(parsed.query)
    gid = query.get("gid", ["0"])[0]

    if "output=csv" in raw_url:
        return raw_url

    if "/pubhtml" in raw_url or "/pub" in raw_url:
        base = raw_url.split("/pubhtml")[0].split("/pub")[0]
        return f"{base}/pub?output=csv&gid={gid}"

    if "/edit" in raw_url:
        raise SheetError(
            "This looks like a normal edit link, not a published one. In the "
            "sheet, use File > Share > Publish to web and paste that link "
            "instead (Awqaat MT never uses your edit link)."
        )

    raise SheetError(
        "Couldn't recognise that as a Google Sheets publish link. Use "
        "File > Share > Publish to web and paste the link it gives you."
    )


async def fetch_csv_text(session: aiohttp.ClientSession, csv_url: str) -> str:
    """Fetch the raw CSV text for a published sheet."""
    try:
        async with session.get(csv_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 401 or resp.status == 403:
                raise SheetAuthError(
                    "The sheet refused access. Make sure it's published to the "
                    "web (not just shared) and set to 'Anyone with the link'."
                )
            if resp.status != 200:
                raise SheetError(f"Sheet fetch failed with HTTP {resp.status}.")
            text = await resp.text()
    except aiohttp.ClientError as err:
        raise SheetError(f"Couldn't reach the sheet: {err}") from err

    if "<html" in text[:200].lower():
        raise SheetAuthError(
            "Got an HTML page instead of CSV data. Make sure the sheet is "
            "published to the web as CSV (File > Share > Publish to web > "
            "select CSV), not just shared with a person or as pubhtml."
        )
    return text


def parse_headers(csv_text: str) -> list[str]:
    """Return the header row of the sheet, in order."""
    reader = csv.reader(io.StringIO(csv_text))
    try:
        headers = next(reader)
    except StopIteration as err:
        raise SheetError("The sheet appears to be empty.") from err
    headers = [h.strip() for h in headers if h.strip()]
    if not headers:
        raise SheetError("Couldn't find any column headers in the sheet.")
    return headers


def parse_rows(csv_text: str) -> list[dict[str, str]]:
    """Parse all data rows into a list of dicts keyed by header."""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
    return rows


def parse_sheet_date(raw: str) -> date | None:
    """Parse a date cell using known formats. Returns None if unparseable."""
    raw = raw.strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    # Last resort: ISO-ish prefix (e.g. sheet gives a datetime string)
    match = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse_sheet_time(raw: str) -> tuple[int, int] | None:
    """Parse a time cell (HH:MM or HH:MM:SS) into (hour, minute). None if blank/unparseable."""
    raw = raw.strip()
    if not raw:
        return None
    for fmt in _TIME_FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.hour, parsed.minute
        except ValueError:
            continue
    return None
