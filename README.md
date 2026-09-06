# Nancy Pelosi Stock Tracker

Tracks Nancy Pelosi's stock and stock-option transactions and publishes them
as a simple table (`index.html`), updated daily by a scheduled GitHub Action.

## Data source

Transactions come from **Periodic Transaction Reports (PTRs)** filed with
the **Clerk of the U.S. House of Representatives**
(<https://disclosures-clerk.house.gov>) under the STOCK Act.

This is **not SEC EDGAR**. Members of Congress are not SEC-registered
corporate insiders, so their trades are not Form 4 / 13D-13G filings — they
go through the House (or Senate) financial disclosure system instead. The
pipeline downloads the House Clerk's official annual filing index, finds
PTRs filed under the last name "Pelosi", and parses the linked PTR PDF for
each one.

## Known data limitations

* **No exact price or share count is ever disclosed.** PTRs report a
  transaction as a **dollar-value range** (e.g. `$15,001 - $50,000`), not an
  exact amount, price, or quantity.
* `est_value_usd` is simply the midpoint of that disclosed range.
* `est_price_usd` / `est_quantity` are a **derived best-effort estimate**:
  a historical closing price near the transaction date is looked up (via
  Stooq's free CSV endpoint) and used to back into an estimated share count
  (`est_value_usd / est_price_usd`). This lookup only runs for plain stock
  trades with a resolvable ticker, is capped per run, and fails silently
  (leaving the fields `null`) rather than guessing.
* Options transactions are flagged with `asset_type: "Stock Option"` but do
  not get a price/quantity estimate, since option pricing isn't available
  from a simple daily-close feed.
* Always check `filing_url` (the underlying PDF) before treating any number
  here as authoritative.

## Files

* `track_pelosi.py` — fetches the House Clerk index + PTR PDFs, parses new
  transactions, and writes `pelosi_trades.json` (cumulative) and
  `pelosi_updates.json` (this run's new transactions).
* `index.html` — static page that renders `pelosi_trades.json`.
* `.github/workflows/daily-update.yml` — runs the tracker daily and commits
  any new data.

## Tracking more members

`TRACKED_MEMBERS` in `track_pelosi.py` is a list — add another
`{"display_name": ..., "last_name": ...}` entry to track additional House
members the same way.

## A note on parsing reliability

The House Clerk's PTR PDFs are parsed with `pdfplumber`'s table extraction
(falling back to text regex if no table is detected). The government
endpoints used here (`disclosures-clerk.house.gov`) could not be reached
for live testing from the environment this was originally built in, so the
first real scheduled/manual run should be checked against the
`debug_output.txt` artifact it uploads — if the PDF layout doesn't match
what the parser expects, that log will show raw extracted rows to debug
against.
