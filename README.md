# Relevant News

Automatischer News-Aggregator: RSS-Feeds abrufen → nach Relevanz filtern → ins Deutsche übersetzen → zusammenfassen → als tägliches Briefing ausliefern.

## Pipeline

```
Quellen (16 RSS-Feeds) → Fetcher → Relevanz-Filter → Übersetzer (EN→DE) → Summarizer (LLM) → Ausgabe (Markdown + Telegram)
```

| Schritt | Script | Beschreibung |
|---------|--------|-------------|
| **Fetch** | `fetcher.py` | RSS-Feeds parsen, Artikel-Metadaten + Volltext extrahieren, als JSON speichern |
| **Filter** | `filter.py` | Keyword-basierte Relevanz-Filterung mit Scoring, konfigurierbar via `filters.yaml` |
| **Translate** | `translator.py` | Englische (und anderssprachige) Artikel via LLM (DeepSeek) ins Deutsche übersetzen |
| **Summarize** | `summarizer.py` | Übersetzte Artikel via LLM auf 3–5 Kernpunkte kürzen, Tages-Digest erstellen |
| **Output** | `output.py` | Markdown-Datei schreiben + per Telegram (Hermes CLI oder Bot API) zustellen |
| **Orchestrator** | `run.py` | Gesamte Pipeline ausführen, wahlweise einzelne Schritte oder Dry-Run |

## Quellen

16 RSS-Feeds aus 8 Quellen:

| Quelle | Feeds | Sprache |
|--------|-------|---------|
| NZZ | Technologie, International, Wirtschaft | DE |
| Tages-Anzeiger | Front, Digital, Wirtschaft | DE |
| FAZ | Aktuell | DE |
| New York Times | Technology, World, Business | EN |
| South China Morning Post | News, China, Business | EN |
| VentureBeat | Tech-News | EN |
| Hacker News | Frontpage | EN |
| Reddit | r/programming (Top/Day) | EN |

Konfiguriert in [`sources.yaml`](sources.yaml).

## Voraussetzungen

