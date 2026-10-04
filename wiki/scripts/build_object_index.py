#!/usr/bin/env python3
"""Build a compact lookup index from Wiki frontmatter only."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


WIKI = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"_meta", "_state", "agent", "inbox", "learning-events", "reports", "review", "scripts", "tests"}


def eligible_pages(wiki: Path = WIKI) -> list[Path]:
    return [
        path for path in sorted(wiki.rglob("*.md"))
        if not any(part in SKIP_DIRS for part in path.relative_to(wiki).parts)
    ]


def file_signatures(wiki: Path = WIKI) -> dict[str, list[int]]:
    """Cheap freshness data: no page contents are read here."""
    signatures = {}
    for path in eligible_pages(wiki):
        stat = path.stat()
        signatures[path.relative_to(wiki).as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return signatures


def frontmatter(path: Path) -> str | None:
    lines = []
    with path.open(encoding="utf-8") as handle:
        if handle.readline().rstrip("\n") != "---":
            return None
        for line in handle:
            if line.rstrip("\n") == "---":
                return "".join(lines)
            lines.append(line)
    return None


def scalar(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip().strip('"') if match else None


def list_values(text: str, key: str) -> list[str]:
    match = re.search(rf"^{re.escape(key)}:\s*\n((?:[ \t]+-.*\n?)*)", text, re.MULTILINE)
    if not match:
        return []
    return [item.strip().strip('"') for item in re.findall(r"^[ \t]+-\s*(.+)$", match.group(1), re.MULTILINE)]


def build(wiki: Path = WIKI) -> dict:
    objects = []
    source_mtimes = []
    by_id = {}
    by_ref = {}
    by_path = {}
    signatures = file_signatures(wiki)
    for path in eligible_pages(wiki):
        relative = path.relative_to(wiki)
        meta = frontmatter(path)
        if meta is None:
            continue
        object_id = scalar(meta, "id")
        object_type = scalar(meta, "type")
        if not object_id or not object_type:
            continue
        source_mtimes.append(path.stat().st_mtime)
        title = scalar(meta, "title") or path.stem
        item = {
            "id": object_id,
            "type": object_type,
            "path": relative.as_posix(),
            "wikilink": path.stem,
            "title": title,
            "ref_aliases": list_values(meta, "ref_aliases"),
        }
        if object_id in by_id:
            raise ValueError(f"duplicate object id: {object_id}")
        by_id[object_id] = len(objects)
        if item["path"] in by_path:
            raise ValueError(f"duplicate object path: {item['path']}")
        by_path[item["path"]] = len(objects)
        for alias in item["ref_aliases"]:
            if alias in by_ref:
                raise ValueError(f"duplicate ref alias: {alias}")
            by_ref[alias] = len(objects)
        objects.append(item)
    return {
        "schema_version": 1,
        "generated_at": datetime.fromtimestamp(max(source_mtimes, default=0), ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "object_count": len(objects),
        "objects": objects,
        "by_id": by_id,
        "by_ref": by_ref,
        "by_path": by_path,
        "file_signatures": signatures,
    }


def save(index: dict, wiki: Path = WIKI) -> Path:
    output = wiki / "_state" / "object-index.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def ensure_current(wiki: Path = WIKI) -> tuple[dict, str, list[str]]:
    """Return a current index, rebuilding only when stable-page signatures differ."""
    output = wiki / "_state" / "object-index.json"
    current = file_signatures(wiki)
    if not output.exists():
        index = build(wiki)
        save(index, wiki)
        return index, "rebuilt_missing", sorted(current)

    index = json.loads(output.read_text(encoding="utf-8"))
    previous = index.get("file_signatures")
    if previous == current:
        return index, "current", []

    changed = sorted(
        path for path in set(previous or {}) | set(current)
        if (previous or {}).get(path) != current.get(path)
    )
    index = build(wiki)
    save(index, wiki)
    return index, "rebuilt_changed", changed


def main() -> None:
    index = build()
    output = save(index)
    print(json.dumps({"objects": index["object_count"], "refs": len(index["by_ref"]), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
