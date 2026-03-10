---
name: vklass
description: Fetch today's school schedule, meals, and calendar events from the Vklass school system.
metadata: {"openclaw":{"emoji":"🏫","requires":{"bins":["python3"],"env":["VKLASS_USERNAME","VKLASS_PASSWORD"]}}}
---

## What it does

Authenticates with the Vklass Swedish school system (https://vklass.se) and returns:
- Today's lunch/meal for each child
- Any gym/PE class today or tomorrow
- Today's full calendar (lessons, events)
- Unread notification count

Data is fetched live from `custodian.vklass.se` on every invocation. Nothing is cached.

## Inputs

| Source | Name | Required | Description |
|--------|------|----------|-------------|
| env | `VKLASS_USERNAME` | yes | Vklass login username (guardian account) |
| env | `VKLASS_PASSWORD` | yes | Vklass login password |

Credentials must be set as environment variables before invoking this skill. They are never stored in chat output.

## Workflow

1. **Verify env vars** — check that `VKLASS_USERNAME` and `VKLASS_PASSWORD` are set. If either is missing, abort immediately with:
   > "Vklass credentials not configured. Please set VKLASS_USERNAME and VKLASS_PASSWORD environment variables."

2. **Run scraper** — find this skill's directory and execute:
   ```bash
   python3 "$SKILL_DIR/vklass.py"
   ```
   Credentials are picked up automatically from the environment.

3. **Parse JSON output** — the script prints a single JSON object to stdout:
   ```json
   {
     "children": [
       {
         "name": "...",
         "meal": "...",
         "gymclass": "today|tomorrow|none",
         "calendar": [{"start": "ISO", "end": "ISO", "text": "..."}],
         "notifications": 0
       }
     ]
   }
   ```
   If the top-level key is `"error"`, treat it as a failure (see Failure handling).

4. **Format summary** — present the data as a human-readable summary (see Output format).

## Output format

For each child, produce a section like:

```
🏫 Vklass — [Child Name]

🍽️  Lunch: [meal text, or "Not listed" if empty]
🏃  Gym class: Today / Tomorrow / None today
📅  Today's schedule:
    09:00–10:00  Swedish
    10:15–11:00  Math
    ...          (sorted by start time; omit if empty)
🔔  Notifications: [count] unread
```

- Sort calendar events by `start` time ascending.
- Use 24h HH:MM format for times. Strip the date part from ISO timestamps.
- If `calendar` is empty, write "No events scheduled today."
- If `notifications` is 0, omit the notifications line.
- Separate multiple children with a blank line and a `---` divider.

## Guardrails

- **Read-only** — this skill never modifies any data in Vklass.
- **No credential leakage** — never echo, log, or include credentials in the chat summary.
- **No fabrication** — if a field is missing or empty, say so. Never invent schedule data.
- **Single source of truth** — all data comes directly from the scraper output. Do not supplement with guesses.

## Failure handling

| Scenario | Action |
|----------|--------|
| Missing env vars | Abort before running the script; show the message from step 1 |
| Auth failure (HTTP error / "Authentication failed") | Show the raw error message and advise: "Check your VKLASS_USERNAME and VKLASS_PASSWORD." |
| `python3` not found | Advise: "python3 is required. Install it with your package manager." |
| Missing Python deps | The script self-reports: "Run: pip install requests beautifulsoup4" |
| Empty `children` list | Report: "Authenticated successfully but found no children in the account." |
| Any other exception | Show the error text verbatim; do not retry automatically. |
