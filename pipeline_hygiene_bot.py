#!/usr/bin/env python3
"""Daily Pipeline Hygiene Bot — the follow-up enforcer.

Every weekday morning, posts one list per closer (AJ, Bronson) in
#sales-discussion of every deal that needs action TODAY:

  1. NO-SHOW RECOVERY  — every open deal in stage #5 (no show), with age.
     Never falls off until rescheduled or moved to Lost.
  2. FOLLOW-UP DEBT    — stage #7 (Deal In Progress) deals with zero GHL
     activity for STALE_DAYS+ days. At ESCALATE_DAYS+ the line is marked
     ESCALATED and tags Mani.
  3. MISSING OUTCOMES  — tracker rows whose appointment already happened but
     Sales Status or Outcome was never logged.

Fresh-start rule: only items whose last activity is on/after FRESH_START are
tracked daily. Everything older lives on the one-time Pipeline Purge List
sheet and shows up as a single counter line. Deals assigned to anyone else
(Mani, Krisz, unassigned) are summarized in one count line so nothing rots
invisibly.

Sources: GHL opportunities API (all three pipelines) + B2B Sales Tracker
endpoint. Stateless — ages derive from GHL timestamps, so an ignored deal
climbs the list on its own every day.

Env:
  SLACK_BOT_TOKEN   — xoxb-... (required unless DRY_RUN)
  GHL_TOKEN         — private integration token (falls back to built-in)
  HYGIENE_CHANNEL_ID — optional channel override
  DRY_RUN=1         — print instead of posting
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests

EASTERN = ZoneInfo("America/New_York")

SALES_DISCUSSION_CHANNEL = "C08U2V0594N"
CLOSER_FEEDBACK_CHANNEL = "C0AHZ1QA3GB"

GHL_TOKEN = os.environ.get("GHL_TOKEN") or "pit-eb371404-9c61-40dc-9cbe-1082b01777a6"
GHL_LOCATION = "LcTHdnPRh7CiaxqatNDm"
GHL_BASE = "https://services.leadconnectorhq.com"
GHL_HEADERS = {"Authorization": f"Bearer {GHL_TOKEN}", "Version": "2021-07-28"}

B2B_ENDPOINT_URL = os.environ.get(
    "B2B_ENDPOINT_URL",
    "https://script.google.com/macros/s/AKfycbzsHS8IxfgskOsIXAwT1Lj5t7MHEMJv9h3Kvj-hIUSbUnphyM-Fy2yYPjAhrtfZ4njs/exec",
)
B2B_API_TOKEN = os.environ.get("B2B_API_TOKEN", "b2b_0WjbYUXFCny_c6yqxGM2iDMRY0sjbIK7wEusS2DWfzI")

# pipeline id -> (label, stage5_noshow_id, stage7_inprogress_id)
PIPELINES = {
    "RndkDrnqLz5X5Ff7CNjm": ("Roofing",
                             "741cabd6-4ed0-4209-8d4b-4e2825ae5350",
                             "da14994c-3838-4c07-872a-003a125a3774"),
    "5JhQfYeeu9O4eAjR89mR": ("HVAC",
                             "92556e69-56aa-461e-bd4d-bd97fc5d1015",
                             "c19c969b-e808-4987-a5bb-422c773ae76a"),
    "dcD7SJR2L2PlZZUlqH9f": ("Windows/Doors",
                             "d273d7f2-fda9-46b4-b10e-d4c821426487",
                             "1463f12a-77cc-44e2-833f-5fdc258523ae"),
}

CLOSERS = [
    {"name": "AJ", "sheet_key": "aj", "ghl_id": "grXOyu4fGN6l73qAcbpv", "slack_id": "U0A748MBHK7"},
    {"name": "Bronson", "sheet_key": "bronson", "ghl_id": "8Hrx0yBeg48Fe4Z62vhQ", "slack_id": "U0AF0EJHRSS"},
]
MANI_SLACK_ID = "U08K21YETD2"

STALE_DAYS = 2        # Deal In Progress with no GHL activity for this long -> flagged
ESCALATE_DAYS = 7     # flagged item this old -> ESCALATED, tags Mani
# Fresh-start line (Mani, 2026-07-10): the daily list only tracks items whose
# last activity is on/after this date. Everything older lives on the one-time
# Pipeline Purge List sheet and is summarized in a single counter line.
FRESH_START = date(2026, 7, 7)
PURGE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1v7pYDh7c7ISvAv60MK2DW1HrRCUBycQFJCRK7fvdVD8/edit"
MAX_LINES_PER_SECTION = 12

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def log(msg: str) -> None:
    print(msg, flush=True)


# ─────────────────────────────────────────────────────────────────────
# GHL
# ─────────────────────────────────────────────────────────────────────

def ghl_search_stage(pipeline_id: str, stage_id: str) -> list[dict]:
    """All open opportunities in one pipeline stage (paginated)."""
    out: list[dict] = []
    page = 1
    while page <= 30:
        r = requests.get(
            f"{GHL_BASE}/opportunities/search",
            headers=GHL_HEADERS,
            params={"location_id": GHL_LOCATION, "pipeline_id": pipeline_id,
                    "pipeline_stage_id": stage_id, "status": "open",
                    "limit": 100, "page": page},
            timeout=60,
        )
        r.raise_for_status()
        batch = r.json().get("opportunities", [])
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.3)
    return out


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_since(s: Optional[str], now: datetime) -> Optional[int]:
    dt = parse_iso(s)
    if dt is None:
        return None
    return max(0, (now - dt).days)


def _add_deduped(bucket: list, item: dict) -> None:
    """Same lead often exists as an opportunity in several pipelines — keep one
    line per contact, preferring the entry that carries a dollar value."""
    for i, existing in enumerate(bucket):
        if existing["contact"] == item["contact"]:
            if (item["value"] or 0) > (existing["value"] or 0):
                bucket[i] = item
            return
    bucket.append(item)


def _is_fresh(ref_iso: Optional[str]) -> bool:
    dt = parse_iso(ref_iso)
    return dt is not None and dt.astimezone(EASTERN).date() >= FRESH_START


def collect_ghl_items(now: datetime) -> dict[str, dict[str, Any]]:
    """Per closer ghl_id: {noshow: [...], debt: [...], purge_noshow: n, purge_debt: n};
    'other' bucket for deals assigned to nobody / other reps. Items whose last
    activity predates FRESH_START count toward the purge-sheet counters only."""
    buckets: dict[str, dict[str, Any]] = {
        c["ghl_id"]: {"noshow": [], "debt": [], "purge_noshow": 0, "purge_debt": 0}
        for c in CLOSERS
    }
    buckets["other"] = {"noshow": [], "debt": [], "purge_noshow": 0, "purge_debt": 0}

    for pid, (label, stage5, stage7) in PIPELINES.items():
        for opp in ghl_search_stage(pid, stage5):
            ref = opp.get("lastStageChangeAt") or opp.get("updatedAt")
            key = opp.get("assignedTo") if opp.get("assignedTo") in buckets else "other"
            if not _is_fresh(ref):
                buckets[key]["purge_noshow"] += 1
                continue
            _add_deduped(buckets[key]["noshow"],
                         {"name": opp.get("name") or "?", "contact": opp.get("contactId"),
                          "pipeline": label, "age": days_since(ref, now) or 0,
                          "value": opp.get("monetaryValue")})
        for opp in ghl_search_stage(pid, stage7):
            age = days_since(opp.get("updatedAt"), now)
            if age is None or age < STALE_DAYS:
                continue
            key = opp.get("assignedTo") if opp.get("assignedTo") in buckets else "other"
            if not _is_fresh(opp.get("updatedAt")):
                buckets[key]["purge_debt"] += 1
                continue
            _add_deduped(buckets[key]["debt"],
                         {"name": opp.get("name") or "?", "contact": opp.get("contactId"),
                          "pipeline": label, "age": age, "value": opp.get("monetaryValue")})
        log(f"GHL {label}: scanned stages 5+7")

    for b in buckets.values():
        b["noshow"].sort(key=lambda x: -x["age"])
        b["debt"].sort(key=lambda x: -x["age"])
    return buckets


# ─────────────────────────────────────────────────────────────────────
# Sheet: appointments that happened but were never logged
# ─────────────────────────────────────────────────────────────────────

def parse_sheet_date(s: Optional[str]) -> Optional[date]:
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


def collect_sheet_items(today: date) -> dict[str, list]:
    r = requests.get(B2B_ENDPOINT_URL, params={"token": B2B_API_TOKEN},
                     timeout=120, allow_redirects=True)
    r.raise_for_status()
    rows = r.json().get("rows", [])
    log(f"Sheet: {len(rows)} rows")

    out: dict[str, list] = {c["sheet_key"]: [] for c in CLOSERS}
    cutoff = FRESH_START
    for row in rows:
        key = (row.get("Closer") or "").strip().lower().split()[:1]
        key = key[0] if key else ""
        if key not in out:
            continue
        d = parse_sheet_date(row.get("Date Appt Is Set For"))
        if d is None or not (cutoff <= d < today):
            continue
        status = (row.get("Sales Status") or "").strip().lower()
        outcome = (row.get("Outcome") or "").strip().lower()
        name = (row.get("Name of Lead") or "?").strip() or "?"
        if not status:
            out[key].append({"name": name, "date": d, "problem": "no Show/Noshow logged"})
        elif status == "show" and not outcome:
            out[key].append({"name": name, "date": d, "problem": "showed, no Outcome logged"})
    for items in out.values():
        items.sort(key=lambda x: x["date"])
    return out


# ─────────────────────────────────────────────────────────────────────
# Rendering + posting
# ─────────────────────────────────────────────────────────────────────

def fmt_value(v: Any) -> str:
    try:
        return f" — ${int(v):,}" if v else ""
    except (TypeError, ValueError):
        return ""


def render_section(title: str, lines: list[str], empty_note: str) -> list[str]:
    out = [f"{title} ({len(lines)}):"] if lines else [f"{title}: {empty_note}"]
    shown = lines[:MAX_LINES_PER_SECTION]
    out.extend(shown)
    if len(lines) > len(shown):
        out.append(f"  ...and {len(lines) - len(shown)} more")
    return out


def render(now_et: datetime, ghl: dict, sheet: dict) -> str:
    divider = "—" * 18
    lines = [
        f"DAILY PIPELINE HYGIENE — {now_et.strftime('%a %b %d')}",
        "Every deal below needs ONE of these today: follow-up logged in GHL, reschedule booked, or moved to Lost.",
    ]
    for c in CLOSERS:
        g = ghl[c["ghl_id"]]
        s = sheet[c["sheet_key"]]
        total = len(g["noshow"]) + len(g["debt"]) + len(s)
        lines += ["", divider, f"{c['name'].upper()} — {total} item(s) <@{c['slack_id']}>", divider]

        noshow_lines = [f"  {i['name']} — {i['pipeline']} — {i['age']}d since no-show{fmt_value(i['value'])}"
                        for i in g["noshow"]]
        lines += render_section("NO-SHOW RECOVERY", noshow_lines, "clear")

        debt_lines = []
        for i in g["debt"]:
            esc = f"  ESCALATED <@{MANI_SLACK_ID}>" if i["age"] >= ESCALATE_DAYS else ""
            debt_lines.append(f"  {i['name']} — {i['pipeline']} — {i['age']}d silent{fmt_value(i['value'])}{esc}")
        lines += render_section(f"FOLLOW-UP DEBT ({STALE_DAYS}d+ no activity)", debt_lines, "clear")

        sheet_lines = [f"  {i['name']} — appt {i['date'].strftime('%b %d')} — {i['problem']}" for i in s]
        lines += render_section("MISSING OUTCOMES (tracker)", sheet_lines, "clear")

        purge = g["purge_noshow"] + g["purge_debt"]
        if purge:
            lines.append(f"Still on the July purge list (pre-{FRESH_START.strftime('%b %d')} items, "
                         f"not tracked daily): {purge} deals — {PURGE_SHEET_URL}")

    other = ghl["other"]
    other_total = (len(other["noshow"]) + len(other["debt"])
                   + other["purge_noshow"] + other["purge_debt"])
    if other_total:
        recent = other["debt"] + other["noshow"]
        example = f" (e.g. {', '.join(i['name'] for i in recent[:3])})" if recent else ""
        lines += ["", f"Unassigned / other reps: {other_total} deal(s) in follow-up stages "
                      f"not owned by AJ or Bronson{example} — <@{MANI_SLACK_ID}> assign or kill."]
    return "\n".join(lines)


def post(text: str) -> None:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    override = os.environ.get("HYGIENE_CHANNEL_ID")
    targets = [override] if override else [SALES_DISCUSSION_CHANNEL, CLOSER_FEEDBACK_CHANNEL]
    for channel in targets:
        try:
            slack.chat_postMessage(channel=channel, text=text)
            log(f"Posted hygiene list to {channel}")
            return
        except SlackApiError as e:
            err = e.response.get("error")
            log(f"Post to {channel} failed ({err})")
            if err not in ("not_in_channel", "channel_not_found"):
                raise
    sys.exit("Could not post hygiene list to any channel")


def main() -> int:
    now = datetime.now(timezone.utc)
    now_et = now.astimezone(EASTERN)
    today = now_et.date()

    ghl = collect_ghl_items(now)
    sheet = collect_sheet_items(today)
    text = render(now_et, ghl, sheet)

    if os.environ.get("DRY_RUN"):
        log("\n===== DRY RUN — would post: =====\n" + text)
        return 0
    if not os.environ.get("SLACK_BOT_TOKEN"):
        sys.exit("SLACK_BOT_TOKEN not set")
    post(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
