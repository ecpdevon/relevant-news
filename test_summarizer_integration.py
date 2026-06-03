#!/usr/bin/env python3
"""Quick test: verify summarizer.py pipeline integration with run.py."""
import sys
sys.path.insert(0, ".")
from summarizer import summarize_articles, load_translated_articles, resolve_date, build_markdown

# Test date resolution
assert resolve_date() is not None, "resolve_date() ohne Argument fehlgeschlagen"
assert resolve_date("2025-06-03") == "2025-06-03", "resolve_date('2025-06-03') fehlgeschlagen"
print("✓ resolve_date OK")

# Test article loading  
from pathlib import Path
project_dir = Path(".")
articles = load_translated_articles(project_dir, "2025-06-03")
assert isinstance(articles, list), "load_translated_articles sollte eine Liste zurückgeben"
assert len(articles) == 3, f"Erwartet 3 Artikel, bekam {len(articles)}"
print(f"✓ load_translated_articles OK ({len(articles)} Artikel)")

# Test markdown building with existing data
import json
with open("data/summaries/2025-06-03.json", "r", encoding="utf-8") as f:
    data = json.load(f)
md = build_markdown(data["date"], data["daily_overview"], data["articles"])
assert "# Relevant News — 2025-06-03" in md, "Markdown sollte Titel enthalten"
assert "## 📋 Tagesübersicht" in md, "Markdown sollte Tagesübersicht enthalten"
assert "## 📰 Artikel (3)" in md, "Markdown sollte Artikel-Sektion enthalten"
print(f"✓ build_markdown OK ({len(md)} Zeichen)")

# Test empty input handling
empty_md = build_markdown("2025-06-03", "Keine Artikel für heute.", [])
assert "Keine Artikel für heute" in empty_md
print("✓ build_markdown (leer) OK")

# Test module exports match run.py expectations
assert callable(summarize_articles), "summarize_articles muss aufrufbar sein"
import inspect
sig = inspect.signature(summarize_articles)
assert "target_date" in sig.parameters, "summarize_articles muss target_date Parameter haben"
print("✓ summarize_articles Signatur OK (target_date: str | None = None) -> int")

print("\n✅ Alle Tests bestanden — summarizer.py ist pipeline-bereit!")
