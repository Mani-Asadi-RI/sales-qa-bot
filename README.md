# Sales QA Bot

Python port of the Sales QA Cowork prompt. Runs every 30 minutes via GitHub Actions. Scans `#closer-feedback-channel` for `fathom.video/share/...` links posted without a QA reply, pulls each recording's transcript, scores the call, and posts three thread replies: a Scorecard, a Compliance Rating, and a Prospect Rating.

## Flow

1. Pull the last N messages from `#closer-feedback-channel`.
2. Build a frozen list of messages that contain a `fathom.video` share link and have no existing QA reply (scorecard / compliance / prospect).
3. For each unprocessed message:
   - Resolve the recording via the Fathom API (rotates through 3 keys — Mani / Bronson / Krisz).
   - If the call is an internal Roofignite meeting, post a `SKIPPED` reply and move on.
   - Search Slack for prior calls with the same prospect so Claude has multi-call context (handles closers doing a second/third call with the same lead).
   - Ask Claude for a single JSON response covering scorecard items, compliance flags, and prospect signals. The bot then clamps values (non-DM Character cap, etc.), computes arithmetic, and renders three plaintext Slack messages.
   - Post each message as a thread reply and verify the post landed.

## Reference prompts

The scoring logic lives in three Markdown files checked into the repo — the bot loads them at startup and includes them in every Claude call. These are the source of truth for how calls are scored:

- `Sales-QA-Bot-FULL-COMBINED-Prompt.md` — primary prompt (combined system + scoring rubric)
- `qa-rating-methodology-deep-dive.md` — compliance + prospect methodology
- `qa-scorecard-methodology-mani-style.md` — Mani's 53-call patterns + signature phrases

Edit these to change scoring behavior; no code change needed.

## Schedule

`.github/workflows/qa-bot.yml` runs `*/30 * * * *` (every 30 minutes). GitHub cron granularity means the real fire time can lag 5–15 min during peak, so expect scorecards to land within ~45 min of a fathom link being posted.

Concurrency group `sales-qa-bot` with `cancel-in-progress: false` — long runs won't get killed by the next tick.

## Env vars

| Var | Purpose |
|---|---|
| `SLACK_BOT_TOKEN` | `xoxb-...` — channel read + thread reply |
| `ANTHROPIC_API_KEY` | `sk-ant-...` — scoring |
| `FATHOM_API_KEY_MANI` | Fathom API key for Mani's recordings |
| `FATHOM_API_KEY_BRONSON` | Fathom API key for Bronson's recordings |
| `FATHOM_API_KEY_KRISZ` | Fathom API key for Krisz's recordings |

All are wired through GitHub Secrets in the workflow. Rotate Fathom keys in the Fathom dashboard and update the corresponding GitHub Secret; do not paste keys into source.

## Running locally

```bash
pip install -r requirements.txt
export SLACK_BOT_TOKEN=xoxb-...
export ANTHROPIC_API_KEY=sk-ant-...
export FATHOM_API_KEY_MANI=...
export FATHOM_API_KEY_BRONSON=...
export FATHOM_API_KEY_KRISZ=...
python sales_qa_bot.py
```

The run is idempotent: if a fathom link already has a QA scorecard reply in the thread, the bot skips it. Safe to re-run.

## Key files

- `sales_qa_bot.py` — single-file entrypoint (~820 lines)
- `requirements.txt` — `anthropic`, `slack_sdk`, `requests`
- `.github/workflows/qa-bot.yml` — GitHub Actions schedule + env

## Dedup + idempotency

The bot treats a fathom link as "already processed" if any reply in its thread contains one of: `QA SCORECARD`, `COMPLIANCE RATING`, `PROSPECT RATING`, `SKIPPED`. That means hand-editing a QA reply won't cause a re-post; manual `SKIPPED` is honored.

## Gotchas

- Fathom API occasionally returns 429 / 5xx; the bot rotates through keys before giving up on a link. Check logs for `fathom {owner}: HTTP ...` messages if scorecards aren't landing.
- Multi-call context: if Claude scores the wrong call of a series, check whether the Slack search for prior calls returned the correct prior threads.
- Messages over ~3,400 chars get split by Slack. The bot pre-splits so formatting stays intact.
