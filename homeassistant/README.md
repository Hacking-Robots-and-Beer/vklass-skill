# Vklass — Home Assistant Custom Integration

Fetches today's lunch menu, gym class indicator, schedule, unread notifications,
and latest weekly letter from the [Vklass](https://vklass.se) school system.

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

For each child the integration creates sensors:

| Entity | State | Notes |
|--------|-------|-------|
| `sensor.vklass_<child>_meal` | Today's lunch | Pipe-separated menu items; `"Not listed"` if unavailable |
| `sensor.vklass_<child>_gym_class` | `today` / `tomorrow` / `none` | Keyword match on calendar events |
| `sensor.vklass_<child>_notifications` | Unread count | Integer |
| `sensor.vklass_<child>_schedule` | Event count today | Full list in `events` attribute |

The `schedule` sensor exposes two extra attributes:
- `events` — list of `{start, end, text}` sorted by start time
- `next_event` — the next upcoming event today, or `null`

Additional attributes on each child device:
- `report_date` — date of the latest weekly letter
- `upcoming` — list of upcoming tests/assignments from the latest weekly letter
- `ical_url` — iCal subscription URL for the school calendar

## iCal subscription

The `ical_url` attribute contains a direct link to the school's calendar feed:

```
https://cal.vklass.se/<UUID>.ics?includelectures=false&custodian=true
```

Import this into Google Calendar, Apple Calendar, or any iCal-compatible app
to get school events (sport days, term dates, etc.) without individual lessons.

## Update interval

Data is refreshed every **30 minutes**.

## Example automations

### Gym bag reminder

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

### Lunch menu notification

```yaml
automation:
  - alias: "Daily lunch menu"
    trigger:
      - platform: time
        at: "10:30:00"
    action:
      - service: notify.mobile_app
        data:
          message: "Today's lunch: {{ states('sensor.vklass_alice_meal') }}"
```

### Upcoming test alert

```yaml
automation:
  - alias: "Upcoming test alert"
    trigger:
      - platform: time
        at: "18:00:00"
        weekday: sun
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.vklass_alice_schedule', 'upcoming') | length > 0 }}"
    action:
      - service: notify.mobile_app
        data:
          message: >
            Upcoming this week:
            {{ state_attr('sensor.vklass_alice_schedule', 'upcoming') | join(', ') }}
```
