# QA Methodology Deep-Dive — Compliance Rating & Prospect Rating

This document explains, in full detail, how the Compliance Rating and the Prospect Rating are produced. It's written for Claude Code so it can refine prompts, tune rubrics, and lock scoring consistency into the rebuild.

---

## Part 1: The Compliance Rating (single score, 0-10)

### What it measures

The Compliance Rating answers a single question: **did the closer follow the RoofIgnite sales process on this call?** It is entirely closer-focused. It does not consider whether the prospect was a good fit, whether they closed, or whether the outcome was favorable. A closer can run a textbook call and have the prospect decline (that's a 9-10 Compliance). A closer can fumble their way into a close (that's still a 3-4 Compliance).

This is a process-adherence score. Think of it as "did they run the play?"

### The RoofIgnite sales process (the "play")

Every call is expected to follow this sequence:

1. **Frame-setting and recording disclosure** at the open. "I'm going to ask you some questions first to understand your business, then I'll show you what we do, then we'll see if it's a fit." Recording is disclosed either verbally or implicitly via the calendar invite.

2. **Discovery before pitch.** No product pitch until the closer understands:
   - Annual revenue (current)
   - Team size and roles (installers, office staff, other closers)
   - Current lead sources (referrals, Google LSA, door-knocking, existing marketing)
   - Current marketing spend (if any) and ROI
   - Average ticket size
   - Close rate from current leads
   - What's working and what's broken
   - Growth goal (revenue target for next 12 months)
   - Biggest bottleneck (leads, closers, install capacity, cash flow)

3. **Reflection and value tie-in.** After discovery, the closer restates the prospect's situation in the prospect's words, then ties the RoofIgnite solution to those specific pain points. Not "here are our features" but "you said X, here's how we fix X."

4. **Solution walkthrough.** System, ads, appointments, close process, case studies, concrete examples from similar contractors. The closer should use at least one case study that matches the prospect's size or geography when possible.

5. **Buy-in check before pricing.** The closer should get explicit or implicit agreement that the solution makes sense BEFORE dropping pricing. Something like "does this look like what you've been looking for?" or "if the numbers work, is this something you'd want to move forward on?"

6. **Pricing presented with ROI math.** Price is given with expected return, usually framed as cost-per-appointment vs. their current cost-per-lead. Ad spend to appointment conversion should match these benchmarks (20% margin of error acceptable):
   - $100/day ad spend → ~14 appointments/month
   - $150/day ad spend → ~21 appointments/month
   - $200/day ad spend → ~25 appointments/month

7. **Objection handling without panic-dropping price.** If the prospect objects, the closer should reframe value, pull case studies, or trial-close. Dropping price twice in one call without a value reframe is a compliance violation. Dropping price to "close the deal" when the real objection is something else (decision-maker sign-off, timing) is a compliance violation.

8. **Close attempt / concrete next step.** Either:
   - Card collected and onboarding starts
   - Specific next-step call booked on calendar
   - Explicit commitment ("I'll text you by 7:30 with a decision") with a follow-up plan

9. **Post-close expectation-setting.** After the card is collected, the close is NOT done. The closer must:
   - Walk through onboarding timeline
   - Set realistic appointment ramp expectations (first 2-3 weeks vs. steady state)
   - Introduce the delivery team or explain handoff
   - Reiterate case studies to reinforce the decision
   - Make sure the prospect is excited and not about to refund

10. **Pre-onboarding checklist sent and receipt confirmed on the call.** Before the call ends, the closer must send the pre-onboarding checklist to the prospect (text/email) AND verbally confirm with the prospect that it was received. Both halves are required: sending without confirming receipt does not satisfy this step, and confirming receipt of something that wasn't sent on the call does not either. This applies to every closed deal call going forward. If the call did not reach a close (no card / no commitment), this step is N/A. If the call closed and the checklist was not sent + confirmed received during the call, that is a compliance violation.

### Scoring rubric (10-point scale)

