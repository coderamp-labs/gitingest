"""Configuration file for the project."""

import tempfile
from pathlib import Path

MAX_FILE_SIZE = 10 * 1024 * 1024  # Maximum size of a single file to process (10 MB)
MAX_DIRECTORY_DEPTH = 20  # Maximum depth of directory traversal
MAX_FILES = 10_000  # Maximum number of files to process
MAX_TOTAL_SIZE_BYTES = 500 * 1024 * 1024  # Maximum size of output file (500 MB)
DEFAULT_TIMEOUT = 60  # seconds

# Memory optimization settings
BATCH_SIZE = 100  # Process files in batches to reduce memory usage
MEMORY_CHECK_INTERVAL = 25  # Check memory usage every N files (more frequent)
AGGRESSIVE_GC_INTERVAL = 10  # Force garbage collection every N files for large repos
MEMORY_PRESSURE_THRESHOLD_MB = 2000  # Trigger aggressive cleanup at 2GB usage

OUTPUT_FILE_NAME = "digest.txt"

TMP_BASE_PATH = Path(tempfile.gettempdir()) / "gitingest"
