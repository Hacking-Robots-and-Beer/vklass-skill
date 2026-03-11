#!/usr/bin/env python3
"""
Vklass scraper — fetches schedule, weekly reports, and notifications.

Usage:
    python vklass.py [--username USERNAME] [--password PASSWORD]

Credentials are read from CLI args or env vars VKLASS_USERNAME / VKLASS_PASSWORD.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(json.dumps({"error": f"Missing dependency: {e}. Run: pip install requests beautifulsoup4"}))
    sys.exit(1)

AUTH_BASE = "https://auth.vklass.se"
CUSTODIAN_BASE = "https://custodian.vklass.se"


def get_verification_token(session: requests.Session) -> str:
    resp = session.get(f"{AUTH_BASE}/credentials", timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    if not token_input:
        raise ValueError("Could not find __RequestVerificationToken in login page")
    return token_input["value"]


def authenticate(session: requests.Session, username: str, password: str) -> None:
    token = get_verification_token(session)
    resp = session.post(
        f"{AUTH_BASE}/credentials/signin",
        data={
            "username": username,
            "password": password,
            "__RequestVerificationToken": token,
        },
        allow_redirects=True,
        timeout=15,
    )
    if resp.status_code not in (200, 302):
        raise ValueError(f"Authentication failed (HTTP {resp.status_code})")


def parse_students(session: requests.Session) -> list[dict]:
    # Absence/Notify: server-rendered JSON blob with all ward IDs and names.
    # Pattern: "fullName":"Sam","disabled":false,...,"value":"348307"
    resp = session.get(f"{CUSTODIAN_BASE}/Absence/Notify", timeout=15)
    resp.raise_for_status()
    id_html = resp.text

    id_map: dict[str, str] = {}  # name -> student_id
    seen_ids: set[str] = set()
    for m in re.finditer(r'"fullName"\s*:\s*"([^"]+)"[^}]{0,300}"value"\s*:\s*"(\d{4,})"', id_html):
        name, sid = m.group(1), m.group(2)
        if sid not in seen_ids:
            seen_ids.add(sid)
            id_map[name] = sid

    # Home/Welcome: server-rendered student cards with today's meal.
    # Each card is a div.vk-student-card; name in .vk-student-card-header__text.
    resp2 = session.get(f"{CUSTODIAN_BASE}/Home/Welcome", timeout=15)
    resp2.raise_for_status()
    soup = BeautifulSoup(resp2.text, "html.parser")

    students: list[dict] = []
    seen_names: set[str] = set()

    for card in soup.find_all("div", class_="vk-student-card"):
        name_el = card.find(class_="vk-student-card-header__text")
        name = name_el.get_text(strip=True) if name_el else ""
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        today_div = card.find("div", {"data-vk-first-day": "true"})
        food_div = today_div.find("div", class_="vk-student-card__day__food") if today_div else None
        meal_items = [li.get_text(strip=True) for li in food_div.find_all("li")] if food_div else []
        meal = " | ".join(meal_items)

        # Match name to student ID from Absence/Notify (names may be short/first only)
        sid = id_map.get(name, "")
        if not sid:
            for full_name, full_sid in id_map.items():
                if full_name.startswith(name) or name in full_name:
                    sid = full_sid
                    break

        students.append({"id": sid, "name": name, "meal": meal})

    return students


def fetch_weekly_reports(session: requests.Session) -> dict[str, dict]:
    """Returns latest weekly report per student, keyed by student name."""
    resp = session.get(
        f"{CUSTODIAN_BASE}/WeeklyReports/Archive/",
        headers={"X-Requested-With": "Fetch", "vk-client-has-tracking-detail": "True"},
        timeout=15,
    )
    if not resp.ok:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    reports: dict[str, dict] = {}

    for panel in soup.find_all("vkau-expansion-panel"):
        trigger = panel.find(attrs={"slot": "expansion-panel-trigger"})
        content_div = panel.find("div", class_="legacy-html")
        if not trigger or not content_div:
            continue

        badge = trigger.find("vkau-icon-badge")
        if not badge:
            continue

        name = badge.get("text", "")
        if not name or name in reports:
            continue  # panels are newest-first; skip older reports

        date = badge.get("secondary-text", "")

        upcoming = []
        events_section = content_div.find("section", class_="events")
        if events_section:
            for li in events_section.find_all("li"):
                text = li.get_text(separator=" ", strip=True)
                if text:
                    upcoming.append(text)

        # iCal URL without lectures (cleaner for calendar apps)
        ical_url = ""
        for a in content_div.find_all("a", href=True):
            href = a["href"].strip()
            if "cal.vklass.se" in href and "includelectures=false" in href:
                ical_url = href
                break

        reports[name] = {"date": date, "upcoming": upcoming, "ical_url": ical_url}

    return reports


def fetch_calendar(session: requests.Session, student_id: str) -> list[dict]:
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=2)

    resp = session.post(
        f"{CUSTODIAN_BASE}/Events/FullCalendar",
        data={
            "students": student_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        timeout=15,
    )
    if not resp.ok:
        return []

    try:
        events_raw = resp.json()
    except Exception:
        return []

    events = []
    for ev in events_raw if isinstance(events_raw, list) else []:
        events.append({
            "start": ev.get("start", ""),
            "end": ev.get("end", ""),
            "text": ev.get("title", ev.get("text", ev.get("name", ""))),
        })
    return events


def detect_gymclass(calendar: list[dict]) -> str:
    gym_keywords = ["idrott", "gym", "pe ", "sport", "idrottslektion", "fysik"]
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)

    for ev in calendar:
        text = ev.get("text", "").lower()
        if any(kw in text for kw in gym_keywords):
            start_str = ev.get("start", "")
            try:
                ev_date = datetime.fromisoformat(start_str).date()
                if ev_date == today:
                    return "today"
                if ev_date == tomorrow:
                    return "tomorrow"
            except Exception:
                pass
    return "none"


def _extract_school_id(html: str) -> str:
    """Extract the selected school ID from the StudyOverview/Student page."""
    soup = BeautifulSoup(html, "html.parser")
    sel = soup.find("select", {"id": "SchoolId"})
    if not sel:
        return ""
    opt = sel.find("option", {"selected": True})
    return opt["value"] if opt else ""


def _extract_study_overview_json(html: str) -> list[dict]:
    """Extract course items from the JSON blob embedded in StudyOverview/Courses page."""
    m = re.search(r"enhanceServerHtml\('studyoverview-courses',\s*'',\s*'(\{.*?)\s*',\s*'", html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    items = data.get("items", []) + data.get("inactiveItems", [])
    return [
        {
            "subject": item.get("subjectName", item.get("courseName", "")),
            "course": item.get("courseNameAndCourseCode", ""),
            "judgement": item.get("judgement", ""),
            "grade": item.get("grade"),
            "date": item.get("date", ""),
            "active": item.get("courseActive", True),
        }
        for item in items
    ]


def fetch_study_overview(session: requests.Session, student_id: str) -> list[dict]:
    resp = session.get(f"{CUSTODIAN_BASE}/StudyOverview/Student/{student_id}", timeout=15)
    if not resp.ok:
        return []
    school_id = _extract_school_id(resp.text)
    if not school_id:
        return []
    resp2 = session.get(
        f"{CUSTODIAN_BASE}/StudyOverview/Courses/{student_id}?school={school_id}",
        timeout=15,
    )
    if not resp2.ok:
        return []
    return _extract_study_overview_json(resp2.text)


def fetch_notifications(session: requests.Session) -> int:
    resp = session.get(f"{CUSTODIAN_BASE}/Account/Scoreboard", timeout=15)
    if not resp.ok:
        return 0
    try:
        data = resp.json()
        if isinstance(data, dict):
            return int(data.get("notifications", data.get("unread", data.get("count", 0))))
        if isinstance(data, int):
            return data
    except Exception:
        pass
    return 0


def scrape(username: str, password: str) -> dict:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })

    authenticate(session, username, password)
    students = parse_students(session)
    notifications = fetch_notifications(session)
    reports = fetch_weekly_reports(session)

    children = []
    for student in students:
        student_id = student["id"]
        calendar = fetch_calendar(session, student_id) if student_id else []
        report = reports.get(student["name"], {})
        study_overview = fetch_study_overview(session, student_id) if student_id else []
        children.append({
            "name": student["name"],
            "meal": student["meal"],
            "gymclass": detect_gymclass(calendar),
            "calendar": calendar,
            "notifications": notifications,
            "report_date": report.get("date", ""),
            "upcoming": report.get("upcoming", []),
            "ical_url": report.get("ical_url", ""),
            "study_overview": study_overview,
        })

    return {"children": children}


def main():
    parser = argparse.ArgumentParser(description="Fetch Vklass schedule data")
    parser.add_argument("--username", default=os.environ.get("VKLASS_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("VKLASS_PASSWORD", ""))
    args = parser.parse_args()

    if not args.username or not args.password:
        print(json.dumps({"error": "Missing credentials. Set VKLASS_USERNAME and VKLASS_PASSWORD or pass --username/--password"}))
        sys.exit(1)

    try:
        result = scrape(args.username, args.password)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
