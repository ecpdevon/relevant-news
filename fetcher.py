#!/usr/bin/env python3
"""fetcher.py — RSS-Feed-Artikel abrufen und als JSON speichern.

Liest sources.yaml ein, parst jeden RSS-Feed via feedparser, holt die
letzten 10 Artikel pro Quelle und speichert die Ergebnisse in
data/articles/<datum>.json. Fehler bei einzelnen Quellen (Timeout,
ungültiges XML etc.) werden geloggt und die nächste Quelle wird
trotzdem verarbeitet.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import yaml

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("fetcher")

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------
MAX_ARTICLES_PER_FEED = 10
PROJECT_ROOT = Path(__file__).resolve().parent
SOURCES_FILE = PROJECT_ROOT / "sources.yaml"
ARTICLES_DIR = PROJECT_ROOT / "data" / "articles"


def load_sources(path: Path) -> list[dict]:
    """sources.yaml einlesen und als Liste von Quell-Dicts zurückgeben."""
    if not path.exists():
        log.error("sources.yaml nicht gefunden unter %s", path)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not data or "sources" not in data:
        log.error("sources.yaml enthält keinen 'sources'-Schlüssel")
        sys.exit(1)

    return data["sources"]


def parse_date(entry) -> str | None:
    """Bestes Datum aus einem feedparser-Eintrag extrahieren."""
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None)
        if tp:
            try:
                dt = datetime(*tp[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except (TypeError, ValueError):
                continue
    return None


def extract_fulltext(entry) -> str:
    """Volltext aus einem feedparser-Eintrag extrahieren.

    feedparser stellt verschiedene Content-Felder bereit; wir versuchen
    der Reihe nach das reichhaltigste zu nehmen.
    """
    # content: meist der vollständige HTML-Artikelkörper
    content_list = getattr(entry, "content", None)
    if content_list:
        return content_list[0].get("value", "")

    # summary_detail: manchmal vollständiger
    summary_detail = getattr(entry, "summary_detail", None)
    if summary_detail:
        return summary_detail.get("value", "")

    # summary als letzter Fallback (plain text)
    return getattr(entry, "summary", "")


def extract_summary(entry) -> str:
    """Kurzzusammenfassung aus einem feedparser-Eintrag."""
    # Manche Feeds liefern description, andere summary
    for attr in ("description", "summary"):
        val = getattr(entry, attr, None)
        if val:
            return val
    return ""


def fetch_feed(source: dict) -> list[dict]:
    """Einzelnen Feed abrufen und bis zu MAX_ARTICLES_PER_FEED Artikel parsen."""
    url = source["url"]
    name = source.get("name", url)
    log.info("Rufe Feed ab: %s (%s)", name, url)

    try:
        parsed = feedparser.parse(url)
    except Exception as exc:
        log.warning("Feedparser-Fehler bei %s: %s", name, exc)
        return []

    # feedparser liefert bozo_exception bei Parse-Fehlern, aber manchmal
    # trotzdem Einträge — wir loggen den Fehler, verarbeiten aber trotzdem.
    bozo = getattr(parsed, "bozo_exception", None)
    if bozo:
        log.warning("Bozo-Fehler bei %s: %s", name, bozo)

    if not parsed.entries:
        log.warning("Keine Einträge in Feed %s", name)
        return []

    articles = []
    for entry in parsed.entries[:MAX_ARTICLES_PER_FEED]:
        article = {
            "source": name,
            "source_url": url,
            "language": source.get("language", "unknown"),
            "title": getattr(entry, "title", ""),
            "url": getattr(entry, "link", ""),
            "date": parse_date(entry),
            "summary": extract_summary(entry),
            "fulltext": extract_fulltext(entry),
        }
        articles.append(article)

    log.info("  → %d Artikel von %s geholt", len(articles), name)
    return articles


def save_articles(articles: list[dict]) -> Path:
    """Artikel-Liste als JSON in data/articles/<datum>.json speichern."""
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_path = ARTICLES_DIR / f"{today}.json"

    # Falls die Datei schon existiert (z. B. bei mehreren Läufen am selben
    # Tag), laden wir die vorhandenen Daten und mergen mit neuen.
    existing = []
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Bestehende JSON-Datei %s ist kaputt — wird überschrieben", output_path)

    # Merge: neue Artikel an vorhandene anhängen (Deduplizierung nach URL)
    seen_urls = {a["url"] for a in existing}
    new_articles = [a for a in articles if a["url"] not in seen_urls]

    all_articles = existing + new_articles
    output_path.write_text(
        json.dumps(all_articles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(
        "Gespeichert: %s (%d Artikel, davon %d neu)",
        output_path,
        len(all_articles),
        len(new_articles),
    )
    return output_path


def main() -> None:
    """Haupt-Pipeline: Quellen laden, Feeds fetchen, Ergebnisse speichern."""
    log.info("=== fetcher.py gestartet ===")

    sources = load_sources(SOURCES_FILE)
    log.info("%d Quellen aus sources.yaml geladen", len(sources))

    all_articles: list[dict] = []
    success_count = 0
    fail_count = 0

    for source in sources:
        try:
            articles = fetch_feed(source)
            if articles:
                all_articles.extend(articles)
                success_count += 1
            else:
                fail_count += 1
        except Exception as exc:
            log.warning(
                "Unerwarteter Fehler bei Quelle %s: %s",
                source.get("name", source.get("url", "?")),
                exc,
            )
            fail_count += 1

    if not all_articles:
        log.warning("Keine Artikel abgerufen — nichts zu speichern.")
        sys.exit(0)

    output_path = save_articles(all_articles)
    log.info(
        "=== fetcher.py beendet: %d Quellen erfolgreich, %d fehlgeschlagen, "
        "%d Artikel gesamt → %s ===",
        success_count,
        fail_count,
        len(all_articles),
        output_path,
    )


if __name__ == "__main__":
    main()
