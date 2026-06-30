#!/usr/bin/env python3.14
"""
Daily Brief generator — gathers today's open tasks from Obsidian vault via vault-tasks.py, 
yesterday's Quill meeting transcripts, and lifestyle data (weather, quote, calendar),
then posts to Telegram and saves a markdown brief into the Obsidian Tasks vault.

Runs at 0900 CT daily via cronjob `daily-brief`.
Outputs to Telegram as raw text (no Markdown formatting for clean delivery).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


# ── Config ────────────────────────────────────────────────────────
OBSIDIAN_TASKS_DIR   = Path("/Users/mrchriswdixon/Obsidian/SecondBrain/Tasks")
QUILL_OUTPUT_DIR     = Path("/Users/mrchriswdixon/workspace/notes/quill-transcripts")
PULL_DATA_SCRIPT     = Path(__file__).parent / "pull_data.py"


# ── Lifestyle data (weather, quote, calendar) ────────────────────

def get_lifestyle_data() -> dict:
    """Pull weather, quote, and today's calendar via pull_data.py script."""
    try:
        result = subprocess.run(
            [sys.executable, str(PULL_DATA_SCRIPT)],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            print(f"[WARN] pull_data.py failed: {result.stderr.strip()}", file=sys.stderr)
            return {"weather": {}, "quote": {}, "calendar": {"events": []}}
        data = json.loads(result.stdout)
        return data
    except Exception as exc:
        print(f"[WARN] Lifestyle data fetch error: {exc}", file=sys.stderr)
        return {"weather": {}, "quote": {}, "calendar": {"events": []}}


# ── Helpers ───────────────────────────────────────────────────────

def get_my_tasks() -> list[dict]:
    """Fetch open (non-Done) tasks from the local Obsidian vault via vault-tasks.py.

    Replaces the old Notion Task List read. The vault is now the source of truth.
    """
    helper = Path(__file__).parent / "vault-tasks.py"
    try:
        result = subprocess.run(
            [sys.executable, str(helper), "list", "--open", "--json"],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as exc:
        return [{"error": f"vault-tasks.py failed to run: {exc}"}]
    if result.returncode != 0:
        return [{"error": f"vault-tasks.py error: {result.stderr.strip()[:200]}"}]
    try:
        rows = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return [{"error": "vault-tasks.py returned unparseable output"}]

    tasks = []
    for r in rows:
        title = (r.get("title") or "").strip()
        if not title:
            continue
        display_title = title
        for prefix in ["Read:", "Task:", "Book:", "/"]:
            if display_title.startswith(prefix):
                display_title = display_title[len(prefix):].lstrip()
        status = r.get("status") or ""
        if status == "To Read":
            status = "Reading"
        tasks.append({
            "title": display_title.strip(),
            "status": status,
            "due_date": "",  # the vault Task List has no due-date property
            "_is_reading": status == "Reading",
            "_created_time": r.get("created", ""),
        })
    return tasks


def get_yesterday_transcripts() -> list[dict]:
    """Extract yesterday's Quill meeting transcripts via our sqlite script."""
    extract_script = "/Users/mrchriswdixon/.hermes/skills/quill-sync/scripts/extract-meetings.py"
    yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    result = subprocess.run(
        ["/opt/homebrew/bin/python3.14", extract_script, "--date", yesterday, "--output", str(QUILL_OUTPUT_DIR)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0 and "No meetings" not in (result.stdout or ""):
        return [{"error": f"quill-sync failed: {result.stderr}"}]

    yesterday_dir = QUILL_OUTPUT_DIR / yesterday
    if not yesterday_dir.is_dir():
        return []

    meetings = []
    for md_file in sorted(yesterday_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        title = ""
        attendees_raw: list[str] = []
        transcript_started = False

        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.strip() == "---":
                transcript_started = True
            if not transcript_started:
                continue
            if "**Attendees:**" in line:
                next_i = lines.index(line) + 1
                while next_i < len(lines):
                    cl = lines[next_i]
                    if not cl.startswith("- "):
                        break
                    attendees_raw.append(cl[2:].strip())
                    next_i += 1
        meetings.append({
            "title": title or "Untitled Meeting",
            "attendees": list(dict.fromkeys(attendees_raw)),  # unique, preserve order
        })

    return meetings


# ── Brief assembly ────────────────────────────────────────────────

def build_brief_text(
    tasks: list[dict],
    transcripts: list[dict],
    lifestyle: dict | None = None,
) -> str:
    """Build plain-text daily brief for Telegram."""
    today = datetime.now(UTC)
    today_str = today.strftime("%Y-%m-%d")
    lines = [f"📋 Daily Brief — {today_str}", "", f"> Generated at {today.strftime('%I:%M%p CT')}"]

    # ---- Lifestyle section (weather, quote, calendar) ----▌
    if lifestyle:
        w = lifestyle.get("weather", {})
        q = lifestyle.get("quote", {})
        c = lifestyle.get("calendar", {})
        evts = c.get("events", [])

        lines.append("")
        lines.append("☕ Today's Brief:")
        # Weather
        if w:
            loc = w.get("location", "")
            cond = w.get("condition", "")
            det = w.get("details", "")
            loc_parts = loc.split(",") if loc else []
            city = loc_parts[-1].strip() if loc_parts else loc
            lines.append(f"  🌤 {city}: {cond} — {det}")

        # Quote
        if q:
            content = q.get("content", "")
            author = q.get("author", "")
            if content:
                lines.append(f'  ❝ "{content}"')
                if author and "error" not in str(author):
                    lines.append(f"  — {author}")

        # Calendar events — combine multi-line raw output into single clean bullets
        if evts:
            lines.append("  📅 Today:")
            for evt in evts:
                # Combine all property pieces of one event into a single line
                parts = []
                location = ""
                for segment in evt.split():
                    segment = segment.strip("*").strip()
                    if not segment:
                        continue
                    label, _, value = segment.partition(":")
                    if label.strip().lower() == "location":
                        location = value.strip()
                    elif label.strip().lower() in ("notes", "description"):
                        parts.append(value.strip())
                    else:
                        # Name/title — keep only the first non-property word to avoid duplicating
                        if not any(p for p in parts):
                            parts.append(segment)

                line = parts[0] or evt.split()[0] if evt.split() else "(no title)"
                if location:
                    line += f" ({location})"
                if line and "USAGE:" not in line:
                    lines.append(f"    • {line}")
        elif c and not w.get("error"):
            # no events and no weather error means truly empty day
            pass  # don't show calender section if no events

    # Tasks section
    error_tasks = [t for t in tasks if isinstance(t, dict) and "error" in t]
    real_tasks = [t for t in tasks if not (isinstance(t, dict) and "error" in t)]

    if error_tasks:
        lines.append("\n⚠ Task sync failed:")
        for e in error_tasks:
            lines.append(f"  - {e['error']}")
        lines.append("")
    elif real_tasks:
        now_dt = today.date()
        overdue = [t for t in real_tasks if t.get("due_date") and t["due_date"] < today_str]
        due_today = [t for t in real_tasks if t.get("due_date") == today_str]
        non_dated = [t for t in real_tasks if not t.get("due_date")]

        if overdue:
            lines.append("\nOverdue:")
            for t in overdue:
                lines.append(f"  • {t['title']} (Due: {t['due_date']})")
        if due_today:
            lines.append("\nDue Today:")
            for t in due_today:
                status = f" ({t.get('status', '')})" if t.get("status") else ""
                lines.append(f"  • {t['title']}{status}")
        if non_dated:
            lines.append("\nNo Due Date:")
            for t in non_dated:
                status = f" ({t.get('status', '')})" if t.get("status") else ""
                lines.append(f"  • {t['title']}{status}")

    if not real_tasks and not error_tasks:
        lines.append("*No tasks in progress.*")

    # Meetings section
    err_mtgs = [m for m in transcripts if isinstance(m, dict) and "error" in m]
    real_mtgs = [m for m in transcripts if not (isinstance(m, dict) and "error" in m)]

    if err_mtgs:
        lines.append("\n⚠ Quill sync failed:")
        for e in err_mtgs:
            lines.append(f"  - {e['error']}")
    elif real_mtgs:
        lines.append("\nYesterday's Meetings:")
        for m in real_mtgs:
            att_str = ", ".join(m.get("attendees", [])) or "(no attendees)"
            lines.append(f"  • {m['title']} ({att_str})")

    return "\n".join(lines)


def save_raw_brief(content: str) -> Path:
    """Save raw text to cron output for delivery."""
    out_dir = Path("/Users/mrchriswdixon/.hermes/cron/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    filepath = out_dir / f"daily-brief-{datetime.now(UTC).strftime('%Y-%m-%d')}.txt"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── Main ─────────────────────────────────────────────────────────

def main() -> int:
    print("[Daily Brief] Starting generation...", flush=True)

    # Step 1: Lifestyle data (weather, quote, calendar)
    lifestyle = get_lifestyle_data()

    # Step 2: Tasks from the Obsidian vault
    tasks = get_my_tasks()

    # Step 3: Quill transcripts for yesterday
    transcripts = get_yesterday_transcripts()

    # Step 4: Build the brief (tasks + meetings + lifestyle)
    brief_text = build_brief_text(tasks, transcripts, lifestyle)

    print(f"\n--- DAILY BRIEF ---\n{brief_text}\n", flush=True)

    # Step 4: Save brief to Obsidian Tasks vault as markdown
    today_str = datetime.now(UTC).strftime('%Y-%m-%d')
    obs_file = OBSIDIAN_TASKS_DIR / f"daily-brief-{today_str}.md"
    obs_file.write_text(brief_text, encoding="utf-8")
    print(f"[Daily Brief] ✓ Saved to {obs_file}", flush=True)

    return 0


if __name__ == "__main__":
    exit(main() or 0)
