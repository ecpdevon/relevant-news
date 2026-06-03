"""Tests für filter.py — Relevanz-Filter mit gewichtetem Scoring."""
import json
from pathlib import Path

import pytest
import yaml

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from filter import (
    get_today_str,
    is_excluded,
    load_articles,
    load_filters,
    load_tier_map,
    resolve_date,
    score_article,
    score_recency,
    score_topic_match,
    score_practical,
    score_region,
    score_signal_quality,
    run_filter,
    save_result,
)


def _write_filters(path: Path, topic=None, region=None, practical=None,
                   exclude=None, clickbait=None, weights=None, settings=None):
    """Helper: schreibt filters.yaml im neuen Format."""
    f = {}
    if topic is not None:
        f["topic_keywords"] = topic
    if region is not None:
        f["region_keywords"] = region
    if practical is not None:
        f["practical_keywords"] = practical
    if exclude is not None:
        f["exclude_keywords"] = exclude
    if clickbait is not None:
        f["clickbait_patterns"] = clickbait
    if weights is not None:
        f["weights"] = weights
    if settings is not None:
        f["settings"] = settings
    path.write_text(yaml.dump({"filters": f}), encoding="utf-8")


# ===== load_filters =====

def test_load_filters_valid(tmp_path):
    fpath = tmp_path / "filters.yaml"
    _write_filters(
        fpath,
        topic=["ki", "ai", "machine learning"],
        exclude=["sport", "fussball"],
        settings={"max_output": 5, "min_total_score": 10},
    )
    result = load_filters(fpath)
    assert result["topic_keywords"] == ["ki", "ai", "machine learning"]
    assert result["exclude_keywords"] == ["sport", "fussball"]
    assert result["settings"]["max_output"] == 5
    assert result["settings"]["min_total_score"] == 10


def test_load_filters_missing_file():
    with pytest.raises(SystemExit) as exc:
        load_filters(Path("/nonexistent/filters.yaml"))
    assert exc.value.code == 1


def test_load_filters_empty_yaml(tmp_path):
    fpath = tmp_path / "filters.yaml"
    fpath.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        load_filters(fpath)
    assert exc.value.code == 1


def test_load_filters_defaults(tmp_path):
    """Ohne Keywords sind Listen leer, Settings haben Defaults."""
    fpath = tmp_path / "filters.yaml"
    _write_filters(fpath)
    result = load_filters(fpath)
    assert result["topic_keywords"] == []
    assert result["exclude_keywords"] == []
    assert result["settings"]["min_total_score"] == 10
    assert result["settings"]["max_output"] == 10


# ===== load_tier_map =====

def test_load_tier_map(tmp_path):
    spath = tmp_path / "sources.yaml"
    import yaml
    spath.write_text(yaml.dump({
        "sources": [
            {"name": "NZZ Technologie", "tier": 2},
            {"name": "Hacker News", "tier": 3},
            {"name": "Reddit Programming", "tier": 5},
        ]
    }), encoding="utf-8")
    result = load_tier_map(spath)
    assert result["nzz technologie"] == 2
    assert result["hacker news"] == 3
    assert result["reddit programming"] == 5


def test_load_tier_map_missing(tmp_path):
    result = load_tier_map(tmp_path / "nonexistent.yaml")
    assert result == {}


# ===== load_articles =====

def test_load_articles_valid(tmp_path):
    apath = tmp_path / "articles.json"
    apath.write_text(json.dumps([
        {"title": "Test1"}, {"title": "Test2"}
    ]), encoding="utf-8")
    result = load_articles(apath)
    assert len(result) == 2


def test_load_articles_missing(tmp_path):
    assert load_articles(tmp_path / "nonexistent.json") == []


def test_load_articles_not_a_list(tmp_path):
    apath = tmp_path / "articles.json"
    apath.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        load_articles(apath)
    assert exc.value.code == 1


# ===== score_topic_match =====

def test_score_topic_match():
    text = "ki revolution und ai startup news"
    assert score_topic_match(text, ["ki", "ai", "blockchain"], 25) == 6.0  # ki=1, ai=1 → 2 matches ×3 = 6


