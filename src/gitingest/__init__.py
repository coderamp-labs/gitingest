"""Gitingest: A package for ingesting data from Git repositories."""

from gitingest.digest import parse_digest, restore_digest
from gitingest.entrypoint import ingest, ingest_async

__all__ = ["ingest", "ingest_async", "parse_digest", "restore_digest"]
