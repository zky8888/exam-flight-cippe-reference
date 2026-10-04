#!/usr/bin/env python3
"""Validate generated Wiki frontmatter, stable IDs, sources, and wikilinks."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


WIKI = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"_meta", "_state", "agent", "reports", "review", "scripts", "tests"}


def value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip().strip('"') if match else None


def main() -> None:
    pages = [path for path in WIKI.rglob("*.md") if not any(part in SKIP_DIRS for part in path.relative_to(WIKI).parts)]
    errors: list[str] = []
    ids: list[str] = []
    stems = {path.stem for path in WIKI.rglob("*.md")}

    for path in pages:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(WIKI)
        if not text.startswith("---\n"):
            errors.append(f"{relative}: missing YAML frontmatter")
        for required in ("type", "id", "generated", "source_refs"):
            if not re.search(rf"^{required}:", text, re.MULTILINE):
                errors.append(f"{relative}: missing {required}")
        page_id = value(text, "id")
        if page_id:
            ids.append(page_id)
        for target in re.findall(r"\[\[([^\]|#]+)", text):
            if target not in stems:
                errors.append(f"{relative}: dead wikilink [[{target}]]")

    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    errors.extend(f"duplicate id: {item}" for item in duplicates)

    expected = {
        "HOME.md", "RULES.md", "actors/DPO.md", "actors/Supervisory Authority.md", "actors/Controller.md",
        "rules/Article 37 — DPO appointment.md", "rules/Article 38 — DPO position and resources.md",
        "rules/Article 39 — DPO tasks.md", "rules/Article 78(2) — DPA 三个月未告知后的司法救济.md",
        "rules/Article 83 — 行政罚款.md", "questions/TQ 052.md", "questions/TQ 072.md", "questions/TQ 191.md",
    }
    actual = {str(path.relative_to(WIKI)) for path in pages}
    errors.extend(f"missing expected page: {item}" for item in sorted(expected - actual))

    rules_index = WIKI / "RULES.md"
    if rules_index.exists():
        index_text = rules_index.read_text(encoding="utf-8")
        for rule in sorted((WIKI / "rules").glob("*.md")):
            meta = rule.read_text(encoding="utf-8")
            if value(meta, "type") == "rule" and not re.search(rf"\[\[{re.escape(rule.stem)}(?:\||\]\])", index_text):
                errors.append(f"orphan rule missing from RULES.md: {rule.name}")

    if errors:
        print("Projection validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)
    print(f"Projection valid: {len(pages)} generated pages, {len(ids)} unique IDs, no dead wikilinks.")


if __name__ == "__main__":
    main()
