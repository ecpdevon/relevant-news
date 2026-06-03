#!/usr/bin/env python3
"""
Relevanz-Filter für den News-Aggregator.
Gewichtetes Scoring nach filters.yaml: Themenfit, Aktualität, Region, Praxis-Relevanz, Quellqualität.
"""
import json
import os
import sys
import re
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Fehler: PyYAML ist nicht installiert. Bitte führe 'uv pip install pyyaml' aus.")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent


# ═══════════════════════════════════════════
# Konfiguration laden
# ═══════════════════════════════════════════

def load_filters(filters_path: Path) -> dict:
    """Lädt die gewichtete Filter-Konfiguration aus filters.yaml."""
    if not filters_path.exists():
        print(f"Fehler: {filters_path} nicht gefunden.")
        sys.exit(1)

    with open(filters_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        print("Fehler: filters.yaml ist leer.")
        sys.exit(1)

    f = config.get("filters", config)

    topic_keywords = [str(k).lower() for k in f.get("topic_keywords", [])]
    region_keywords = [str(k).lower() for k in f.get("region_keywords", [])]
    practical_keywords = [str(k).lower() for k in f.get("practical_keywords", [])]
    exclude_keywords = [str(k).lower() for k in f.get("exclude_keywords", [])]
    clickbait_patterns = f.get("clickbait_patterns", [])

    weights = f.get("weights", {})
    settings = f.get("settings", {})

    return {
        "topic_keywords": topic_keywords,
        "region_keywords": region_keywords,
        "practical_keywords": practical_keywords,
        "exclude_keywords": exclude_keywords,
        "clickbait_patterns": clickbait_patterns,
        "weights": {
            "topic_match": weights.get("topic_match", 25),
            "recency": weights.get("recency", 20),
            "practical": weights.get("practical", 10),
            "region": weights.get("region", 5),
            "signal_quality": weights.get("signal_quality", 5),
        },
        "settings": {
            "min_total_score": settings.get("min_total_score", 10),
            "max_output": settings.get("max_output", 10),
            "max_article_age_hours": settings.get("max_article_age_hours", 72),
        },
    }


def load_tier_map(sources_path: Path) -> dict:
    """Lädt Quellen-Tier-Mapping aus sources.yaml für Signal-Qualität."""
    if not sources_path.exists():
        return {}
    with open(sources_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tier_map = {}
    for src in config.get("sources", []):
        name = src.get("name", "").lower()
        tier = src.get("tier", 5)
        tier_map[name] = tier
    return tier_map


# ═══════════════════════════════════════════
# Artikel laden
# ═══════════════════════════════════════════

def load_articles(articles_path: Path) -> list:
    """Lädt die Roh-Artikel aus der JSON-Datei."""
    if not articles_path.exists():
        print(f"Info: Keine Artikel-Datei unter {articles_path}. Output wird leere Liste sein.")
        return []

    with open(articles_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not isinstance(articles, list):
        print(f"Fehler: {articles_path} enthält keine JSON-Liste.")
        sys.exit(1)

    return articles


# ═══════════════════════════════════════════
# Ausschluss-Logik
# ═══════════════════════════════════════════

def is_excluded(article: dict, exclude_keywords: list[str], clickbait_patterns: list[str] = None) -> bool:
    """Prüft, ob ein Artikel aufgrund von Ausschluss-Keywords oder Clickbait verworfen wird."""
    title = (article.get("title") or "").lower()
    summary = (article.get("summary") or "").lower()
    text = f"{title} {summary}"

    for keyword in exclude_keywords:
        if keyword in text:
            return True

    if clickbait_patterns:
        for pattern in clickbait_patterns:
            if pattern.lower() in title:
                return True

    return False


# ═══════════════════════════════════════════
# Gewichtetes Scoring
# ═══════════════════════════════════════════

def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    """Zählt case-insensitive Keyword-Matches in einem Textstring."""
    return sum(text.count(kw) for kw in keywords)


def score_topic_match(text: str, keywords: list[str], weight: int) -> float:
    """Themenfit-Score: Keyword-Matches, normalisiert auf Gewicht."""
    if not keywords:
        return 0.0
    matches = _count_keyword_matches(text, keywords)
    # Jeder Match = 3 Punkte, gecapped auf weight
    return min(matches * 3.0, float(weight))


def score_practical(text: str, keywords: list[str], weight: int) -> float:
    """Praxis-Relevanz: Keyword-Matches, normalisiert auf Gewicht."""
    if not keywords:
        return 0.0
    matches = _count_keyword_matches(text, keywords)
    return min(matches * 2.0, float(weight))


def score_region(text: str, keywords: list[str], weight: int) -> float:
    """Region Schweiz/Europa: Keyword-Matches, normalisiert auf Gewicht."""
    if not keywords:
        return 0.0
    matches = _count_keyword_matches(text, keywords)
    return min(matches * 1.0, float(weight))


def score_recency(article: dict, max_age_hours: int, weight: int) -> float:
    """Aktualität: linearer Zerfall von weight → 0 über max_age_hours."""
    date_str = article.get("date", "")
    if not date_str:
        return 0.0
    try:
        pub_date = datetime.fromisoformat(date_str)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - pub_date).total_seconds() / 3600
    except (ValueError, TypeError):
        return 0.0

    if age_hours <= 0:
        return float(weight)
    if age_hours >= max_age_hours:
        return 0.0
    return float(weight) * (1.0 - age_hours / max_age_hours)


def score_signal_quality(article: dict, tier_map: dict, weight: int) -> float:
    """Quellqualität: basierend auf Tier aus sources.yaml."""
    source_name = (article.get("source") or "").lower()
    tier = tier_map.get(source_name, 5)
    tier_scores = {1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4, 5: 0.2}
    return float(weight) * tier_scores.get(tier, 0.2)


def score_article(article: dict, filters: dict, tier_map: dict) -> float:
    """Berechnet den gewichteten Gesamtscore eines Artikels."""
    title = (article.get("title") or "").lower()
    summary = (article.get("summary") or "").lower()
    text = f"{title} {summary}"

    weights = filters["weights"]
    total = 0.0

    total += score_topic_match(text, filters["topic_keywords"], weights["topic_match"])
    total += score_recency(article, filters["settings"]["max_article_age_hours"], weights["recency"])
    total += score_practical(text, filters["practical_keywords"], weights["practical"])
    total += score_region(text, filters["region_keywords"], weights["region"])
    total += score_signal_quality(article, tier_map, weights["signal_quality"])

    return round(total, 1)


# ═══════════════════════════════════════════
# Datums-Helfer
# ═══════════════════════════════════════════

def get_today_str() -> str:
    return date.today().isoformat()


def resolve_date(date_str: str | None = None) -> str:
    if date_str is None:
        return get_today_str()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print(f"Fehler: Ungültiges Datumsformat '{date_str}'. Erwartet: YYYY-MM-DD")
        sys.exit(1)


# ═══════════════════════════════════════════
# Haupt-Pipeline
# ═══════════════════════════════════════════

def run_filter(project_dir: Path, date_str: str | None = None) -> list:
    """Hauptfunktion: Filtert Artikel mit gewichtetem Scoring und gibt Top-N zurück."""
    date_str = resolve_date(date_str)

    # Konfiguration laden
    filters = load_filters(project_dir / "filters.yaml")
    tier_map = load_tier_map(project_dir / "sources.yaml")

    # Artikel laden
    articles = load_articles(project_dir / "data" / "articles" / f"{date_str}.json")
    if not articles:
        return []

    # Filtern, scoren
    min_score = filters["settings"]["min_total_score"]
    max_output = filters["settings"]["max_output"]
    scored = []
    excluded_count = 0

    for article in articles:
        if is_excluded(article, filters["exclude_keywords"], filters["clickbait_patterns"]):
            excluded_count += 1
            continue

        s = score_article(article, filters, tier_map)
        if s >= min_score:
            article_copy = dict(article)
            article_copy["relevance_score"] = s
            scored.append(article_copy)

    # Nach Score sortieren (absteigend), Top N
    scored.sort(key=lambda a: a["relevance_score"], reverse=True)
    top = scored[:max_output]

    print(f"Artikel geladen:    {len(articles)}")
    print(f"Ausgeschlossen:     {excluded_count}")
    print(f"Score >= {min_score}:      {len(scored)}")
    print(f"Top {max_output} ausgewählt:   {len(top)}")

    return top


def save_result(articles: list, project_dir: Path, date_str: str | None = None):
    """Speichert die gefilterten Artikel als JSON."""
    date_str = resolve_date(date_str)
    output_dir = project_dir / "data" / "articles"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date_str}_filtered.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"Gefilterte Artikel gespeichert: {output_path} ({len(articles)} Artikel)")


def main():
    project_dir = PROJECT_ROOT
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    filtered = run_filter(project_dir, date_arg)
    save_result(filtered, project_dir, date_arg)


if __name__ == "__main__":
    main()
