"""Gitingest: A package for ingesting data from Git repositories."""

from gitingest.entrypoint import ingest, ingest_async
from gitingest.extract import extract

__all__ = ["ingest", "ingest_async", "extract"]
