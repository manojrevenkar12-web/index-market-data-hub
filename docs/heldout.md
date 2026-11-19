# The held-out market

Run once on 19 November 2026 (`config/heldout.lock`), after the hub passed the gate on the development market.
Seed 50331, 1 April to 26 June 2026, 180 instruments, 4 indices with 86 distinct constituents. Compared with development:
1.6 times every vendor fault rate, a stormier market (market volatility 1.3% a day instead of 0.9%), 8 splits and
8 renames on constituents (4 with a reused ticker), and Meridian as well as Kestrel sometimes labelling pence as
pounds. 13 vendor-days arrived after the close.

## What the hub got wrong

Nothing that reached a close. 0 of 252 index closes off the true level by more than 1 bp, 0 of 58 corporate actions
missed or misapplied, 12 desk lookups over the quarter (at most 3 on a day).

That is a narrower claim than it looks:

- **The faults come from the same catalogue.** The held-out market changes the seed, the rates and the market, not
  the kinds of fault. The result says the checks generalise across draws and harsher rates; it says nothing about a
  fault the world does not simulate (a vendor that shifts a whole file by a day, a corporate action no vendor
  announces at all, two vendors that copy each other's errors).
- **The desk is always right.** A lookup returns the exchange's close or the true action. A real desk is slower
  and sometimes wrong; the design keeps lookups low (12 in a quarter) partly so that this matters less.
- **Every quote that is not faulty is exact.** Vendors here agree to the fourth decimal when they are right, so
  agreement within 5 bp is easy to find. Real vendors differ by closing-auction rules and rounding.

## What the ablations showed on the held-out market

- Without the desk the hub missed two dividends in the total-return index and was off on 31 closes; the desk's 12
  lookups are what close that gap.
- Without the action checks (every announced action applied by majority) the total-return index was off on 46
  closes, by up to 507 bp.
- Sending desk questions in instrument order rather than by risk used 214 lookups and still let 2 closes through:
  the risky questions were not reached before the close.
- Undated identifiers mattered far less here (2 wrong closes) than on development (74): fewer of the held-out reused
  tickers belonged to index constituents that the other vendors had stopped quoting.

## A scoring mistake found by this run

The first held-out run exposed a bug in the scorer, not in the hub: when a design could never price a constituent
(Northwind sent no quote for it on the base date, and the one-vendor design has nowhere else to look), the index
level was not a number and compared as "not wrong". The one-vendor design could not calculate Global Tech Leaders
30 or Global Dividend 40 on 62 days each. The report counts those 124 index-days as not wrong; the README shows
them as "not calculable" and adds them to that design's count (160, not 36), recovered from the daily series in
`reports/heldout.json`.

The scorer now counts a level that cannot be calculated as wrong and reports it separately
(`unpublished_index_days`); the development report was regenerated with it and did not change. A level can only
become uncalculable on the base date, so the other designs' held-out counts are unaffected (each of them has
errors on every index). The held-out market was not run again; the code fingerprint in the lock is the code that ran.

## Changed after the run, measured on development only

Looking at the dashboard after the run, one development day showed both remaining vendors' quotes for a London stock
"repaired": Kestrel's correctly (pence labelled as pounds) and Meridian's wrongly (made a hundred times too big),
because each was compared with the other's unrepaired quote. The desk caught it before the close, so no index level
was wrong, but it spent a lookup. The unit check now compares a quote with yesterday's golden price moved by the
peers and uses the other vendors only when there is no yesterday. On development the hub's desk lookups went from
14 to 13 with the same zero wrong closes. The held-out figures above are from the code before this change.
