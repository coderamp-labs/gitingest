"""Gitingest: A package for ingesting data from Git repositories."""

from gitingest.entrypoint import ingest, ingest_async

__all__ = ["ingest", "ingest_async"]
