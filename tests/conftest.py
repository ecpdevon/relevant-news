"""Gemeinsame Fixtures für alle Tests."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def project_dir(tmp_path):
    """Temporäres Projektverzeichnis mit data/articles/ Struktur."""
    (tmp_path / "data" / "articles").mkdir(parents=True)
    (tmp_path / "data" / "summaries").mkdir(parents=True)
    (tmp_path / "daily-news").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def sample_articles():
    """Beispiel-Artikel für Filter-/Translator-Tests."""
    return [
        {
            "source": "Heise",
            "source_url": "https://heise.de/rss",
            "language": "de",
            "title": "Neue KI-Modelle von OpenAI vorgestellt",
            "url": "https://heise.de/artikel1",
            "date": "2025-06-03T10:00:00+00:00",
            "summary": "OpenAI hat neue Modelle mit verbesserter Reasoning-Fähigkeit vorgestellt.",
            "fulltext": "Langer Artikel über KI...",
        },
        {
            "source": "TechCrunch",
            "source_url": "https://techcrunch.com/rss",
            "language": "en",
            "title": "Startup raises $50M for AI-powered cybersecurity platform",
            "url": "https://techcrunch.com/artikel2",
            "date": "2025-06-03T09:30:00+00:00",
            "summary": "A cybersecurity startup using AI has raised $50 million in Series B funding.",
            "fulltext": "Long article about cybersecurity and AI investment...",
        },
        {
            "source": "Spiegel",
            "source_url": "https://spiegel.de/rss",
            "language": "de",
            "title": "Sport: Bundesliga plant VAR-Reform",
            "url": "https://spiegel.de/artikel3",
            "date": "2025-06-03T08:00:00+00:00",
            "summary": "Die Bundesliga plant eine umfassende Reform des Videobeweises.",
            "fulltext": "Langer Artikel über VAR...",
        },
    ]


@pytest.fixture
def sample_translated_articles():
    """Übersetzte Beispiel-Artikel für Summarizer-Tests."""
    return [
        {
            "source": "TechCrunch",
            "language": "en",
            "title": "Startup raises $50M for AI-powered cybersecurity platform",
            "url": "https://techcrunch.com/artikel2",
            "summary": "A cybersecurity startup using AI has raised $50 million in Series B funding.",
            "content": "Startup raises $50M for AI-powered cybersecurity platform...",
            "translated": True,
            "translation_status": "ok",
            "title_de": "Startup sammelt 50 Mio. USD für KI-gestützte Cybersicherheitsplattform",
            "summary_de": "Ein Cybersicherheits-Startup mit KI hat 50 Millionen USD in einer Series-B-Finanzierung erhalten.",
        },
        {
            "source": "Heise",
            "language": "de",
            "title": "Neue KI-Modelle von OpenAI vorgestellt",
            "url": "https://heise.de/artikel1",
            "summary": "OpenAI hat neue Modelle mit verbesserter Reasoning-Fähigkeit vorgestellt.",
            "content": "OpenAI hat heute neue Modelle vorgestellt...",
            "translated": False,
            "translation_status": "native",
        },
    ]


@pytest.fixture
def mock_openai_client():
    """Gemockter OpenAI-Client für Translator/Summarizer-Tests."""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Übersetzter Text auf Deutsch."
    client.chat.completions.create.return_value = response
    return client
