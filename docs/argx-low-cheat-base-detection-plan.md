# Plan: Identify Low-Cheat (and Cup) Bases Correctly (e.g. ARGX)

## Problem

For symbol **ARGX**, a pivot is identified and the user considers the stock to have formed a **low-cheat base since 12/3/25**, with the pivot consistent with a low-cheat setup. The current SEPA base detection **does not** list this base. This plan outlines why it may be missed and what to change so such bases are recognized.

## How Base Detection Works Today

1. **Weekly pivot highs**  
   Bases are built **only** from **pivot highs** on the weekly series. A pivot high is a week whose high is the maximum over a 5-week window (2 weeks left, 2 weeks right): `_pivot_highs_lows()` in [turtle_rpm/sepa.py](turtle_rpm/sepa.py).

2. **Candidate base**  
   For each pivot high at index `hi_idx`, a candidate base is the segment from that week until the **next** pivot high (or the last week). So the “start” of the base is always a week that is a **confirmed** pivot high.

3. **Filters**  
   - **Uptrend at base start:** `uptrend_at_date(df_daily, start_ts)` must pass (50 > 150 > 200, 200d rising over 21 days, all SMAs rising vs 5 days ago).  
   - **Duration and shape:** `_classify_base()` returns a type (e.g. Low cheat, Cup completion) or `None`.  
   - Low cheat: 6–52 weeks, no handle, and `latest_close` in the lower third of the cup range.

4. **Low cheat vs Cup completion**  
   Same duration/shape rules; Low cheat is when price is in the **lower third** of the base range (`in_lower_third`); otherwise Cup completion cheat.

## Why ARGX’s Base May Not Be Recognized

### 1. No pivot high at the “expected” peak (most likely)

The base is assumed to start at the **week of the high** (e.g. around 12/3/25). That week is only used as a base start if it is a **pivot high**: its weekly high must be ≥ the high of the two weeks before **and** the two weeks after.

- If the week after the peak has a **higher** weekly high (e.g. a brief spike or gap), the peak week is **not** a pivot high, so no base starts there.
- The next pivot high might be 1–3 weeks later, so the “base” would start later and have shorter duration (e.g. 4–5 weeks), possibly failing the 6-week minimum for Cup/Low cheat, or being classified as Darvas/Power Play or nothing.
- Alternatively, the only pivot high in the recent window might be **earlier** (e.g. months ago), so the current base would be that long base, which might fail uptrend or classification, or be deduplicated.

**Conclusion:** Strict 2-weeks-each-side pivot logic can **miss the actual left rim** of the cup when the top is choppy or has a quick higher weekly high soon after.

### 2. Uptrend filter at base start

`uptrend_at_date(df_daily, start_ts)` is evaluated at the **exact** base start week (the pivot high week). If by that date the stock has already broken structure (e.g. 50d below 150d, or 200d not “rising” over the last 21 days), the candidate base is **dropped** even if the base shape and duration would classify as Low cheat.

So a correct base start and correct classification can still be discarded because of strict uptrend at that single date.

### 3. Duration too short for Cup/Low cheat

If the only valid pivot high is 3–5 weeks ago, duration is 3–5. Cup completion and Low cheat require **6–52 weeks**. Then:

- 2–6 weeks with 90% prior run-up → Power Play (might not apply).
- 4–6 weeks with tight depth → Darvas (might not apply if depth > 25%).
- Otherwise → no type (`base_type` is `None`), and the base is not reported.

So a “forming” low-cheat base that is only 5 weeks old is currently not classified as Low cheat.

### 4. Two pivot lows and “handle” heuristic

Low cheat and Cup completion require **no handle** (`not has_handle`). Handle is set when there are ≥2 pivot lows and the second low is above the midpoint of the range and above the first low. If the weekly series has two such lows in the pullback, the base is classified as Cup w/ handle (if duration 7–65) and never as Low cheat. So a base that is conceptually a “low cheat” (price in lower third, one broad trough) could be reported as Cup w/ handle or another type, or filtered later.

---

## Proposed Changes (in order of impact)

### 1. Pivot-from-high alternatives (catch “left rim” when strict pivot misses)

**Goal:** Don’t rely solely on the strict 2-week pivot high for the start of the base. Allow bases that start at a “trailing” or “last significant” high when that better matches the visual cup.

**Options (pick one or combine):**

- **A. Trailing high as base start**  
  For the **current** (ongoing) base only: besides pivot highs, consider **trailing N-week high** as a possible base start. For example, over the last 8–12 weeks, find the week with the highest high; if that week is not already a pivot high, still build one candidate base from that week to the last week. Then run the same depth/duration/classification and uptrend logic. This creates an extra candidate that can be classified as Low cheat/Cup completion even when the exact peak week was not a 2-sided pivot.

- **B. Relax pivot high for last bar**  
  For the **last** 1–2 weeks of the series, use a **1-week** lookback/lookahead (or lookback-only) so that the most recent peak can qualify as a pivot high sooner. That way a base starting at that peak is considered without waiting for two future weeks.

- **C. Pivot-driven candidate when daily pivot is forming**  
  When the **daily** pivot is forming and we have a pivot date range, find the **last significant high** (e.g. 8– or 10-week high) on the weekly series that occurs **before** the pivot window. Build one candidate base from that week to the last week. Classify it and, if it matches Cup/Low cheat and overlaps the pivot, include it (or merge with existing logic). This aligns base start with “where the cup started” using the pivot as context.

