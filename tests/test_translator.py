"""Tests für translator.py — Übersetzung via DeepSeek LLM API."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from translator import (
    build_translation_text,
    detect_language,
    parse_translation,
    should_translate,
)


# --- detect_language ---

def test_detect_language_too_short():
    """Zu kurzer Text ergibt 'unknown'."""
    result = detect_language("Hi")
    assert result == "unknown"


# --- should_translate ---

def test_should_translate_german():
    """Deutsche Artikel (language='de') werden nicht übersetzt."""
    article = {"language": "de", "title": "Hallo Welt"}
    assert should_translate(article) is False


def test_should_translate_english():
    """Englische Artikel (language='en') werden übersetzt."""
    article = {"language": "en", "title": "Hello World"}
    assert should_translate(article) is True


def test_should_translate_german_full():
    """language='german' wird auch erkannt."""
    article = {"language": "german", "title": "Hallo"}
    assert should_translate(article) is False


def test_should_translate_unknown_defaults_true():
    """Unbekannte Sprache → default True (better safe than sorry)."""
    article = {"language": "fr", "title": "Bonjour"}
    assert should_translate(article) is True


def test_should_translate_no_language_field():
    """Ohne language-Feld → default True."""
    article = {"title": "Some text here in English language for testing"}
    assert should_translate(article) is True


# --- build_translation_text ---

def test_build_translation_text_all_fields():
    """Alle Felder werden im Übersetzungstext zusammengefügt."""
    article = {
        "title": "AI Breakthrough",
        "summary": "New model achieves record performance.",
        "full_text": "Detailed article about the new AI model...",
    }
    result = build_translation_text(article)
    assert "Title: AI Breakthrough" in result
    assert "Summary: New model achieves record performance." in result
    assert "Body: Detailed article about the new AI model..." in result


def test_build_translation_text_content_fallback():
    """content wird als Fallback für full_text verwendet."""
    article = {
        "title": "Test",
        "content": "Some content here.",
    }
    result = build_translation_text(article)
    assert "Body: Some content here." in result


def test_build_translation_text_empty():
    """Leerer Artikel ergibt leeren Text."""
    article = {}
    result = build_translation_text(article)
    assert result == ""


# --- parse_translation ---

def test_parse_translation_none():
    """None-Übersetzung gibt Original-Artikel zurück."""
    article = {"title": "Original", "source": "Test"}
    result = parse_translation(None, article)
    assert result is article
    assert "translated" not in article


def test_parse_translation_structured():
    """Strukturierte LLM-Antwort wird korrekt geparst."""
    article = {"title": "Original Title"}
    text = (
        "Title: Übersetzter Titel\n"
        "Summary: Übersetzte Zusammenfassung\n"
        "Body: Übersetzter Textkörper\n"
    )
    result = parse_translation(text, article)
    assert result["title_de"] == "Übersetzter Titel"
    assert result["summary_de"] == "Übersetzte Zusammenfassung"
    assert result["full_text_de"] == "Übersetzter Textkörper"
    assert result["translation_status"] == "ok"
    assert result["translated"] is True


def test_parse_translation_multiline():
    """Mehrzeilige Body-Felder werden korrekt behandelt."""
    article = {"title": "Original"}
    text = (
        "Title: Titel Deutsch\n"
        "Body: Erste Zeile des Textes\n"
        "Zweite Zeile des Textes\n"
        "Dritte Zeile\n"
    )
    result = parse_translation(text, article)
    assert result["title_de"] == "Titel Deutsch"
    assert "Erste Zeile" in result["full_text_de"]
    assert "Dritte Zeile" in result["full_text_de"]


def test_parse_translation_unstructured():
    """Unstrukturierte Antwort wird als full_text_de gespeichert."""
    article = {"title": "Original"}
    text = "Einfach nur ein deutscher Text ohne Labels."
    result = parse_translation(text, article)
    assert result["full_text_de"] == "Einfach nur ein deutscher Text ohne Labels."
    assert "title_de" not in result
    assert "summary_de" not in result
    assert result["translation_status"] == "ok"
    assert result["translated"] is True


def test_parse_translation_german_labels():
    """Deutsche Labels ('Titel:', 'Zusammenfassung:', 'Text:') werden erkannt."""
    article = {"title": "Original"}
    text = (
        "Titel: Deutscher Titel\n"
        "Zusammenfassung: Deutsche Summary\n"
        "Text: Deutscher Body\n"
    )
    result = parse_translation(text, article)
    assert result["title_de"] == "Deutscher Titel"
    assert result["summary_de"] == "Deutsche Summary"
    assert result["full_text_de"] == "Deutscher Body"
