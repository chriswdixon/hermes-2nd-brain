#!/usr/bin/env python3.14
"""Daily Brief lifestyle data grabber — prints JSON with weather, quote, calendar."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request


WEATHER_URL = "https://wttr.in/Georgetown%2CTX?format=+%C,+%t"
QUOTE_URL   = "https://type.fit/api/quotes?limit=1"
ICALB       = "/opt/homebrew/opt/ical-buddy/bin/icalBuddy"


def get_weather() -> dict:
    try:
        r = subprocess.run(
            ["curl", "-s", WEATHER_URL],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return {"error": f"wttr.in failed: {r.stderr.strip()}"}
        parts = [p.strip() for p in r.stdout.strip().split(",") if p.strip()]
        cond = parts[0] if len(parts) > 0 else "?"
        temp = parts[1] if len(parts) > 1 else "?"
        return {"location": "Georgetown,TX", "condition": cond, "temp": temp}
    except subprocess.TimeoutExpired:
        return {"error": "weather timed out"}
    except Exception as e:
        return {"error": str(e)}


def get_quote() -> dict:
    try:
        req = urllib.request.Request(QUOTE_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if not data or isinstance(data, dict):
            return {"error": "empty quote response"}
        item = data[0]
        return {
            "content": item.get("text", ""),
            "author":  item.get("author", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def get_calendar_today() -> dict:
    try:
        r = subprocess.run(
            [ICALB, "-n", "-p", "eventName,eventStartTime",
             "-f", "%E (%S)", "-ds", "\n", "eventsToday"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return {"events": []}

        # Strip ANSI color/formatting codes and clean bullets
        raw = re.sub(r'\x1b\[[^m]*m', '', r.stdout)

        # Each calendar event starts with a bullet (•). Merge all property lines
        # until the next bullet into the preceding event.
        events = []
        current_event = ""
        for line in raw.strip().splitlines():
            stripped = line.lstrip('\u2022 \t').strip()
            if not stripped:
                continue
            # Lines starting with a bullet (•) = new event
            has_bullet = line.startswith('\u2022')
            if has_bullet and current_event.strip():
                events.append(current_event.strip())
            if has_bullet or not current_event.strip():
                current_event = stripped.lstrip('\u2022').lstrip()
            else:
                # Property line for current event (notes:, location:, time)
                label, _, value = stripped.partition(':')
                lv = label.strip().lower()
                if lv in ('notes', 'description'):
                    current_event += f' — {value.strip()}' if value.strip() else ''
                elif lv in ('location', 'where'):
                    current_event += f' @ {value.strip()}' if value.strip() else ''
                elif ':' in stripped or '/' in stripped:
                    # Likely time range
                    current_event += f' ({stripped})'
                else:
                    current_event += f' ({stripped})'

        if current_event.strip():
            events.append(current_event.strip())

        return {"events": events}
    except subprocess.TimeoutExpired:
        return {"error": "calendar timed out"}
    except FileNotFoundError:
        return {"error": f"icalBuddy missing at {ICALB}"}
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    data = {
        "weather": get_weather(),
        "quote":   get_quote(),
        "calendar":  get_calendar_today(),
    }
    print(json.dumps(data))


if __name__ == "__main__":
    main()
