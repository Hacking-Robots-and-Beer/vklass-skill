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
        ├── sensor.py        # 4 sensors per child
        └── translations/en.json
```

## Vklass auth flow

1. `GET https://auth.vklass.se/credentials` → extract `__RequestVerificationToken`
2. `POST https://auth.vklass.se/credentials/signin` → expect 302
3. Follow redirect to `custodian.vklass.se` to establish session cookies

## Endpoints

All on `https://custodian.vklass.se`:
- `GET /Home` — student cards (names, meals)
- `POST /Events/FullCalendar` body `{studentId, start, end}` — calendar events
- `GET /Account/Scoreboard` — notification counts

## Sensors (per child)

| Sensor | State |
|--------|-------|
| `_meal` | Today's lunch text |
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
