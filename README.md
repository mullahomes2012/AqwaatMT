# Awqaat MT

A Home Assistant custom integration that turns a published Google Sheet of
prayer/event times into entities you can use in automations.

Built for Masjid Quba's prayer time sheets, but the column mapping is fully
free-form — map any column to any entity name, with as many or as few as
your sheet has (5 prayers, 20 rows, seasonal columns like Taraweeh, whatever
you want).

## What it does

- Add the integration once per sheet (e.g. one entry for "Quba", one for
  "18 Degrees") via **Settings > Devices & services > Add integration**.
- Paste your sheet's **published to web** link (File > Share > Publish to
  web in Google Sheets — not the normal edit/share link).
- Pick which columns become entities, and name each one whatever you like —
  entity names don't have to match the sheet's header text at all.
- Each mapped column becomes a `timestamp` sensor holding today's time for
  that column, ready to use directly as an automation trigger.
- A **Refresh** button entity forces an immediate re-fetch; otherwise the
  sheet is re-read automatically just after local midnight.
- If today's date is missing from the sheet, the most recent past date's row
  is used instead (so entities never go blank from a missed sheet update).
- If a specific cell is blank on an otherwise-present date (e.g. a Taraweeh
  column outside Ramadan), that one entity goes `unavailable` for the day.
- Two diagnostic entities per sheet: **Last updated** and **Active sheet
  date** (handy for spotting a stale or unpublished sheet).
- Re-map columns or rename entities any time from the integration's
  **Configure** (options) screen — no re-adding required.

## Install via HACS

1. HACS > Integrations > ⋮ > Custom repositories > add this repo URL,
   category "Integration".
2. Install **Awqaat MT**, restart Home Assistant.
3. Settings > Devices & services > Add integration > search "Awqaat MT".

## Notes

- Sheet times are read as `HH:MM` (seconds are ignored).
- Entity IDs default to `sensor.<sheet name>_<your entity name>`, e.g.
  `sensor.quba_asr`.
