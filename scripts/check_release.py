"""Read-only release hygiene checks; not a comprehensive security audit.

Checks tracked and non-ignored candidate files, not Git history or remote URLs.
Only inline Markdown file links are checked; heading anchors are not validated.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

MAX_FILE_BYTES = 2_000_000
SECRET_PATTERNS = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-|svcacct-)?[0-9A-Za-z_-]{32,}"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[0-9A-Za-z]{36,}|github_pat_[\w]{40,})"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
}
GENERATED_ROOTS = (
    "data/raw/",
    "data/processed/",
    "artifacts/",
    "embeddings/",
    "indexes/",
    ".venv/",
    "venv/",
    "pgdata/",
    "build/",
    "dist/",
)
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)")


def secret_categories(content: str) -> list[str]:
    """Return category names, never matched credential values."""
    return [label for label, pattern in SECRET_PATTERNS.items() if pattern.search(content)]


def check_files(root: Path, candidates: list[Path]) -> list[str]:
    root = root.resolve()
    paths = {path.resolve() for path in candidates}
    issues: list[str] = []
    for path in sorted(paths):
        if not path.is_relative_to(root):
            issues.append("candidate path escapes repository")
            continue
        name = path.relative_to(root).as_posix()
        if path.name != ".env.example" and (path.name == ".env" or path.name.startswith(".env.")):
            issues.append(f"{name}: environment file must not be published")
        if name.startswith(GENERATED_ROOTS):
            issues.append(f"{name}: generated/private directory must not be published")
        if not path.is_file():
            issues.append(f"{name}: candidate is not a regular file")
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            issues.append(f"{name}: exceeds the 2 MB review threshold")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(f"{name}: binary/non-UTF-8 file requires manual review")
            continue
        for label in secret_categories(content):
            issues.append(f"{name}: possible {label} (value withheld)")
        if path.suffix.lower() != ".md":
            continue
        # Ignore code samples; they can legitimately demonstrate placeholder links.
        prose = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        for match in LINK.finditer(prose):
            target = match.group(1).strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = (path.parent / unquote(parsed.path)).resolve()
            if destination not in paths or not destination.is_file():
                issues.append(f"{name}: local link target is not a publishable file: {target}")
    return issues


def candidate_files(root: Path) -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / name for name in result.stdout.decode("utf-8").split("\0") if name]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    candidates = candidate_files(root)
    issues = check_files(root, candidates)
    print(f"Reviewed {len(set(candidates))} tracked/non-ignored candidate files.")
    for issue in issues:
        print(issue)
    if issues:
        return 1
    total = sum(path.stat().st_size for path in set(candidates))
    print(f"PASS: local file links and bounded hygiene checks; candidate content {total:,} bytes.")
    print("Not checked: remote URLs, heading anchors, Git history, arbitrary secret formats.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
