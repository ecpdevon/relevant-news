#!/usr/bin/env python3
"""
Summarizer für den Relevant News Aggregator.

Lädt übersetzte Artikel, fasst jeden via LLM (DeepSeek) auf 3-5 deutsche
Stichpunkte zusammen, erstellt eine Tagesübersicht und speichert das Ergebnis
als JSON + Markdown-Newsletter in data/summaries/<datum>.json|.md .

Aufruf:
    python summarizer.py              # heute
    python summarizer.py 2025-06-01   # bestimmtes Datum
Oder via Pipeline:
    from summarizer import summarize_articles
    n = summarize_articles("2025-06-01")
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# LLM client setup
# ---------------------------------------------------------------------------

_LLM_MODEL = "deepseek-chat"

try:
    from openai import OpenAI
except ImportError:
    print(
        "Fehler: openai ist nicht installiert. "
        "Bitte ausführen: uv pip install openai"
    )
    sys.exit(1)


def _get_client() -> OpenAI:
    """Build an OpenAI-compatible client pointed at DeepSeek."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("Fehler: DEEPSEEK_API_KEY ist nicht gesetzt.")
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def get_today_str() -> str:
    return date.today().isoformat()


def resolve_date(date_str: str | None = None) -> str:
    if date_str is None:
        return get_today_str()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print(
            f"Fehler: Ungültiges Datumsformat '{date_str}'. "
            "Erwartet: YYYY-MM-DD"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Article loading
# ---------------------------------------------------------------------------

def load_translated_articles(project_dir: Path, date_str: str) -> list:
    """Lädt übersetzte Artikel aus data/articles/<date>_translated.json."""
    path = project_dir / "data" / "articles" / f"{date_str}_translated.json"
    if not path.exists():
        print(f"Info: Keine übersetzten Artikel unter {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not isinstance(articles, list):
        print(f"Fehler: {path} enthält keine JSON-Liste.")
        sys.exit(1)

    return articles


# ---------------------------------------------------------------------------
# LLM summarization
# ---------------------------------------------------------------------------

def summarize_article(client: OpenAI, article: dict) -> dict:
    """Fasst einen einzelnen Artikel auf 3-5 deutsche Stichpunkte zusammen."""
    title = article.get("title") or article.get("original_title") or "Unbekannter Titel"
    content = (
        article.get("content")
        or article.get("text")
        or article.get("summary")
        or ""
    )

    prompt = (
        "Fasse diesen Artikel in 3-5 deutschen Stichpunkten zusammen, "
        "die die Kernaussage enthalten."
    )

    try:
        response = client.chat.completions.create(
            model=_LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du bist ein präziser Nachrichten-Redakteur. "
                        "Fasse Artikel in deutschen Stichpunkten zusammen. "
                        "Jeder Stichpunkt soll eine Kernaussage des Artikels "
                        "enthalten. Verwende Bindestriche als Aufzählungszeichen."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\nTitel: {title}\n\nArtikel:\n{content}",
                },
            ],
            temperature=0.3,
            max_tokens=500,
        )
        summary_text = response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"  LLM-Fehler bei '{title[:60]}...': {exc}")
        return {
            "title": title,
            "url": article.get("url", ""),
            "source": article.get("source", ""),
            "summary_points": "",
            "status": "summary_failed",
            "error": str(exc),
        }

    return {
        "title": title,
        "url": article.get("url", ""),
        "source": article.get("source", ""),
        "summary_points": summary_text,
        "status": "summarized",
    }


def summarize_daily_overview(
    client: OpenAI,
    summaries: list,
) -> str:
    """Erstellt eine Tagesübersicht (max. 1 Absatz) über alle Artikel."""
    if not summaries:
        return "Keine Artikel für heute."

    success = [s for s in summaries if s.get("status") == "summarized"]
    if not success:
        return (
            "Zusammenfassung konnte für keinen Artikel erstellt werden. "
            f"({len(summaries)} Artikel verarbeitet)"
        )

    articles_text = "\n\n".join(
        f"**{s['title']}**\n{s.get('summary_points', '')}"
        for s in success
    )

    try:
        response = client.chat.completions.create(
            model=_LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du bist ein Nachrichten-Redakteur. Schreibe eine "
                        "prägnante Tagesübersicht in deutscher Sprache "
                        "(maximal 1 Absatz, max. 5 Sätze). Fasse die "
                        "wichtigsten Themen des Tages zusammen."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Schreibe eine Tagesübersicht (maximal 1 Absatz) über "
                        "die folgenden Nachrichtenartikel. Fasse die "
                        "wichtigsten Themen des Tages zusammen.\n\n"
                        f"Artikel des Tages:\n{articles_text}"
                    ),
                },
            ],
            temperature=0.5,
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"Fehler bei der Tagesübersicht: {exc}")
        return (
            f"Tagesübersicht konnte nicht erstellt werden. "
            f"({len(success)} Artikel zusammengefasst.)"
        )