```
10/10 — All 10 steps executed cleanly. Rare. Must be called out explicitly in the summary.
9/10  — All 10 steps, with a minor imperfection in one (e.g., post-close expectations were
        brief but present).
8/10  — 9 of 10 steps solid. One step missing or weak. Typical "good call" score.
7/10  — 7-8 steps solid. Notable gap (e.g., shallow discovery OR no post-close expectations OR
        pre-onboarding checklist not sent/confirmed on the call).
6/10  — Mixed. Core elements present but process was disorganized. Pricing timing may have
        been off, or reflection/value tie-in skipped.
5/10  — Major process break (e.g., dropped price twice without reframe, OR went to pitch
        without discovery, OR no concrete next step). Still attempted the play.
4/10  — Multiple process breaks. Closer was reactive rather than leading.
3/10  — Barely ran the process. Pricing before buy-in, no discovery, weak close.
2/10  — Almost no process adherence.
1/10  — Closer was unprepared and the call went sideways.
0/10  — Closer violated process in ways that damage the brand or future sale.
```

### Score adjustments — special cases

**Short follow-up/decline calls (under 3 minutes):** score based on what's applicable. A 2-min decline call where the closer was professional, acknowledged the decision, attempted to re-engage, and documented next steps should score 6-8/10. Do NOT score 2/10 just because there was no full discovery on a short follow-up — discovery wasn't applicable.

**Wrong ad spend benchmarks:** if the closer quotes numbers outside the 20% margin of the benchmarks without explaining why, deduct 1-2 points. Example: "$100/day gets you 25 appointments" is way outside the $100/day → 14 appts benchmark (even +20% only gets you to ~17). This is an expectation-setting violation.

**Discount stacking without reframe:** dropping price more than once in a single call without tying each drop to a reciprocal value exchange (e.g., "I'll drop price if you commit today") is a compliance violation. Deduct 1-2 points. Dropping price when the real objection is decision-maker sign-off (not affordability) deducts 2 points.

**Missing recording disclosure:** deduct 0.5-1 point. Usually covered by the Fathom auto-record, but if the closer never acknowledges it's recorded when asked, that's a process break.

**No post-close expectation-setting after card collection:** deduct 1-2 points. This is a common and under-scored violation. The close is not done when the card is collected. The closer must set onboarding expectations, introduce the delivery team or next step, and reinforce the value to prevent buyer's remorse and refund requests.

**Pre-onboarding checklist not sent + confirmed on the call:** deduct 1-2 points. On every closed deal call, the closer must send the pre-onboarding checklist during the call (text/email) AND verbally confirm with the prospect that it was received. Both halves are required. Missing either side (sent but no receipt confirmation, or claimed-sent without evidence in the transcript) is the violation. N/A if the call did not close.

### What to look for in the transcript (mechanical checklist)

For each call, the LLM should scan the transcript and answer these yes/no questions internally before producing a score:

```
Q1.  Did the closer ask about current revenue?                         [ Y / N ]
Q2.  Did the closer ask about team size?                               [ Y / N ]
Q3.  Did the closer ask about current lead sources?                    [ Y / N ]
Q4.  Did the closer ask about current close rate or ticket size?       [ Y / N ]
Q5.  Did the closer ask about the biggest bottleneck or pain point?    [ Y / N ]
Q6.  Did the closer restate the prospect's situation before pitching?  [ Y / N ]
Q7.  Was the solution tied explicitly to the prospect's pain points?   [ Y / N ]
Q8.  Did the closer get buy-in before revealing pricing?               [ Y / N ]
Q9.  Did the closer present ROI math with pricing?                     [ Y / N ]
Q10. Were ad-spend/appointment numbers within 20% of benchmarks?       [ Y / N ]
Q11. Was there a concrete next step?                                   [ Y / N ]
Q12. If card was collected, were onboarding expectations set?          [ Y / N / N/A ]
Q13. Did the closer drop price more than once without value reframe?   [ Y / N ]  (Y = bad)
Q14. Did the closer handle objections without neediness?               [ Y / N ]
Q15. Was the call professionally run (tone, pacing, framing)?          [ Y / N ]
Q16. If card was collected, did the closer send the pre-onboarding
     checklist to the prospect AND verbally confirm receipt
     during the call?                                                  [ Y / N / N/A ]
```

Baseline: start at 10 points. Deduct for each "N" on Q1-Q12, Q14, Q15. Deduct double for "Y" on Q13. Floor at 0, cap at 10. Round to nearest integer.

