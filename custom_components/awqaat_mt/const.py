"""Constants for Awqaat MT."""

DOMAIN = "awqaat_mt"

CONF_NAME = "name"
CONF_SHEET_URL = "sheet_url"
CONF_COLUMNS = "columns"  # dict[str, dict] -> {header: {"enabled": bool, "friendly_name": str}}
CONF_DATE_COLUMN = "date_column"

ATTR_SOURCE_DATE = "source_date"
ATTR_SHEET_HEADER = "sheet_header"

DEFAULT_NAME = "Awqaat MT"

# How many days back we're willing to look for a usable fallback row
MAX_FALLBACK_DAYS = 30
