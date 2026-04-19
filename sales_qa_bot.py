#!/usr/bin/env python3
"""
Sales QA Bot — executable version of the full combined prompt.

Reference docs (authoritative; source of truth for scoring):
  - Sales-QA-Bot-FULL-COMBINED-Prompt.md  (primary)
  - qa-rating-methodology-deep-dive.md     (compliance + prospect methodology)
  - qa-scorecard-methodology-mani-style.md (Mani's 53-call patterns, signature phrases)

Flow (batch, single invocation processes ALL unprocessed):
  1. Read last N Slack messages from #closer-feedback-channel
  2. Build frozen list of fathom.video messages without QA replies
  3. For each:
       - Resolve recording via Fathom API (tries all 3 keys)
       - If internal meeting → post skip reply
       - Else search Slack for prior calls with the same prospect (multi-call context)
       - Ask Claude for a single JSON response with all scoring data
       - Python clamps (non-DM Character cap), computes arithmetic, renders 3 messages
       - Post scorecard, compliance, prospect rating as thread replies
       - Verify

Env:
  SLACK_BOT_TOKEN    — xoxb-...
  ANTHROPIC_API_KEY  — sk-ant-...
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

import anthropic
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

CHANNEL_ID = "C0AHZ1QA3GB"
BASE_DIR = Path(__file__).parent
PROMPT_FILES = [
    BASE_DIR / "Sales-QA-Bot-FULL-COMBINED-Prompt.md",
    BASE_DIR / "qa-rating-methodology-deep-dive.md",
    BASE_DIR / "qa-scorecard-methodology-mani-style.md",
]

FATHOM_KEYS = {
    "Mani Asadi":    "toiZ6ioL9wWrFQY3U_68mQ.P6nmq2iPZ6n-yzspyeb8Uw9bqyRqUPf2rVVhtOjWH-c",
    "Bronson Boyko": "SroP03Cu6f378sJytGkDKA.CoWYni5-XU_womTc6eNVXYLfyD8aY-wLqprxws5IO6U",
    "Krisz Suto":    "EgDHKWZquyusctBckVfZLQ.cBnpMF_zEU7jY0twNbyuOSXv3UYr7COBxVTC6BVlv44",
}
FATHOM_LIST_URL = "https://api.fathom.ai/external/v1/meetings"
FATHOM_LINK_RE = re.compile(r"https?://(?:www\.)?fathom\.video/share/[A-Za-z0-9_-]+")
TS_RE = re.compile(r"\b\d{2}:\d{2}:\d{2}\b")
QA_MARKERS = ("QA SCORECARD", "COMPLIANCE RATING", "PROSPECT RATING", "SKIPPED")
DIVIDER = "\u2014" * 18  # 18 × em dash (matches preferred style)
MAX_MSG_CHARS = 3400  # keep each Slack message below the auto-split threshold

MODEL = "claude-opus-4-7"
CHANNEL_READ_LIMIT = 20


# ─────────────────────────────────────────────────────────────────────
# JSON schema Claude must fill in
# ─────────────────────────────────────────────────────────────────────

JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "classification": {
            "type": "string",
            "enum": ["qualifying", "skip"],
            "description": "qualifying = real external-prospect growth consult; skip = internal/interview/vendor/etc."
        },
        "skip_reason": {
            "type": "string",
            "description": "If classification=skip, a specific one-sentence reason (e.g. 'Internal team huddle', 'Media buyer interview', 'Job interview'). Empty string if qualifying.",
        },
        "call_context": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "closer_name": {"type": "string"},
                "prospect_name": {"type": "string"},
                "prospect_company": {"type": "string"},
                "prospect_location": {"type": "string", "description": "City, State or Region if identifiable."},
                "duration_minutes": {"type": "number"},
                "is_followup": {"type": "boolean"},
                "followup_note": {"type": "string", "description": "e.g. 'Call #2 with X — follow-up from 2026-04-17'. Empty if not a follow-up."}
            },
            "required": ["closer_name", "prospect_name", "prospect_company", "prospect_location", "duration_minutes", "is_followup", "followup_note"]
        },
        "qa_scorecard": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "frame_control": {"anyOf": [{"type": "integer", "enum": [0, 1, 2]}, {"type": "null"}]},
                "discovery_depth": {"anyOf": [{"type": "integer", "enum": [0, 1, 2]}, {"type": "null"}]},
                "authority_positioning": {"anyOf": [{"type": "integer", "enum": [0, 1, 2]}, {"type": "null"}]},
                "objection_handling": {"anyOf": [{"type": "integer", "enum": [0, 1, 2]}, {"type": "null"}]},
                "close_attempt": {"anyOf": [{"type": "integer", "enum": [0, 1, 2]}, {"type": "null"}]},
                "context_sentence": {"type": "string", "description": "1-2 sentences (max 250 chars): who, call length, outcome."},
                "closer_issues": {"type": "string", "description": "2 sentences (max 400 chars); include HH:MM:SS timestamps. No bracket line numbers."},
                "prospect_factors": {"type": "string", "description": "1 sentence (max 200 chars); outside closer's control."},
                "what_went_well": {
                    "type": "array",
                    "items": {"type": "string", "description": "1 sentence (max 220 chars) with HH:MM:SS timestamp. Exactly 2-3 items."}
                },
                "areas_for_improvement": {
                    "type": "array",
                    "items": {"type": "string", "description": "Gap (with HH:MM:SS) plus a short quoted script. Max 250 chars per item. Exactly 2-3 items."}
                },
                "biggest_mistake": {"type": "string", "description": "Max 350 chars. What happened (with HH:MM:SS) + quoted script. Or 'None — no critical error.'"},
                "missed_buying_signal": {"type": "string", "description": "Max 250 chars. Prospect's exact words + what closer should have done. Or 'None — prospect showed no buying signals.'"},
                "tone_warning": {"type": "string", "description": "Max 150 chars. 1 sentence or 'None.'"},
                "verdict": {"type": "string", "description": "Max 350 chars. 1-2 sentences: overall + next action. For follow-ups, assess the full engagement."}
            },
            "required": ["frame_control", "discovery_depth", "authority_positioning", "objection_handling", "close_attempt", "context_sentence", "closer_issues", "prospect_factors", "what_went_well", "areas_for_improvement", "biggest_mistake", "missed_buying_signal", "tone_warning", "verdict"]
        },
        "compliance": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "complied_on": {
                    "type": "string",
                    "description": "1-3 sentence prose paragraph (under 500 chars) naming what the closer did RIGHT on this call. Reference HH:MM:SS timestamps. Cover any of: discovery before pitch, value tie-in, buy-in before pricing, benchmarks within 20% ($100/day→14, $150→21, $200→25), 12-week program framing, concrete next step, post-close expectations, use of Mani signature language ('let me ask', 'my clients', named case studies), price-drop discipline."
                },
                "missed": {
                    "type": "string",
                    "description": "1-3 sentence prose paragraph (under 500 chars) naming what the closer MISSED or broke. Reference HH:MM:SS timestamps. Cover deductions from the same Mani-style checklist."
                },
                "score": {"type": "integer", "description": "0-10. Consider the full engagement on follow-ups, not just this call."}
            },
            "required": ["complied_on", "missed", "score"]
        },
        "prospect_rating": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "is_decision_maker": {"type": "boolean", "description": "True only if Owner/CEO/President/Founder/Partner with signing authority. Sales Manager/Director/Ops Manager/Marketing/Estimator = FALSE."},
                "dm_evidence": {"type": "string", "description": "1 sentence citing title or 'check with X' language from transcript."},
                "character_raw": {"type": "integer", "description": "Unclamped score. Python applies non-DM cap."},
                "character_note": {"type": "string", "description": "1-2 sentences, transcript refs."},
                "business_raw": {"type": "integer"},
                "business_note": {"type": "string", "description": "1-2 sentences. Revenue, team, ICP fit."},
                "location_raw": {"type": "integer"},
                "location_note": {"type": "string", "description": "1 sentence. Market tier context."},
                "sales_compliance_raw": {"type": "integer"},
                "sales_compliance_note": {"type": "string", "description": "1-2 sentences. Prep, punctuality, engagement."}
            },
            "required": ["is_decision_maker", "dm_evidence", "character_raw", "character_note", "business_raw", "business_note", "location_raw", "location_note", "sales_compliance_raw", "sales_compliance_note"]
        }
    },
    "required": ["classification", "skip_reason", "call_context", "qa_scorecard", "compliance", "prospect_rating"]
}


# ─────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(msg, flush=True)


# ─────────────────────────────────────────────────────────────────────
# System prompt assembly (cached)
# ─────────────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    parts = []
    for f in PROMPT_FILES:
        if not f.exists():
            sys.exit(f"Missing reference doc: {f}")
        parts.append(f"===== {f.name} =====\n\n{f.read_text()}")
    return "\n\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────
# Slack: find unprocessed recordings + prior-prospect search
# ─────────────────────────────────────────────────────────────────────

def find_unprocessed(slack: WebClient) -> list[dict]:
    resp = slack.conversations_history(channel=CHANNEL_ID, limit=CHANNEL_READ_LIMIT)
    messages = resp.get("messages", [])
    candidates: list[dict] = []
    for m in messages:
        text = (m.get("text") or "")
        blob = text + str(m.get("attachments", "")) + str(m.get("blocks", ""))
        match = FATHOM_LINK_RE.search(blob)
        if not match:
            continue
        candidates.append({"message_ts": m["ts"], "share_url": match.group(0), "text": text})

    unprocessed = []
    for c in candidates:
        replies = slack.conversations_replies(channel=CHANNEL_ID, ts=c["message_ts"]).get("messages", [])
        processed = any(
            any(marker in (r.get("text", "") or "").upper() for marker in QA_MARKERS)
            for r in replies[1:]
        )
        if not processed:
            unprocessed.append(c)

    unprocessed.sort(key=lambda x: float(x["message_ts"]))  # oldest first (RULE 15)
    return unprocessed


def search_prior_scorecards(
    slack: WebClient,
    prospect_name: str,
    current_ts: str,
) -> str:
    """Return compact prior-call context string, or empty if none found.
    Two paths:
      (1) Slack search API (fast, but may fail if scope not granted).
      (2) Fallback: walk recent channel history for fathom.video messages whose
          parent text mentions the prospect name.
    """
    context_parts: list[str] = []
    name = (prospect_name or "").strip()
    if len(name) < 3:
        return ""

    # Path 1: Slack search API
    try:
        result = slack.search_messages(query=f'"{name}" in:#closer-feedback-channel')
        for m in (result.get("messages", {}).get("matches", []) or [])[:3]:
            ts = m.get("ts")
            if not ts or ts == current_ts:
                continue
            try:
                replies = slack.conversations_replies(channel=CHANNEL_ID, ts=ts).get("messages", [])
            except SlackApiError:
                continue
            for r in replies[1:]:
                t = (r.get("text") or "").strip()
                if any(k in t.upper() for k in ("QA SCORECARD", "COMPLIANCE RATING", "PROSPECT RATING")):
                    context_parts.append(f"[from {ts}] {t[:1500]}")
    except SlackApiError:
        pass

    # Path 2: Walk recent channel history
    if not context_parts:
        try:
            hist = slack.conversations_history(channel=CHANNEL_ID, limit=200).get("messages", [])
        except SlackApiError:
            hist = []
        first = name.split()[0].lower()
        for m in hist:
            ts = m.get("ts")
            if not ts or ts == current_ts:
                continue
            blob = (m.get("text") or "").lower() + str(m.get("attachments", "")).lower()
            if FATHOM_LINK_RE.search(blob) and first in blob:
                try:
                    replies = slack.conversations_replies(channel=CHANNEL_ID, ts=ts).get("messages", [])
                except SlackApiError:
                    continue
                parent_text = (m.get("text") or "").strip()[:500]
                prior_feedback = []
                for r in replies[1:]:
                    t = (r.get("text") or "").strip()
                    if any(k in t.upper() for k in ("QA SCORECARD", "COMPLIANCE RATING", "PROSPECT RATING")):
                        prior_feedback.append(t[:1200])
                if prior_feedback:
                    block = f"[earlier Slack post ts={ts}]\n{parent_text}\n\n" + "\n\n".join(prior_feedback)
                    context_parts.append(block)
        context_parts = context_parts[:2]

    return "\n\n---\n\n".join(context_parts) if context_parts else ""


# ─────────────────────────────────────────────────────────────────────
# Fathom API
# ─────────────────────────────────────────────────────────────────────

def fetch_fathom_meeting(share_url: str) -> Optional[tuple[dict, str]]:
    for owner, key in FATHOM_KEYS.items():
        cursor = None
        for _ in range(25):
            params: dict[str, Any] = {"include_transcript": "true", "limit": 50}
            if cursor:
                params["cursor"] = cursor
            r = requests.get(FATHOM_LIST_URL, headers={"X-Api-Key": key}, params=params, timeout=30)
            if r.status_code != 200:
                log(f"  Fathom {owner} returned {r.status_code}: {r.text[:200]}")
                break
            data = r.json()
            for item in data.get("items", []):
                if item.get("share_url") == share_url:
                    return item, owner
            cursor = data.get("next_cursor")
            if not cursor:
                break
    return None


def format_transcript(transcript: list[dict]) -> str:
    lines = []
    for i, entry in enumerate(transcript, start=1):
        speaker = entry.get("speaker", {})
        if isinstance(speaker, dict):
            name = speaker.get("display_name") or speaker.get("name") or "Unknown"
        else:
            name = str(speaker)
        ts = entry.get("timestamp") or ""
        text = (entry.get("text") or "").strip().replace("\n", " ")
        prefix = f"[{i}] {ts}" if ts else f"[{i}]"
        lines.append(f"{prefix} {name}: {text}")
    return "\n".join(lines)


def format_attendees(invitees: list[dict]) -> str:
    if not invitees:
        return "(none reported)"
    parts = []
    for inv in invitees:
        name = inv.get("name", "?")
        email = inv.get("email", "?")
        ext = "external" if inv.get("is_external") else "internal"
        parts.append(f"- {name} <{email}> ({ext})")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────
# Claude call: structured output
# ─────────────────────────────────────────────────────────────────────

def analyze_with_claude(
    system_prompt: str,
    meeting: dict,
    owner: str,
    share_url: str,
    prior_context: str,
) -> dict:
    client = anthropic.Anthropic()

    invitees = meeting.get("calendar_invitees", []) or []
    transcript_text = format_transcript(meeting.get("transcript", []) or [])
    attendees_text = format_attendees(invitees)
    title = meeting.get("title") or meeting.get("meeting_title") or "(untitled)"
    domains_type = meeting.get("calendar_invitees_domains_type") or "unknown"

    prior_section = f"\n\nPRIOR CALLS WITH THIS PROSPECT (use for multi-call context):\n{prior_context}\n" if prior_context else "\n\nPRIOR CALLS WITH THIS PROSPECT: none found.\n"

    user_msg = f"""Analyze ONE Fathom recording per the system-prompt rubric.

