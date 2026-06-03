"""Tests für run.py — Pipeline-Orchestrator."""
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run import fmt_path, PIPELINE, run_pipeline, run_step


# --- fmt_path ---

def test_fmt_path():
    """{date}-Platzhalter wird korrekt ersetzt."""
    result = fmt_path(Path("/data/articles/{date}.json"), "2025-06-03")
    assert str(result) == str(Path("/data/articles/2025-06-03.json"))


def test_fmt_path_no_placeholder():
    """Ohne {date} bleibt der Pfad unverändert."""
    result = fmt_path(Path("/static/output.md"), "2025-06-03")
    assert str(result) == str(Path("/static/output.md"))


# --- PIPELINE structure ---

def test_pipeline_order():
    """Pipeline-Schritte sind in der richtigen Reihenfolge."""
    step_names = [s["name"] for s in PIPELINE]
    assert step_names == ["fetcher", "filter", "translator", "summarizer", "output"]


def test_pipeline_all_steps_have_required_keys():
    """Jeder Schritt hat die benötigten Keys."""
    required = {"name", "desc", "script", "date_arg", "output"}
    for step in PIPELINE:
        missing = required - set(step.keys())
        assert not missing, f"Schritt {step.get('name', '?')} fehlen: {missing}"


def test_pipeline_date_arg_values():
    """date_arg enthält nur gültige Werte."""
    valid = {"flag", "positional", "none"}
    for step in PIPELINE:
        assert step["date_arg"] in valid, f"Ungültiges date_arg in {step['name']}"


# --- run_step (mocked subprocess) ---

def test_run_step_success(tmp_path, monkeypatch):
    """Erfolgreicher Schritt-Durchlauf."""
    monkeypatch.setattr("run.PROJECT_ROOT", tmp_path)

    # Erstelle Dummy-Script und Output-Datei
    script = tmp_path / "test_step.py"
    script.write_text("print('ok')")

    output_path = tmp_path / "output.json"
    output_path.write_text("{}")

    step = {
        "name": "test",
        "desc": "Test-Schritt",
        "script": "test_step.py",
        "date_arg": "flag",
        "output": output_path,
    }

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = run_step(step, "2025-06-03", python="python")

    assert result is True
    mock_run.assert_called_once()


def test_run_step_failure(tmp_path, monkeypatch):
    """Fehlgeschlagener Schritt gibt False zurück."""
    monkeypatch.setattr("run.PROJECT_ROOT", tmp_path)

    script = tmp_path / "fail_step.py"
    script.write_text("import sys; sys.exit(1)")

    step = {
        "name": "fail",
        "desc": "Fehler-Schritt",
        "script": "fail_step.py",
        "date_arg": "positional",
        "output": tmp_path / "out.json",
    }

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error!"
        mock_run.return_value = mock_result

        result = run_step(step, "2025-06-03", python="python")

    assert result is False


def test_run_step_missing_script(tmp_path, monkeypatch):
    """Fehlendes Script wird soft-geskipped (True)."""
    monkeypatch.setattr("run.PROJECT_ROOT", tmp_path)

    step = {
        "name": "missing",
        "desc": "Fehlt",
        "script": "nicht_da.py",
        "date_arg": "none",
        "output": tmp_path / "out.json",
    }

    result = run_step(step, "2025-06-03", python="python")
    assert result is True  # soft-skip


def test_run_step_date_arg_flag(tmp_path, monkeypatch):
    """date_arg='flag' übergibt --date <day>."""
    monkeypatch.setattr("run.PROJECT_ROOT", tmp_path)

    script = tmp_path / "flag_step.py"
    script.write_text("print('ok')")

    step = {
        "name": "flag",
        "desc": "Flag Test",
        "script": "flag_step.py",
        "date_arg": "flag",
        "output": tmp_path / "out.json",
    }

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        run_step(step, "2025-06-03", python="python")

    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert "--date" in args
    assert "2025-06-03" in args


def test_run_step_date_arg_positional(tmp_path, monkeypatch):
    """date_arg='positional' übergibt Datum als letztes Arg."""
    monkeypatch.setattr("run.PROJECT_ROOT", tmp_path)

    script = tmp_path / "pos_step.py"
    script.write_text("print('ok')")

    step = {
        "name": "pos",
        "desc": "Positional Test",
        "script": "pos_step.py",
        "date_arg": "positional",
        "output": tmp_path / "out.json",
    }

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        run_step(step, "2025-06-03", python="python")

    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert args[-1] == "2025-06-03"


def test_run_step_date_arg_none(tmp_path, monkeypatch):
    """date_arg='none' übergibt kein Datum."""
    monkeypatch.setattr("run.PROJECT_ROOT", tmp_path)

    script = tmp_path / "none_step.py"
    script.write_text("print('ok')")

    step = {
        "name": "none",
        "desc": "No Date",
        "script": "none_step.py",
        "date_arg": "none",
        "output": tmp_path / "out.json",
    }

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        run_step(step, "2025-06-03", python="python")

    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert "2025-06-03" not in args
    assert "--date" not in args


# --- run_pipeline ---

def test_run_pipeline_dry_run():
    """Dry-Run führt keine Scripts aus."""
    with patch("subprocess.run") as mock_run:
        result = run_pipeline("2025-06-03", dry_run=True)
        assert result is True
        mock_run.assert_not_called()


def test_run_pipeline_stops_on_failure(tmp_path, monkeypatch):
    """Pipeline stoppt beim ersten Fehler."""
    monkeypatch.setattr("run.PROJECT_ROOT", tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_success = MagicMock()
        mock_success.returncode = 0
        mock_success.stdout = "ok"
        mock_success.stderr = ""

        mock_fail = MagicMock()
        mock_fail.returncode = 1
        mock_fail.stdout = ""
        mock_fail.stderr = "fail"

        mock_run.side_effect = [mock_success, mock_fail]

        for step in PIPELINE:
            s = tmp_path / step["script"]
            s.write_text("print('ok')")

        result = run_pipeline("2025-06-03")

    assert result is False