Weighting guidance for deductions:
- Q1-Q5 (discovery): -0.5 each if missing
- Q6-Q7 (value tie-in): -1.0 each if missing
- Q8 (buy-in before pricing): -1.5 if missing
- Q9-Q10 (ROI/benchmarks): -1.0 each if missing or wrong
- Q11 (next step): -2.0 if missing (this is critical)
- Q12 (post-close expectations): -1.5 if missing and card was collected
- Q13 (price-drop stacking): -2.0 if Y
- Q14 (tone in objection handling): -1.0 if N
- Q15 (professionalism): -2.0 if N (rare but serious)

This mechanical pass gives a defensible, repeatable score. Combine it with judgment on severity — a discovery that asked every question but stayed at surface level is not the same as a deep discovery, even if both get "Y" on Q1-Q5.

### The output format (what goes in the Slack message)

```
*COMPLIANCE RATING: X/10*

[2-4 sentences explaining: (1) what was compliant, (2) what process breaks occurred with
transcript timestamps, (3) whether ad spend math was within benchmarks, (4) whether
post-close expectations were set. Reference specific moments with [line] and HH:MM:SS.]

_Sent using_ Claude
```

Max 800 characters total. Must cite at least 1-2 transcript timestamps for any deductions.

---

## Part 2: The Prospect Rating (weighted, 0-10)

### What it measures

The Prospect Rating answers: **is this a prospect RoofIgnite wants to work with, and how ready are they to buy?** It is entirely about the prospect. The closer's performance is scored separately (QA Scorecard + Compliance).

This rating feeds directly into the GHL pipeline-stage-updater. Higher ratings get prioritized. Lower ratings get nurtured or disqualified. Getting this scale wrong breaks pipeline automation.

### The formula

```
overall = round(
    character         × 0.30 +
    business          × 0.30 +
    location          × 0.25 +
    sales_compliance  × 0.15
)
```

All 4 inputs are 0-10. The result is rounded to the nearest integer. **Never use a /5 scale for any category. Ever.**

### Category 1: Character (weight 30%)

**What it measures:** trustworthiness, openness, decisiveness, and — critically — whether this person can actually say yes.

**The non-decision-maker cap (MANDATORY):**
If the prospect is not the Owner, CEO, President, Founder, Principal, or Partner with signing authority, their Character score is **CAPPED AT 4/10**. This is non-negotiable and enforced in code (Python clamps the value after the LLM returns it).

Titles that trigger the cap:
- Sales Manager, Sales Director, VP Sales
- Operations Manager, Office Manager
- Marketing Director, Marketing Manager
- Project Manager, Production Manager
- Estimator, Lead Estimator
- Coordinator (any kind)
- Customer Service Manager
- Any title that reports to someone else for discretionary-spend approval

Signals that indicate non-DM status even without a clear title:
- "Let me run this by [name]"
- "I'll need to check with my [partner/CEO/wife who handles finance]"
- "We have to clear the funds"
- "I need to get approval for this spend"
- "My [role] makes the final call on marketing"

If any of these phrases appear, the prospect is a non-DM and Character caps at 4/10.

**Scoring rubric for Character:**

```
10/10 — Owner, radically transparent, decisive, honors commitments, engaged, professional.
        Extremely rare. Use only when the call shows exceptional character.
9/10  — Owner, transparent with real numbers, decisive within the call, good listener,
        professional tone. Strong yes.
8/10  — Owner, shares real numbers, asks good questions, shows up professionally. Normal
        strong prospect.
7/10  — Owner, mostly open, some hedging, ultimately reasonable. Typical good call.
6/10  — Owner, somewhat guarded, slower to commit, professional but not energized.
5/10  — Owner, evasive on numbers, hesitant, wants to "think about it" without concrete
        commitment.
4/10  — Owner who is grinding hard on price, disrespectful, constantly interrupting.
        OR non-DM prospect (cap applies).
3/10  — Non-DM, responsive, professional but can't decide.
2/10  — Non-DM, scattered, unprepared, dragging the process.
1/10  — Non-DM with hostile or unprofessional behavior.
0/10  — Bad actor, clearly a tire-kicker or someone extracting info without intent.
```

