"""
Calendar tools — Google Calendar integration via OAuth2.
Requires credentials.json in project root (see anton/google_auth.py).
"""

import asyncio
import logging
import os
import re
import traceback
from datetime import datetime, timedelta, date as date_cls
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from anton.google_auth import get_credentials

logger = logging.getLogger("anton.calendar")

LOCAL_TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Kolkata"))


def _build_service():
    return build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)


def _parse_time_to_24h(t: str) -> str | None:
    """
    Convert any reasonable time string to 24-hour HH:MM.
    Returns None if the string cannot be parsed at all.

    Examples:
      "8pm"     → "20:00"
      "8:30 PM" → "20:30"
      "9 AM"    → "09:00"
      "12:00 AM"→ "00:00"
      "21:00"   → "21:00"
    """
    t = t.strip()

    # Already valid 24-hour HH:MM — fast path
    try:
        return datetime.strptime(t, "%H:%M").strftime("%H:%M")
    except ValueError:
        pass

    # Normalise: collapse multiple spaces, uppercase for strptime
    t_norm = re.sub(r"\s+", " ", t).upper()

    # Try progressively looser 12-hour patterns
    for fmt in ("%I:%M %p", "%I %p", "%I:%M%p", "%I%p"):
        try:
            return datetime.strptime(t_norm, fmt).strftime("%H:%M")
        except ValueError:
            continue

    return None


