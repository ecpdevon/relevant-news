#!/usr/bin/env python
"""
Relevant News — Haupt-Pipeline

Orchestriert die tägliche Pipeline:
    fetcher → filter → translator → summarizer → output

Usage:
    python run.py              # Heutiges Datum
    python run.py --date 2025-06-02
    python run.py --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Project root & configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"

# Pipeline steps in order.
#
# Each step defines:
#   script     — Python file in PROJECT_ROOT
#   desc       — human-readable description
#   output     — expected output file (with {date} placeholder)
#   date_arg   — how the date is passed to the script:
#       "flag"       →  --date <day>        (preferred, e.g. output.py)
#       "positional" →  <day>               (e.g. filter.py)
#       "none"       →  no date arg         (script uses date.today() itself)
PIPELINE: list[dict] = [
    {
        "name": "fetcher",
        "desc": "Artikel aus RSS-Quellen abrufen",
        "script": "fetcher.py",
        "date_arg": "none",
        "output": DATA_DIR / "articles" / "{date}.json",
    },
    {
        "name": "filter",
        "desc": "Relevanz-Filter anwenden",
        "script": "filter.py",
        "date_arg": "positional",
        "output": DATA_DIR / "articles" / "{date}_filtered.json",
    },
    {
        "name": "translator",
        "desc": "Artikel ins Deutsche übersetzen",
        "script": "translator.py",
        "date_arg": "flag",
        "output": DATA_DIR / "articles" / "{date}_translated.json",
    },
    {
        "name": "summarizer",
        "desc": "Zusammenfassungen erstellen",
        "script": "summarizer.py",
        "date_arg": "flag",
        "output": DATA_DIR / "summaries" / "{date}.md",
    },
    {
        "name": "output",
        "desc": "Ausgabe speichern & zustellen",
        "script": "output.py",
        "date_arg": "flag",
        "output": PROJECT_ROOT / "daily-news" / "{date}.md",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_path(template: Path, day: str) -> Path:
    """Replace {date} placeholder in a path template."""
    return Path(str(template).format(date=day))


def run_step(step: dict, day: str, python: str = sys.executable) -> bool:
    """Execute a single pipeline step via subprocess.

    Respects step['date_arg'] to pass the date correctly:
      "flag"       →  script.py --date <day>
      "positional" →  script.py <day>
      "none"       →  script.py

    Returns True on success, False on failure.
    """
    script = PROJECT_ROOT / step["script"]
    desc = step["desc"]
    date_arg = step.get("date_arg", "flag")

    print(f"\n{'=' * 60}")
    print(f"  [{step['name'].upper()}] {desc}")
    print(f"{'=' * 60}")

    if not script.exists():
        print(f"  ⚠  Script nicht gefunden: {script}")
        print(f"     (wird von einem anderen Worker erstellt — überspringe)")
        return True  # soft-skip — sibling worker may not have finished yet

    # Build command
    cmd = [python, str(script)]
    if date_arg == "flag":
        cmd += ["--date", day]
    elif date_arg == "positional":
        cmd.append(day)
    # "none" → no date arg

    t0 = time.monotonic()
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=300,  # 5 min per step
    )

    elapsed = time.monotonic() - t0

    # Print captured output
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"  │ {line}")

    if result.returncode != 0:
        print(f"  ✗ Fehlgeschlagen (rc={result.returncode}, {elapsed:.1f}s)")
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                print(f"  │ [stderr] {line}")
        return False

    # Verify output file was created
    out_path = fmt_path(step["output"], day)
    if out_path.exists():
        size = out_path.stat().st_size
        print(f"  ✓ OK ({elapsed:.1f}s) → {out_path} ({size:,} bytes)")
    else:
        print(f"  ⚠  Script lief durch, aber Ausgabedatei fehlt: {out_path}")

    return True


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(day: str, *, dry_run: bool = False) -> bool:
    """Run the full pipeline for a given date. Returns True if all steps succeed."""

    print(f"\n╔{'═' * 58}╗")
    print(f"║  Relevant News Pipeline — {day}")
    print(f"║  Projekt: {PROJECT_ROOT}")
    print(f"╚{'═' * 58}╝")

    if dry_run:
        print("\n  🔍 DRY-RUN — keine Scripts werden ausgeführt\n")
        for step in PIPELINE:
            out = fmt_path(step["output"], day)
            dep = step.get("depends_on")
            print(f"  [{step['name']:>12}] {step['desc']}")
            print(f"               script : {step['script']}")
            print(f"               output : {out}")
            if dep:
                print(f"               depends: {dep}")
            print()
        return True

    python = sys.executable
    print(f"  Python : {python}\n")

    success = True
    for step in PIPELINE:
        ok = run_step(step, day, python)
        if not ok:
            success = False
            print(f"\n  ✗ Pipeline abgebrochen bei Schritt '{step['name']}'")
            break

    return success


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Relevant News — tägliche News-Pipeline ausführen",
    )
    parser.add_argument(
        "--date",
        help="Datum im Format YYYY-MM-DD (Standard: heute)",
        default=date.today().isoformat(),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, was ausgeführt würde (keine Scripts starten)",
    )
    parser.add_argument(
        "--step",
        choices=[s["name"] for s in PIPELINE],
        help="Nur einen einzelnen Schritt ausführen",
    )
    args = parser.parse_args()

    # Validate date
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Ungültiges Datum: {args.date} (erwartet: YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)

    # Single-step mode
    if args.step:
        step = next(s for s in PIPELINE if s["name"] == args.step)
        success = run_step(step, args.date)
    else:
        success = run_pipeline(args.date, dry_run=args.dry_run)

    # Final summary
    print(f"\n{'─' * 60}")
    if success:
        print(f"  ✓ Pipeline abgeschlossen für {args.date}")
        out = PROJECT_ROOT / "daily-news" / f"{args.date}.md"
        if out.exists():
            print(f"  📄 Endausgabe: {out}")
        sys.exit(0)
    else:
        print(f"  ✗ Pipeline fehlgeschlagen für {args.date}")
        sys.exit(1)


if __name__ == "__main__":
    main()