**Recommendation:** Implement **A** (trailing high candidate for current base) first; optionally add **C** so that when we already show “Pivot forming” and “In base: No”, we try this pivot-anchored candidate and re-evaluate “In base”.

### 2. Relax uptrend at base start for the current base

**Goal:** Avoid discarding a valid Low cheat/Cup base because uptrend fails on the single week of the pivot high (e.g. after a sharp pullback).

**Options:**

- Evaluate uptrend at **1–2 weeks before** base start (still in the run-up), or  
- For bases that end on the **last week** (current base), allow a **slightly relaxed** uptrend rule: e.g. 50 > 150 > 200 and 200d rising, but do not require all three SMAs to be rising vs 5 days ago at base start.  
- Or: require uptrend at **either** base start **or** at the week of the base low (or at the start of the pivot window).

**Recommendation:** Add an option (e.g. `relax_uptrend_for_current_base`) that, for the candidate whose `end_date` is the last week, also accepts uptrend at `start_ts - 1 week` if uptrend at `start_ts` fails. Document the behavior and keep it behind a flag so it can be tuned.

### 3. Allow Cup / Low cheat for “forming” bases (e.g. 5 weeks)

**Goal:** Don’t miss a Low cheat that is only 5 weeks old because the minimum is 6.

**Change:** For bases that are **current** (segment ends on the last week), allow Cup completion cheat and Low cheat when **duration_weeks >= 5** (instead of 6). Optionally cap the “forming” case at a max duration (e.g. 12 weeks) so we don’t over-label very long consolidations. Keep the existing 6–52 rule for **completed** (non-current) bases.

**File:** [turtle_rpm/sepa.py](turtle_rpm/sepa.py) – `_classify_base()` and/or the caller that passes `duration_weeks`; may need to pass a flag like `is_current_base` so classification can use 5–52 for current and 6–52 for completed.

### 4. Diagnostics (optional but recommended)

**Goal:** Understand exactly why ARGX (or any symbol) has no base in the list.

**Implementation:**

- Add an optional **debug/diagnostic** mode (e.g. `find_bases(..., debug=True)` or a separate script) that:
  - Prints weekly pivot high and pivot low indices and dates.
  - For each candidate base (from each pivot high, and from any new “trailing high” or “pivot-anchored” candidate):
    - Prints start_ts, end_ts, duration_weeks, depth_pct, base_low, latest_close, in_lower_third, has_handle, two_lows.
    - Prints whether uptrend_at_date passed and why not if it failed.
    - Prints the result of _classify_base (base_type or None).
  - This will show whether the failure is: no pivot high at the right week, uptrend filter, duration, or classification.

**Recommendation:** Implement a small diagnostic path (e.g. in a `scripts/diagnose_bases.py` or via a query param on the SEPA page) that outputs the above for a given symbol, so future “base not recognized” cases can be debugged quickly.

---

## Implementation order

| Step | Task |
|------|------|
| 1 | Add diagnostics (script or debug flag) to log pivot highs/lows and per-candidate uptrend/classification so we can confirm the cause for ARGX. |
| 2 | Implement trailing-high candidate for current base: from the last 8–12 weeks, take the week with the highest high; if it is not already a pivot high, build one candidate base from that week to the last week; run existing classification and uptrend; deduplicate by start_date with existing candidates. |
| 3 | Optionally relax uptrend for current base (e.g. allow uptrend at start_ts - 1 week when base is current). |
| 4 | Allow Cup/Low cheat for current base when duration_weeks >= 5 (and &lt;= 52). |
| 5 | Optionally add pivot-anchored candidate when daily pivot is forming and “In base” is currently No: use last significant high before pivot window as base start. |

---

## Files to touch

- **[turtle_rpm/sepa.py](turtle_rpm/sepa.py):**  
  - `_pivot_highs_lows`: optionally add 1-week pivot for last 1–2 bars (if doing B).  
  - `find_bases`: add trailing-high candidate for current base; optional `relax_uptrend_for_current_base` and `is_current_base` for classification; pass `is_current` into classification for 5-week Cup/Low cheat.  
  - `_classify_base`: add parameter or logic for “current base” and use 5–52 weeks for Cup completion / Low cheat when current.  
- **New script (e.g. [scripts/diagnose_bases.py](scripts/diagnose_bases.py)):** Load symbol, run find_bases with debug output (pivot highs/lows, per-candidate stats, uptrend result, base_type).  
- **[pages/1_specific_entry_point_analysis.py](pages/1_specific_entry_point_analysis.py):** If implementing pivot-anchored candidate, ensure the “In base” logic uses the new candidate (no change if trailing-high alone fixes ARGX).

---

## Success criteria

- For **ARGX** (and similar symbols), when a low-cheat-style base has formed since a clear peak (e.g. around 12/3/25) and the daily pivot is present:
  - At least one base is listed.
  - That base is classified as **Low cheat** (or Cup completion cheat when price is not in the lower third).
  - “In base” shows **Yes** with that base type when the pivot is forming inside it.
- No regression: existing symbols that already show bases (e.g. Cup w/ handle, Darvas) still show the same or a consistent base.
- Diagnostics make it clear why a base was or wasn’t found for any given symbol.
