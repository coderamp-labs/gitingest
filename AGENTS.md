# Agent instructions for this repository

This repository contains Gitingest, a Python CLI/package that turns repositories into prompt-friendly text digests.

When working here with Hermes or another coding agent:

1. Use a virtual environment; do not install into system Python.
2. Run focused tests before claiming changes work:
   ```bash
   python -m pytest tests/test_cli.py tests/test_ingestion.py -q
   ```
3. For Hermes context-pack changes, smoke test:
   ```bash
   python scripts/hermes_ingest.py . --name gitingest-smoke --include "*.py,*.md,pyproject.toml" --exclude ".venv/*"
   ```
4. Do not print or commit GitHub tokens. Prefer `GITHUB_TOKEN` from the environment for private repositories.
5. Treat generated context packs as local artifacts; they belong under `~/.hermes/repo-context/`, not in git.
