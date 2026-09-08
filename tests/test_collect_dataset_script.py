"""Tests for scripts/collect_dataset.py batch behavior (Milestone 4).

The GitHub boundary (analyze_user) is monkeypatched -- no live calls, no
database writes.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_dataset.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("collect_dataset_script", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


def test_continues_across_per_user_failures_and_reports(script, tmp_path, capsys, monkeypatch):
    calls = []

    def fake_analyze(username):
        calls.append(username)
        if username == "boom":
            raise RuntimeError("simulated transient failure")
        return {"score": {"total_score": 50}, "time": 0.1}

    monkeypatch.setattr(script, "analyze_user", fake_analyze)

    listing = tmp_path / "usernames.txt"
    listing.write_text("alice\nboom\ncarol\n", encoding="utf-8")

    exit_code = script.main(["collect_dataset.py", str(listing)])
    out = capsys.readouterr().out

    assert calls == ["alice", "boom", "carol"]  # did not stop at "boom"
    assert exit_code == 2  # finished, but with failures
    assert "succeeded: 2" in out
    assert "failed:    1" in out
    assert "elapsed:" in out
    assert "boom: RuntimeError: simulated transient failure" in out


def test_all_success_returns_zero(script, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        script, "analyze_user",
        lambda u: {"score": {"total_score": 33}, "time": 0.0},
    )
    listing = tmp_path / "u.txt"
    listing.write_text("alice\nbob\n", encoding="utf-8")

    assert script.main(["collect_dataset.py", str(listing)]) == 0
    assert "succeeded: 2" in capsys.readouterr().out


def test_missing_file_returns_one_and_explains(script, tmp_path, capsys):
    assert script.main(["collect_dataset.py", str(tmp_path / "absent.txt")]) == 1
    assert "not found" in capsys.readouterr().out


def test_empty_after_comments_returns_one(script, tmp_path, capsys):
    listing = tmp_path / "u.txt"
    listing.write_text("# nothing here\n\n", encoding="utf-8")
    assert script.main(["collect_dataset.py", str(listing)]) == 1
    assert "No usernames to collect" in capsys.readouterr().out


def test_does_not_print_the_github_token(script, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_SUPERSECRETVALUE123")

    def fake_analyze(username):
        raise RuntimeError("GitHub request failed: 403")

    monkeypatch.setattr(script, "analyze_user", fake_analyze)
    listing = tmp_path / "u.txt"
    listing.write_text("alice\n", encoding="utf-8")

    script.main(["collect_dataset.py", str(listing)])
    assert "ghp_SUPERSECRETVALUE123" not in capsys.readouterr().out