Recording metadata:
- Owner (Fathom account): {owner}
- Share URL: {share_url}
- Title: {title}
- Recording ID: {meeting.get("recording_id")}
- calendar_invitees_domains_type: {domains_type}

Calendar invitees:
{attendees_text}
{prior_section}

Transcript (line-numbered, with HH:MM:SS timestamps):
{transcript_text}

INSTRUCTIONS:
1. Decide classification: "qualifying" = external-prospect growth consult; "skip" = internal team meeting / interview / vendor call / non-sales. Impromptu Zoom meetings CAN be real consults — judge from transcript content, not title.
2. If skip: fill skip_reason with one specific sentence; leave other fields with reasonable placeholder values.
3. If qualifying: fill ALL fields per the schema.

FORMATTING RULES (critical — the Slack scorecard MUST fit in one message):
- In prose fields, reference moments by HH:MM:SS timestamp ONLY (e.g., "at 00:05:23" or "00:18:00-00:22:34"). Do NOT use [line number] brackets.
- Be aggressively concise. Every character counts. Closer reads this on mobile. The ENTIRE scorecard must fit in ~3400 chars including section headers, so respect the per-field char caps in the schema.
- Cut filler: drop throat-clearing phrases, don't restate the same idea twice, single-sentence bullets preferred over compound sentences.
- Prospect location: infer from EVERY available signal — explicit city/state, company HQ, named markets, timezone mentions, references like "our Tampa office". Only use "Unknown" if truly silent. "Northern VA", "Atlanta metro", or "EST coast" beats blank.
- Follow-up calls: set is_followup=true and write followup_note as "Call #2 with [Name] — follow-up from [date or time]". Score the FULL engagement favorably — do not penalize this call for discovery/pitching that already happened on the first call. A good follow-up after a strong first call deserves a 6-8, not a 3-5.
- Prospect rating: RAW unclamped scores. Python applies the non-DM Character cap at 4 automatically.
- Compliance: two separate short paragraphs — `complied_on` (positives) and `missed` (negatives). Both must cite HH:MM:SS timestamps.
- No emojis anywhere.

