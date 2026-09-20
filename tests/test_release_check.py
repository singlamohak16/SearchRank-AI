"""The release check never publishes files or prints matched secret values."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release.py"
SPEC = importlib.util.spec_from_file_location("release_check", SCRIPT)
assert SPEC and SPEC.loader
release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_check)


def test_local_links_require_publishable_target(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    guide = tmp_path / "guide with spaces.md"
    readme.write_text("[guide](<guide with spaces.md#setup>)\n", encoding="utf-8")
    guide.write_text("# Setup\n", encoding="utf-8")
    assert release_check.check_files(tmp_path, [readme, guide]) == []
    assert "not a publishable file" in release_check.check_files(tmp_path, [readme])[0]


def test_external_anchor_and_fenced_example_links_are_not_file_checks(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "[site](https://example.invalid/) [section](#setup)\n```md\n[x](missing.md)\n```",
        encoding="utf-8",
    )
    assert release_check.check_files(tmp_path, [readme]) == []


@pytest.mark.parametrize(
    ("prefix", "body", "label"),
    [
        ("AIza", "A" * 35, "Google API key"),
        ("sk-proj-", "B" * 40, "OpenAI-style key"),
        ("ghp_", "C" * 36, "GitHub token"),
        ("-----BEGIN ", "PRIVATE KEY-----", "private key"),
    ],
)
def test_secret_findings_are_redacted(
    tmp_path: Path,
    prefix: str,
    body: str,
    label: str,
) -> None:
    secret = prefix + body
    path = tmp_path / "example.txt"
    path.write_text(secret, encoding="utf-8")
    issues = release_check.check_files(tmp_path, [path])
    assert len(issues) == 1 and label in issues[0]
    assert secret not in issues[0]


def test_environment_example_allowed_but_private_file_rejected(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    private = tmp_path / ".env.local"
    example.write_text("GEMINI_API_KEY=\n", encoding="utf-8")
    private.write_text("GEMINI_API_KEY=\n", encoding="utf-8")
    assert release_check.check_files(tmp_path, [example]) == []
    assert "must not be published" in release_check.check_files(tmp_path, [private])[0]


def test_generated_files_large_files_and_binary_require_review(tmp_path: Path) -> None:
    generated = tmp_path / "artifacts" / "result.json"
    generated.parent.mkdir()
    generated.write_text("{}", encoding="utf-8")
    large = tmp_path / "large.txt"
    large.write_bytes(b"x" * (release_check.MAX_FILE_BYTES + 1))
    binary = tmp_path / "binary.dat"
    binary.write_bytes(b"\xff")
    issues = release_check.check_files(tmp_path, [generated, large, binary])
    assert len(issues) == 3


def test_missing_and_outside_files_are_rejected(tmp_path: Path) -> None:
    issues = release_check.check_files(
        tmp_path, [tmp_path / "missing", tmp_path.parent / "outside"]
    )
    assert len(issues) == 2
