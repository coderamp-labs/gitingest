# Hermes Agent usage

Gitingest is useful inside Hermes because it can turn a local folder or GitHub repository into a compact context pack before an agent starts editing, reviewing, or planning.

## Quick local context pack

```bash
python scripts/hermes_ingest.py /path/to/repo --name my-repo
```

This writes:

```text
~/.hermes/repo-context/my-repo/
  context.md     # summary + tree + selected file contents
  prompt.md      # paste-ready instruction for Hermes
  manifest.json  # source, generation time, sizes, filters
```

Then tell Hermes:

```text
Use the repository context pack at ~/.hermes/repo-context/my-repo/context.md and help me review the architecture.
```

## Remote repository

```bash
python scripts/hermes_ingest.py https://github.com/coderamp-labs/gitingest --name gitingest
```

## Smaller focused pack

Use include/exclude patterns when a full repo is too large:

```bash
python scripts/hermes_ingest.py . \
  --name backend-only \
  --include "*.py,*.md,pyproject.toml" \
  --exclude "tests/fixtures/*,docs/*"
```

## Why this is Hermes-friendly

- Output is saved to `~/.hermes/repo-context/` instead of pasted directly into chat.
- `prompt.md` gives Hermes safe handling rules for snapshot context.
- Default excludes skip common generated/binary/heavy files.
- `manifest.json` records the source and filters for repeatability.

## Safety notes

- The pack is a snapshot. If Hermes will edit code, it should inspect the live filesystem first.
- Do not include secrets intentionally. If a repo may contain secrets, use focused `--include` patterns or add excludes.
- For private GitHub repositories, prefer using `GITHUB_TOKEN` from the environment rather than passing a token inline.
