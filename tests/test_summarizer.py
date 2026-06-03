"""Tests für summarizer.py — Zusammenfassung via LLM."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from summarizer import (
    build_markdown,
    get_today_str,
    load_translated_articles,
    resolve_date,
    save_results,
    summarize_article,
    summarize_daily_overview,
)


# --- resolve_date ---

def test_resolve_date_today():
    """None ergibt heute."""
    result = resolve_date(None)
    assert result == get_today_str()


def test_resolve_date_valid():
    """Valides Datum wird durchgereicht."""
    result = resolve_date("2025-06-03")
    assert result == "2025-06-03"


def test_resolve_date_invalid():
    """Ungültiges Datum führt zu sys.exit(1)."""
    with pytest.raises(SystemExit) as exc:
        resolve_date("03-06-2025")
    assert exc.value.code == 1


# --- get_today_str ---

def test_get_today_str_format():
    """get_today_str gibt YYYY-MM-DD zurück."""
    result = get_today_str()
    assert len(result) == 10
    assert result[4] == "-"
    assert result[7] == "-"


# --- load_translated_articles ---

def test_load_translated_articles_valid(tmp_path):
    """Valides JSON wird geladen."""
    (tmp_path / "data" / "articles").mkdir(parents=True)
    articles = [{"title": "Test", "translated": True}]
    path = tmp_path / "data" / "articles" / "2025-06-03_translated.json"
    path.write_text(json.dumps(articles), encoding="utf-8")

    result = load_translated_articles(tmp_path, "2025-06-03")
    assert len(result) == 1
    assert result[0]["title"] == "Test"


def test_load_translated_articles_missing(tmp_path):
    """Fehlende Datei ergibt leere Liste."""
    result = load_translated_articles(tmp_path, "2025-06-03")
    assert result == []


def test_load_translated_articles_not_a_list(tmp_path):
    """Keine JSON-Liste führt zu sys.exit(1)."""
    (tmp_path / "data" / "articles").mkdir(parents=True)
    path = tmp_path / "data" / "articles" / "2025-06-03_translated.json"
    path.write_text(json.dumps({"oops": "dict"}), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        load_translated_articles(tmp_path, "2025-06-03")
    assert exc.value.code == 1


# --- summarize_article ---

def test_summarize_article_success(mock_openai_client):
    """Erfolgreiche Zusammenfassung via Mock-Client."""
    article = {
        "title": "AI Breakthrough",
        "url": "https://example.com/1",
        "source": "TechCrunch",
        "content": "Researchers at Stanford have developed a new AI model...",
    }

    result = summarize_article(mock_openai_client, article)

    assert result["title"] == "AI Breakthrough"
    assert result["url"] == "https://example.com/1"
    assert result["source"] == "TechCrunch"
    assert result["status"] == "summarized"
    assert result["summary_points"] == "Übersetzter Text auf Deutsch."


def test_summarize_article_api_error(mock_openai_client):
    """API-Fehler wird abgefangen und als summary_failed markiert."""
    mock_openai_client.chat.completions.create.side_effect = RuntimeError("API down")

    article = {"title": "Test", "url": "https://ex.com", "source": "X"}
    result = summarize_article(mock_openai_client, article)

    assert result["status"] == "summary_failed"
    assert "API down" in result["error"]


def test_summarize_article_missing_content():
    """Fehlender Content wird durch summary ersetzt."""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Zusammenfassung."
    client.chat.completions.create.return_value = response

    article = {
        "title": "Test",
        "url": "https://ex.com",
        "source": "X",
        "summary": "Kurze Zusammenfassung",
    }
    result = summarize_article(client, article)
    assert result["status"] == "summarized"


# --- summarize_daily_overview ---

def test_summarize_daily_overview_empty():
    """Leere Liste gibt Standardtext zurück."""
    client = MagicMock()
    result = summarize_daily_overview(client, [])
    assert result == "Keine Artikel für heute."


def test_summarize_daily_overview_all_failed():
    """Nur fehlgeschlagene Zusammenfassungen."""
    client = MagicMock()
    summaries = [
        {"title": "X", "status": "summary_failed", "error": "err"},
    ]
    result = summarize_daily_overview(client, summaries)
    assert "konnte für keinen Artikel" in result


def test_summarize_daily_overview_success(mock_openai_client):
    """Erfolgreiche Tagesübersicht."""
    summaries = [
        {"title": "AI News", "status": "summarized", "summary_points": "- KI Fortschritt\n- Neue Modelle"},
        {"title": "Tech", "status": "summarized", "summary_points": "- Startup Funding\n- IPO"},
    ]
    mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "Heute gab es wichtige KI-Entwicklungen."

    result = summarize_daily_overview(mock_openai_client, summaries)
    assert result == "Heute gab es wichtige KI-Entwicklungen."


def test_summarize_daily_overview_api_error(mock_openai_client):
    """API-Fehler bei Tagesübersicht wird abgefangen."""
    mock_openai_client.chat.completions.create.side_effect = RuntimeError("timeout")

    summaries = [
        {"title": "AI", "status": "summarized", "summary_points": "- Punkt 1"},
    ]
    result = summarize_daily_overview(mock_openai_client, summaries)
    assert "konnte nicht erstellt werden" in result
    assert "1 Artikel" in result


# --- build_markdown ---

def test_build_markdown_structure():
    """Markdown-Newsletter hat korrekte Struktur."""
    summaries = [
        {
            "title": "KI Fortschritt",
            "url": "https://example.com/1",
            "source": "TechCrunch",
            "status": "summarized",
            "summary_points": "- Punkt 1\n- Punkt 2",
        },
    ]

    result = build_markdown("2025-06-03", "Heutige Übersicht", summaries)

    assert "# Relevant News — 2025-06-03" in result
    assert "## 📋 Tagesübersicht" in result
    assert "Heutige Übersicht" in result
    assert "## 📰 Artikel (1)" in result
    assert "### 1. KI Fortschritt" in result
    assert "[https://example.com/1]" in result
    assert "*Quelle: TechCrunch*" in result
    assert "- Punkt 1" in result


def test_build_markdown_failed_summary():
    """Fehlgeschlagene Zusammenfassung wird markiert."""
    summaries = [
        {
            "title": "Fehler",
            "url": "",
            "source": "X",
            "status": "summary_failed",
            "error": "timeout",
        },
    ]

    result = build_markdown("2025-06-03", "Übersicht", summaries)
    assert "⚠️" in result
    assert "timeout" in result


def test_build_markdown_unknown_status():
    """Unbekannter Status wird mit Fallback-Text dargestellt."""
    summaries = [
        {
            "title": "Irgendwas",
            "url": "",
            "source": "X",
            "status": "pending",
        },
    ]

    result = build_markdown("2025-06-03", "Übersicht", summaries)
    assert "Keine Zusammenfassung" in result


# --- save_results ---

def test_save_results(tmp_path):
    """JSON und Markdown werden korrekt gespeichert."""
    summaries = [
        {
            "title": "Test",
            "url": "https://ex.com",
            "source": "X",
            "status": "summarized",
            "summary_points": "- Punkt",
        },
    ]

    save_results("2025-06-03", "Tagesübersicht", summaries, tmp_path)

    json_path = tmp_path / "data" / "summaries" / "2025-06-03.json"
    md_path = tmp_path / "data" / "summaries" / "2025-06-03.md"

    assert json_path.exists()
    assert md_path.exists()

    # JSON validieren
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["date"] == "2025-06-03"
    assert data["daily_overview"] == "Tagesübersicht"
    assert data["article_count"] == 1

    # Markdown hat Inhalt
    md = md_path.read_text(encoding="utf-8")
    assert len(md) > 0


def test_save_results_empty(tmp_path):
    """Leere Zusammenfassungen werden trotzdem gespeichert."""
    save_results("2025-06-03", "Keine Artikel für heute.", [], tmp_path)

    json_path = tmp_path / "data" / "summaries" / "2025-06-03.json"
    md_path = tmp_path / "data" / "summaries" / "2025-06-03.md"

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["article_count"] == 0