Return ONLY the JSON object matching the schema. No prose outside the JSON, no code fences.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
        output_config={"format": {"type": "json_schema", "schema": JSON_SCHEMA}},
    )

    # Extract JSON from response
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Claude returned invalid JSON: {e}\nRaw: {text[:500]}")


# ─────────────────────────────────────────────────────────────────────
# Python-side arithmetic, clamping, rendering
# ─────────────────────────────────────────────────────────────────────

def compute_qa_total(scorecard: dict) -> tuple[int, str]:
    """Return (overall_out_of_10, arithmetic_string)."""
    cats = [
        ("Frame Control", scorecard.get("frame_control")),
        ("Discovery Depth", scorecard.get("discovery_depth")),
        ("Authority & Positioning", scorecard.get("authority_positioning")),
        ("Objection Handling", scorecard.get("objection_handling")),
        ("Close Attempt", scorecard.get("close_attempt")),
    ]
    scored = [(name, v) for name, v in cats if v is not None]
    na = [name for name, v in cats if v is None]
    total = sum(v for _, v in scored)
    max_possible = 2 * len(scored)
    if max_possible == 0:
        return 0, "N/A"
    if na:
        overall = round((total / max_possible) * 10)
        arith = "+".join(str(v) for _, v in scored) + f" = {total}/{max_possible} → {overall}/10 (N/A: {', '.join(na)})"
    else:
        overall = total
        arith = "+".join(str(v) for _, v in scored) + f" = {total}"
    return overall, arith


