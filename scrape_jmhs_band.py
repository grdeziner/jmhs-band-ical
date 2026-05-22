#!/usr/bin/env python3
"""
JMHS Band Calendar Scraper
Fetches events from jmhsband.org DPCalendar API and generates an .ics file.
Designed to run daily via GitHub Actions to keep the calendar up to date.
"""

import requests
import re
import hashlib
from datetime import datetime, timedelta
from html import unescape


# ââ Configuration ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

BASE_URL = "https://jmhsband.org/index.php"
CALENDAR_IDS = [133, 104, 147, 137, 103, 80, 81, 84, 73, 83, 85]
ITEM_ID = 605
MONTHS_AHEAD = 6  # How many months ahead to fetch
MONTHS_BEHIND = 1  # How many months behind to include (catch recent changes)
OUTPUT_FILE = "jmhs_band_calendar.ics"
CALENDAR_NAME = "JMHS Band"
TIMEZONE = "America/New_York"


# ââ Fetch events from DPCalendar API ââââââââââââââââââââââââââââââââââââââââââ

def fetch_events(start_date: str, end_date: str) -> list:
    """Fetch events from the DPCalendar JSON API for a given date range."""
    params = {
        "option": "com_dpcalendar",
        "view": "events",
        "format": "raw",
        "limit": "0",
        "Itemid": str(ITEM_ID),
        "filter[search]": "",
        "filter[location]": "",
        "filter[radius]": "20",
        "filter[length-type]": "m",
        "filter[created_by]": "",
        "list[start-date]": start_date,
        "list[end-date]": end_date,
    }

    # Add each calendar ID
    for cal_id in CALENDAR_IDS:
        params.setdefault("filter[calendars][]", [])
    # requests needs list values passed differently
    param_list = []
    for key, val in params.items():
        param_list.append((key, val))
    for cal_id in CALENDAR_IDS:
        param_list.append(("filter[calendars][]", str(cal_id)))
    # Also add the special -2 filter that the site uses
    param_list.append(("filter[calendars][]", "-2"))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://jmhsband.org/index.php/calendar",
    }
    response = requests.get(BASE_URL, params=param_list, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()
    if not data.get("success"):
        raise RuntimeError(f"API returned error: {data.get('message', 'Unknown error')}")

    return data.get("data", {}).get("events", [])


def fetch_all_events() -> list:
    """Fetch events across a wide date range, deduplicating by event ID."""
    now = datetime.now()
    start = now - timedelta(days=30 * MONTHS_BEHIND)
    end = now + timedelta(days=30 * MONTHS_AHEAD)

    start_str = start.strftime("%Y-%m-%dT00:00:00")
    end_str = end.strftime("%Y-%m-%dT00:00:00")

    print(f"Fetching events from {start_str} to {end_str}...")
    events = fetch_events(start_str, end_str)
    print(f"Fetched {len(events)} events.")

    # Deduplicate by event ID
    seen = set()
    unique = []
    for event in events:
        eid = event.get("id")
        if eid not in seen:
            seen.add(eid)
            unique.append(event)

    return unique


# ââ Parse and clean event data ââââââââââââââââââââââââââââââââââââââââââââââââ

def strip_html(html: str) -> str:
    """Remove HTML tags and decode entities."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", "", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_category(description_html: str) -> str:
    """Extract the calendar category like [Rehearsal] from the description HTML."""
    if not description_html:
        return ""
    match = re.search(r"\[([^\]]+)\]", description_html)
    return match.group(1) if match else ""


def make_uid(event_id: int) -> str:
    """Generate a stable UID for an event."""
    return f"jmhs-band-{event_id}@jmhsband.org"


def escape_ical(text: str) -> str:
    """Escape text for iCalendar fields."""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    return text


def fold_line(line: str) -> str:
    """Fold long lines per RFC 5545 (max 75 octets per line)."""
    result = []
    while len(line.encode("utf-8")) > 75:
        # Find a safe split point (at 75 bytes)
        encoded = line.encode("utf-8")
        cut = 75
        # Don't split in the middle of a multi-byte character
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        result.append(encoded[:cut].decode("utf-8"))
        line = " " + encoded[cut:].decode("utf-8")
    result.append(line)
    return "\r\n".join(result)


# ââ Generate iCalendar output âââââââââââââââââââââââââââââââââââââââââââââââââ

def format_datetime(dt_str: str, all_day: bool) -> tuple:
    """
    Format a datetime string for iCalendar.
    Returns (param, value) where param is the DTSTART/DTEND parameter string.
    """
    if all_day:
        # All-day events: "2026-05-15" â "20260515"
        dt = datetime.strptime(dt_str[:10], "%Y-%m-%d")
        return "VALUE=DATE", dt.strftime("%Y%m%d")
    else:
        # Timed events: "2026-05-04T15:30:00" â "20260504T153000"
        dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
        return f"TZID={TIMEZONE}", dt.strftime("%Y%m%dT%H%M%S")


def event_to_vevent(event: dict) -> str:
    """Convert a DPCalendar event dict to a VEVENT string."""
    lines = []
    lines.append("BEGIN:VEVENT")

    uid = make_uid(event["id"])
    lines.append(f"UID:{uid}")

    # Timestamps
    now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines.append(f"DTSTAMP:{now_stamp}")

    all_day = event.get("allDay", False)

    # DTSTART
    start_str = event.get("start", "")
    if start_str:
        param, value = format_datetime(start_str, all_day)
        lines.append(f"DTSTART;{param}:{value}")

    # DTEND
    end_str = event.get("end", "")
    if end_str:
        if all_day:
            # iCal all-day DTEND is exclusive, so add 1 day
            dt = datetime.strptime(end_str[:10], "%Y-%m-%d") + timedelta(days=1)
            lines.append(f"DTEND;VALUE=DATE:{dt.strftime('%Y%m%d')}")
        else:
            param, value = format_datetime(end_str, False)
            lines.append(f"DTEND;{param}:{value}")
    elif not all_day and start_str:
        # No end time â default to 1 hour after start
        dt = datetime.strptime(start_str[:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=1)
        lines.append(f"DTEND;TZID={TIMEZONE}:{dt.strftime('%Y%m%dT%H%M%S')}")

    # Summary (title)
    title = event.get("title", "Untitled")
    lines.append(f"SUMMARY:{escape_ical(title)}")

    # Category from description HTML
    category = extract_category(event.get("description", ""))
    if category:
        lines.append(f"CATEGORIES:{escape_ical(category)}")

    # Description â strip HTML to plain text
    desc_html = event.get("description", "")
    desc_text = strip_html(desc_html)
    if desc_text:
        lines.append(f"DESCRIPTION:{escape_ical(desc_text)}")

    # Location
    location = event.get("location", "")
    if isinstance(location, list):
        # Location is sometimes an empty array
        location = ""
    if location:
        lines.append(f"LOCATION:{escape_ical(str(location))}")

    # URL
    url = event.get("url", "")
    if url:
        if url.startswith("/"):
            url = f"https://jmhsband.org{url}"
        lines.append(f"URL:{url}")

    # Omit per-event COLOR so all events use the calendar's default color.
    # This lets the subscriber control the color in their calendar app.

    lines.append("END:VEVENT")
    return "\r\n".join(fold_line(line) for line in lines)


def generate_vtimezone() -> str:
    """Generate a VTIMEZONE component for America/New_York."""
    return "\r\n".join([
        "BEGIN:VTIMEZONE",
        "TZID:America/New_York",
        "BEGIN:STANDARD",
        "DTSTART:19701101T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
        "TZOFFSETFROM:-0400",
        "TZOFFSETTO:-0500",
        "TZNAME:EST",
        "END:STANDARD",
        "BEGIN:DAYLIGHT",
        "DTSTART:19700308T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
        "TZOFFSETFROM:-0500",
        "TZOFFSETTO:-0400",
        "TZNAME:EDT",
        "END:DAYLIGHT",
        "END:VTIMEZONE",
    ])


def generate_ical(events: list) -> str:
    """Generate a complete iCalendar document from a list of events."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//JMHS Band Calendar Scraper//EN",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        "X-WR-TIMEZONE:America/New_York",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALDESC:Auto-generated calendar for {CALENDAR_NAME}. Updated daily.",
        # Force calendar apps to refresh more frequently
        "REFRESH-INTERVAL;VALUE=DURATION:P1D",
        "X-PUBLISHED-TTL:PT12H",
    ]

    header = "\r\n".join(lines)
    timezone = generate_vtimezone()
    vevents = "\r\n".join(event_to_vevent(e) for e in events)
    footer = "END:VCALENDAR"

    return f"{header}\r\n{timezone}\r\n{vevents}\r\n{footer}\r\n"


# ââ Main ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def main():
    events = fetch_all_events()

    if not events:
        print("Warning: No events found. Writing empty calendar.")

    ical_content = generate_ical(events)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(ical_content)

    print(f"Written {len(events)} events to {OUTPUT_FILE}")
    print(f"File size: {len(ical_content)} bytes")


if __name__ == "__main__":
    main()
