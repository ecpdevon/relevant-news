# Relevant News — Quellen-Analyse

## Recherche-Ergebnis (Stand: Juni 2026)

### ✅ Quellen mit RSS-Feeds (direkt nutzbar)

| # | Quelle | Sprache | Feed-Typ | Basis-URL | Kategorien |
|---|--------|---------|----------|-----------|------------|
| 1 | **NZZ** | DE | RSS | `nzz.ch/<kategorie>.rss` | technologie, wirtschaft, international, schweiz, wissenschaft, feuilleton, sport, zürich |
| 2 | **Tages-Anzeiger** | DE | RSS | `partner-feeds.publishing.tamedia.ch/rss/tagesanzeiger/<kat>` | front, schweiz, wirtschaft, digital, kultur, wissen, panorama, leben, sport/* |
| 3 | **SCMP** | EN | RSS | `scmp.com/rss/<id>/feed` | 91=News, 2=HongKong, 4=China, 3=Asia, 5=World, 92=Business, 10=Companies |
| 4 | **VentureBeat** | EN | RSS | `venturebeat.com/feed/` | Tech-News, AI, Games, Enterprise |
| 5 | **Hacker News** | EN | API + RSS | `hnrss.org/frontpage` | Dritt-Anbieter-RSS der Frontpage |
| 6 | **Reddit** | EN | JSON-API | `reddit.com/r/<subreddit>/.json` | Beliebiges Subreddit; kein API-Key nötig für Basic-Reads |
| 7 | **FAZ** | DE | RSS (eingeschränkt) | `faz.net/rss/aktuell/` | Nur Headlines; Paywall schränkt Volltext ein |
| 8 | **NYT** | EN | RSS | `rss.nytimes.com/services/xml/rss/nyt/<kat>.xml` | Viele Kategorien, aber Artikel hinter Paywall |

### ⚠️ Paywall-Notizen

- **NZZ, FAZ, NYT, Tages-Anzeiger**: RSS liefert meist nur Überschriften + Teaser. Volltext erfordert Login oder Scraping.
- **SCMP**: Einige Artikel frei, andere hinter Paywall.
- **VentureBeat, Hacker News, Reddit**: Volltext meist frei verfügbar.

### 🔧 Empfohlene Strategie

1. **RSS-First**: Für alle Quellen mit RSS zuerst Feed parsen → Titel + Summary holen
2. **Readability Fallback**: Für Artikel-Links `readability`-Extraktion (via `newspaper3k` oder `trafilatura`)
3. **Reddit via JSON**: `reddit.com/r/<subreddit>/top.json?t=day&limit=10`
4. **Hacker News via API**: `hacker-news.firebaseio.com/v0/topstories.json`

Quelle: NZZ
  Feed: https://www.nzz.ch/technologie.rss
  Feed: https://www.nzz.ch/international.rss
  Feed: https://www.nzz.ch/wirtschaft.rss
  Sprache: de
  Paywall: Ja (Titel + Teaser frei)

Quelle: FAZ
  Feed: https://www.faz.net/rss/aktuell/
  Sprache: de
  Paywall: Ja (stark)

Quelle: Tages-Anzeiger
  Feed: https://partner-feeds.publishing.tamedia.ch/rss/tagesanzeiger/front
  Feed: https://partner-feeds.publishing.tamedia.ch/rss/tagesanzeiger/digital
  Feed: https://partner-feeds.publishing.tamedia.ch/rss/tagesanzeiger/wirtschaft
  Sprache: de
  Paywall: Ja

Quelle: New York Times
  Feed: https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml
  Feed: https://rss.nytimes.com/services/xml/rss/nyt/World.xml
  Feed: https://rss.nytimes.com/services/xml/rss/nyt/Business.xml
  Sprache: en
  Paywall: Ja

Quelle: SCMP
  Feed: https://www.scmp.com/rss/91/feed
  Feed: https://www.scmp.com/rss/4/feed
  Sprache: en
  Paywall: Teilweise

Quelle: VentureBeat
  Feed: https://venturebeat.com/feed/
  Sprache: en
  Paywall: Nein

Quelle: Hacker News
  Feed: https://hnrss.org/frontpage
  API: https://hacker-news.firebaseio.com/v0/topstories.json
  Sprache: en
  Paywall: Nein

Quelle: Reddit
  Methode: .json-Endpoint (z.B. /r/MachineLearning/top.json?t=day&limit=10)
  Feed: https://www.reddit.com/r/programming/top.rss?t=day&limit=10
  Sprache: en
  Paywall: Nein