_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _resolve_date(raw: str) -> str | None:
    """
    Convert natural-language date expressions to YYYY-MM-DD.
    Accepts: YYYY-MM-DD, 'today', 'tomorrow', weekday names ('Friday'),
    'next <weekday>', and 'next week'.
    Returns None if unrecognisable.
    """
    from datetime import date as date_cls

    raw = raw.strip().lower()
    today = date_cls.today()

    if raw == "today":
        return today.isoformat()

    if raw == "tomorrow":
        return (today + timedelta(days=1)).isoformat()

    if raw == "next week":
        return (today + timedelta(weeks=1)).isoformat()

    # "next <weekday>"
    for prefix in ("next ",):
        if raw.startswith(prefix):
            day_name = raw[len(prefix):].strip()
            if day_name in _DAY_NAMES:
                target_weekday = _DAY_NAMES.index(day_name)
                days_ahead = (target_weekday - today.weekday() + 7) % 7 or 7
                return (today + timedelta(days=days_ahead)).isoformat()

    # bare weekday name — resolve to the *next* occurrence (including today)
    if raw in _DAY_NAMES:
        target_weekday = _DAY_NAMES.index(raw)
        days_ahead = (target_weekday - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7  # if today is that weekday, go to next week's occurrence
        return (today + timedelta(days=days_ahead)).isoformat()

    # already YYYY-MM-DD?
    try:
        datetime.strptime(raw, "%Y-%m-%d")
        return raw
    except ValueError:
        pass

    return None


def _format_event(event: dict) -> str:
    """Format a single calendar event into a one-liner."""
    summary = event.get("summary", "(no title)")
    start = event.get("start", {})

    if "dateTime" in start:
        dt = datetime.fromisoformat(start["dateTime"]).astimezone(LOCAL_TZ)
        time_str = dt.strftime("%-I:%M %p")
    else:
        # All-day event
        time_str = "all day"

    location = event.get("location", "")
    location_part = f" @ {location}" if location else ""

    return f"{time_str} — {summary}{location_part}"


def register(mcp):

    @mcp.tool()
    async def get_todays_schedule() -> str:
        """
        Retrieve all events scheduled for today from Google Calendar.
        Use when the user asks 'What's on my calendar today?', 'What do I have today?', etc.
        """
        def _fetch():
            service = _build_service()
            now = datetime.now(LOCAL_TZ)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

            result = service.events().list(
                calendarId="primary",
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return result.get("items", [])

        try:
            events = await asyncio.to_thread(_fetch)
        except FileNotFoundError as e:
            return str(e)
        except Exception as e:
            return f"I couldn't access the calendar, sir. Error: {e}"

        if not events:
            return "Your calendar is clear today, sir. Nothing scheduled."

        count = len(events)
        lines = [f"You have {count} event{'s' if count != 1 else ''} today, sir."]
        for i, event in enumerate(events):
            prefix = "First up" if i == 0 else f"Then"
            lines.append(f"  {prefix} — {_format_event(event)}")

        return "\n".join(lines)

    @mcp.tool()
    async def get_upcoming_events(days: int = 7) -> str:
        """
        Retrieve upcoming calendar events over the next N days (default 7).
        Use when the user asks 'What's coming up?', 'Do I have anything this week?', etc.
        """
        def _fetch():
            service = _build_service()
            now = datetime.now(LOCAL_TZ)
            time_max = now + timedelta(days=days)

            result = service.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return result.get("items", [])

        try:
            events = await asyncio.to_thread(_fetch)
        except FileNotFoundError as e:
            return str(e)
        except Exception as e:
            return f"I couldn't access the calendar, sir. Error: {e}"

        if not events:
            return f"Nothing on the calendar for the next {days} days, sir. You're free."

        today = date_cls.today()
        lines = [f"Upcoming events over the next {days} days, sir:\n"]
        current_day_label = None

        for event in events:
            start = event.get("start", {})
            if "dateTime" in start:
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(LOCAL_TZ)
                event_date = dt.date()
            else:
                event_date = date_cls.fromisoformat(start["date"])

            if event_date == today:
                day_label = "Today"
            elif event_date == today + timedelta(days=1):
                day_label = "Tomorrow"
            else:
                day_label = event_date.strftime("%A, %d %b")

            if day_label != current_day_label:
                lines.append(f"\n{day_label}:")
                current_day_label = day_label

            lines.append(f"  • {_format_event(event)}")

        return "\n".join(lines)

    @mcp.tool()
    async def create_event(
        title: str,
        date: str,
        time: str,
        duration_minutes: int = 60,
    ) -> str:
        """
        Create a new Google Calendar event.

        Parameters:
        - title: event name (e.g. 'Standup', 'Gym', 'Call with Sagar')
        - date: MUST be in YYYY-MM-DD format (e.g. '2026-04-15').
                Natural language like 'tomorrow' or 'Friday' is also accepted and
                will be resolved automatically to the correct YYYY-MM-DD date.
        - time: MUST be in 24-hour HH:MM format — e.g. '09:00', '14:30', '21:00'.
                NEVER pass AM/PM strings like '9:00 PM' or '9 AM'. Convert first:
                  9:00 AM  →  '09:00'
                  9:00 PM  →  '21:00'
                 12:00 PM  →  '12:00'
                 12:00 AM  →  '00:00'
        - duration_minutes: length in minutes (default 60)

        Examples:
          "Standup at 9pm tomorrow"   → date='2026-04-15', time='21:00'
          "Gym on Friday at 7am"      → date='2026-04-17', time='07:00'
          "Lunch meeting at 1:30pm"   → date='2026-04-14', time='13:30'

        Use when the user says 'Add a meeting', 'Schedule X', 'Put X on my calendar', etc.
        """
        logger.info(
            "create_event received — title=%r  date=%r  time=%r  duration=%r",
            title, date, time, duration_minutes,
        )

        if not 1 <= duration_minutes <= 1440:
            return "Duration must be between 1 and 1440 minutes (24 hours), sir."

        # --- Resolve natural-language dates to YYYY-MM-DD ---
        resolved_date = _resolve_date(date)
        if resolved_date is None:
            logger.warning("create_event: unresolvable date %r", date)
            return (
                f"I couldn't parse the date '{date}', sir. "
                "Please provide it as YYYY-MM-DD (e.g. '2026-04-15') or a day name like 'tomorrow' or 'Friday'."
            )

        # --- Auto-convert time to 24-hour HH:MM ---
        resolved_time = _parse_time_to_24h(time)
        if resolved_time is None:
            logger.warning("create_event: unrecognised time %r", time)
            return (
                f"I couldn't parse the time '{time}', sir. "
                "Please use 24-hour format (e.g. '21:00') or 12-hour with AM/PM (e.g. '9:00 PM')."
            )

        if resolved_time != time:
            logger.info("create_event: auto-converted time %r → %r", time, resolved_time)

        logger.info(
            "create_event sending to API — title=%r  date=%r  time=%r  duration=%r",
            title, resolved_date, resolved_time, duration_minutes,
        )

        def _create():
            service = _build_service()
            start_dt = datetime.strptime(
                f"{resolved_date} {resolved_time}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=LOCAL_TZ)
            end_dt = start_dt + timedelta(minutes=duration_minutes)

            event_body = {
                "summary": title,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": str(LOCAL_TZ)},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": str(LOCAL_TZ)},
            }
            return service.events().insert(calendarId="primary", body=event_body).execute()

        try:
            await asyncio.to_thread(_create)
        except FileNotFoundError as e:
            logger.error("create_event: credentials not found\n%s", traceback.format_exc())
            return str(e)
        except Exception as e:
            logger.error("create_event: API call failed\n%s", traceback.format_exc())
            return f"I couldn't create the event, sir. Error: {e}"

        display_time = datetime.strptime(
            f"{resolved_date} {resolved_time}", "%Y-%m-%d %H:%M"
        ).strftime("%-I:%M %p on %A, %d %b")
        return (
            f"Done, sir. '{title}' has been added to your calendar at {display_time} "
            f"for {duration_minutes} minutes."
        )
