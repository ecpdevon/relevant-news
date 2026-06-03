# Relevant News — Projekt-Kontext

Ein automatischer News-Aggregator, der Artikel aus vordefinierten RSS-Quellen abruft,
nach Relevanz filtert, ins Deutsche übersetzt und zusammenfasst.

## Technologie
- Python 3.11 mit `uv` als Package Manager
- `feedparser` für RSS, `requests` + `beautifulsoup4` für Web
- LLM via Hermes/DeepSeek API für Übersetzung + Zusammenfassung
- YAML für Konfiguration, JSON für Zwischenspeicherung
- Markdown für finale Ausgabe

## Verzeichnisstruktur
```
relevant-news/
├── sources.yaml      # Quellen-Konfiguration
├── filters.yaml      # Relevanz-Keywords
├── fetcher.py        # Artikel abrufen
├── filter.py         # Relevanz-Filter
├── translator.py     # Übersetzung DE
├── summarizer.py     # Zusammenfassung
├── output.py         # Ausgabe/Delivery
├── run.py            # Haupt-Pipeline
├── README.md         # Doku
└── data/
    ├── articles/     # Roh-Artikel (JSON)
    └── summaries/    # Zusammenfassungen (JSON + MD)
```

## Pipeline-Reihenfolge
1. sources.yaml definieren
2. fetcher.py → data/articles/<datum>.json
3. filter.py → data/articles/<datum>_filtered.json
4. translator.py → data/articles/<datum>_translated.json
5. summarizer.py → data/summaries/<datum>.md
6. run.py orchestriert alles
7. Cron-Job für tägliche Ausführung