- **Python 3.11+**
- **uv** — Package Manager ([Installation](https://docs.astral.sh/uv/getting-started/installation/))
- **Hermes AI Agent** — für Cron-Automatisierung und LLM-Zugriff via DeepSeek API
- **Telegram** (optional) — für automatischen Versand des Briefings

## Installation

```bash
# 1. Repository clonen
git clone <repo-url> relevant-news
cd relevant-news

# 2. Virtuelles Environment + Abhängigkeiten
uv venv
uv pip install -r requirements.txt

# 3. Quellen und Filter konfigurieren
# sources.yaml und filters.yaml sind bereits vorhanden.
# Passe sie nach deinen Interessen an (siehe Konfiguration unten).
```

### Abhängigkeiten (requirements.txt)

```
feedparser>=6.0        # RSS-Parsing
requests>=2.31         # HTTP-Client
beautifulsoup4>=4.12   # HTML-Extraktion (Web-Scraping)
pyyaml>=6.0            # YAML-Konfiguration
python-telegram-bot>=21.0  # Telegram Bot API
openai>=1.0            # LLM-Client (DeepSeek-kompatibel)
```

## Konfiguration

### `sources.yaml` — Nachrichtenquellen

Jede Quelle definiert: Name, Typ (`rss`), URL, Sprache (`de`/`en`) und Kategorie:

```yaml
sources:
  - name: NZZ Technologie
    type: rss
    url: https://www.nzz.ch/technologie.rss
    language: de
    category: tech

  - name: Hacker News
    type: rss
    url: https://hnrss.org/frontpage
    language: en
    category: tech

settings:
  max_articles_per_source: 10
  max_total_articles: 50
  request_timeout: 15
  user_agent: "RelevantNews/1.0"
```

Quellen deaktivieren: Zeile mit `#` auskommentieren.

### `filters.yaml` — Relevanz-Regeln

Drei Keyword-Gruppen mit unterschiedlicher Wirkung:

```yaml
filters:
  include_keywords:       # Artikel MÜSSEN mindestens eines enthalten
    - KI / AI / Machine Learning / LLM / GPT / Claude
    - Python / Rust / Open Source / GitHub
    - Cloud / AWS / Kubernetes / Cybersecurity
    - Startup / IPO / Venture Capital
    - China / USA / EU / Regulierung

  exclude_keywords:       # Artikel mit diesen Begriffen werden verworfen
    - Sport / Fussball / Tennis / Formel 1
    - Promi / Klatsch / Royal / Boulevard
    - Horoskop / Wetter

  priority_keywords:      # Extra-Score für Durchbrüche und Exklusivmeldungen
    - Durchbruch / Revolutionär / Erstmals / Rekord / Exklusiv

  settings:
    min_score: 1
    max_articles_output: 15
    source_weights:       # Hochwertige Quellen werden bevorzugt
      "New York Times": 1.3
      NZZ: 1.2
      FAZ: 1.2
      "Hacker News": 0.6
      Reddit: 0.5
```

## Nutzung

### Komplette Pipeline

```bash
# Heutiges Datum
uv run python run.py

# Bestimmtes Datum
uv run python run.py --date 2025-06-02

# Dry-Run (zeigt an, was ausgeführt würde)
uv run python run.py --dry-run
```

### Einzelne Schritte

```bash
# Nur einen bestimmten Pipeline-Schritt ausführen
uv run python run.py --step fetcher
uv run python run.py --step filter --date 2025-06-02
uv run python run.py --step translator
uv run python run.py --step summarizer
uv run python run.py --step output
```

### Einzelne Module direkt

```bash
uv run python fetcher.py              # Heutige Artikel fetchen
uv run python filter.py 2025-06-02    # Filtern (positional date)
uv run python translator.py --date 2025-06-02
uv run python summarizer.py --date 2025-06-02
uv run python output.py --date 2025-06-02
```

### Ausgabe

- **Markdown-Datei:** `daily-news/<datum>.md`
- **Zwischendaten:** `data/articles/<datum>.json` → `_filtered.json` → `_translated.json`
- **Zusammenfassung:** `data/summaries/<datum>.json` + `<datum>.md`

## Automatisierung (Cron)

Täglicher Cron-Job um **08:00 Uhr** — führt die Pipeline aus und sendet das Briefing per Telegram.

```bash
# Status prüfen
hermes cron list

# Manuell auslösen
hermes cron run 1983dec04982

# Zeitplan ändern
hermes cron update 1983dec04982 --schedule "0 7 * * *"

# Pausieren / Fortsetzen
hermes cron pause 1983dec04982
hermes cron resume 1983dec04982
```

## Verzeichnisstruktur

```
relevant-news/
├── AGENTS.md             # Projekt-Kontext für KI-Agenten
├── PLAN.md               # Implementierungsplan
├── README.md             # Diese Datei
├── pyproject.toml        # Projekt-Metadaten + Abhängigkeiten
├── requirements.txt      # Python-Abhängigkeiten
├── sources.yaml          # Quellen-Konfiguration (16 Feeds)
├── filters.yaml          # Relevanz-Regeln (Keywords + Scoring)
│
├── fetcher.py            # RSS-Fetcher (feedparser)
├── filter.py             # Relevanz-Filter (Keyword-Matching)
├── translator.py         # Übersetzung EN→DE (LLM)
├── summarizer.py         # Zusammenfassung (LLM)
├── output.py             # Ausgabe + Telegram-Delivery
├── run.py                # Pipeline-Orchestrator
├── _validate.py          # Konfigurations-Validator
│
├── test_summarizer_integration.py  # Integrationstest
├── SOURCES_ANALYSIS.md   # Quellen-Analyse
│
├── data/
│   ├── articles/         # Roh-Artikel + Zwischenschritte (JSON)
│   └── summaries/        # Zusammenfassungen (JSON + MD)
│
└── daily-news/           # Finale Tages-Briefings (MD)
```

## LLM-Konfiguration

Übersetzung und Zusammenfassung nutzen das in Hermes konfigurierte LLM (DeepSeek). Die Module lesen `DEEPSEEK_API_KEY` und `DEEPSEEK_BASE_URL` aus der Umgebung — in einer Hermes-Session oder via Cron-Job sind diese automatisch gesetzt. Kein separater API-Key nötig.

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| `ModuleNotFoundError: feedparser` | `uv pip install -r requirements.txt` |
| `FileNotFoundError: sources.yaml` | Datei existiert im Projekt-Root. Falls gelöscht: aus Backup wiederherstellen. |
| RSS-Feed liefert keine Artikel | Feed-Quelle ggf. umgezogen — URL in `sources.yaml` prüfen |
| Übersetzung überspringt Artikel | LLM-API nicht erreichbar — `hermes status` prüfen |
| Cron-Job schlägt fehl | `hermes cron log 1983dec04982` für Fehlerdetails |
| Keine Telegram-Nachricht | Telegram-Integration prüfen: `hermes config get messaging` |
| `_validate.py` meldet Fehler | YAML-Syntax in `sources.yaml` oder `filters.yaml` prüfen |

## Entwicklung

```bash
# Dev-Dependencies installieren
uv pip install -e ".[dev]"

# Tests ausführen
uv run pytest test_summarizer_integration.py -v

# Linting
uv run ruff check .
```

## Lizenz

MIT
