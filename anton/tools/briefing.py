"""
Briefing tools — morning/daily briefing assembled from weather, calendar, Gmail, and news.

Calls each source concurrently via asyncio.gather; any individual failure is skipped
gracefully so the rest of the briefing still delivers.
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date as date_cls
from zoneinfo import ZoneInfo

import httpx

from anton.config import config

_IST = ZoneInfo(config.TIMEZONE)

_NEWS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
]


# ---------------------------------------------------------------------------
# Ordinal suffix helper
# ---------------------------------------------------------------------------

def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


# ---------------------------------------------------------------------------
# Individual async fetchers — each returns a formatted string or None on failure
# ---------------------------------------------------------------------------

async def _fetch_weather() -> str | None:
    if not config.OPENWEATHER_API_KEY:
        return None
    city = config.HOME_CITY
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": config.OPENWEATHER_API_KEY, "units": "metric"},
            )
        if r.status_code != 200:
            return None
        data = r.json()
        temp = round(data["main"]["temp"])
        condition = data["weather"][0]["description"].capitalize()
        return f"{temp}°C in {data['name']}, {condition}."
    except Exception:
        return None


async def _fetch_schedule() -> str | None:
    try:
        from googleapiclient.discovery import build
        from anton.google_auth import get_credentials

        def _call():
            now = datetime.now(_IST)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            svc = build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)
            result = svc.events().list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return result.get("items", [])

        events = await asyncio.to_thread(_call)
        if not events:
            return "No events scheduled today."

        count = len(events)
        first = events[0]
        start_raw = first.get("start", {})
        if "dateTime" in start_raw:
            dt = datetime.fromisoformat(start_raw["dateTime"]).astimezone(_IST)
            time_str = dt.strftime("%-I:%M %p")
        else:
            time_str = "all day"

        title = first.get("summary", "(no title)")
        return f"{count} event{'s' if count != 1 else ''} today. First up — {title} at {time_str}."
    except Exception:
        return None


async def _fetch_emails() -> str | None:
    try:
        from googleapiclient.discovery import build
        from anton.google_auth import get_credentials

        def _call():
            svc = build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)
            lst = svc.users().messages().list(
                userId="me", labelIds=["INBOX", "UNREAD"], maxResults=3
            ).execute()
            messages = lst.get("messages", [])
            if not messages:
                return []
            results = []
            for msg in messages:
                detail = svc.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject"],
                ).execute()
                headers = {h["name"].lower(): h["value"]
                           for h in detail.get("payload", {}).get("headers", [])}
                sender = headers.get("from", "Unknown")
                sender_name = sender.split("<")[0].strip().strip('"') or sender
                results.append({"from": sender_name, "subject": headers.get("subject", "(no subject)")})
            return results

        emails = await asyncio.to_thread(_call)
        if not emails:
            return "No unread emails."

        count = len(emails)
        top = emails[0]
        return (
            f"{count} unread email{'s' if count != 1 else ''}. "
            f"Top one from {top['from']} — {top['subject']}."
        )
    except Exception:
        return None


async def _fetch_news() -> str | None:
    try:
        headlines = []
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            tasks = [client.get(url, headers={"User-Agent": "Anton-AI/1.0"}) for url in _NEWS_FEEDS]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, Exception) or resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:3]:
                title = item.findtext("title", "").strip()
                if title:
                    headlines.append(title)
            if len(headlines) >= 3:
                break

        if not headlines:
            return None

        lines = [f"  {i + 1}. {h}" for i, h in enumerate(headlines[:3])]
        return "\n".join(lines)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp):

    @mcp.tool()
    async def morning_briefing() -> str:
        """
        Deliver a full morning briefing: weather, calendar, emails, and top news — all at once.
        Use when the user says 'Good morning', 'Brief me', 'Morning briefing',
        'What's on today?', 'Catch me up', etc.
        """
        now = datetime.now(_IST)
        hour = now.hour

        greeting = (
            "Good morning"   if 5  <= hour < 12 else
            "Good afternoon" if 12 <= hour < 17 else
            "Good evening"   if 17 <= hour < 21 else
            "Good evening"
        )

        day_name   = now.strftime("%A")
        day_num    = _ordinal(now.day)
        month_year = now.strftime("%B, %I:%M %p IST")
        time_line  = f"It's {day_name}, {day_num} {month_year}."

        # Fire all four sources concurrently
        weather, schedule, emails, news = await asyncio.gather(
            _fetch_weather(),
            _fetch_schedule(),
            _fetch_emails(),
            _fetch_news(),
        )

        sections = [f"{greeting}, sir. {time_line}"]

        if weather:
            sections.append(f"\nWeather: {weather}")

        if schedule:
            sections.append(f"\nCalendar: {schedule}")
        else:
            sections.append("\nCalendar: Your schedule is clear today, sir.")

        if emails:
            sections.append(f"\nEmails: {emails}")
        else:
            sections.append("\nEmails: Inbox is clear, sir.")

        if news:
            sections.append(f"\nTop headlines:\n{news}")

        if 5 <= hour < 12:
            closing = "Have a productive day, sir."
        elif 12 <= hour < 17:
            closing = "Have a great afternoon, sir."
        elif 17 <= hour < 21:
            closing = "Have a good evening, sir."
        else:
            closing = "Get some rest when you can, sir."
        sections.append(f"\n{closing}")

        return "\n".join(sections)
