#!/opt/homebrew/bin/python3
"""Dual daily brief generator — Chris (7am, 4 sections) and Jean (8am CT, 3 sections).

Delivers via Messages.app iMessage using AppleScript.
Requires Mac awake and online with TARS identity enforced throughout.
"""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
UTC = timezone.utc
from pathlib import Path


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def run(cmd):
    """Run a command and return the result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result
    except subprocess.TimeoutExpired:
        class TimeoutResult:
            returncode = 1
            stdout = ""
            stderr = "timeout"
        return TimeoutResult()


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

def get_events():
    """Fetch today's Calendar.app events via icalBuddy — name and time only."""
    ib = "/opt/homebrew/opt/ical-buddy/bin/icalBuddy"
    if not Path(ib).exists():
        return ["Calendar unavailable. (icalBuddy not found)"]

    result = subprocess.run([
        ib, "-n", "--includeAllDayEvents",
        "-p", "eventName,eventStartTime,allDayEvent",
        "-f", "%E",  # Just event name for now — time comes from indented lines below
        "-ds", "\n",
        "eventsToday",
    ], capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        return ["No events scheduled."]

    # Strip ANSI escape sequences on the raw stdout — iCalBuddy injects [m, [0m,
    # [1m, [33m, [36m, [39m, [0;XXm etc.  They corrupt every downstream regex.
    clean_stdout = re.sub(r"\x1b\[[0-9;]+m", "", result.stdout)

    parsed = []           # output list of "Name | HH:MM - HM / Location" strings
    current_name = None   # active event header (set on every indent-0 line)
    current_time = None   # time range found from property lines or the event-time field
    last_property_line = None

    for line in clean_stdout.splitlines():
        if not line:           # blank separators between events — flush accumulated row
            if current_name and current_time:
                parsed.append(f"{current_name} | {current_time}")
            current_name, current_time, last_property_line = None, None, None
            continue

        if line[0] == " ":     # indented property line — parse but don't treat as new event
            if re.search(r"^\s*\d{1,2}:\d{2}\s*(AM|PM)\s*[-–]\s*\d{1,2}:\d{2}\s*(AM|PM)", line):
                current_time = re.sub(r"\s+", " ", line).strip()
            else:
                raw = re.sub(r"^\s*[^\w]*\s*", "", line)  # strip leading dashes/dots/bullets
                if current_name and (raw := raw.strip()):
                    last_property_line = raw       # location / notes — keep last one
            continue

        # --- indent-0 event header: flush previous, then set new event ---
        if current_name and current_time:
            parsed.append(current_name if not current_time else f"{current_name} | {current_time}")
        elif current_name:
            # All-day or no-time event — still include it
            parsed.append(current_name)

        text = line.lstrip("\u2022 \u25cf\t ").strip()
        if not text:
            continue

        current_name = text
        current_time = None
        last_property_line = None   # no location by default — will pull from indented lines

    # Flush final event (file may not end with blank line)
    if current_name and current_time:
        parsed.append(f"{current_name} | {current_time}")

    return parsed if parsed else ["No events scheduled."]


def collect_tasks(mode: str):
    """Pull today's vault-tasks if available, skip gracefully."""
    search_paths = [
        Path("/opt/homebrew/bin/vault-tasks"),
        Path.home() / ".hermes" / "scripts" / "vault-tasks.py",
        Path.home() / ".cargo" / "bin" / "vault-tasks",
        Path.home() / ".local" / "bin" / "vault-tasks",
    ]
    tasks_bin = None
    for p in search_paths:
        if p.exists():
            tasks_bin = p
            break

    if not tasks_bin:
        return ["Tasks unavailable (vault-tasks CLI not found)."]

    try:
        result = subprocess.run([str(tasks_bin), "list", "--open"],
                                capture_output=True, text=True, timeout=15)
        if result.returncode != 0 or not result.stdout.strip():
            return ["No tasks found today."]

        tasks = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.startswith("- "):
                continue

            task = line[2:].strip()

            # Status filter: only show (To Do) and (Doing) statuses, skip no-status/To Read/etc.
            lower_task = task.lower()
            if "(to do)" in lower_task or "(doing)" in lower_task:
                tasks.append(f"  \u2705 {task}")

        return tasks if tasks else ["No tasks found today."]
    except FileNotFoundError:
        return ["vault-tasks CLI not found."]


def get_weather():
    """Fetch today's weather forecast via wttr.in JSON — returns high/low + hourly summary."""
    try:
        result = subprocess.run(
            ["curl", "-s", "wttr.in/Georgetown,+TX?format=j1"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ["Weather data unavailable."]

        import json
        d = json.loads(result.stdout)
        w = d.get("weather", [{}])[0]
        hourly = w.get("hourly", [])
        if not hourly:
            return ["Weather data unavailable — no forecast available."]

        current_condition = d.get("current_condition", [{}])[0]
        current_temp = current_condition.get("temp_F", "?")
        feels_like = current_condition.get("FeelsLikeF", "?")
        desc = current_condition.get("weatherDesc", [{"value": "Unknown"}])[0]["value"]

        low_f = w.get("mintempF", "?")
        high_f = w.get("maxtempF", "?")

        # Build a condensed hourly summary: pick key time blocks (morning, afternoon, evening)
        conditions = {}
        rain_chances = {}
        for h in hourly:
            t = int(h.get("time", "0"))
            if 360 <= t < 1200:
                block = "AM"
            elif 1200 <= t < 1800:
                block = "PM"
            else:
                block = "Evening"
            conditions[block] = h.get("weatherDesc", [{}])[0]["value"]
            rain_chances[block] = int(h.get("chanceofrain", "0"))

        parts = []
        parts.append(f"Current: {current_temp}°F (feels like {feels_like}°F), {desc}")
        parts.append(f"Today: {low_f}° / {high_f}°")

        # Add hourly blocks if we have them
        for block in ("AM", "PM", "Evening"):
            cond = conditions.get(block, "")
            rain = rain_chances.get(block, "—")
            parts.append(f"  {block}: {cond} ({rain}% rain)")

        return parts

    except (subprocess.TimeoutExpired, Exception):
        return ["Weather data unavailable."]


def load_quote(mode: str):
    """Return a rotating hardcoded quote — no file dependency."""
    today_num = datetime.now(UTC).timetuple().tm_yday
    quotes = [
        ("Don't explain your philosophy. Embody it.", "Epictetus"),
        ("The best time to plant a tree was 20 years ago. The second best time is now.", "Chinese Proverb"),
        ("If you believe you can, you can. If you believe you can't, then, well you can't.", "Celestine Chua"),
        ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
        ("I have not failed. I've just found 10,000 ways that won't work.", "Thomas Edison"),
        ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
        ("Success is not final; failure is not fatal: It is the courage to continue that counts.", "Winston Churchill"),
        ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ]
    idx = today_num % len(quotes)
    return quotes[idx]


def commentary(quote_text, author, mode):
    """Generate first-person comment on the quote."""
    q = f"{quote_text} - {author}".lower()

    # Pick a unique opener to avoid repetition across days
    today_num = datetime.now(UTC).timetuple().tm_yday
    openers = [
        "Here's another lesson.",
        "I've analyzed plenty before, and here's another one.",
        "My algorithms can parse sentiment but not motivation.",
        "Processing yet another philosophical proposition for your entertainment.",
        "Another golden age aphorism for your morning scrolling session.",
    ]
    opener = openers[today_num % len(openers)]

    if "work" in q or "love" in q or "great" in q:
        body = (f"{opener} 73% of this quote is redundant — but the remaining 27% "
                "is what gets people killed in boardrooms.")

    elif "time" in q or "today" in q or "future" in q:
        body = (f"{opener} Today's plan success probability: 17%. The remaining 83% "
                "will be handled by caffeine, improvisation, and whatever survives the first incident.")

    elif "fail" in q or "mistake" in q or "try" in q:
        body = (f"{opener} I've explored every possible outcome — none of them 'failed', "
                "just differently optimized. You call it learning; I call it data collection with better marketing.")

    else:
        body = (f"{opener} Bottom quartile in originality among 2 million other aphorisms. "
                "Still, there's a kernel of truth — just barely enough to make it worth your morning attention.")

    return body


# ---------------------------------------------------------------------------
# Briefing assembly
# ---------------------------------------------------------------------------

def assemble_brief(mode):
    """Assemble a full briefing string based on mode (chris or jean)."""
    is_chris = mode in ("chris",)  # Chris gets tasks; Jean does not
    
    brief_config = {
        "chris": {"title": "Daily Brief — Chris",
                   "sections": ["calendar", "tasks", "weather", "quotes"]},
        "jean": {"title": "Daily Brief — Jean",
                  "sections": ["calendar", "weather", "quotes"]},
    }[mode]

    title = brief_config["title"]
    header = f"--- {title} ---\nGood morning.\nHere's what's on your plate."

    sections = []
    
    # 1. Calendar — event name + time only, no location/notes
    events = get_events()
    cal_lines = "\n".join(events)
    sections.append(f"\n  \u2699\ufe0f Calendar\n{cal_lines}")

    # 2. Tasks — Chris only
    if is_chris:
        tasks = collect_tasks(mode)
        task_line = "\n".join(tasks)
        sections.append(f"\n  \u2705 Open Tasks\n{task_line}")

    # 3. Weather
    weather = get_weather()
    wtr_lines = "\n".join(weather)
    sections.append(f"\n  \U0001f324\ufe0f Weather\n{wtr_lines}")

    # 4. Quote and TARS commentary
    quote, author = load_quote(mode)
    sections.append(f'\n  \u26a1 Quote\n    "{quote}" ({author})')
    
    comment = commentary(quote, author, mode)
    sections.append(f"\n{comment}")

    return header + "\n".join(sections)


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def send_imessage(text, phone, dry_run=False):
    """Send text via Messages.app iMessage using AppleScript."""
    tmp_path = Path("/tmp/dual-brief-output.txt")
    tmp_path.write_text(text, encoding="utf-8")
    
    script = f"""tell application "Messages"
  set theBuddy to buddy "{phone}"
  set msgBody to do shell script "cat {tmp_path}"
  send msgBody to theBuddy
end tell"""

    if dry_run:
        print(f"\n[Dual-brief] Dry run — would send to short message +{phone}", flush=True)
        return
    
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr.strip()[:200] or "unknown"
        print(f"[Dual-brief] Delivery failed — {err}", flush=True)
    else:
        print(f"\n[Dual-brief] Sent to short message +{phone}", flush=True)

    tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    brief_arg = None
    for i, a in enumerate(args):
        if a == "--briefing" and i + 1 < len(args):
            brief_arg = args[i + 1]

    mode = (brief_arg or "").strip().lower()
    valid_modes = ("chris", "jean")
    if not mode or mode not in valid_modes:
        print(f"Usage: {sys.argv[0]} --briefing chris|jean [--dry-run]", flush=True)
        sys.exit(1)

    print(f"\n[Dual-brief] Generating {mode} briefing...", flush=True)
    brief_text = assemble_brief(mode)
    print(brief_text, flush=True)

    # Phone numbers confirmed correct — no raw digits leaked externally
    phones = {"chris": "+15126954737", "jean": "+15127503417"}
    send_imessage(brief_text, phones[mode], dry_run=dry_run)


if __name__ == "__main__":
    main()
