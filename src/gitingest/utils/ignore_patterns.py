"""Default ignore patterns for Gitingest."""

from __future__ import annotations

from pathlib import Path

DEFAULT_IGNORE_PATTERNS: set[str] = {
    # Python
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "__pycache__",
    ".pytest_cache",
    ".coverage",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    "poetry.lock",
    "Pipfile.lock",
    # JavaScript/FileSystemNode
    "node_modules",
    "bower_components",
    "package-lock.json",
    "yarn.lock",
    ".npm",
    ".yarn",
    ".pnpm-store",
    "bun.lock",
    "bun.lockb",
    # Java
    "*.class",
    "*.jar",
    "*.war",
    "*.ear",
    "*.nar",
    ".gradle/",
    "build/",
    ".settings/",
    ".classpath",
    "gradle-app.setting",
    "*.gradle",
    # IDEs and editors / Java
    ".project",
    # C/C++
    "*.o",
    "*.obj",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.lib",
    "*.out",
    "*.a",
    "*.pdb",
    # Binary
    "*.bin",
    # Swift/Xcode
    ".build/",
    "*.xcodeproj/",
    "*.xcworkspace/",
    "*.pbxuser",
    "*.mode1v3",
    "*.mode2v3",
    "*.perspectivev3",
    "*.xcuserstate",
    "xcuserdata/",
    ".swiftpm/",
    # Ruby
    "*.gem",
    ".bundle/",
    "vendor/bundle",
    "Gemfile.lock",
    ".ruby-version",
    ".ruby-gemset",
    ".rvmrc",
    # Rust
    "Cargo.lock",
    "**/*.rs.bk",
    # Java / Rust
    "target/",
    # Go
    "pkg/",
    # .NET/C#
    "obj/",
    "*.suo",
    "*.user",
    "*.userosscache",
    "*.sln.docstates",
    "*.nupkg",
    # Go / .NET / C#
    "bin/",
    # Version control
    ".git",
    ".svn",
    ".hg",
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    # Images and media
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.pdf",
    "*.mov",
    "*.mp4",
    "*.mp3",
    "*.wav",
    # Virtual environments
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenv",
    # IDEs and editors
    ".idea",
    ".vscode",
    ".vs",
    "*.swo",
    "*.swn",
    ".settings",
    "*.sublime-*",
    # Temporary and cache files
    "*.log",
    "*.bak",
    "*.swp",
    "*.tmp",
    "*.temp",
    ".cache",
    ".sass-cache",
    ".eslintcache",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    # Build directories and artifacts
    "build",
    "dist",
    "target",
    "out",
    "*.egg-info",
    "*.egg",
    "*.whl",
    "*.so",
    # Documentation
    "site-packages",
    ".docusaurus",
    ".next",
    ".nuxt",
    # Database
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    # Other common patterns
    ## Minified files
    "*.min.js",
    "*.min.css",
    ## Source maps
    "*.map",
    ## Terraform
    "*.tfstate*",
    ## Dependencies in various languages
    "vendor/",
    # Gitingest
    "digest.txt",
}


def load_ignore_patterns(root: Path, filename: str) -> set[str]:
    """Load ignore patterns from ``filename`` found under ``root``.

    The loader walks the directory tree, looks for the supplied ``filename``,
    and returns a unified set of patterns. It implements the same parsing rules
    we use for ``.gitignore`` and ``.gitingestignore`` (git-wildmatch syntax with
    support for negation and root-relative paths).

    Parameters
    ----------
    root : Path
        Directory to walk.
    filename : str
        The filename to look for in each directory.

    Returns
    -------
    set[str]
        A set of ignore patterns extracted from the ``filename`` file found under the ``root`` directory.

    """
    patterns: set[str] = set()

    for ignore_file in root.rglob(filename):
        if ignore_file.is_file():
            patterns.update(_parse_ignore_file(ignore_file, root))
    return patterns


def _parse_ignore_file(ignore_file: Path, root: Path) -> set[str]:
    """Parse an ignore file and return a set of ignore patterns.

    Parameters
    ----------
    ignore_file : Path
        The path to the ignore file.
    root : Path
        The root directory of the repository.

    Returns
    -------
    set[str]
        A set of ignore patterns.

    """
    patterns: set[str] = set()

    # Path of the ignore file relative to the repository root
    rel_dir = ignore_file.parent.relative_to(root)
    base_dir = Path() if rel_dir == Path() else rel_dir

    with ignore_file.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):  # comments / blank lines
                continue

            # Handle negation ("!foobar")
            negated = line.startswith("!")
            if negated:
                line = line[1:]

            # Handle leading slash ("/foobar")
            if line.startswith("/"):
                line = line.lstrip("/")

            pattern_body = (base_dir / line).as_posix()
            patterns.add(f"!{pattern_body}" if negated else pattern_body)

    return patterns