def test_score_topic_match_capped():
    """Score wird auf weight gecapped."""
    text = "ki ki ki ki ki ki ki ki ki ki ki"  # 11 matches
    assert score_topic_match(text, ["ki"], 25) == 25.0


def test_score_topic_match_empty():
    assert score_topic_match("irgendwas", [], 25) == 0.0


# ===== score_practical =====

def test_score_practical():
    text = "neues gesetz zur regulierung verabschiedet"
    assert score_practical(text, ["gesetz", "regulierung", "kosten"], 10) == 4.0  # 2 matches ×2 = 4


def test_score_practical_capped():
    text = "gesetz regulierung kosten preis pflicht neu"
    assert score_practical(text, ["gesetz", "regulierung", "kosten", "preis", "pflicht", "neu"], 10) == 10.0


# ===== score_region =====

def test_score_region():
    text = "schweiz und eu beschliessen schengen reform"
    assert score_region(text, ["schweiz", "eu", "schengen", "alpen"], 5) == 3.0


def test_score_region_capped():
    text = "schweiz eu schengen alpen bundesrat zürich"
    assert score_region(text, ["schweiz", "eu", "schengen", "alpen", "bundesrat", "zürich"], 5) == 5.0


# ===== score_recency =====

def test_score_recency_now():
    from datetime import datetime, timezone
    article = {"date": datetime.now(timezone.utc).isoformat()}
    assert score_recency(article, 72, 20) == 20.0


def test_score_recency_old():
    old = "2020-01-01T00:00:00+00:00"
    assert score_recency({"date": old}, 72, 20) == 0.0


def test_score_recency_missing_date():
    assert score_recency({}, 72, 20) == 0.0


# ===== score_signal_quality =====

def test_score_signal_quality():
    tier_map = {"heise": 2, "reddit programming": 5}
    # tier 2 → 0.8 * 5 = 4.0
    assert score_signal_quality({"source": "Heise"}, tier_map, 5) == 4.0
    # tier 5 → 0.2 * 5 = 1.0
    assert score_signal_quality({"source": "Reddit Programming"}, tier_map, 5) == 1.0
    # unknown → tier 5 → 1.0
    assert score_signal_quality({"source": "Unbekannt"}, tier_map, 5) == 1.0


# ===== score_article (Gesamtscore) =====

def test_score_article_full():
    from datetime import datetime, timezone
    filters = {
        "topic_keywords": ["ki", "python", "open source"],
        "region_keywords": ["schweiz", "eu"],
        "practical_keywords": ["gesetz", "regulierung"],
        "weights": {"topic_match": 25, "recency": 20, "practical": 10, "region": 5, "signal_quality": 5},
        "settings": {"min_total_score": 10, "max_output": 10, "max_article_age_hours": 72},
    }
    tier_map = {"nzz technologie": 2}
    article = {
        "title": "KI und Python Open-Source Gesetz in der Schweiz",
        "summary": "Neue Regulierung für KI in der EU",
        "source": "NZZ Technologie",
        "date": datetime.now(timezone.utc).isoformat(),
    }
    s = score_article(article, filters, tier_map)
    # topic: ki(2), python(1) → 3×3=9  (open source mit - ist separater token, "open-source" matched)
    # recency: 20
    # practical: gesetz(1), regulierung(1) → 2×2=4
    # region: schweiz(1), eu(1) → 2×1=2
    # signal: tier 2 → 4.0
    # total ≈ 39.0
    assert s >= 35.0

def test_score_article_irrelevant():
    filters = {
        "topic_keywords": ["ki", "python"],
        "region_keywords": ["schweiz"],
        "practical_keywords": ["gesetz"],
        "weights": {"topic_match": 25, "recency": 20, "practical": 10, "region": 5, "signal_quality": 5},
        "settings": {"min_total_score": 10, "max_output": 10, "max_article_age_hours": 72},
    }
    tier_map = {}
    article = {
        "title": "Fussball Bundesliga Ergebnisse",
        "summary": "Bayern gewinnt gegen Dortmund",
        "source": "Unbekannt",
        "date": "2020-01-01T00:00:00+00:00",
    }
    s = score_article(article, filters, tier_map)
    # topic: 0, recency: 0, practical: 0, region: 0, signal: 1.0
    assert s == 1.0


