# vklass-skill

OpenClaw skill + Home Assistant custom integration for the [Vklass](https://vklass.se) Swedish school system.

## Repo structure

```
vklass-skill/
├── skills/vklass/          # OpenClaw skill
│   ├── SKILL.md            # Skill definition / runbook
│   └── vklass.py           # CLI scraper (python3, requests, beautifulsoup4)
└── homeassistant/
    ├── README.md            # Install instructions
    └── custom_components/vklass/
        ├── __init__.py      # Entry setup/teardown
        ├── manifest.json
        ├── const.py
        ├── coordinator.py   # Async aiohttp scraper + DataUpdateCoordinator
        ├── config_flow.py   # UI config flow
        ├── sensor.py        # sensors per child
        └── translations/en.json
```

## Vklass auth flow

1. `GET https://auth.vklass.se/credentials` → extract `__RequestVerificationToken`
2. `POST https://auth.vklass.se/credentials/signin` with credentials + token, `allow_redirects=True`
3. Redirects: `/process` → `custodian.vklass.se` — sets cookies `vhvklass.ASPXAUTH`, `se.vklass.authentication`, `vk.vh.localization`

## Endpoints

All on `https://custodian.vklass.se`:

| Method | Path | Purpose | Notes |
|--------|------|---------|-------|
| `GET` | `/Absence/Notify` | Ward IDs + full names | JSON blob in server-rendered HTML: `"fullName":"Sam",...,"value":"348307"` |
| `GET` | `/Home/Welcome` | Student cards with today's meal | `div.vk-student-card` → `.vk-student-card-header__text` (name), `div[data-vk-first-day=true] .vk-student-card__day__food li` (meal items) |
| `POST` | `/Events/FullCalendar` | Calendar events | Form body: `{students, start, end}` with timezone-aware ISO dates; returns JSON array |
| `GET` | `/Account/Scoreboard` | Notification count | Returns `{"notifications": N, "messages": N}` |
| `GET` | `/WeeklyReports/Archive/` | Weekly letters + iCal URLs | Headers: `X-Requested-With: Fetch`, `vk-client-has-tracking-detail: True`; `vkau-expansion-panel` elements, newest first |
| `GET` | `/StudyOverview/Student/{id}` | Study overview shell + school ID | Aurelia SPA; extract school ID from `<select id="SchoolId">` selected option |
| `GET` | `/StudyOverview/Courses/{id}?school={school_id}` | Subject list with judgements | JSON blob in `enhanceServerHtml('studyoverview-courses', '', 'JSON', ...)` script; `items` (active) + `inactiveItems` |

## Data per child

| Field | Source | Notes |
|-------|--------|-------|
| `name` | `/Home/Welcome` `.vk-student-card-header__text` | Short first name |
| `meal` | `/Home/Welcome` `.vk-student-card__day__food` | Today's items joined with ` \| ` |
| `gymclass` | Calendar events keyword match | `today` / `tomorrow` / `none` |
| `calendar` | `/Events/FullCalendar` | 2-day window from today |
| `notifications` | `/Account/Scoreboard` | `.notifications` key |
| `report_date` | `/WeeklyReports/Archive/` | Latest weekly letter date |
| `upcoming` | `/WeeklyReports/Archive/` `section.events li` | Tests, homework next week |
| `ical_url` | `/WeeklyReports/Archive/` | Per-school iCal feed (without lectures) |
| `study_overview` | `/StudyOverview/Student/{id}` | List of subject dicts (keys vary by HTML structure) |

## Weekly reports endpoint detail

- Each `vkau-expansion-panel` = one weekly letter
- Panels are **newest first** — first match per student name = most recent
- Student name in `vkau-icon-badge[text]`, date in `vkau-icon-badge[secondary-text]`
- Upcoming assignments in `section.events li`
- iCal link matched by `cal.vklass.se` + `includelectures=false` in href

## SPA notes (Aurelia)

- `/Home` is a full Aurelia SPA — student cards are NOT server-rendered there
- `/Home/Welcome` IS server-rendered with student cards and meal data
- `/Absence/Notify` IS server-rendered with all ward IDs/names (67KB page)
- Unknown routes with `X-Requested-With: XMLHttpRequest` return 404

## Sensors (per child)

| Sensor | State |
|--------|-------|
| `_meal` | Today's lunch items (pipe-separated) |
| `_gym_class` | `today` / `tomorrow` / `none` |
| `_notifications` | Unread count (int) |
| `_schedule` | Event count; `events` + `next_event` in attributes |

## OpenClaw skill

- Env vars: `VKLASS_USERNAME`, `VKLASS_PASSWORD`
- Invoke: `/vklass` in OpenClaw
- Runs `python3 skills/vklass/vklass.py`, prints JSON, formats summary

## Python deps (scraper / HA)

```
requests
beautifulsoup4
```
HA uses `aiohttp` (built-in) + `beautifulsoup4` (declared in `manifest.json`).
