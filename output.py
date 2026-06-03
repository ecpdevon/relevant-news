"""
Output module for Relevant News pipeline.

Saves the daily summary as Markdown and optionally delivers
it via Telegram (using the Bot API or Hermes CLI).
"""

import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Project layout (same as AGENTS.md)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
SUMMARIES_DIR = DATA_DIR / "summaries"
OUTPUT_DIR = PROJECT_ROOT / "daily-news"


def load_summary(day: Optional[str] = None) -> dict:
    """Load the JSON summary for the given date (YYYY-MM-DD)."""
    day = day or date.today().isoformat()
    path = SUMMARIES_DIR / f"{day}.json"
    if not path.exists():
        raise FileNotFoundError(f"No summary found for {day}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_markdown(day: Optional[str] = None) -> str:
    """Load the Markdown newsletter for the given date."""
    day = day or date.today().isoformat()
    path = SUMMARIES_DIR / f"{day}.md"
    if not path.exists():
        raise FileNotFoundError(f"No markdown found for {day}: {path}")
    return path.read_text(encoding="utf-8")


def save_markdown(content: str, day: Optional[str] = None) -> Path:
    """Save the final Markdown to daily-news/<date>.md."""
    day = day or date.today().isoformat()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{day}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"[output] Saved {out_path} ({len(content)} chars)")
    return out_path


def build_telegram_message(content: str, max_chars: int = 4000) -> str:
    """Truncate and format the summary for Telegram.

    Telegram messages have a 4096 char limit; we stay safely under
    and append a note if truncated.
    """
    if len(content) <= max_chars:
        return content
    truncated = content[: max_chars - 120]
    return truncated + "\n\n---\n📎 *Nachricht gekürzt — vollständiger Artikel siehe angehängte Datei.*"


# ---------------------------------------------------------------------------
# Telegram delivery
# ---------------------------------------------------------------------------

def send_telegram_cli(md_path: Path, day: str) -> bool:
    """Deliver via Hermes CLI (hermes send-message). Uses the active Hermes
    installation to post to the default Telegram home channel."""
    import subprocess

    msg = build_telegram_message(md_path.read_text(encoding="utf-8"))
    try:
        result = subprocess.run(
            ["hermes", "send-message", "telegram", "--message", msg],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"[output] Telegram sent via Hermes CLI ({len(msg)} chars)")
            return True
        print(f"[output] Hermes CLI failed (rc={result.returncode}): {result.stderr.strip()}")
    except FileNotFoundError:
        print("[output] Hermes CLI not found — skipping Telegram delivery")
    except Exception as exc:
        print(f"[output] Telegram delivery error: {exc}")
    return False


def send_telegram_bot(md_path: Path, day: str, bot_token: str, chat_id: str) -> bool:
    """Deliver via raw Telegram Bot API (no extra deps needed, just requests)."""
    import requests

    content = md_path.read_text(encoding="utf-8")
    msg = build_telegram_message(content)

    # Send text message
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print(f"[output] Telegram Bot message sent ({len(msg)} chars)")
    except Exception as exc:
        print(f"[output] Telegram Bot text failed: {exc}")
        return False

    # If the content was truncated, also send the full file
    if len(content) > 4000:
        doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        try:
            with open(md_path, "rb") as f:
                r2 = requests.post(
                    doc_url,
                    data={"chat_id": chat_id, "caption": f"📄 {day} (Volltext)"},
                    files={"document": (md_path.name, f, "text/markdown")},
                    timeout=30,
                )
            r2.raise_for_status()
            print("[output] Telegram Bot document attached")
        except Exception as exc:
            print(f"[output] Telegram Bot document upload failed: {exc}")

    return True


def deliver(
    day: Optional[str] = None,
    *,
    telegram: bool = True,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> Path:
    """Main entry point: save markdown + optionally deliver via Telegram.

    Returns the path to the saved Markdown file.
    """
    day = day or date.today().isoformat()
    content = load_markdown(day)
    out_path = save_markdown(content, day)

    if telegram:
        if bot_token and chat_id:
            send_telegram_bot(out_path, day, bot_token, chat_id)
        else:
            send_telegram_cli(out_path, day)

    return out_path


# ---------------------------------------------------------------------------
# CLI entry point (for standalone use)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deliver the daily news summary.")
    parser.add_argument("--date", help="Date in YYYY-MM-DD (default: today)")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram delivery")
    parser.add_argument("--bot-token", help="Telegram Bot token")
    parser.add_argument("--chat-id", help="Telegram chat ID")
    args = parser.parse_args()

    deliver(
        day=args.date,
        telegram=not args.no_telegram,
        bot_token=args.bot_token,
        chat_id=args.chat_id,
    )