# ---------------------------------------------------------------------------
# Output: JSON + Markdown
# ---------------------------------------------------------------------------

def build_markdown(
    date_str: str,
    daily_overview: str,
    summaries: list,
) -> str:
    """Baut einen Markdown-Newsletter aus den Zusammenfassungen."""
    lines = [
        f"# Relevant News — {date_str}",
        "",
        "## 📋 Tagesübersicht",
        "",
        daily_overview,
        "",
        "---",
        "",
        f"## 📰 Artikel ({len(summaries)})",
        "",
    ]

    for i, s in enumerate(summaries, 1):
        lines.append(f"### {i}. {s['title']}")
        if s.get("url"):
            lines.append(f"🔗 [{s['url']}]({s['url']})")
        if s.get("source"):
            lines.append(f"📡 *Quelle: {s['source']}*")
        lines.append("")

        if s.get("status") == "summarized":
            lines.append(s["summary_points"])
        elif s.get("status") == "summary_failed":
            lines.append(
                f"⚠️ *Zusammenfassung fehlgeschlagen:* "
                f"{s.get('error', 'Unbekannter Fehler')}"
            )
        else:
            lines.append("*(Keine Zusammenfassung)*")

        lines.extend(["", "---", ""])

    return "\n".join(lines)


def save_results(
    date_str: str,
    daily_overview: str,
    summaries: list,
    project_dir: Path,
) -> None:
    """Speichert die Zusammenfassungen als JSON und Markdown."""
    output_dir = project_dir / "data" / "summaries"
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_data = {
        "date": date_str,
        "daily_overview": daily_overview,
        "article_count": len(summaries),
        "articles": summaries,
    }
    json_path = output_dir / f"{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"JSON  gespeichert: {json_path}")

    # Markdown
    md_content = build_markdown(date_str, daily_overview, summaries)
    md_path = output_dir / f"{date_str}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"MD   gespeichert:  {md_path}  ({len(md_content)} Zeichen)")


# ---------------------------------------------------------------------------
# Pipeline entry point (called by run.py)
# ---------------------------------------------------------------------------

def summarize_articles(target_date: str | None = None) -> int:
    """Hauptfunktion für die Pipeline-Orchestrierung.

    Lädt übersetzte Artikel, fasst sie zusammen und speichert die
    Ergebnisse.  Gibt die Anzahl der verarbeiteten Artikel zurück.
    """
    project_dir = Path(__file__).resolve().parent
    date_str = resolve_date(target_date)

    articles = load_translated_articles(project_dir, date_str)

    if not articles:
        print(f"Keine Artikel für {date_str} — leere Ausgabe.")
        save_results(date_str, "Keine Artikel für heute.", [], project_dir)
        return 0

    print(f"Lade {len(articles)} übersetzte Artikel für {date_str} ...")
    client = _get_client()

    # Einzel-Zusammenfassungen
    summaries = []
    for i, article in enumerate(articles, 1):
        title = article.get("title") or article.get("original_title") or "?"
        print(f"  [{i:2d}/{len(articles)}] {title[:70]}")
        summaries.append(summarize_article(client, article))

    ok = sum(1 for s in summaries if s.get("status") == "summarized")
    fail = sum(1 for s in summaries if s.get("status") == "summary_failed")
    print(f"Zusammenfassungen: {ok} ok, {fail} fehlgeschlagen")

    # Tagesübersicht
    print("Erstelle Tagesübersicht ...")
    overview = summarize_daily_overview(client, summaries)

    # Speichern
    save_results(date_str, overview, summaries, project_dir)

    return len(summaries)


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def main() -> None:
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    n = summarize_articles(date_arg)
    print(f"\n✓ Fertig: {n} Artikel zusammengefasst.")


if __name__ == "__main__":
    main()
