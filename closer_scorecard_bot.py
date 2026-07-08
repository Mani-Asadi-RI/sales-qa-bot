#!/usr/bin/env python3
"""Weekly Closer Scorecard — public accountability post, every Monday morning.

Per closer (AJ, Bronson) for the prior week (Mon-Sun):
  - Appointments set / shows / no-shows / show rate   (B2B Sales Tracker sheet)
  - Wins (cash collected) / close rate                 (B2B Sales Tracker sheet)
  - Open pipeline + stale In Process deals             (B2B Sales Tracker sheet)
  - Avg QA scorecard + compliance scores               (#closer-feedback-channel)
  - Repeat offenses flagged by the QA bot              (#closer-feedback-channel)
  - Feedback acknowledgment rate                       (#closer-feedback-channel)
  - Month-to-date close rate vs the 50% bonus target   (B2B Sales Tracker sheet)

Posts to #sales-discussion; falls back to #closer-feedback-channel if the bot
is not a member yet.

Env:
  SLACK_BOT_TOKEN        — xoxb-... (required unless --sheet-only)
  B2B_ENDPOINT_URL       — optional override of the Apps Script /exec URL
  B2B_API_TOKEN          — optional override of the endpoint token
  SCORECARD_CHANNEL_ID   — optional override of the destination channel
  DRY_RUN=1              — print the post instead of sending it

Usage:
  python closer_scorecard_bot.py                # normal weekly run
  python closer_scorecard_bot.py --sheet-only   # print sheet stats, no Slack
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests

EASTERN = ZoneInfo("America/New_York")

CLOSER_FEEDBACK_CHANNEL = "C0AHZ1QA3GB"
SALES_DISCUSSION_CHANNEL = "C08U2V0594N"

B2B_ENDPOINT_URL = os.environ.get(
    "B2B_ENDPOINT_URL",
    "https://script.google.com/macros/s/AKfycbzsHS8IxfgskOsIXAwT1Lj5t7MHEMJv9h3Kvj-hIUSbUnphyM-Fy2yYPjAhrtfZ4njs/exec",
)
B2B_API_TOKEN = os.environ.get("B2B_API_TOKEN", "b2b_0WjbYUXFCny_c6yqxGM2iDMRY0sjbIK7wEusS2DWfzI")

CLOSERS = [
    {"name": "AJ", "sheet_key": "aj", "slack_id": "U0A748MBHK7"},
    {"name": "Bronson", "sheet_key": "bronson", "slack_id": "U0AF0EJHRSS"},
]

CLOSE_RATE_BONUS_TARGET = 0.50  # monthly close rate >= 50% earns the +5% comp bonus
STALE_DAYS = 7

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def log(msg: str) -> None:
    print(msg, flush=True)


# ─────────────────────────────────────────────────────────────────────
# B2B Sales Tracker sheet
# ─────────────────────────────────────────────────────────────────────

def parse_sheet_date(s: Optional[str]) -> Optional[date]:
    """Handles 'Thu Jul 09 2026 03:00:00 GMT-0400 (...)' and '1/5/2026' / '1/5/26'."""
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^[A-Za-z]{3}\s+([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})", s)
    if m and m.group(1) in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return date(y, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


def fetch_sheet_rows() -> list[dict]:
    r = requests.get(
        B2B_ENDPOINT_URL,
        params={"token": B2B_API_TOKEN},
        timeout=120,
        allow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    rows = data.get("rows", [])
    log(f"Sheet: {len(rows)} rows fetched")
    return rows


def val(row: dict, col: str) -> str:
    return (row.get(col) or "").strip()


def sheet_stats(rows: list[dict], sheet_key: str, week_start: date, week_end: date,
                month_start: date, today: date) -> dict[str, Any]:
    mine = [r for r in rows if val(r, "Closer").lower().split()[:1] == [sheet_key]]

    def appt_date(r: dict) -> Optional[date]:
        return parse_sheet_date(r.get("Date Appt Is Set For"))

    def in_week(d: Optional[date]) -> bool:
        return d is not None and week_start <= d < week_end

    appts = [r for r in mine if in_week(appt_date(r))]
    shows = [r for r in appts if val(r, "Sales Status").lower() == "show"]
    noshows = [r for r in appts if val(r, "Sales Status").lower() == "noshow"]
    decided = len(shows) + len(noshows)

    wins = [r for r in mine
            if val(r, "Outcome").lower() == "won"
            and in_week(parse_sheet_date(r.get("Date Cash Collected")))]

    in_process = [r for r in mine if val(r, "Outcome").lower() == "in process"]
    stale = []
    for r in in_process:
        d = appt_date(r)
        if d is not None and d < today - timedelta(days=STALE_DAYS):
            stale.append(r)

    mtd_shows, mtd_wins = [], []
    for r in mine:
        if val(r, "Sales Status").lower() == "show":
            d = appt_date(r)
            if d is not None and month_start <= d <= today:
                mtd_shows.append(r)
        if val(r, "Outcome").lower() == "won":
            d = parse_sheet_date(r.get("Date Cash Collected"))
            if d is not None and month_start <= d <= today:
                mtd_wins.append(r)

    return {
        "appts": len(appts),
        "shows": len(shows),
        "noshows": len(noshows),
        "show_rate": (len(shows) / decided) if decided else None,
        "wins": len(wins),
        "close_rate": (len(wins) / len(shows)) if shows else None,
        "in_process": len(in_process),
        "stale": len(stale),
        "stale_names": [val(r, "Name of Lead") for r in stale][:8],
        "mtd_shows": len(mtd_shows),
        "mtd_wins": len(mtd_wins),
        "mtd_close_rate": (len(mtd_wins) / len(mtd_shows)) if mtd_shows else None,
    }


# ─────────────────────────────────────────────────────────────────────
# QA channel stats (#closer-feedback-channel)
# ─────────────────────────────────────────────────────────────────────

def fetch_channel_since(slack, channel: str, oldest_ts: float, latest_ts: float) -> list[dict]:
    messages: list[dict] = []
    cursor = None
    while True:
        kwargs: dict[str, Any] = {"channel": channel, "oldest": str(oldest_ts),
                                  "latest": str(latest_ts), "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = slack.conversations_history(**kwargs)
        messages.extend(resp.get("messages", []))
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.5)
    return messages


def qa_stats(slack, week_start_ts: float, week_end_ts: float) -> dict[str, dict[str, Any]]:
    from slack_sdk.errors import SlackApiError

    per: dict[str, dict[str, Any]] = {
        c["sheet_key"]: {"scored": 0, "qa_scores": [], "compliance_scores": [],
                         "repeat_offenses": 0, "acked": 0, "slack_id": c["slack_id"]}
        for c in CLOSERS
    }
    parents = fetch_channel_since(slack, CLOSER_FEEDBACK_CHANNEL, week_start_ts, week_end_ts)
    log(f"QA channel: {len(parents)} messages since window start")

    for m in parents:
        text = m.get("text") or ""
        cm = re.search(r"Closer:\s*([^\n<]+)", text, re.IGNORECASE)
        if not cm:
            continue
        first = cm.group(1).strip().lower().split()
        key = first[0] if first else ""
        if key not in per:
            continue
        ts = m.get("ts")
        try:
            replies = slack.conversations_replies(channel=CLOSER_FEEDBACK_CHANNEL, ts=ts).get("messages", [])
        except SlackApiError:
            continue
        time.sleep(0.3)

        scorecard = next((r.get("text") or "" for r in replies[1:]
                          if "SALES QA SCORECARD" in (r.get("text") or "").upper()), None)
        if not scorecard:
            continue  # skipped/internal or not yet scored

        stats = per[key]
        stats["scored"] += 1

        sm = re.search(r"Overall Score:\s*(\d+)\s*/\s*10", scorecard)
        if sm:
            stats["qa_scores"].append(int(sm.group(1)))
        for r in replies[1:]:
            t = r.get("text") or ""
            comp = re.search(r"COMPLIANCE RATING:\s*(\d+)\s*/\s*10", t.replace("*", ""))
            if comp:
                stats["compliance_scores"].append(int(comp.group(1)))
        if re.search(r"REPEAT \(", scorecard):
            stats["repeat_offenses"] += 1
        if any((r.get("user") == stats["slack_id"]) for r in replies[1:]):
            stats["acked"] += 1

    return per


# ─────────────────────────────────────────────────────────────────────
# Rendering + posting
# ─────────────────────────────────────────────────────────────────────

def pct(x: Optional[float]) -> str:
    return f"{round(x * 100)}%" if x is not None else "n/a"


def avg(xs: list[int]) -> str:
    return f"{sum(xs) / len(xs):.1f}/10" if xs else "n/a"


def render(week_start: date, week_end: date, today: date,
           sheet: dict[str, dict], qa: dict[str, dict]) -> str:
    month_name = today.strftime("%B")
    lines = [
        "WEEKLY CLOSER SCORECARD",
        f"Week of {week_start.strftime('%b %d')} - {(week_end - timedelta(days=1)).strftime('%b %d, %Y')}",
        "",
    ]
    for c in CLOSERS:
        k = c["sheet_key"]
        s = sheet[k]
        q = qa.get(k, {})
        scored = q.get("scored", 0)
        acked = q.get("acked", 0)
        divider = "—" * 18
        lines += [
            divider,
            f"{c['name'].upper()}",
            divider,
            f"Appointments: {s['appts']} set | {s['shows']} showed | {s['noshows']} no-show | Show rate: {pct(s['show_rate'])}",
            f"Closes: {s['wins']} won (cash collected) | Close rate (won/shows): {pct(s['close_rate'])}",
            f"Pipeline: {s['in_process']} In Process | {s['stale']} stale (appt older than {STALE_DAYS} days)",
        ]
        if s["stale_names"]:
            lines.append(f"Stale deals needing action: {', '.join(n for n in s['stale_names'] if n)}")
        lines += [
            f"QA: {scored} calls scored | Avg scorecard: {avg(q.get('qa_scores', []))} | Avg compliance: {avg(q.get('compliance_scores', []))}",
            f"Repeat offenses flagged: {q.get('repeat_offenses', 0)}",
            f"Feedback acknowledged: {acked}/{scored}" + (f" ({pct(acked / scored)})" if scored else ""),
            f"Bonus tracker ({month_name}): {s['mtd_wins']} wins / {s['mtd_shows']} shows MTD = {pct(s['mtd_close_rate'])} close rate vs 50% target for the +5% bonus",
            "",
        ]
    lines += [
        "Acknowledgment rule: every scorecard requires a reply with your #1 takeaway within 24 hours.",
        "Bonus eligibility requires 100% feedback acknowledgment and zero stale pipeline at month end.",
    ]
    return "\n".join(lines)


def post(slack, text: str) -> None:
    from slack_sdk.errors import SlackApiError

    override = os.environ.get("SCORECARD_CHANNEL_ID")
    targets = [override] if override else [SALES_DISCUSSION_CHANNEL, CLOSER_FEEDBACK_CHANNEL]
    for channel in targets:
        try:
            slack.chat_postMessage(channel=channel, text=text)
            log(f"Posted scorecard to {channel}")
            return
        except SlackApiError as e:
            err = e.response.get("error")
            log(f"Post to {channel} failed ({err}); trying fallback" if channel != targets[-1]
                else f"Post to {channel} failed ({err})")
            if err not in ("not_in_channel", "channel_not_found"):
                raise
    sys.exit("Could not post scorecard to any channel")


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

def main() -> int:
    sheet_only = "--sheet-only" in sys.argv

    now_et = datetime.now(EASTERN)
    today = now_et.date()
    week_end = today - timedelta(days=today.weekday())      # this Monday
    week_start = week_end - timedelta(days=7)               # prior Monday
    month_start = today.replace(day=1)
    week_start_ts = datetime(week_start.year, week_start.month, week_start.day,
                             tzinfo=EASTERN).timestamp()
    week_end_ts = datetime(week_end.year, week_end.month, week_end.day,
                           tzinfo=EASTERN).timestamp()

    log(f"Window: {week_start} to {week_end} (exclusive), MTD from {month_start}")

    rows = fetch_sheet_rows()
    sheet = {c["sheet_key"]: sheet_stats(rows, c["sheet_key"], week_start, week_end, month_start, today)
             for c in CLOSERS}

    if sheet_only:
        for k, s in sheet.items():
            log(f"{k}: {s}")
        return 0

    if not os.environ.get("SLACK_BOT_TOKEN"):
        sys.exit("SLACK_BOT_TOKEN not set")
    from slack_sdk import WebClient
    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

    qa = qa_stats(slack, week_start_ts, week_end_ts)
    text = render(week_start, week_end, today, sheet, qa)

    if os.environ.get("DRY_RUN"):
        log("\n===== DRY RUN — would post: =====\n" + text)
        return 0

    post(slack, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
