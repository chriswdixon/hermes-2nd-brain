#!/usr/bin/env python3
"""vault-notes.py — deterministic note CRUD over the Obsidian SecondBrain vault.

Companion to vault-tasks.py. Replaces the old Notion note-write path. Notes are
markdown files in ~/Obsidian/SecondBrain/Notes/ with YAML frontmatter
(title, created, tags, source, type), matching the existing vault convention.

Usage:
  vault-notes.py add "Title" [--tags a,b] [--source URL] [--body "text"] [--folder Notes]
  vault-notes.py list [--folder Notes] [--tag TAG] [--json]

Notes:
  - Filename is canonical (the note title). A redundant `title:` field is written
    for workflows that read frontmatter directly.
  - `created` is today's date. `tags` always includes the base tag for the folder.
  - Never hand-edit frontmatter elsewhere; go through this helper so the format
    stays consistent with vault-tasks.py.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

VAULT = Path.home() / "Obsidian" / "SecondBrain"
DEFAULT_FOLDER = "Notes"

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


def sanitize(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", title).strip()


def split_tags(raw: str) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def cmd_add(a):
    folder = VAULT / a.folder
    f = folder / f"{sanitize(a.title)}.md"
    if f.exists():
        print(f"exists: {f}", file=sys.stderr)
        return 1
    folder.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    tags = split_tags(a.tags)
    base = "note"
    if base not in tags:
        tags.insert(0, base)
    lines = [
        "---",
        f'title: "{a.title}"',
        f"created: {today}",
        f"tags: {yaml_list(tags)}",
    ]
    if a.source:
        lines.append(f"source: {a.source}")
    lines.append("type: note")
    lines.append("---")
    fm = "\n".join(lines) + "\n\n"
    body = (a.body + "\n") if a.body else ""
    f.write_text(fm + body, encoding="utf-8")
    print(f"created: {f}")
    return 0


def cmd_list(a):
    folder = VAULT / a.folder
    out = []
    if folder.is_dir():
        for f in sorted(folder.glob("*.md")):
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = split_tags(tags.strip("[]"))
            out.append({
                "title": str(fm.get("title") or f.stem),
                "created": str(fm.get("created") or ""),
                "tags": tags,
                "source": str(fm.get("source") or ""),
                "file": str(f),
            })
    if a.tag:
        out = [n for n in out if a.tag.lower() in [str(t).lower() for t in n["tags"]]]
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for n in out:
            print(f"- {n['title']} ({n['created'] or 'no date'})")
    return 0


def main():
    p = argparse.ArgumentParser(description="Note CRUD over the Obsidian vault.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add")
    pa.add_argument("title")
    pa.add_argument("--tags", default="")
    pa.add_argument("--source", default="")
    pa.add_argument("--body", default="")
    pa.add_argument("--folder", default=DEFAULT_FOLDER)
    pa.set_defaults(func=cmd_add)

    pl = sub.add_parser("list")
    pl.add_argument("--folder", default=DEFAULT_FOLDER)
    pl.add_argument("--tag")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    a = p.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