# ===== is_excluded =====

def test_is_excluded_keyword():
    article = {"title": "Bundesliga Sport News"}
    assert is_excluded(article, ["bundesliga", "fussball"], []) is True


def test_is_excluded_clickbait():
    article = {"title": "Sie werden nicht glauben was passiert ist"}
    patterns = ["Sie werden nicht glauben", "Schockierend"]
    assert is_excluded(article, [], patterns) is True


def test_is_excluded_none():
    article = {"title": "KI Innovationen"}
    assert is_excluded(article, ["sport"], ["Schockierend"]) is False


def test_is_excluded_case_insensitive():
    article = {"title": "SPORT NEWS HEUTE"}
    assert is_excluded(article, ["sport"], []) is True


def test_is_excluded_empty():
    assert is_excluded({"title": "irgendwas"}, [], []) is False


# ===== resolve_date =====

def test_resolve_date_today():
    assert resolve_date(None) == get_today_str()


def test_resolve_date_valid():
    assert resolve_date("2025-06-03") == "2025-06-03"


def test_resolve_date_invalid():
    with pytest.raises(SystemExit) as exc:
        resolve_date("03-06-2025")
    assert exc.value.code == 1


# ===== run_filter (Integration) =====

def test_run_filter_no_articles(tmp_path):
    (tmp_path / "data" / "articles").mkdir(parents=True)
    _write_filters(tmp_path / "filters.yaml", topic=["ki"])
    result = run_filter(tmp_path, "2025-06-03")
    assert result == []


def test_run_filter_full_flow(tmp_path):
    from datetime import datetime, timezone

    (tmp_path / "data" / "articles").mkdir(parents=True)

    # filters.yaml
    _write_filters(
        tmp_path / "filters.yaml",
        topic=["ki", "startup"],
        exclude=["sport", "fussball"],
        clickbait=["unglaublich"],
        settings={"min_total_score": 10, "max_output": 2, "max_article_age_hours": 72},
    )

    # sources.yaml
    spath = tmp_path / "sources.yaml"
    spath.write_text(yaml.dump({
        "sources": [
            {"name": "Heise", "tier": 2},
            {"name": "TechCrunch", "tier": 2},
        ]
    }), encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    articles = [
        {"title": "KI Revolution", "summary": "KI verändert die Welt", "url": "https://ex.com/1", "source": "Heise", "date": now},
        {"title": "Startup sammelt 50M ein", "summary": "Startup und KI im Fokus", "url": "https://ex.com/2", "source": "TechCrunch", "date": now},
        {"title": "Bundesliga Sport News", "summary": "Fussball Ergebnisse", "url": "https://ex.com/3", "source": "Spiegel", "date": now},
        {"title": "Wetter morgen", "summary": "Sonnig", "url": "https://ex.com/4", "source": "Tagesschau", "date": now},
    ]
    (tmp_path / "data" / "articles" / "2025-06-03.json").write_text(json.dumps(articles), encoding="utf-8")

    result = run_filter(tmp_path, "2025-06-03")

    # article #3 excluded (sport/fussball), #4 score too low
    # #1 and #2 should pass
    assert len(result) <= 2
    assert len(result) >= 1
    titles = {a["title"] for a in result}
    assert "KI Revolution" in titles or "Startup sammelt 50M ein" in titles
    for a in result:
        assert "relevance_score" in a


# ===== save_result =====

def test_save_result(tmp_path):
    articles = [{"title": "Test", "url": "https://ex.com", "relevance_score": 42.5}]
    save_result(articles, tmp_path, "2025-06-03")
    out_path = tmp_path / "data" / "articles" / "2025-06-03_filtered.json"
    assert out_path.exists()
    saved = json.loads(out_path.read_text(encoding="utf-8"))
    assert saved == articles
