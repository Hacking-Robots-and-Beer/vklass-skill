# vklass-skill

Vklass integration in two flavours:

| | Location | Use case |
|-|----------|----------|
| **OpenClaw skill** | `skills/vklass/` | Ask your AI assistant for today's schedule |
| **Home Assistant integration** | `homeassistant/custom_components/vklass/` | Sensors + automations in HA |

[Vklass](https://vklass.se) is a Swedish school communication platform used by guardians to follow their children's schedule, meals, and school messages.

---

## OpenClaw skill

### What it does

Authenticates with Vklass and returns a formatted summary of:
- Today's lunch menu per child
- Gym/PE class indicator (today / tomorrow / none)
- Full day schedule as a timeline
- Unread notification count

### Requirements

- `python3`
- `pip install requests beautifulsoup4`
- Env vars `VKLASS_USERNAME` and `VKLASS_PASSWORD`

### Install

Copy (or symlink) `skills/vklass/` into your OpenClaw workspace `skills/` folder:

```bash
cp -r skills/vklass ~/.openclaw/skills/
# or symlink:
ln -s $(pwd)/skills/vklass ~/.openclaw/skills/vklass
```

### Usage

Set credentials and invoke the skill:

```bash
export VKLASS_USERNAME=your@email.se
export VKLASS_PASSWORD=yourpassword

# Test the scraper directly
python3 skills/vklass/vklass.py

# In OpenClaw
/vklass
```

### Manual scraper output

```json
{
  "children": [
    {
      "name": "Alice",
      "meal": "Pasta Bolognese",
      "gymclass": "today",
      "calendar": [
        { "start": "2026-03-10T08:00:00", "end": "2026-03-10T09:00:00", "text": "Svenska" }
      ],
      "notifications": 2
    }
  ]
}
```

---

## Home Assistant integration

### What it does

Creates **4 sensors per child**, refreshed every 30 minutes:

| Sensor | State | Example |
|--------|-------|---------|
| `sensor.vklass_<child>_meal` | Today's lunch | `Pasta Bolognese` |
| `sensor.vklass_<child>_gym_class` | `today` / `tomorrow` / `none` | `today` |
| `sensor.vklass_<child>_notifications` | Unread messages | `3` |
| `sensor.vklass_<child>_schedule` | Events today (count) | `5` |

The `_schedule` sensor also exposes `events` (full sorted list) and `next_event` as attributes.

### Install

**Manual:**

```bash
cp -r homeassistant/custom_components/vklass \
      /path/to/homeassistant/config/custom_components/
```

Then restart Home Assistant.

**HACS:** Add this repo as a custom repository (category: Integration), install *Vklass*, restart.

### Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Vklass**
3. Enter your guardian account username and password
4. One device per child is created automatically

### Example automation — gym bag reminder

```yaml
automation:
  - alias: "Gym bag reminder"
    trigger:
      - platform: time
        at: "07:30:00"
    condition:
      - condition: state
        entity_id: sensor.vklass_alice_gym_class
        state: "today"
    action:
      - service: notify.mobile_app
        data:
          message: "Alice has gym today — don't forget the bag!"
```

---

## Auth flow

Both integrations use the same Vklass authentication:

1. `GET https://auth.vklass.se/credentials` — extract `__RequestVerificationToken`
2. `POST https://auth.vklass.se/credentials/signin` — submit credentials, expect `302`
3. Follow redirect to `custodian.vklass.se` to establish session cookies

All subsequent data is fetched from `custodian.vklass.se`.

---

## Repo structure

```
vklass-skill/
├── skills/
│   └── vklass/
│       ├── SKILL.md        # OpenClaw skill definition
│       └── vklass.py       # Python scraper
└── homeassistant/
    ├── README.md
    └── custom_components/
        └── vklass/
            ├── __init__.py
            ├── manifest.json
            ├── const.py
            ├── coordinator.py
            ├── config_flow.py
            ├── sensor.py
            └── translations/
                └── en.json
```
