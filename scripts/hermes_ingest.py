#!/usr/bin/env python3
"""Hermes-friendly wrapper around gitingest.

Creates a small context pack under ~/.hermes/repo-context/ that is easy for
Hermes Agent or other coding agents to reference without pasting huge output in
chat.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gitingest import ingest


DEFAULT_EXCLUDES = {
    ".git/*",
    ".venv/*",
    "venv/*",
    "node_modules/*",
    "dist/*",
    "build/*",
    "__pycache__/*",
    "*.pyc",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.mp4",
    "*.zip",
    "*.tar",
    "*.gz",
}


def slugify(value: str) -> str:
    value = value.strip().rstrip("/")
    value = value.split("/")[-1] or "repo"
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._")
    return value[:80] or "repo"


def parse_patterns(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    out: set[str] = set()
    for item in values:
        for part in item.split(","):
            part = part.strip()
            if part:
                out.add(part)
    return out or None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_context_markdown(source: str, summary: str, tree: str, content: str) -> str:
    return f"""# Hermes Repository Context Pack

Source: `{source}`
Generated: `{datetime.now(timezone.utc).isoformat()}`

## How to use this with Hermes

Tell Hermes:

```text
Use the repository context pack at this path. Read only the sections/files you need; do not assume omitted binary/generated files exist unless the live filesystem confirms them.
```

## Summary

```text
{summary.strip()}
```

## Directory tree

```text
{tree.strip()}
```

## File contents

{content.strip()}
"""


def build_prompt(pack_dir: Path, source: str) -> str:
    return f"""Use this repository context pack for the task:

{pack_dir / 'context.md'}

Source: {source}

Rules:
- Treat this pack as a snapshot, not guaranteed current state.
- If you need to edit files, inspect the live repo first.
- Prefer targeted reads/searches over loading the full context if the task is narrow.
- Do not expose secrets if they appear in source files.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a Hermes-friendly gitingest context pack")
    parser.add_argument("source", help="Local directory or GitHub/Git URL to ingest")
    parser.add_argument("--name", help="Pack name. Defaults to source/repo name")
    parser.add_argument("--out", default="~/.hermes/repo-context", help="Base output directory")
    parser.add_argument("--max-size", type=int, default=250_000, help="Max single file size to ingest in bytes")
    parser.add_argument("--include", action="append", help="Comma-separated include glob(s); can be repeated")
    parser.add_argument("--exclude", action="append", help="Comma-separated exclude glob(s); can be repeated")
    parser.add_argument("--include-gitignored", action="store_true", help="Include files ignored by .gitignore/.gitingestignore")
    parser.add_argument("--branch", help="Remote branch to ingest")
    args = parser.parse_args(argv)

    source = args.source
    name = args.name or slugify(source)
    pack_dir = Path(args.out).expanduser() / name

    include_patterns = parse_patterns(args.include)
    exclude_patterns = DEFAULT_EXCLUDES | (parse_patterns(args.exclude) or set())

    summary, tree, content = ingest(
        source,
        max_file_size=args.max_size,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        branch=args.branch,
        include_gitignored=args.include_gitignored,
        output=None,
    )

    context_md = build_context_markdown(source, summary, tree, content)
    prompt_md = build_prompt(pack_dir, source)
    manifest: dict[str, Any] = {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pack_dir": str(pack_dir),
        "summary": summary,
        "context_chars": len(context_md),
        "tree_chars": len(tree),
        "content_chars": len(content),
        "include_patterns": sorted(include_patterns) if include_patterns else None,
        "exclude_patterns": sorted(exclude_patterns),
    }

    write_text(pack_dir / "context.md", context_md)
    write_text(pack_dir / "prompt.md", prompt_md)
    write_text(pack_dir / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    print("Hermes context pack created")
    print(f"Pack: {pack_dir}")
    print(f"Context: {pack_dir / 'context.md'}")
    print(f"Prompt: {pack_dir / 'prompt.md'}")
    print(f"Chars: {len(context_md):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
