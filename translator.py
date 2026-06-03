#!/usr/bin/env python3
"""translator.py — Übersetzt englische Nachrichtenartikel via DeepSeek LLM API.

Pipeline-Position: Nach filter.py, vor summarizer.py

1. Lädt gefilterte Artikel aus data/articles/<datum>_filtered.json
2. Nur englische Artikel übersetzen (deutsche belassen)
3. Übersetzung via OpenAI-kompatible API (DeepSeek)
4. Prompt: 'Übersetze folgenden Nachrichtenartikel ins Deutsche...'
5. Speichert in data/articles/<datum>_translated.json
6. Fehler-Toleranz: Artikel als 'translation_failed' markieren wenn LLM nicht erreichbar

Usage:
    python translator.py                    # heute
    python translator.py 2025-06-03        # explizites Datum
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

# --- Dependencies (lazy-checked) ---

# openai >= 1.0.0 is the official client; we use it to call DeepSeek's
# OpenAI-compatible endpoint.
try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package not found. Install with: uv pip install openai")
    print("       or: pip install openai")
    sys.exit(1)

# langdetect for language detection as fallback when 'language' field is missing.
try:
    from langdetect import detect as langdetect_detect, DetectorFactory
    DetectorFactory.seed = 0  # deterministic
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


# --- Configuration -----------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = PROJECT_ROOT / "data" / "articles"

# DeepSeek API (OpenAI-compatible)
API_BASE_URL = "https://api.deepseek.com/v1"
API_MODEL = "deepseek-v4-pro"

# Translation prompt
TRANSLATION_PROMPT = (
    "Übersetze folgenden Nachrichtenartikel ins Deutsche. "
    "Behalte Fachbegriffe und Eigennamen bei. "
    "Formatiere den Text sauber."
)

# --- Helpers ----------------------------------------------------------------

def _load_api_key() -> str:
    """Load DEEPSEEK_API_KEY from the hermes secrets file."""
    hermes_env = Path(os.path.expanduser("~")) / "AppData" / "Local" / "hermes" / ".env"
    if hermes_env.exists():
        with open(hermes_env, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() == "DEEPSEEK_API_KEY":
                    return val.strip().strip('"').strip("'")
    return ""


def detect_language(text: str) -> str:
    """Detect language. Returns 'en', 'de', or 'unknown'."""
    if HAS_LANGDETECT and len(text) >= 20:
        try:
            result = langdetect_detect(text)
            return result
        except Exception:
            pass
    return "unknown"


def translate_article(client: OpenAI, article_text: str) -> str | None:
    """Translate a single article text via DeepSeek API.

    Returns translated text, or None on failure.
    """
    try:
        response = client.chat.completions.create(
            model=API_MODEL,
            messages=[
                {"role": "system", "content": TRANSLATION_PROMPT},
                {"role": "user", "content": article_text},
            ],
            temperature=0.3,  # low temp for faithful translation
            max_tokens=4096,
            timeout=120,  # per-request timeout in seconds
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  [ERROR] Translation API call failed: {e}", file=sys.stderr)
        return None


def should_translate(article: dict) -> bool:
    """Decide whether an article needs translation.

    Returns True if the article appears to be in English (or other non-German).
    """
    lang = (article.get("language") or "").lower().strip()

    # Explicit language field from the fetcher (e.g. from sources.yaml)
    if lang in ("de", "german"):
        return False
    if lang in ("en", "english"):
        return True

    # Try to detect from text content
    title = article.get("title", "")
    summary = article.get("summary", "")
    full_text = article.get("full_text", "") or article.get("content", "")
    combined = f"{title} {summary} {full_text}"[:2000]

    if combined.strip():
        detected = detect_language(combined)
        if detected == "de":
            return False
        if detected == "en":
            return True

    # Default: if we're unsure, try to translate (better safe than sorry)
    return True


def build_translation_text(article: dict) -> str:
    """Build the text to send to the LLM for translation."""
    parts = []
    if article.get("title"):
        parts.append(f"Title: {article['title']}")
    if article.get("summary"):
        parts.append(f"Summary: {article['summary']}")
    if article.get("full_text"):
        parts.append(f"Body: {article['full_text']}")
    elif article.get("content"):
        parts.append(f"Body: {article['content']}")
    return "\n\n".join(parts)


def parse_translation(text: str | None, article: dict) -> dict:
    """Parse the LLM translation response back into structured fields.

    The LLM may return a free-form German text. We store it as-is in
    translated_title and translated_full_text, and also keep the original.
    """
    if text is None:
        return article  # no translation available

    # Simple heuristic: if the LLM returned lines starting with
    # "Titel:" / "Zusammenfassung:" / "Text:", parse them.
    fields: dict[str, str] = {}
    current_key = None
    current_value: list[str] = []

    for line in text.split("\n"):
        line_lower = line.lower().strip()
        if line_lower.startswith("title:") or line_lower.startswith("titel:"):
            if current_key and current_value:
                fields[current_key] = "\n".join(current_value).strip()
            current_key = "title_de"
            current_value = [line.split(":", 1)[1].strip() if ":" in line else ""]
        elif line_lower.startswith("summary:") or line_lower.startswith("zusammenfassung:"):
            if current_key and current_value:
                fields[current_key] = "\n".join(current_value).strip()
            current_key = "summary_de"
            current_value = [line.split(":", 1)[1].strip() if ":" in line else ""]
        elif line_lower.startswith("body:") or line_lower.startswith("text:"):
            if current_key and current_value:
                fields[current_key] = "\n".join(current_value).strip()
            current_key = "full_text_de"
            current_value = [line.split(":", 1)[1].strip() if ":" in line else ""]
        else:
            if current_key:
                current_value.append(line)

    if current_key and current_value:
        fields[current_key] = "\n".join(current_value).strip()

    # If no structured fields detected, treat the whole response as full_text_de
    if not fields:
        article["full_text_de"] = text.strip()
    else:
        for k, v in fields.items():
            article[k] = v

    article["translation_status"] = "ok"
    article["translated"] = True
    return article


# --- Main -------------------------------------------------------------------

def run(date_str: str | None = None) -> Path:
    """Run the translation pipeline.

    Args:
        date_str: Optional date string YYYY-MM-DD. Defaults to today.

    Returns:
        Path to the output file.
    """
    if date_str is None:
        date_str = date.today().isoformat()

    input_path = ARTICLES_DIR / f"{date_str}_filtered.json"
    output_path = ARTICLES_DIR / f"{date_str}_translated.json"

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Make sure filter.py has run first.")
        sys.exit(1)

    # Load articles
    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not isinstance(articles, list):
        print(f"ERROR: Expected a JSON array in {input_path}, got {type(articles).__name__}")
        sys.exit(1)

    print(f"Loaded {len(articles)} articles from {input_path}")

    # Load API key
    api_key = _load_api_key()
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not found in hermes .env file.")
        print("All articles will be marked as translation_failed.")
        # Continue anyway — mark all as failed
        for a in articles:
            a["translation_status"] = "translation_failed"
            a["translated"] = False
    else:
        client = OpenAI(base_url=API_BASE_URL, api_key=api_key)

        # Process articles
        translated_count = 0
        skipped_count = 0
        failed_count = 0

        for i, article in enumerate(articles):
            title = article.get("title", f"Article #{i+1}")[:80]
            print(f"  [{i+1}/{len(articles)}] {title}...", end=" ", flush=True)

            # Always initialize translation fields
            article.setdefault("translated", False)
            article.setdefault("translation_status", "pending")

            if not should_translate(article):
                article["translation_status"] = "native"
                article["translated"] = False
                print("(German — skipped)")
                skipped_count += 1
                continue

            # Build text and translate
            text = build_translation_text(article)
            translated = translate_article(client, text)

            if translated is None:
                article["translation_status"] = "translation_failed"
                article["translated"] = False
                failed_count += 1
                print("FAILED")
            else:
                article = parse_translation(translated, article)
                translated_count += 1
                print("OK")

            # Incremental save after each article (resilience against timeouts)
            os.makedirs(output_path.parent, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)

        print(f"\nDone: {translated_count} translated, {skipped_count} skipped (native), "
              f"{failed_count} failed, {len(articles)} total")

    print(f"Output written to: {output_path}")
    return output_path


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(date_arg)
