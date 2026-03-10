# Vklass — Home Assistant Custom Integration

Fetches today's school schedule, lunch menu, gym class indicator, and unread
notifications from the [Vklass](https://vklass.se) school system.

## Installation

### HACS (recommended)
1. Add this repo as a custom repository in HACS (category: Integration).
2. Install **Vklass** from HACS.
3. Restart Home Assistant.

### Manual
1. Copy `custom_components/vklass/` into your HA config folder:
   ```
   <config>/custom_components/vklass/
   ```
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Vklass**.
3. Enter your guardian account username and password.
4. HA will verify the credentials and create one device per child.

## Entities

For each child the integration creates four sensors:

| Entity | State | Notes |
|--------|-------|-------|
| `sensor.vklass_<child>_meal` | Today's lunch text | `"Not listed"` if unavailable |
| `sensor.vklass_<child>_gym_class` | `today` / `tomorrow` / `none` | Based on keyword match in calendar |
| `sensor.vklass_<child>_notifications` | Unread count | Integer |
| `sensor.vklass_<child>_schedule` | Event count today | Full list in `events` attribute |

The `schedule` sensor exposes two extra attributes:
- `events` — list of `{start, end, text}` sorted by start time (HH:MM)
- `next_event` — the next upcoming event today, or `null`

## Update interval

Data is refreshed every **30 minutes**.

## Example automation

Pack gym bag reminder:

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
