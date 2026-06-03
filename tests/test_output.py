"""Tests für output.py — Ausgabe & Telegram-Delivery."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from output import (
    build_telegram_message,
    load_markdown,
    load_summary,
    save_markdown,
    send_telegram_bot,
    send_telegram_cli,
)


# --- load_summary ---

def test_load_summary_valid(tmp_path, monkeypatch):
    """Valide Summary-JSON wird geladen."""
    monkeypatch.setattr("output.SUMMARIES_DIR", tmp_path)
    summary = {"date": "2025-06-03", "daily_overview": "Heute...", "article_count": 2}
    (tmp_path / "2025-06-03.json").write_text(json.dumps(summary), encoding="utf-8")

    result = load_summary("2025-06-03")
    assert result["date"] == "2025-06-03"
    assert result["article_count"] == 2


def test_load_summary_missing(tmp_path, monkeypatch):
    """Fehlende Datei wirft FileNotFoundError."""
    monkeypatch.setattr("output.SUMMARIES_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_summary("2025-06-03")


def test_load_summary_default_today(tmp_path, monkeypatch):
    """Ohne day-Parameter wird heute verwendet."""
    monkeypatch.setattr("output.SUMMARIES_DIR", tmp_path)
    from datetime import date
    today = date.today().isoformat()
    summary = {"date": today}
    (tmp_path / f"{today}.json").write_text(json.dumps(summary), encoding="utf-8")

    result = load_summary()
    assert result["date"] == today


# --- load_markdown ---

def test_load_markdown_valid(tmp_path, monkeypatch):
    """Valides Markdown wird geladen."""
    monkeypatch.setattr("output.SUMMARIES_DIR", tmp_path)
    (tmp_path / "2025-06-03.md").write_text("# Relevant News\n\nInhalt...", encoding="utf-8")

    result = load_markdown("2025-06-03")
    assert "# Relevant News" in result


def test_load_markdown_missing(tmp_path, monkeypatch):
    """Fehlende Datei wirft FileNotFoundError."""
    monkeypatch.setattr("output.SUMMARIES_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_markdown("2025-06-03")


# --- save_markdown ---

def test_save_markdown(tmp_path, monkeypatch):
    """Markdown wird korrekt gespeichert."""
    monkeypatch.setattr("output.OUTPUT_DIR", tmp_path)

    result = save_markdown("# Test\n\nContent", "2025-06-03")
    assert result.exists()
    assert result.read_text(encoding="utf-8") == "# Test\n\nContent"


def test_save_markdown_default_today(tmp_path, monkeypatch):
    """Ohne day-Parameter wird heute verwendet."""
    monkeypatch.setattr("output.OUTPUT_DIR", tmp_path)

    result = save_markdown("# Today")
    from datetime import date
    assert date.today().isoformat() in str(result)


# --- build_telegram_message ---

def test_build_telegram_message_short():
    """Kurzer Text wird nicht gekürzt."""
    content = "Kurzer Text unter 4000 Zeichen."
    result = build_telegram_message(content)
    assert result == content


def test_build_telegram_message_long():
    """Langer Text wird gekürzt mit Hinweis."""
    content = "X" * 5000
    result = build_telegram_message(content)
    assert len(result) <= 4000
    assert "gekürzt" in result


def test_build_telegram_message_custom_max():
    """Custom max_chars wird respektiert."""
    content = "A" * 5000
    result = build_telegram_message(content, max_chars=500)
    # Die Nachricht inkl. Kürzungshinweis ist maximal max_chars lang
    assert len(result) <= 500


# --- send_telegram_cli ---

def test_send_telegram_cli_success(tmp_path):
    """Erfolgreicher Hermes-CLI-Aufruf."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Kurzer Test", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        result = send_telegram_cli(md_path, "2025-06-03")
        assert result is True
        mock_run.assert_called_once()


def test_send_telegram_cli_failure(tmp_path):
    """Fehlgeschlagener Hermes-CLI-Aufruf."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error message"
        mock_run.return_value = mock_result

        result = send_telegram_cli(md_path, "2025-06-03")
        assert result is False


def test_send_telegram_cli_not_found(tmp_path):
    """Hermes CLI nicht installiert."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")

    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = send_telegram_cli(md_path, "2025-06-03")
        assert result is False


def test_send_telegram_cli_long_message(tmp_path):
    """Lange Nachricht wird vor dem Senden gekürzt."""
    long_text = "# " + "X" * 5000
    md_path = tmp_path / "test.md"
    md_path.write_text(long_text, encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        result = send_telegram_cli(md_path, "2025-06-03")
        assert result is True

        # Check that the message was truncated
        call_msg = mock_run.call_args[0][0][-2]  # --message arg
        assert len(call_msg) <= 4000


# --- send_telegram_bot ---

def test_send_telegram_bot_success(tmp_path):
    """Erfolgreicher Bot-API-Aufruf."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_telegram_bot(md_path, "2025-06-03", "fake_token", "123")
        assert result is True


def test_send_telegram_bot_failure(tmp_path):
    """Bot-API-Fehler."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")

    with patch("requests.post", side_effect=Exception("Network error")):
        result = send_telegram_bot(md_path, "2025-06-03", "fake_token", "123")
        assert result is False


def test_send_telegram_bot_long_with_document(tmp_path):
    """Lange Nachricht triggert auch Dokument-Upload."""
    long_text = "X" * 5000
    md_path = tmp_path / "test.md"
    md_path.write_text(long_text, encoding="utf-8")

    with patch("requests.post") as mock_post:
        # First call: sendMessage
        # Second call: sendDocument
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_telegram_bot(md_path, "2025-06-03", "fake_token", "123")
        assert result is True
        # Should have been called twice (text + document)
        assert mock_post.call_count == 2