**Key signals to pull from transcript:**
- Who makes the final decision on spend? (direct question from closer or volunteered)
- How does the prospect handle numbers? (transparent, vague, evasive)
- How do they respond to pushback? (thoughtful, defensive, dismissive)
- Do they show up on time? Prepared?
- Do they commit cleanly or leave things open-ended?
- Are they respectful to the closer?
- Do they ask questions about the product or about tangential things?
- When they say "I'll get back to you" — is it with a specific time or vague?

### Category 2: Business (weight 30%)

**What it measures:** does this contractor's business align with RoofIgnite's ICP?

**RoofIgnite ICP (primary):**
- Roofing contractor doing **$2.5M+ annual revenue** (minimum bar)
- Sweet spot: **$3M-$10M**
- Has install capacity to handle 20-25+ new appointments per month
- Has at least one dedicated closer (owner-only shops score lower because they can't scale without the bottleneck)
- Healthy margins (can afford marketing investment)
- Growing or stable trajectory (not declining)

**Adjacent ICP (also served):**
- Gutter contractors at similar revenue levels
- HVAC contractors at similar revenue levels
- Windows and doors contractors at similar revenue levels
- These score similarly if revenue is in the $2.5M+ range

**Scoring rubric for Business:**

```
10/10 — $10M+ roofing/adjacent, strong margins, scalable ops, multiple closers, growing
        fast. Elite prospect.
9/10  — $5M-$10M, solid team, good margins, clear growth, sales process in place.
8/10  — $3M-$5M, growing, has a closer or two, decent margins. Solid ICP fit.
7/10  — $2.5M-$3M, hitting minimum, some momentum, owner-led sales but willing to scale.
6/10  — $2M-$2.5M, just below ICP, strong potential but currently sub-scale.
5/10  — $1.5M-$2M, below ICP, would need major infrastructure work before RoofIgnite
        can deliver value.
4/10  — $1M-$1.5M, too small, can't absorb appointment volume.
3/10  — $500k-$1M, owner-operator with no team.
2/10  — Under $500k, solo operator, not a real business yet.
1/10  — Not actively operating, just starting, or between jobs.
0/10  — Not actually in roofing/adjacent trades. Wrong vertical entirely.
```

**Key signals to pull from transcript:**
- Annual revenue (direct answer, or estimated from team size × 250k/year per installer as a rough heuristic)
- Team size breakdown (installers, reps, office staff, other closers)
- Average ticket size ($8k retail average, $15-25k insurance, varies by market)
- Close rate on current leads (industry norms: 25-40% on referrals, 15-25% on cold marketing)
- Current marketing spend and what it returns
- Years in business (new businesses = higher risk even if revenue is good)
- Number of locations / service area
- Growth trajectory (revenue trend over last 2-3 years)
- Profit margin discussion (healthy roofers run 15-30% gross margin; anything much lower indicates problems)
- Whether they have a sales process or just winging it

**Specialty weighting:** if the prospect is in gutters/HVAC/windows at strong revenue, score the same as roofing at that revenue. Do NOT deduct for non-roofing verticals within the adjacent list.

**Red flags that override revenue:**
- Declining revenue trajectory: cap at 6/10 regardless of current size
- Bad reputation (mentions of lawsuits, bankruptcy history, BBB issues): cap at 5/10
- Chaotic ops (can't describe their own process): cap at 6/10
- "I just want leads, I'll figure out the rest": cap at 6/10 — they'll churn

### Category 3: Location (weight 25%)

**What it measures:** is this prospect in a market where RoofIgnite's appointment-generation system performs well? Some markets have high storm activity, dense population, insurance-driven work, and high ticket sizes. Others are seasonal, low-density, or have structural issues.

**Tier system:**

```
Tier 1 (9-10): Florida, Texas, California, Georgia
   High storm activity (hurricanes, hail), high population, high insurance claim rates,
   strong ticket sizes. These markets print money when the system is running.

Tier 2 (7-8): Carolinas (NC/SC), Tennessee, Oklahoma, Kansas, Missouri, Colorado,
              Nebraska, Alabama, Louisiana, Mississippi, Arkansas
   Good storm activity (hail belt, tornado alley), decent density, insurance-driven
   work. Strong markets.

Tier 3 (5-7): Virginia, Pennsylvania, Ohio, Indiana, Michigan, Illinois, Wisconsin,
              Minnesota, Iowa, Arizona, Nevada, Utah, Idaho, New Mexico
   Mixed storm activity, moderate density, competitive. Appointments cost more.

Tier 4 (3-5): Massachusetts, Connecticut, New York, New Jersey, Maryland, Delaware,
              West Virginia, Kentucky, Oregon, Washington
   Lower storm activity, higher competition, stricter regulations, higher ad costs.
   Still workable but needs a disciplined operator.

Tier 5 (1-3): Vermont, New Hampshire, Maine, Montana, Wyoming, North Dakota,
              South Dakota, Alaska, rural/low-density regions generally
   Very limited market size, seasonal, low-density. System doesn't scale well here.

Canada: typically 4-6 depending on province and city. Toronto/Calgary/Vancouver rate
   higher. Smaller Canadian cities rate lower due to limited market size and different
   insurance dynamics.
```

**Factors to check:**
- Storm activity (hail, hurricanes, high winds)
- Population density in their service area
- Competition level (how many roofers per 100k population)
- Insurance vs. retail mix (insurance work is typically higher ticket)
- Seasonality (markets with 6-month peak seasons score lower than year-round)
- State regulations (licensing, contractor laws that slow down work)
- Ticket-size norms in the market ($6k market vs. $12k market matters)

**Scoring examples:**
- Houston, TX: 10/10 — top-tier market, huge population, constant storm activity
- Miami, FL: 10/10 — hurricane exposure, high ticket sizes, dense market
- Atlanta, GA: 9/10 — hail activity, growing market, strong density
- Charlotte, NC: 8/10 — hail belt, growing region
- Columbus, OH: 7/10 — decent hail, competitive
- Northern Virginia: 6/10 — moderate storm, competitive DMV market
- Upstate New York: 4/10 — seasonal, competitive
- Rural Montana: 2/10 — too sparse
- Toronto, Ontario: 6/10 — decent urban market, different insurance dynamics
- Rural Saskatchewan: 3/10 — limited population

### Category 4: Sales Compliance (weight 15%)

**What it measures:** did the prospect prepare for the call and show up ready to do business?

This is NOT the same as closer Compliance. This is prospect-side preparation and engagement.

**Signals to check:**
- Did they watch the prep videos sent before the call? (closers often ask or it becomes obvious)
- Did they arrive on time?
- Is the decision-maker on the call, or only a proxy?
- Are they engaged (asking questions, taking notes, reacting to content)?
- Did they bring their numbers (revenue, spend, close rate) or do they have to guess?
- Are they respectful of the process or trying to jump to pricing first?
- Were they responsive in the lead-up (booking confirmations, prep completion)?
- Did they allow enough time on the call (full 60-90 min block, or are they rushing)?

**Scoring rubric:**

```
10/10 — Watched all prep, on time, DM on call, brought numbers, fully engaged,
        respectful of process, allocated full time block. Dream prospect behavior.
9/10  — Watched prep, on time, DM present, engaged throughout, prepared with data.
8/10  — Mostly prepared, on time, DM present, good engagement.
7/10  — Some prep skipped but showed up ready to engage. Typical compliant prospect.
6/10  — Skipped prep but engaged in real-time. Workable.
5/10  — Showed up without prep, had to learn on the call, somewhat distracted.
4/10  — Late start, no prep, some distraction (phone calls, kids, other tabs).
3/10  — Late, no prep, DM not on call, had to reschedule once already.
2/10  — Rescheduled multiple times, barely present, clearly not prioritizing.
1/10  — Didn't actually want the call, showed up reluctantly, poor engagement.
0/10  — No-show at the actual call (won't usually generate a transcript, but if a
        partial call happened and they bailed early, this is 0).
```

### Weighted formula in action (worked examples)

**Example 1: A-tier prospect**
- Character: 9 (owner, decisive, transparent)
- Business: 8 ($4M roofing, growing)
- Location: 9 (Atlanta, GA)
- Sales Compliance: 9 (watched prep, DM on call, engaged)

Formula: (9 × 0.30) + (8 × 0.30) + (9 × 0.25) + (9 × 0.15)
       = 2.70 + 2.40 + 2.25 + 1.35
       = 8.70
       → **9/10**

**Example 2: Non-DM on call**
- Character: 4 (Sales Manager, cap applied — would have been 7 without cap)
- Business: 8 ($5M roofing)
- Location: 8 (Charlotte, NC)
- Sales Compliance: 7 (decent prep, engaged, but not DM)

Formula: (4 × 0.30) + (8 × 0.30) + (8 × 0.25) + (7 × 0.15)
       = 1.20 + 2.40 + 2.00 + 1.05
       = 6.65
       → **7/10**

Note: even with a strong business and location, the non-DM cap pulls the overall down meaningfully. This is by design — a non-DM call can't close.

**Example 3: Below ICP**
- Character: 7 (Owner, open, decent)
- Business: 4 ($1.2M, too small)
- Location: 7 (Oklahoma, Tier 2)
- Sales Compliance: 6 (some prep, some not)

Formula: (7 × 0.30) + (4 × 0.30) + (7 × 0.25) + (6 × 0.15)
       = 2.10 + 1.20 + 1.75 + 0.90
       = 5.95
       → **6/10**

Nurture candidate — right person, wrong size today.

### The output format (what goes in the Slack message)

```
*PROSPECT RATING: X/10*

*Character:* X/10
*Business:* X/10
*Location:* X/10
*Sales Compliance:* X/10

Formula: (X × 0.30) + (X × 0.30) + (X × 0.25) + (X × 0.15) = X.XX → *X*

*Character (X/10):* [1-2 sentences. Cite DM status. Reference transcript moments.]

*Business (X/10):* [1-2 sentences. Revenue, team, fit with ICP. Reference specific data from call.]

*Location (X/10):* [1-2 sentences. Tier + market context.]

*Sales Compliance (X/10):* [1-2 sentences. Prep, engagement, punctuality.]

*GHL: [Brief CRM-relevant note about contact details or offer status.]*

[1-2 sentence final assessment. What would change the rating? If follow-up, note context.]

_Sent using_ Claude
```

Max 2500 characters total.

---

## Part 3: How the two ratings interact (and how they DON'T)

### Separation of concerns

**Closer performance** (QA Scorecard + Compliance Rating) = about the closer.
**Prospect quality** (Prospect Rating) = about the prospect.

A closer can score 10/10 Compliance on a 3/10 prospect. A closer can score 2/10 Compliance on an 9/10 prospect. These are independent axes.

**Do not cross-contaminate.** If the prospect is a non-DM and the call didn't close, that is NOT the closer's fault and should not appear in the Compliance deduction list. The Prospect Rating captures it (via the Character cap). The closer's Compliance should only reflect whether they ran the process correctly given the prospect they had.

### Where they do interact

Only in the QA Scorecard's "CLOSER vs PROSPECT ACCOUNTABILITY" section. That section explicitly separates:
- CLOSER-OWNED ISSUES (things the closer did wrong)
- PROSPECT-DRIVEN FACTORS (things outside closer's control: non-DM, bad fit, wrong market, etc.)

This is the guardrail that prevents the closer from being penalized for prospect-quality problems.

---

## Part 4: Prompt engineering recommendations for Claude Code

When refining the LLM prompt for these two ratings, enforce these rules:

### Structural rules (hard constraints)

1. Force JSON output via tool_use with strict schema. No free-text scoring.
2. Clamp values in Python after the LLM returns. Non-DM → Character capped at 4. Individual category max 10. QA category max 2.
3. Compute the weighted formula in Python, not in the LLM. Never let the LLM do the arithmetic.
4. Compute the QA overall sum in Python, not in the LLM. Same reason.
5. Validate that every `*_note` string contains at least one timestamp pattern (`\b\d{2}:\d{2}:\d{2}\b`) before allowing the message to post. If it doesn't, re-prompt the LLM once with a correction instruction.

### Rubric-enforcement rules (soft but important)

6. Include the exact rubrics from this document in the system prompt. Don't paraphrase. The model should have the 10/9/8/7 definitions in front of it.
7. For Compliance, make the model produce the Q1-Q15 checklist internally (as a private reasoning step) before committing to a score. You can either (a) expose this via extended thinking, or (b) ask for it as an internal `_scratchpad` field in the JSON that gets dropped before templating.
8. Give the model 3-5 few-shot examples of past calls with their correct scores, especially edge cases (non-DM, short follow-up, very high/very low scores).
9. When the model produces a score of 9 or 10 on ANY category, require it to justify specifically why this is rare-tier. A threshold check: if overall QA ≥ 9 or overall Prospect ≥ 9, the note fields must contain explicit "exceptional because X" language.

### Guardrail rules (prevent drift)

10. Reject any LLM output where category names have been renamed or reordered. Parser should fail-fast and re-prompt.
11. Reject any output using a /5 scale (check for "/5" in rendered Slack messages before posting).
12. Reject any output with emoji. Strip and re-validate, or re-prompt.
13. Reject any output where the arithmetic shown doesn't match the category scores (catches hallucination).

### Few-shot examples Claude Code should include in the prompt

**Example A — A-tier owner call:**
Transcript summary: Texas roofer, $4M revenue, owner on call, watched prep, committed on call with card collected, onboarding walked through.
Expected Compliance: 9/10
Expected Prospect: Character 9, Business 8, Location 10, Sales Compliance 9 → overall 9
Why: all 9 steps of process executed, DM present and decisive, strong market, strong business.

**Example B — Non-DM grinding on price:**
Transcript summary: Sales Manager at $6M roofer in Ohio, didn't watch prep, pushed back hard on pricing, needed to "check with the CEO" multiple times, no close.
Expected Compliance: 7/10 (closer ran process but dropped price once, legit deduction)
Expected Prospect: Character 4 (cap), Business 8, Location 7, Sales Compliance 5 → overall 6
Why: closer did their part; prospect is non-DM which limits close probability regardless.

**Example C — Short decline follow-up:**
Transcript summary: 2-min call. Prospect from previous week says "we're going to pass for now." Closer thanks them, asks what changed, leaves door open professionally.
Expected Compliance: 7/10 (short call, limited scope, closer handled professionally)
Expected Prospect: Character 6, Business 7, Location 7, Sales Compliance 5 → overall 6
Why: discovery N/A on a decline call, closer scored on what was observable.

**Example D — Below ICP:**
Transcript summary: $1M solo operator in rural Montana, eager to work together but doesn't have the revenue or market to support the spend.
Expected Compliance: 8/10 (closer ran process, tried to qualify out gracefully)
Expected Prospect: Character 7, Business 3, Location 2, Sales Compliance 6 → overall 4
Why: good person, wrong time. Nurture candidate.

**Example E — Internal team meeting (skip):**
Transcript shows Mani + Bronson + Krisz doing a team huddle. No external prospect.
Expected classification: `internal_meeting`
Expected action: skip, post the "Internal team meeting detected" reply, no QA/Compliance/Prospect scoring.

---

## Part 5: Quick reference card (print this out)

```
QA SCORECARD       — 5 categories × /2 each = /10 total (sum, then normalize if N/A)
                     Categories: Frame Control, Discovery Depth, Authority & Positioning,
                                 Objection Handling, Close Attempt

COMPLIANCE RATING  — Single score /10. Process adherence only. Closer-focused.
                     Baseline 10, deduct per Q1-Q15 checklist. Round to integer.

PROSPECT RATING    — 4 categories × /10 each.
                     Character 30%, Business 30%, Location 25%, Sales Compliance 15%
                     Non-DM cap: Character max 4/10.
                     Formula: (C×0.30) + (B×0.30) + (L×0.25) + (SC×0.15)
                     Compute in Python, not the LLM.
```

---

## Handoff note for Claude Code

This document is the source of truth for how Compliance and Prospect Ratings should be computed. When building the `llm_analyzer.py` module and the system prompt:

1. Embed the full rubrics (not summaries) in the system prompt.
2. Enforce JSON schema via tool_use.
3. Clamp values in Python after receiving the LLM output.
4. Compute all arithmetic in Python.
5. Include 3-5 few-shot examples with correct scoring.
6. Validate timestamp citations before posting.
7. Reject and re-prompt on any format drift.

If something in this document contradicts the original SKILL.md, this document wins — it's the refined, consolidated version.
