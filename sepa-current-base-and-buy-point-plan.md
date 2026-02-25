# SEPA: Current Base Focus and Buy Point (Backward-Looking)

## Goal

1. **Emphasize the current base** – The base we are still within (still at or before a valid buy point). Past bases are secondary.
2. **Buy point for each base** – For every base (current and past), show when the **buy point** would have been identified by our logic **looking backwards only** (no future data). For past bases this is the historical “when would we have gotten the entry signal?” For the current base it tells us whether we’re before the buy point or at it.
3. **Table** – Extend the SEPA bases table with: current vs past, and buy-point date (and optionally buy-point price / resistance level).

---

## Definitions (to refine in this doc)

### Current base

- **Candidate**: The most recent base in our list (the one whose *end* of base is the last week in the dataset, or the only base that has no “next” pivot high after it).
- **“Still in”**: We consider ourselves “still in” this base if either:
  - Price has **not yet** closed above the base’s buy-point resistance (so the buy point has not been triggered), or
  - The buy point was triggered recently and we’re still “within” a reasonable hold window (optional; can be out of scope for v1).
- **Simpler v1**: “Current base” = the single base that ends on the last week of data (i.e. the most recent base). All others are “past bases.” No need to check “has breakout happened yet” for labeling—we still compute and show the buy point date for every base.

*Your edit: clarify how you want “current” defined (e.g. only one current base, or “we are still within buy zone” with a rule).*

### Past base

- Any base that is **not** the current base. For these we are only interested in: “When would the buy point have been identified looking backwards?”

### Buy point (backward-looking)

- **Resistance level** depends on base type:
  - **Cup w/ handle**: Handle high (the high of the handle before breakout), or right rim of cup—first close above that.
  - **Double bottom**: Neckline = intermediate high between the two lows—first close above neckline.
  - **Darvas box**: Box high (resistance of the consolidation)—first close above box high.
  - **Cup completion cheat / Low cheat**: Left rim of cup = prior_high (start of base). First close above prior_high.
  - **Power Play**: Consolidation high (high of the 2–6 week base)—first close above that high.
- **Buy point date**: The **first week** (or first day, if we use daily data for precision) where **close ≥ resistance** using only data available at that time (no look-ahead). If we work on weekly bars: first week where weekly close > resistance. Optionally we can refine to “first *day*” by scanning daily bars after that week.
- **Not yet triggered**: If from base start through end of data we never had close ≥ resistance, then “Buy point date” = *Not yet* (or blank / “—” for current base, and for past bases this would mean that base never triggered a buy in our lookback).

*Your edit: confirm resistance rules per base type and whether buy point is weekly vs daily.*

---

## Table changes

Current columns: **Base type**, **Start date**, **Depth (%)**, **Duration (weeks)**.

Proposed new columns:

| Column            | Meaning |
|-------------------|--------|
| **Current?**      | Yes = this is the current (most recent) base; No = past base. |
| **Buy point date**| For past bases: the first date (week or day) when close exceeded the base’s resistance (backward-looking). For current base: same if already triggered; otherwise “Not yet” or “—”. |
| **Buy point price** (optional) | The resistance level we used. Helps users see “breakout above X.” |

Ordering: list **current base first** (if any), then past bases (e.g. by start date descending). Or: past bases first by start date, then current base at top—*your preference*.

*Your edit: add/remove columns, rename, or change order.*

---

## Implementation outline (after you approve the plan)

1. **Resistance level** – In `find_bases` (or a helper), for each detected base compute the **resistance** used for buy point:
   - Cup w/ handle: handle high (or right cup rim from weekly segment).
   - Double bottom: max high between the two lows (neckline).
   - Darvas: high of the base range (already have prior_high as start; box high = prior_high or max High in segment).
   - Cup completion / Low cheat: prior_high.
   - Power Play: prior_high (or max High in the 2–6 week segment).
2. **Buy point date** – For each base, walk forward from base start through end of base (and optionally a few weeks after) using **weekly** close (or daily if we add daily scan): first bar where close ≥ resistance. That date is “buy point date.” If none, return null → display “Not yet” or “—”.
3. **Current base** – Mark the base that ends on the last week of data as “current”; all others “past.”
4. **Table** – Add columns “Current?”, “Buy point date”, and optionally “Buy point price”. Sort so current base is prominent (e.g. first row).

No UI or logic changes beyond the bases table and the data produced by `find_bases` (or a small post-pass).

---

## Open choices (for you to edit)

- **Current base**: One per symbol (the latest base) or allow multiple “current” if we define “still in buy zone” differently?
- **Buy point granularity**: Weekly (first week close above resistance) vs daily (first day close above resistance)?
- **Resistance per type**: Any changes to the rules above (e.g. handle high for cup w/ handle, neckline for double bottom)?
- **Table**: Keep “Duration (weeks)” and “End date” or drop one? Add “Buy point price” or keep only “Buy point date”?

Once you’ve edited this plan, we can implement accordingly.