def apply_non_dm_cap(prospect: dict) -> dict:
    """Clamp Character to ≤4 if not a decision-maker. Returns rating dict with resolved fields."""
    is_dm = prospect.get("is_decision_maker", False)
    character = prospect.get("character_raw", 0)
    if not is_dm:
        character = min(character, 4)
    business = max(0, min(10, prospect.get("business_raw", 0)))
    location = max(0, min(10, prospect.get("location_raw", 0)))
    sales_comp = max(0, min(10, prospect.get("sales_compliance_raw", 0)))
    character = max(0, min(10, character))
    weighted = (character * 0.30) + (business * 0.30) + (location * 0.25) + (sales_comp * 0.15)
    return {
        "is_decision_maker": is_dm,
        "character": character,
        "character_capped": (not is_dm and prospect.get("character_raw", 0) > 4),
        "business": business,
        "location": location,
        "sales_compliance": sales_comp,
        "weighted_raw": weighted,
        "overall": round(weighted),
        "character_note": prospect.get("character_note", ""),
        "business_note": prospect.get("business_note", ""),
        "location_note": prospect.get("location_note", ""),
        "sales_compliance_note": prospect.get("sales_compliance_note", ""),
        "dm_evidence": prospect.get("dm_evidence", ""),
    }


def _safe_len(text: str, limit: int = 38000) -> str:
    """Silent hard cap at Slack's ~40K limit. Should never trigger in normal use."""
    return text if len(text) <= limit else text[:limit].rstrip()


