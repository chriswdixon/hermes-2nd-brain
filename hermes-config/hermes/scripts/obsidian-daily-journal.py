#!/usr/bin/env python3
"""Generate a daily journal draft in Obsidian SecondBrain vault.

Each day gets a .md file under Journals/YYYY/MMDD.md with:
- Header with date and day name
- Tasks completed/created today
- A section for you to add your own notes/reflections

Agent (running this as a cron job) should fill in the Slack/P2/meeting sections.

Usage:
  python3 obsidian-daily-journal.py          # uses today's date
  python3 obsidian-daily-journal.py 2026-06-25
"""

import argparse
import datetime
from pathlib import Path
import re

try:
    import yaml
except ImportError:
    yaml = None

VAULT = Path.home() / "Obsidian" / "SecondBrain"
JOURNALS = VAULT / "Journals"


# These methods are called by the cron agent between MCP tool calls.
# The agent invokes the methods directly from the cron prompt; they produce Markdown to be inserted into the journal file.

def fmt_slack_text(raw: str) -> str:
    """Clean Slack HTML markup and convert links to bare URLs."""
    # Convert entities
    text = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # Strip mentions <@U123456|Name> -> Name or just "Person"
    text = re.sub(r"<@\w+\|([^>]*)>", r"\1", text) if "|" in raw else raw
    # Convert links [text](url) to bare text - keep them as markdown links
    # Already markdown, so leave alone
    # Strip angle-bracket URLs <http://...>
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    return text.strip()


def fmt_ts(ts: str) -> str:
    """Convert Slack timestamp to HH:MM AM/PM."""
    try:
        t = int(float(ts))
        dt = datetime.datetime.fromtimestamp(t)
        return dt.strftime("%H:%M")
    except (ValueError, TypeError, OSError):
        return ts[:8] if len(str(ts)) >= 8 else ts


def render_slack_markdown(agent_data: dict) -> str:
    """Render fetched Slack data as Obsidian-friendly markdown."""
    msgs = agent_data.get("slack_messages") or []
    if not msgs:
        return "**Slack activity:** *(no messages from backchannel)*
---"

    lines = ["**Slack — #vip-fde-backchannel**"]
    for m in msgs:
        author = m.get("username", m.get("user", "unknown"))
        if "|" in str(m.get("user", "")):
            parts = m["user"].split("|")
            if len(parts) > 1:
                author = parts[-1]
        ts = fmt_ts(str(m.get("ts", "")))
        text = fmt_slack_text(str(m.get("txt", "")))
        lines.append(f"- **{author}** ({ts}): {text}")

    return "\n".join(lines) + "\n---"


def render_quill_markdown(agent_data: dict) -> str:
    """Render Quill meeting transcripts."""
    meetings = agent_data.get("quill_meetings") or []
    if not meetings:
        return "**Meetings:** *(waiting for today's Quill exports)*
---"

    lines = ["**Meetings (from Quill)**"]
    for mtg in meetings:
        name = mtg.get("meeting_name", "Untitled Meeting")
        time_str = mtg.get("time", "")
        attendees = mtg.get("attendees", [])
        if attendees:
            lines.append(f"- {name} ({time_str}) — with: {', '.join(attendees)}")
        else:
            lines.append(f"- {name} ({time_str})")

    return "\n".join(lines) + "\n---"


def render_calendar_markdown(events: list[dict]) -> str:
    """Render calendar events from dual-brief output."""
    if not events:
        return ""  # Already handled by generate_journal() default

    lines = ["**Today's Calendar:**"]
    for ev in events:
        title = ev.get("name", "Untitled")
        time = ev.get("time", "(no time)")
        loc = ev.get("location", "")
        all_day = ev.get("allDay", False)

        extra = f" [All Day]" if all_day else ""
        lines.append(f"- **{title}** — {time}{extra}")
        if loc:
            lines.append(f"  - Location: {loc}")

    return "\n".join(lines) + "\n---"


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


def get_tasks_for_date(date: datetime.date):
    """Return (completed[], created_or_modified[]) for the given date."""
    completed = []
    created = []
    tasks_dir = VAULT / "Tasks"
    if not tasks_dir.is_dir():
        return completed, created

    for f in sorted(tasks_dir.glob("*.md")):
        fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        status = str(fm.get("status", "")).strip()
        created_raw = fm.get("created", "")
        
        if isinstance(created_raw, datetime.date):
            task_date = created_raw
        else:
            try:
                task_date = datetime.datetime.strptime(str(created_raw), "%Y-%m-%d").date()
            except ValueError:
                continue

        if "Done" in status.lower() and task_date == date:
            completed.append((f.stem, task_date))
        elif task_date == date:
            created.append((f.stem, task_date))

    return completed, created


def fmt_date(d):
    return d.strftime("%A, %B %d, %Y")


def generate_journal(date: datetime.date) -> Path:
    """Generate journal entry and write to Obsidian vault. Returns file path."""
    month_dir = JOURNALS / date.strftime("%Y") / date.strftime("%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    file_path = month_dir / f"{date.strftime('%m%d')}.md"

    completed, created = get_tasks_for_date(date)
    
    lines = []
    lines.append(f"# Journal - {fmt_date(date)}")
    lines.append("")
    lines.append(f"**Date:** {fmt_date(date)}")
    lines.append("")

    # Section: Tasks worked on today
    lines.append("## Work Logged\n")

    if completed:
        lines.append("**Tasks completed today:**")
        for title, _ in completed:
            lines.append(f"- {title}")
    
    if created:
        lines.append("\n**Tasks started/updated today:**")
        for title, _ in created:
            lines.append(f"- {title}")

    if not completed and not created:
        lines.append("*No tasks logged for this date.*")

    lines.append("")

    # Placeholders for agent to fill during cron run
    lines.append("**Meetings:** *(awaiting Quill data)*\n---")
    lines.append("")
    lines.append("**Slack activity:** *(awaiting from:me search)*\n---")
    lines.append("")
    lines.append("**P2 posts:** *(awaiting MGS results)*\n---")
    lines.append("")

    # User notes section (blank for manual entry)
    lines.append("---\n\n## My Notes\n")

    output_text = "\n".join(lines)
    file_path.write_text(output_text, encoding="utf-8")
    return file_path


def main():
    parser = argparse.ArgumentParser(description="Generate daily Obsidian journal draft.")
    parser.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    if args.date:
        target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.date.today()

    path = generate_journal(target_date)
    print(f"Journal entry created: {path}")


if __name__ == "__main__":
    main()
