#!/usr/bin/env python3
"""Generate a "What I worked on this week" summary in Obsidian.

Pulls data from:
  - Obsidian Tasks (completed tasks, status changes)
  - Obsidian Journals (daily entries for the past week)
  - Quill meetings (confirmed meeting transcripts)
  - Slack from:me messages (public channels)
  - MGS author posts (P2/blog posts by mrchriswdixon)

Output: writes to Journals/YYYY/MMDD-weekly.md in the vault.

Usage:
  python3 obsidian-weekly-summary.py                     # this week (Fri-Fri CT)
  python3 obsidian-weekly-summary.py --week-start 2026-06-15 --week-end 2026-06-20
"""

import argparse
import datetime
import json
import re
import subprocess as sp
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


VAULT = Path.home() / "Obsidian" / "SecondBrain"
JOURNALS = VAULT / "Journals"
WEEKLY_PREFIX = "week-summary-"


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    data = {}
    if yaml:
        try:
            data = yaml.safe_load(block) or {}
        except Exception:
            pass
    if not data:
        for line in block.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                data[k.strip()] = v.strip().strip('"')
    return data, body


def fetch_tasks_in_range(start: datetime.date, end: datetime.date) -> list[dict]:
    """Get tasks with created or status date in [start, end]."""
    tasks = []
    tasks_dir = VAULT / "Tasks"
    if not tasks_dir.is_dir():
        return tasks

    for f in tasks_dir.glob("*.md"):
        fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        title = f.stem
        status = str(fm.get("status", "")).strip()
        created = fm.get("created", "")
        # Validate status and parsed created date
        try:
            created_date = datetime.datetime.strptime(str(created), "%Y-%m-%d").date()
        except ValueError:
            created_date = None
        
        if "Done" in status.lower():
            if created_date and start <= created_date <= end:
                tasks.append({"title": title, "status": status, "date": created_date.isoformat(), "source": "task-done"})
        elif created_date and start <= created_date <= end:
            tasks.append({"title": title, "status": status, "date": created_date.isoformat(), "source": "task-created"})

    return sorted(tasks, key=lambda x: x["date"], reverse=True)


def fetch_journals_for_week(start: datetime.date, end: datetime.date) -> list[str]:
    """Read daily journal files for the date range and extract content."""
    entries = []
    current = start
    while current <= end:
        month_dir = JOURNALS / current.strftime("%Y") / current.strftime("%m")
        file_path = month_dir / f"{current.strftime('%m%d')}.md"
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
            # Extract just the "My Notes" or body content after headers,
            # trimming placeholders from cron agent.
            lines = content.split("\n")
            notes = []
            in_notes = False
            for line in lines:
                if line.startswith("## My Notes"):
                    in_notes = True
                    continue
                if in_notes and line.strip():
                    notes.append(line)
            summary_lines = [l for l in notes if not l.startswith("*") or "=" in l[:2]]
            entry_title = file_path.stem
            entries.append({"title": entry_title, "date": current.isoformat(), "notes": "\n".join(summary_lines).strip()})
        current += datetime.timedelta(days=1)
    
    return entries


def read_quill_meetings(start: datetime.date, end: datetime.date) -> list[dict]:
    """Delegate Quill meeting extraction to agent process. Script returns None to signal delegation."""
    # The actual extraction is done by the extract-meetings.py script called in the cron agent context.
    return []  # placeholder


def summarize_week_data(week_start, week_end):
    """Aggregate all data sources and return raw data for the agent to process.
    
    Returns dict with keys: tasks, journals, meetings_query, slack_query, p2_query
    The fields that are "query" strings contain the date ranges that the cron agent
    should use when calling MCP tools (Slack, MGS).
    """
    start_dt = datetime.datetime.combine(week_start, datetime.time(9, 0), tzinfo=datetime.timezone(datetime.timedelta(hours=-6)))  # 9am CT
    end_dt = datetime.datetime.combine(week_end, datetime.time(9, 0), tzinfo=datetime.timezone(datetime.timedelta(hours=-6)))

    tasks = fetch_tasks_in_range(week_start, week_end)
    journals = fetch_journals_for_week(week_start, week_end)

    return {
        "start": start_dt,
        "end": end_dt,
        "tasks": tasks,
        "journals": journals,
        "slack_query": f"from:chriswdixon days:7",
        "p2_author": "mrchriswdixon",
        "date_from": week_start.isoformat(),
        "date_to": week_end.isoformat(),
    }


def build_weekly_markdown(data) -> str:
    """Build the weekly summary markdown."""
    lines = []
    
    fmt_date = lambda d: d.strftime("%A, %b %d") if isinstance(d, datetime.date) else d
    
    lines.append(f"# Weekly Summary — {fmt_date(data['start'].date())} to {fmt_date(data['end'].date())}")
    lines.append("")

    # Section 1: Tasks (completed)
    completed = [t for t in data["tasks"] if "Done" in t.get("status", "").lower()]
    created = [t for t in data["tasks"] if not completed or "Done" not in t.get("status", "").lower()]
    
    lines.append("**Completed Tasks:**")
    if completed:
        for t in completed[:10]:
            lines.append(f"- {t['title']} ({t['date']})")
    
    # Section 2: Journals summary
    lines.append(f"\n**Daily Journals ({len(data['journals'])} entries):**")
    for j in data["journals"]:
        if j["notes"].strip():
            # Truncate notes to first meaningful line
            note_lines = [l for l in j["notes"].split("\n") if l.strip() and not l.startswith("*")]
            note_preview = " ".join(note_lines[:2]) if note_lines else "(empty)"
            lines.append(f"- **{j['date']}**: {note_preview}")

    # Agent will fill remaining sections: meetings, Slack, P2
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate weekly summary.")
    parser.add_argument("--week-start", help="Start date YYYY-MM-DD")
    parser.add_argument("--week-end", help="End date YYYY-MM-DD")
    args = parser.parse_args()
    
    if args.week_start and args.week_end:
        week_start = datetime.datetime.strptime(args.week_start, "%Y-%m-%d").date()
        week_end = datetime.datetime.strptime(args.week_end, "%Y-%m-%d").date()
    else:
        # Default: last full Friday 9am-to-Friday 9am CT window
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        end = now - datetime.timedelta(hours=6)  # shift to CT
        week_ago = datetime.date.fromisoformat((end - datetime.timedelta(weeks=1)).strftime("%Y-%m-%d"))
        this_friday = (datetime.date.today() + datetime.timedelta(days=(5 - datetime.date.today().weekday()) % 7)).isoformat()
        week_start = week_ago
        week_end = datetime.date.today()

    data = summarize_week_data(week_start, week_end)
    
    print("=== Weekly Summary Data ===")
    print(json.dumps({
        "period": f"{str(data['start'].date())} to {str(data['end'].date())}",
        "tasks_completed": len([t for t in data["tasks"] if 'Done' in t.get("status","").lower()]),
        "tasks_created_or_changed": len(data["tasks"]),
        "journa_entries_found": len(data["journals"]),
        "daily_journal_dates": [j["date"] for j in data["journals"]],
        "slack_query": data["slack_query"],
        "p2_author": data["p2_author"],
        "task_titles": [t["title"] for t in data["tasks"][:15]],
    }, indent=2))


if __name__ == "__main__":
    main()