def render_scorecard(data: dict) -> str:
    ctx = data["call_context"]
    sc = data["qa_scorecard"]
    overall, arith = compute_qa_total(sc)

    def fmt_cat(label: str, val: Optional[int]) -> str:
        return f"{label} — {'N/A' if val is None else f'{val}/2'}"

    header_lines = ["SALES QA SCORECARD"]
    if ctx.get("is_followup") and ctx.get("followup_note"):
        header_lines.append(ctx["followup_note"].strip())
    header_lines.append(f"Overall Score: {overall} / 10")

    lines: list[str] = []
    lines.extend(header_lines)
    lines += [
        DIVIDER,
        "CATEGORY BREAKDOWN",
        DIVIDER,
        fmt_cat("Frame Control", sc.get("frame_control")),
        fmt_cat("Discovery Depth", sc.get("discovery_depth")),
        fmt_cat("Authority & Positioning", sc.get("authority_positioning")),
        fmt_cat("Objection Handling", sc.get("objection_handling")),
        fmt_cat("Close Attempt", sc.get("close_attempt")),
        f"Arithmetic: {arith}",
        "",
        sc.get("context_sentence", "").strip(),
        "",
        DIVIDER,
        "CLOSER vs PROSPECT ACCOUNTABILITY",
        DIVIDER,
        f"CLOSER-OWNED ISSUES: {sc.get('closer_issues', '').strip()}",
        f"PROSPECT-DRIVEN FACTORS: {sc.get('prospect_factors', '').strip()}",
        "",
        DIVIDER,
        "WHAT WENT WELL",
        DIVIDER,
    ]
    for item in (sc.get("what_went_well") or []):
        lines.append(item.strip())
    lines += [
        "",
        DIVIDER,
        "AREAS FOR IMPROVEMENT",
        DIVIDER,
    ]
    for item in (sc.get("areas_for_improvement") or []):
        lines.append(item.strip())
    lines += [
        "",
        DIVIDER,
        "SINGLE BIGGEST MISTAKE",
        DIVIDER,
        sc.get("biggest_mistake", "").strip(),
        "",
        f"MISSED BUYING SIGNAL: {sc.get('missed_buying_signal', '').strip()}",
        "",
        DIVIDER,
        "TONE WARNING",
        DIVIDER,
        sc.get("tone_warning", "").strip(),
        "",
        DIVIDER,
        "VERDICT",
        DIVIDER,
        sc.get("verdict", "").strip(),
    ]
    return _safe_len("\n".join(lines))


