# Relevant News — Projektplan

Ein automatischer News-Aggregator, der Artikel aus vordefinierten Quellen abruft,
nach Relevanz filtert, übersetzt und zusammenfasst.

## Architektur (Pipeline)

```
Quellen → Fetcher → Relevanz-Filter → Übersetzer → Summarizer → Ausgabe
```

## 1. Quellen-Konfiguration (`sources.yaml`)

Was du definieren musst:
- **RSS-Feeds**: URLs von Nachrichtenseiten (z.B. Heise, Tagesschau, TechCrunch)
- **API-Quellen**: NewsAPI, GNews, etc. (brauchen API-Key)
- **Spezifische Themen**: Keywords, Branchen, Technologien die dich interessieren
- **Sprache(n) der Quellen**: Englisch, ggf. weitere → Zielsprache Deutsch

Beispiel:
```yaml
sources:
  - name: Heise
    type: rss
    url: https://www.heise.de/rss/heise-atom.xml
    language: de
  - name: TechCrunch
    type: rss
    url: https://techcrunch.com/feed/
    language: en
```

## 2. Article Fetcher (`fetcher.py`)

Aufgabe:
- Quellen aus `sources.yaml` einlesen
- RSS-Feeds parsen (via `feedparser`)
- Web-Scraping für Seiten ohne RSS (via `requests` + `beautifulsoup4`)
- Artikel-Metadaten extrahieren: Titel, URL, Datum, Autor, Volltext
- Rohdaten in `articles/` als JSON speichern

## 3. Relevanz-Filter (`filter.py`)

Was du definieren musst:
- **Keywords/Themen**: Welche Themen interessieren dich? (z.B. "KI", "Python", "SpaceX")
- **Ausschlusskriterien**: Was willst du NICHT? (z.B. "Sport", "Promi-News")
- **Quellen-Priorität**: Welche Quellen sind wichtiger?
- **Maximale Artikelanzahl**: z.B. Top 10 pro Tag

Umsetzung:
- Keyword-Matching gegen Titel + Zusammenfassung
- Optional: LLM-basierte Relevanz-Bewertung für bessere Genauigkeit

## 4. Übersetzung (`translator.py`)

Aufgabe:
- Nur englische (und anderssprachige) Artikel übersetzen
- Deutsche Artikel unverändert lassen
- Übersetzung via LLM (DeepSeek/OpenAI) — bessere Qualität als Google Translate
- Prompt: "Übersetze diesen Artikel ins Deutsche. Behalte Fachbegriffe bei."

## 5. Zusammenfassung (`summarizer.py`)

Aufgabe:
- Jeden Artikel auf 3-5 Kernpunkte kürzen
- Optional: Tageszusammenfassung aller Artikel als Newsletter
- LLM-basiert für natürliche Sprache

## 6. Ausgabe & Delivery (`output.py`)

Optionen:
- **Markdown-Datei**: `daily-news/2025-06-02.md`
- **Telegram-Nachricht**: Automatisch via Hermes Cron senden
- **HTML-Seite**: Lokale Webansicht

## 7. Automatisierung

- Hermes Cron-Job: täglich um 8:00 Uhr
- Oder manuell via `python run.py`

## Tech-Stack

| Komponente | Technologie |
|-----------|------------|
| Sprache | Python 3.11 |
| RSS-Parsing | `feedparser` |
| Web-Scraping | `requests` + `beautifulsoup4` |
| LLM (Übersetzung/Summary) | Hermes/DeepSeek API |
| Konfiguration | YAML |
| Ausgabe | Markdown + Telegram |
| Scheduling | Hermes Cron |

## Nächste Schritte

Siehe Kanban-Board: `hermes kanban list`
