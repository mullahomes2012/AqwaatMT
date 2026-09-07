"""Config flow for Awqaat MT."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_COLUMNS, CONF_DATE_COLUMN, CONF_NAME, CONF_SHEET_URL, DOMAIN
from .sheet_client import (
    SheetError,
    fetch_csv_text,
    normalize_to_csv_url,
    parse_headers,
)

_LOGGER = logging.getLogger(__name__)


class _SheetFlowMixin:
    """Shared steps for the initial config flow and the options (re-map) flow.

    Subclasses provide: self._data (working copy of entry data being built),
    self._headers (list[str] fetched from the sheet), and _finish(data) to
    commit the result (create the entry, or update + reload it).
    """

    _data: dict[str, Any]
    _headers: list[str]

    async def _fetch_headers(self, name: str, raw_url: str) -> dict[str, str] | None:
        """Normalize + fetch the sheet, populate self._headers. Returns an error dict or None."""
        try:
            csv_url = normalize_to_csv_url(raw_url)
            async with aiohttp.ClientSession() as session:
                csv_text = await fetch_csv_text(session, csv_url)
            headers = parse_headers(csv_text)
        except SheetError as err:
            _LOGGER.debug("Sheet fetch/parse failed: %s", err)
            return {"base": "sheet_error", "error_detail": str(err)}

        self._headers = headers
        self._data[CONF_NAME] = name
        self._data[CONF_SHEET_URL] = csv_url
        self._data[CONF_DATE_COLUMN] = headers[0]
        return None

    def _columns_schema(self, defaults: dict[str, bool] | None = None) -> vol.Schema:
        defaults = defaults or {}
        fields = {}
        for header in self._headers[1:]:  # skip the date column
            fields[vol.Optional(header, default=defaults.get(header, False))] = bool
        return vol.Schema(fields)

    def _naming_schema(self, selected: list[str], defaults: dict[str, str] | None = None) -> vol.Schema:
        defaults = defaults or {}
        fields = {}
        for header in selected:
            fields[vol.Optional(header, default=defaults.get(header, header))] = str
        return vol.Schema(fields)


class AwqaatConfigFlow(config_entries.ConfigFlow, _SheetFlowMixin, domain=DOMAIN):
    """Handle a config flow for Awqaat MT (one entry per sheet)."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._headers: list[str] = []
        self._selected: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._fetch_headers(user_input[CONF_NAME], user_input[CONF_SHEET_URL])
            if error is None:
                return await self.async_step_columns()
            errors["base"] = error["base"]
            self._last_error_detail = error.get("error_detail", "")

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_SHEET_URL): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"error_detail": getattr(self, "_last_error_detail", "")},
        )

    async def async_step_columns(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._selected = [h for h, enabled in user_input.items() if enabled]
            if not self._selected:
                return self.async_show_form(
                    step_id="columns",
                    data_schema=self._columns_schema(),
                    errors={"base": "no_columns_selected"},
                )
            return await self.async_step_naming()

        return self.async_show_form(step_id="columns", data_schema=self._columns_schema())

    async def async_step_naming(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            columns = {
                header: {"enabled": True, "friendly_name": friendly_name.strip() or header}
                for header, friendly_name in user_input.items()
            }
            self._data[CONF_COLUMNS] = columns
            await self.async_set_unique_id(f"{self._data[CONF_SHEET_URL]}::{self._data[CONF_NAME]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)

        return self.async_show_form(
            step_id="naming", data_schema=self._naming_schema(self._selected)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "AwqaatOptionsFlow":
        return AwqaatOptionsFlow(config_entry)


class AwqaatOptionsFlow(config_entries.OptionsFlow, _SheetFlowMixin):
    """Re-map columns or rename entities for an existing entry, any time."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._data: dict[str, Any] = dict(config_entry.data)
        self._headers: list[str] = []
        self._selected: list[str] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._fetch_headers(user_input[CONF_NAME], user_input[CONF_SHEET_URL])
            if error is None:
                return await self.async_step_columns()
            errors["base"] = error["base"]
            self._last_error_detail = error.get("error_detail", "")

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self._data.get(CONF_NAME, "")): str,
                vol.Required(CONF_SHEET_URL, default=self._data.get(CONF_SHEET_URL, "")): str,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"error_detail": getattr(self, "_last_error_detail", "")},
        )

    async def async_step_columns(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        existing = self._entry.data.get(CONF_COLUMNS, {})
        current_defaults = {h: cfg.get("enabled", False) for h, cfg in existing.items()}

        if user_input is not None:
            self._selected = [h for h, enabled in user_input.items() if enabled]
            if not self._selected:
                return self.async_show_form(
                    step_id="columns",
                    data_schema=self._columns_schema(current_defaults),
                    errors={"base": "no_columns_selected"},
                )
            return await self.async_step_naming()

        return self.async_show_form(
            step_id="columns", data_schema=self._columns_schema(current_defaults)
        )

    async def async_step_naming(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        existing = self._entry.data.get(CONF_COLUMNS, {})
        name_defaults = {h: cfg.get("friendly_name", h) for h, cfg in existing.items()}

        if user_input is not None:
            columns = {
                header: {"enabled": True, "friendly_name": friendly_name.strip() or header}
                for header, friendly_name in user_input.items()
            }
            self._data[CONF_COLUMNS] = columns
            # Updating entry.data fires the update listener registered in
            # __init__.py, which reloads the entry — no need to do it here too.
            self.hass.config_entries.async_update_entry(self._entry, data=self._data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="naming", data_schema=self._naming_schema(self._selected, name_defaults)
        )
