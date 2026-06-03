"""Tests für fetcher.py — RSS-Feed-Artikel abrufen und speichern."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

# Importiere die testbaren Funktionen
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetcher import (
    extract_fulltext,
    extract_summary,
    load_sources,
    parse_date,
    save_articles,
)


# --- load_sources ---

def test_load_sources_valid(tmp_path):
    """Valide sources.yaml wird korrekt geladen."""
    sources_yaml = tmp_path / "sources.yaml"
    sources_yaml.write_text(
        yaml.dump({
            "sources": [
                {"name": "Heise", "url": "https://heise.de/rss", "language": "de"},
                {"name": "TechCrunch", "url": "https://techcrunch.com/rss", "language": "en"},
            ]
        }),
        encoding="utf-8",
    )
    result = load_sources(sources_yaml)
    assert len(result) == 2
    assert result[0]["name"] == "Heise"
    assert result[1]["language"] == "en"


def test_load_sources_missing_file():
    """Fehlende Datei führt zu sys.exit(1)."""
    with pytest.raises(SystemExit) as exc:
        load_sources(Path("/nonexistent/sources.yaml"))
    assert exc.value.code == 1


def test_load_sources_no_sources_key(tmp_path):
    """YAML ohne 'sources'-Schlüssel führt zu sys.exit(1)."""
    sources_yaml = tmp_path / "sources.yaml"
    sources_yaml.write_text(yaml.dump({"other": "stuff"}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        load_sources(sources_yaml)
    assert exc.value.code == 1


# --- parse_date ---

def test_parse_date_valid():
    """Valides published_parsed-Tupel wird korrekt zu ISO-String."""
    class Entry:
        published_parsed = (2025, 6, 3, 10, 30, 0, 1, 154, 0)

    result = parse_date(Entry())
    assert result == "2025-06-03T10:30:00+00:00"


def test_parse_date_updated_fallback():
    """Falls published_parsed fehlt, wird updated_parsed verwendet."""
    class Entry:
        published_parsed = None
        updated_parsed = (2025, 6, 2, 15, 0, 0, 1, 153, 0)

    result = parse_date(Entry())
    assert result == "2025-06-02T15:00:00+00:00"


def test_parse_date_none():
    """Ohne Datum-Informationen wird None zurückgegeben."""
    class Entry:
        published_parsed = None
        updated_parsed = None

    result = parse_date(Entry())
    assert result is None


def test_parse_date_invalid_tuple():
    """Ungültiges Tupel wird abgefangen (TypeError)."""
    class Entry:
        published_parsed = ("invalid",)
        updated_parsed = None

    result = parse_date(Entry())
    assert result is None


# --- extract_fulltext ---

def test_extract_fulltext_content():
    """content-Feld wird bevorzugt."""
    class ContentValue:
        value = "Volltext aus content"

    class ContentItem:
        def get(self, key, default):
            return "Volltext aus content"

    class Entry:
        content = [ContentItem()]
        summary_detail = None
        summary = "kurz"

    result = extract_fulltext(Entry())
    assert result == "Volltext aus content"


def test_extract_fulltext_summary_detail_fallback():
    """Ohne content wird summary_detail verwendet."""

    class SD:
        def get(self, key, default):
            return "Volltext aus summary_detail"

    class Entry:
        content = None
        summary_detail = SD()
        summary = "kurz"

    result = extract_fulltext(Entry())
    assert result == "Volltext aus summary_detail"


def test_extract_fulltext_summary_fallback():
    """Ohne content und summary_detail wird summary verwendet."""
    class Entry:
        content = None
        summary_detail = None
        summary = "Nur summary"

    result = extract_fulltext(Entry())
    assert result == "Nur summary"


def test_extract_fulltext_empty():
    """Alles None ergibt leeren String."""
    class Entry:
        content = None
        summary_detail = None
        summary = ""

    result = extract_fulltext(Entry())
    assert result == ""


# --- extract_summary ---

def test_extract_summary_description_first():
    """description wird vor summary bevorzugt."""
    class Entry:
        description = "Beschreibung"
        summary = "Zusammenfassung"

    result = extract_summary(Entry())
    assert result == "Beschreibung"


def test_extract_summary_fallback():
    """Ohne description wird summary verwendet."""
    class Entry:
        description = None
        summary = "Zusammenfassung"

    result = extract_summary(Entry())
    assert result == "Zusammenfassung"


def test_extract_summary_empty():
    """Beide leer ergibt leeren String."""
    class Entry:
        description = None
        summary = None

    result = extract_summary(Entry())
    assert result == ""


# --- save_articles ---

def test_save_articles_new(tmp_path, monkeypatch):
    """Neue Artikel werden als JSON gespeichert."""
    monkeypatch.setattr("fetcher.ARTICLES_DIR", tmp_path)

    articles = [
        {
            "source": "Heise", "url": "https://h.de/1",
            "title": "Test", "date": "2025-06-03T10:00:00+00:00",
        }
    ]

    result = save_articles(articles)

    assert result.suffix == ".json"
    assert result.parent == tmp_path

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["source"] == "Heise"


def test_save_articles_deduplication(tmp_path, monkeypatch):
    """Doppelte URLs werden beim Mergen nicht erneut gespeichert."""
    monkeypatch.setattr("fetcher.ARTICLES_DIR", tmp_path)

    # Zuerst einen Artikel speichern
    articles1 = [
        {"source": "Heise", "url": "https://h.de/1", "title": "Test1"}
    ]
    save_articles(articles1)

    # Dann nochmal mit überlappendem Set speichern
    articles2 = [
        {"source": "Heise", "url": "https://h.de/1", "title": "Test1"},  # Duplikat
        {"source": "Spiegel", "url": "https://s.de/2", "title": "Test2"},  # Neu
    ]
    result = save_articles(articles2)

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert len(saved) == 2  # Nur 2, nicht 3


def test_save_articles_empty_result_still_saves(tmp_path, monkeypatch):
    """Auch leere Liste produziert eine JSON-Datei."""
    monkeypatch.setattr("fetcher.ARTICLES_DIR", tmp_path)
    result = save_articles([])

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved == []
