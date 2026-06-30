#!/usr/bin/env python3
"""vault-tasks.py — deterministic task CRUD over the Obsidian SecondBrain vault.

Single source of truth for TARS, the 7am briefing, and daily-brief.py.
Replaces the old Notion "Task List" integration. Tasks are markdown notes
in ~/Obsidian/SecondBrain/Tasks/ with YAML frontmatter (status, created).

Usage:
  vault-tasks.py list [--open] [--status STATUS] [--json]
  vault-tasks.py add "Title" [--status "To Do"] [--body "text"]
  vault-tasks.py set-status "Title" "Doing"
  vault-tasks.py done "Title"

Status values mirror the old Notion select exactly:
  "To Do", "Doing", "Done 🙌", "To Read", or empty.
"open" = anything that is not Done.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

VAULT = Path.home() / "Obsidian" / "SecondBrain"
TASKS = VAULT / "Tasks"
DONE = "Done 🙌"
OPEN_STATUSES = {"To Do", "Doing", "To Read", ""}

try:
    import yaml
except ImportError:
    yaml = None


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    if yaml:
        try:
            return (yaml.safe_load(block) or {}), body
        except Exception:
            pass
    data = {}
    for line in block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            data[k.strip()] = v.strip().strip('"')
    return data, body


def load_tasks():
    out = []
    if not TASKS.is_dir():
        return out
    for f in sorted(TASKS.glob("*.md")):
        fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        out.append({
            "title": f.stem,
            "status": str(fm.get("status") or "").strip(),
            "created": str(fm.get("created") or ""),
            "file": str(f),
        })
    return out


def sanitize(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", title).strip()


def find_task(query: str):
    tasks = load_tasks()
    for t in tasks:
        if t["title"].lower() == query.lower():
            return t
    s = sanitize(query).lower()
    for t in tasks:
        if t["title"].lower() == s:
            return t
    matches = [t for t in tasks if query.lower() in t["title"].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print("ambiguous; candidates:", file=sys.stderr)
        for m in matches:
            print(f"  - {m['title']}", file=sys.stderr)
    return None


def cmd_list(a):
    tasks = load_tasks()
    if a.open:
        tasks = [t for t in tasks if t["status"] in OPEN_STATUSES]
    if a.status:
        tasks = [t for t in tasks if t["status"].lower() == a.status.lower()]
    if a.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    else:
        for t in tasks:
            print(f"- {t['title']} ({t['status'] or 'no status'})")
    return 0


def cmd_add(a):
    f = TASKS / f"{sanitize(a.title)}.md"
    if f.exists():
        print(f"exists: {f}", file=sys.stderr)
        return 1
    TASKS.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    fm = f"---\nstatus: {a.status}\ncreated: {today}\ntags: [task]\n---\n\n"
    body = (a.body + "\n") if a.body else ""
    f.write_text(fm + body, encoding="utf-8")
    print(f"created: {f}")
    return 0


def write_status(t, status: str):
    f = Path(t["file"])
    text = f.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    block, rest = text[3:end], text[end:]
    if re.search(r"(?m)^status:.*$", block):
        block = re.sub(r"(?m)^status:.*$", f"status: {status}", block)
    else:
        block = block.rstrip("\n") + f"\nstatus: {status}\n"
    f.write_text("---" + block + rest, encoding="utf-8")
    print(f"{t['title']} -> {status or 'no status'}")
    return 0


def cmd_set_status(a):
    t = find_task(a.title)
    if not t:
        print(f"not found: {a.title}", file=sys.stderr)
        return 1
    return write_status(t, a.status)


def cmd_done(a):
    t = find_task(a.title)
    if not t:
        print(f"not found: {a.title}", file=sys.stderr)
        return 1
    return write_status(t, DONE)


def main():
    p = argparse.ArgumentParser(description="Task CRUD over the Obsidian vault.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--open", action="store_true", help="only non-Done tasks")
    pl.add_argument("--status")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    pa = sub.add_parser("add")
    pa.add_argument("title")
    pa.add_argument("--status", default="To Do")
    pa.add_argument("--body", default="")
    pa.set_defaults(func=cmd_add)

    ps = sub.add_parser("set-status")
    ps.add_argument("title")
    ps.add_argument("status")
    ps.set_defaults(func=cmd_set_status)

    pd = sub.add_parser("done")
    pd.add_argument("title")
    pd.set_defaults(func=cmd_done)

    a = p.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
