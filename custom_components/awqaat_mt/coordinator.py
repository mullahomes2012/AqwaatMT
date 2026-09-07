"""Coordinator for Awqaat MT."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_COLUMNS, CONF_DATE_COLUMN, CONF_SHEET_URL, MAX_FALLBACK_DAYS
from .sheet_client import (
    SheetError,
    fetch_csv_text,
    normalize_to_csv_url,
    parse_rows,
    parse_sheet_date,
    parse_sheet_time,
)

_LOGGER = logging.getLogger(__name__)


class AwqaatCoordinator(DataUpdateCoordinator):
    """Fetches the sheet on demand (midnight + manual) and resolves today's values."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"awqaat_mt_{entry.entry_id}",
            update_interval=None,  # only midnight + manual trigger, never polled
        )
        self.entry = entry
        self._session = None

    @property
    def config_columns(self) -> dict:
        return self.entry.data.get(CONF_COLUMNS, {})

    async def _async_update_data(self) -> dict:
        """Fetch the sheet and compute today's resolved values."""
        import aiohttp

        sheet_url = self.entry.data[CONF_SHEET_URL]
        date_column = self.entry.data.get(CONF_DATE_COLUMN)

        async with aiohttp.ClientSession() as session:
            try:
                csv_url = normalize_to_csv_url(sheet_url)
                csv_text = await fetch_csv_text(session, csv_url)
                rows = parse_rows(csv_text)
            except SheetError as err:
                raise UpdateFailed(str(err)) from err

        if not rows:
            raise UpdateFailed("Sheet had no data rows.")

        if date_column is None or date_column not in rows[0]:
            raise UpdateFailed(
                f"Date column '{date_column}' not found in the sheet anymore."
            )

        # Build date -> row map
        by_date: dict = {}
        for row in rows:
            row_date = parse_sheet_date(row.get(date_column, ""))
            if row_date is not None:
                by_date[row_date] = row

        if not by_date:
            raise UpdateFailed("Couldn't parse any dates from the sheet's date column.")

        today = dt_util.now().date()
        active_date = today
        active_row = by_date.get(today)

        if active_row is None:
            # Fall back to the most recent past date within MAX_FALLBACK_DAYS
            for delta in range(1, MAX_FALLBACK_DAYS + 1):
                candidate = today - timedelta(days=delta)
                if candidate in by_date:
                    active_date = candidate
                    active_row = by_date[candidate]
                    break

        if active_row is None:
            raise UpdateFailed(
                f"No row for today ({today.isoformat()}) and no usable row in the "
                f"previous {MAX_FALLBACK_DAYS} days."
            )

        values: dict[str, datetime | None] = {}
        for column, cfg in self.config_columns.items():
            if not cfg.get("enabled"):
                continue
            raw = active_row.get(column, "")
            parsed_time = parse_sheet_time(raw)
            if parsed_time is None:
                values[column] = None
                continue
            hour, minute = parsed_time
            # Always anchor to TODAY's date, so the sensor fires as a trigger
            # today even when the value came from a fallback row.
            naive = datetime.combine(today, datetime.min.time()).replace(
                hour=hour, minute=minute
            )
            values[column] = dt_util.as_local(naive)

        return {
            "values": values,
            "active_date": active_date,
            "is_fallback": active_date != today,
            "last_updated": dt_util.now(),
        }