def render_compliance(data: dict) -> str:
    c = data["compliance"]
    score = int(c.get("score", 0))
    complied = c.get("complied_on", "").strip() or c.get("narrative", "").strip()
    missed = c.get("missed", "").strip()

    lines = [
        f"*COMPLIANCE RATING: {score}/10*",
        "",
        "*What they complied on:*",
        complied,
    ]
    if missed:
        lines += [
            "",
            "*Where they missed:*",
            missed,
        ]
    return _safe_len("\n".join(lines))


def render_prospect_rating(data: dict) -> str:
    p = apply_non_dm_cap(data["prospect_rating"])

    formula = (
        f"Formula: ({p['character']} x 0.30) + ({p['business']} x 0.30) + "
        f"({p['location']} x 0.25) + ({p['sales_compliance']} x 0.15) = "
        f"{p['weighted_raw']:.2f} → {p['overall']}"
    )

    char_note = p["character_note"].strip()
    if p["character_capped"]:
        char_note = f"(Non-DM cap applied) {char_note}" if char_note else "(Non-DM cap applied)"
    dm_ev = p.get("dm_evidence", "").strip()
    if dm_ev:
        char_note = f"{char_note} {dm_ev}".strip()

    lines = [
        f"*PROSPECT RATING: {p['overall']}/10*",
        f"Character: {p['character']}/10",
        f"Business: {p['business']}/10",
        f"Location: {p['location']}/10",
        f"Sales Compliance: {p['sales_compliance']}/10",
        formula,
        "",
        f"*Character ({p['character']}/10):*",
        char_note,
        "",
        f"*Business ({p['business']}/10):*",
        p['business_note'].strip(),
        "",
        f"*Location ({p['location']}/10):*",
        p['location_note'].strip(),
        "",
        f"*Sales Compliance ({p['sales_compliance']}/10):*",
        p['sales_compliance_note'].strip(),
    ]
    return _safe_len("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────

EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def validate_timestamps(data: dict) -> list[str]:
    """Return list of missing-timestamp warnings. Soft validation — log, don't block."""
    problems = []
    sc = data.get("qa_scorecard", {})
    for key in ("closer_issues", "biggest_mistake"):
        val = sc.get(key, "") or ""
        if val.strip() and "None" not in val and not TS_RE.search(val):
            problems.append(f"qa_scorecard.{key} missing HH:MM:SS timestamp")
    for i, item in enumerate(sc.get("what_went_well") or []):
        if not TS_RE.search(item):
            problems.append(f"what_went_well[{i}] missing timestamp")
    for i, item in enumerate(sc.get("areas_for_improvement") or []):
        if not TS_RE.search(item):
            problems.append(f"areas_for_improvement[{i}] missing timestamp")
    return problems


def strip_emoji(s: str) -> str:
    return EMOJI_RE.sub("", s)


# ─────────────────────────────────────────────────────────────────────
# Slack posting
# ─────────────────────────────────────────────────────────────────────

def post_thread(slack: WebClient, thread_ts: str, text: str) -> None:
    text = strip_emoji(text)
    slack.chat_postMessage(channel=CHANNEL_ID, thread_ts=thread_ts, text=text)


def verify_thread_has_feedback(slack: WebClient, thread_ts: str) -> bool:
    replies = slack.conversations_replies(channel=CHANNEL_ID, ts=thread_ts).get("messages", [])
    return any(
        any(marker in (r.get("text", "") or "").upper() for marker in QA_MARKERS)
        for r in replies[1:]
    )


# ─────────────────────────────────────────────────────────────────────
# Process one recording
# ─────────────────────────────────────────────────────────────────────

def process_one(slack: WebClient, system_prompt: str, item: dict) -> None:
    ts = item["message_ts"]
    url = item["share_url"]
    log(f"\n─── Processing {url} (ts={ts})")

    found = fetch_fathom_meeting(url)
    if not found:
        msg = (f"_QA SCORECARD — SKIPPED_\n"
               f"Recording not found in any Fathom account (Mani, Bronson, Krisz). "
               f"Will retry on next cycle.\n\n")
        log(f"  Not found in any Fathom account — posting skip.")
        post_thread(slack, ts, msg)
        return

    meeting, owner = found
    log(f"  Found in {owner}'s account, recording_id={meeting.get('recording_id')}")

    # Hard pre-filter only for clear-cut internal (all_internal domain type).
    # Anything else → let Claude decide from transcript (RULE 10).
    domains_type = meeting.get("calendar_invitees_domains_type")
    if domains_type == "all_internal":
        msg = ("_QA SCORECARD — SKIPPED_\n"
               "Internal team meeting detected (all attendees on roofignite.com). "
               "Only prospect-facing calls are QA'd.\n\n")
        log("  Pre-filter: all_internal — posting skip.")
        post_thread(slack, ts, msg)
        return

    # Try to extract prospect name hint from Slack message text (the "Met with:" line)
    prospect_hint = ""
    met_match = re.search(r"Met with:?\s*([^\n]+)", item.get("text", ""), re.IGNORECASE)
    if met_match:
        prospect_hint = met_match.group(1).strip()
    # Also pull invitee names from Fathom as search fallback (more reliable than Slack "Met with")
    search_names: list[str] = []
    if prospect_hint:
        search_names.append(prospect_hint.split("<")[0].strip())
    for inv in (meeting.get("calendar_invitees") or []):
        if inv.get("is_external") and inv.get("name"):
            search_names.append(inv["name"])

    prior_context = ""
    seen_names = set()
    for name in search_names:
        key = name.lower().strip()
        if not key or key in seen_names:
            continue
        seen_names.add(key)
        ctx = search_prior_scorecards(slack, name, ts)
        if ctx:
            prior_context = ctx
            log(f"  Found prior context via '{name}' ({len(ctx)} chars)")
            break
    if not prior_context:
        log("  No prior calls found for this prospect.")

    log("  Calling Claude...")
    try:
        data = analyze_with_claude(system_prompt, meeting, owner, url, prior_context)
    except Exception as e:
        log(f"  Claude analysis failed (NOT posting to Slack; will retry next cycle): {e}")
        return

    if data.get("classification") == "skip":
        reason = data.get("skip_reason", "Non-qualifying call.")
        msg = (f"_QA SCORECARD — SKIPPED_\n"
               f"{reason}\nQA analysis not applicable.\n\n")
        log(f"  Classified as skip: {reason}")
        post_thread(slack, ts, msg)
        return

    problems = validate_timestamps(data)
    if problems:
        log(f"  WARN: {len(problems)} timestamp issue(s) — {problems[:2]}")

    log("  Posting scorecard...")
    post_thread(slack, ts, render_scorecard(data))
    time.sleep(0.5)
    log("  Posting compliance rating...")
    post_thread(slack, ts, render_compliance(data))
    time.sleep(0.5)
    log("  Posting prospect rating...")
    post_thread(slack, ts, render_prospect_rating(data))

    if verify_thread_has_feedback(slack, ts):
        log("  Verified thread has feedback.")
    else:
        log("  WARNING: verification failed.")


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

def main() -> int:
    if not os.environ.get("SLACK_BOT_TOKEN"):
        sys.exit("SLACK_BOT_TOKEN not set")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")

    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    log("Loading reference prompt docs...")
    system_prompt = load_system_prompt()
    log(f"  System prompt: {len(system_prompt):,} chars (cached per request)")

    try:
        unprocessed = find_unprocessed(slack)
    except SlackApiError as e:
        sys.exit(f"Slack read failed: {e.response.get('error')}")

    if not unprocessed:
        log("No new unprocessed recordings. Exiting.")
        return 0

    log(f"Frozen list: {len(unprocessed)} unprocessed recording(s). Batch processing all.")
    for i, item in enumerate(unprocessed, 1):
        log(f"\n═══ [{i}/{len(unprocessed)}] ═══")
        try:
            process_one(slack, system_prompt, item)
        except Exception as e:
            log(f"  FATAL on {item['share_url']}: {type(e).__name__}: {e}")
            # continue to next recording

    log("\nAll recordings processed. Task complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
