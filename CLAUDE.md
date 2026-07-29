# Summer Grandeur 2026 — Auction Analysis

Working brief for analysing Thomaston Place Auction Galleries' Summer Grandeur 2026 sale
(August 28–30, 2026) for a private buyer. Read this fully before touching the data — it
defines who the buyer is, how to evaluate lots, and what to produce.

**Sale structure:** Day 1 = lots 1001–1503 (502 lots; lot 1128 withdrawn). Day 2 = lots
2001–2509 (509 lots; marine/Nantucket/whaling). Day 3 = lots 3001+ (489 lots;
bronzes/trade signs). 1,500 lots total.

---

## 1. The repository

All sale data is already scraped and on disk. Verified layout:

```
data/
  lots.csv                 # 1,500 rows: day, lot_number, title, estimate_low,
                           # estimate_high, current_bid, bid_count, image_count, url
  day1/ day2/ day3/
    catalog/page-NNN.html  # paginated catalog listing pages (25–26 per day)
    lot-urls.txt           # day2/day3 only: one lot URL per line
    lots/{slug}/           # one directory per lot, e.g.
                           #   19th-c-bronze-bell-on-iron-swing-bracket_64abae2b41/
      meta.json            # structured fields (see below)
      lot.html             # raw lot page capture (~85 KB each)
      images/NNN.jpg       # local full-size photos — every lot has at least one
thomaston-scrape.php       # the scraper that built data/ (probe/run/status/report modes)
cacert.pem                 # CA bundle for the scraper, not project data

tools/parse_lots.py        # data/ -> build/lots.json + build/titles-{day}.txt
tools/build_page.py        # lots.json + analysis/ -> summer-grandeur-2026.html
analysis/verdicts-day*.json  # hand-written verdicts, one file per day (append here)
build/                     # generated intermediates, safe to delete and rebuild
summer-grandeur-2026.html  # THE DELIVERABLE — single-file, mobile-first
```

**Rebuild the page with:** `python3 tools/parse_lots.py && python3 tools/build_page.py`

**`meta.json` fields:** `url`, `slug`, `lot_number` (string), `title`, `estimate_low`,
`estimate_high`, `current_bid`, `bid_count`, `description`, `image_count`, `images`
(Invaluable CDN URLs), `image_variants`. Lot number → slug mapping lives here; there is
no separate index, so build one when parsing.

**Data realities, verified:**

- **`description` is `null` in all 1,500 `meta.json` files**, and the
  `lotDescriptionFields` div in every `lot.html` is empty — descriptions load client-side
  and were not captured. The hand-off hoped full descriptions (dimensions, weights,
  hallmarks, condition notes) would be on disk; **they are not**. Weights and condition
  must come from the photographs, the live lot page (`url` in meta.json), or preview.
- **Local images are the real unlock.** ~5,200 JPGs, every lot covered. The prior chat
  session could not see any photograph; you can. Use them (see §7).
- `lots.csv` has a few rows with empty titles — fall back to `meta.json` or the slug.
- Bid data (`current_bid`, `bid_count`) is a snapshot from scrape time, not live.
- **The prior session's HTML page was never uploaded**, so the deliverable was rebuilt
  fresh to the §11 spec as `summer-grandeur-2026.html`. The 71 chat-session verdicts are
  likewise not on disk; only the conclusions carried in this file survive, and several
  have since been overturned by the photographs (see §10).

---

## 2. The buyer

Collector in midcoast Maine (Bath area), long-time antique and vintage buyer, shops
Thomaston regularly plus the Route 1 corridor.

**Buying for a personal collection this sale — not for resale.** The question is not "can
I double this" but "if I ever had to let it go, what do I lose?" Melt values and auction
comps are a **floor and a sanity check**, not a target.

Consequences of collecting rather than flipping:

- **Condition-discount opportunities are good buys.** The market punishes some flaws far
  out of proportion to how they look on a shelf — period repairs, monograms, replaced
  finials, mismatched-but-right-era components. Flag these; they're often the best value
  on the floor.
- **Authenticity matters more, not less.** A reproduction bought at antique prices is
  something they look at every day.
- **Patience score is required on every lot** (see §5). If a thing surfaces at Thomaston
  every third sale, don't stretch. If it's genuinely uncommon, that's the honest case for
  going past comp.

### Criteria, in priority order

1. **True antiques** — 100+ years old (see §6 for the dating line)
2. **Precious metals** — gold, sterling; melt is the floor
3. **Authentic Art Nouveau** — genuine period pieces, *not* Nouveau-*style* revival
4. **Named makers** — documented, attributable
5. **Maine coastal art** — new interest this sale (see §8)

### Budget

- **$100–1,000 hammer per lot**, so **$132–1,318 all-in**
- Bidding **online at 25% buyer's premium**
- This band rules out real Tiffany Studios shades, diamond solitaires, significant signed
  Gallé. Anything with a headline name landing under $1,000 hammer is damaged, a
  fragment, or wrong — **treat a suspiciously cheap big name as a red flag, not a find**

---

## 3. The money

```
All-in  = hammer × 1.25 (online premium) × 1.055 (Maine sales tax) = hammer × 1.32
Phone/absentee premium is 20% → factor 1.27 (worth ~$53 on a $1,000 hammer)
```

Buying personally means **no resale-certificate exemption** — Maine sales tax always
applies.

### Melt basis — use these, they are deliberately conservative

| Metal | Working spot | Per gram |
|---|---|---|
| Gold | $4,000/ozt | $128.60 |
| Silver | $50/ozt | $1.61 |
| Sterling (92.5%) | — | **$1.49** |
| 10K (41.7%) | — | **$53.63** |
| 14K (58.5%) | — | **$75.23** |
| 18K (75%) | — | **$96.45** |

Actual silver was ~$58 when this was set. **The working number is intentionally below
market** so a bid that clears on paper still clears if metals slip before 28 August.

**Conversions and rules:**

- `dwt × 1.5552 = grams`, then `× purity × spot per gram`
- **Catalogue weights are gross.** Always deduct stones, glass liners, wooden handles,
  fitted cases, base-metal hinges before calculating
- **A refiner pays 85–90% of calculated melt.** Knock that off before calling something
  a buy
- **"Gold-filled" and "silver plated" have no melt floor at all** — thin layer over base
  metal. Don't let the word "gold" in a title imply metal value
- **"Silver mounted"** means a collar or cap on a glass/ceramic body — minimal content
- Composite/doublet opals are worth far less relative to gold content than solid stones

**Do not trust a spot price from a bullion dealer's marketing page.** A prior session
pulled "$100+ silver" from one and it drove two wrong verdicts. If you need a current
price, use a neutral source and say where it came from.

---

## 4. Standing principles

Learned across this buyer's history. Apply without being reminded.

- **"After [maker]"** in an auction title means copy or reproduction, not authenticity
- **"...style"** means the cataloguer is declining to commit to a period attribution
- **"School of X"** with no name attached is a hopeful label, not an attribution — price
  it as the anonymous work it is
- **Boilerplate maker biographies attached to lots are indexing, not provenance**
- **Unidentified signatures are speculative.** "Artisan signed" means the cataloguer saw
  a signature and couldn't identify it — don't pay named-maker money for it
- **Comps are eBay and auction sold prices.** 1stDibs and dealer asking prices are *not*
  comps — cite them only to show the shape of a spread, never as expected value
- **10K gold** points to American rather than British Victorian origin
- Original un-electrified oil lamps should not be converted
- Romanian "Tip Gallé" cameo repros: blue-on-butterscotch palette, flat acid-etched
  graphic quality, cast alloy frames, thin glass; blacklight can reveal ground-off "Tip"
  marks

---

## 5. Output format per lot

Every analysed lot gets all of these:

| Field | Notes |
|---|---|
| **Verdict** | STRONG BUY / BUY / STRETCH-WORTHY / BUY IF CHEAP / CHECK FIRST / PASS |
| **Criteria fit** | Which of the five buckets it hits |
| **Date + evidence class** | See §6 — the evidence class is mandatory |
| **Analysis** | Prose. What it is, why it does or doesn't fit, what the market does |
| **Problems** | Condition risks, repro tells, catalogue language doing work |
| **Target** | Where the value is genuinely good |
| **Walk-away ceiling** | Hard stop. Auction rooms are built to blur this line |
| **All-in at ceiling** | ceiling × 1.32 |
| **Patience** | How often this surfaces at auction. Required — see §2 |

**Two numbers, always.** A single "max bid" is not useful.

Where a verdict rests on a number you looked up rather than computed, **say so and cite
it**, so the buyer can check the input. They have caught a bad input before and were
right to.

---

## 6. Dating — this is the core criterion

**The antique line is 1926** (100 years before the sale).

Every lot gets a period **and an evidence class**. The buyer specifically values this
distinction; do not collapse it.

- **Catalogued** — Thomaston stated the date. A claim you can hold the house to
- **Inferred** — derived from maker, form, production window, or artist's active period.
  An argument, not a fact
- **Unverified** — nobody has committed. Dressed as an antique, may not be

Status buckets: `antique` (confidently pre-1926) / `border` (straddles the line or
genuinely uncertain) / `modern` (post-1926).

Reference from the completed work: of 54 early lots, 19 were Catalogued, 26 Inferred, 9
Unverified. If your Inferred proportion is much higher than that, you're guessing too
freely.

---

## 7. Use the images — this is the whole reason for the move to Claude Code

The chat session **could not see any lot photographs** — all 71 existing verdicts rest on
titles, estimates, and market knowledge alone. The photos are now local
(`data/{day}/lots/{slug}/images/`), every lot has at least one, and you can open them.
This is the single biggest capability gain and it converts CHECK FIRST verdicts into real
calls. It matters even more now that we know full descriptions were never captured (§1) —
the images are the only condition evidence on disk.

For flagged lots, actually look for:

- **Hallmarks and maker's marks** — crispness, placement, whether they look period or
  applied
- **Signatures** — pencil in the margin vs. printed in the plate; legibility
- **Print process** — inkjet dot structure (giclée, worthless) vs. continuous tone
  (collotype, real). This distinction is worth thousands on the Wyeth lots
- **Silver overlay condition** — lifting at edges, grey polished-thin patches, hairlines
  in glass beneath
- **Construction** — hand-cut dovetails, irregular saw marks, shrinkage, old oxidation in
  unfinished areas. Circular saw marks mean post-1830 at the earliest, usually much later
- **Bronze vs. spelter** — Deco figures especially; spelter is much lighter and worth a
  fraction
- **Solid vs. clad** — Kathodian and similar bookends are metal shells over composition
  cores
- **Completeness** — count instruments against fitted recesses in cased sets; empty
  slots are money off

---

## 8. Maine coastal art — different standard, applied deliberately

New interest this sale. **Almost none of it clears 100 years** — the Monhegan and
Ogunquit colonies peak c.1900–1960. Evaluate on regional desirability and maker, not
antique status, and **say explicitly when a lot earns its place this way rather than on
age.**

**Works on paper are where the budget buys something real.** A signed print by a properly
collected Maine artist sits in band while the same artist's oils are $3,000+.

Names to watch: **Carroll Thayer Berry** (Rockport, colour woodblocks), **Leo Meissner**
(Monhegan wood engravings), **Stow Wengenroth** (lithographs), **Maurice "Jake" Day**
(Damariscotta; also a Disney *Bambi* background artist, which adds a second collector
base), **Lawrence Sisson**, **William Thon** (watercolours; oils out of reach), **Charles
Herbert Woodbury** (Ogunquit colony founder), **Andrew and Jamie Wyeth** (see §9).

Also: **anonymous 19th-century marine work** — unsigned ship portraits and coastal oils.
No maker premium, and genuinely satisfies the 100-year criterion.

**Cautions.** Supply is deep — Thomaston runs this material constantly, so patience
scores here should be high. Read the frame separately from the picture in both
directions: a period frame can outvalue a mediocre painting, and good small works get
dragged down by ugly 1970s reframing that's simply fixable. Hyper-local material (named
midcoast towns) sells to a small but committed regional audience.

---

## 9. Traps already identified — carry forward

**The Wyeth block, lots 1162–1172.** Eleven consecutive lots, one consignor, all
reproductions, all opening $50–100 with the most famous name in Maine painting. The room
will bid these on the name. Process is everything:

- **1163 is a giclée** — inkjet, post-1990, no edition authority, carries the *highest*
  estimate ($400–600) and has the least substance
- **1169 is three copies of the Helga portfolios** — 1987 mass-market publishing,
  $30–100 each
- **Seven lots say only "print"** with no process named — that silence is the catalogue
  declining to commit
- **1164 says "collograph," almost certainly a typo for "collotype"** — the authorised
  Triton/Aristo process, often pencil-signed. This is the one worth pursuing

Researched collotype comps: "The Reefer" (ed. of 300, pencil-signed) estimated
$1,000–2,000 and has hammered $2,900 and $4,750. But "The Sauna" — a Brandywine River
Museum fundraiser edition of 200, properly signed — was estimated $300–500. **Edition
size and image drive the value; fundraiser editions sit at the bottom even when signed.**
Note some Wyeth editions were signed on a colophon page rather than each sheet.

**The California painter consignment.** Wood, Ealy, Lopez, Kratter, de Treville, Frazer,
White, Frates — 15+ lots across Day 1, clearly one consignment, wrong coast, no criteria
fit. Identify and skip similar blocks rather than analysing each.

**Estimates above melt on bullion lots.** Lot 1121 (Washington Mint medallion) is
estimated $300–500 against ~$182 of silver. Private-mint medallions carry no numismatic
premium over bullion. When the estimate exceeds melt on a modern bullion piece, the
estimate is the trap.

**Roseville and Steuben estimates run ahead of the market.** Both corrected hard and
haven't recovered. Roseville is also the most reproduced American art pottery — soft,
blurry mould detail and too-uniform glaze are the tells.

**Weak markets generally:** Eastlake and upholstered Victorian furniture, lap desks,
decorative copper and brass, dinnerware in quantity, anonymous 19th-century child
portraits.

---

## 10. Open questions on already-analysed lots

The images have now been read against every question below. Four are **closed**; the rest
need a scale, a scale-pan or a loupe and therefore need preview. (Full descriptions are
not on disk — see §1 — so anything the photos can't settle needs the live lot page or the
15–27 August preview.)

| Lot | Question | Status |
|---|---|---|
| 1164 | Collotype or collagraph? | **CLOSED — neither.** The sheet carries a printed trademark banner "A COLLOGRAPH Print" plus "© 1993 Aaron Ashley Inc., Yonkers, N.Y." and "Made in U.S.A." No pencil signature, no edition. A 1990s commercial reproduction worth $50–100. **The collotype hypothesis was wrong** and the $1,000–2,000 comps do not apply. |
| 1121 | Actual weight and fineness | **CLOSED — trap confirmed.** Gilt silver Washington Mint Sacagawea novelty in its box and capsule. Quarter pound ≈ 3.6 ozt ≈ $182, and the plating makes a refiner discount it further. Estimate is ~3× melt. |
| 1115 | Net silver weight, less glass liners | **CLOSED enough to act.** Five small pieces — salt, pepper, lidded mustard, two spoons — with a cobalt liner clearly visible. Edwardian-to-George-V weights, so melt sits at the **bottom** of the $93–231 band. Buy as a cased set, not as metal. |
| 1033 | Height of the Alvin vase | **Partly closed.** Base is marked with pattern number V1084C and the overlay is genuine engraved period work over seeded glass — authenticity is settled, **height is not**. Shot on seamless white with no scale. Measure at preview. |
| 1066 | Confirm sterling throughout, get weight | Open — needs the scale. Mid-century, so melt-plus-a-little at best. |
| 1088 | What's actually in the watchmaker's tools? | Open — photos show a general scatter, no lathe or staking set visible. Count at preview. |
| 1181 | Postcard contents — Maine RPPCs? | Open — both photos show the albums **closed**. Must be opened at preview; the most preview-dependent lot in Day 1. |
| 1017 | Period Federal or Colonial Revival? | Open — photos don't show the underside. Look for circular saw marks. |
| 1110 | Woodbury — oil, watercolour, or etching? | Open — medium still unstated. Note **3467 is a second Woodbury question** ("attributed to", $300–400); resolve both in one visit. |
| 1069/1070 | Currier originals or later facsimiles? | Open — needs a loupe on the sheet for dot rosette vs. continuous litho tone. |

---

## 11. Deliverable

A **single-file browsable HTML page**, mobile-first — it gets used on a phone in the
gallery.

The prior session's page (`summer-grandeur-day1-lots-1001-1181.html`) is **not in the
repo**, so build fresh to the same spec:

- Sticky filter bar: verdict chips, age chips, free-text search, ★ starred list
- Per-lot card: linked thumbnail, title, dateline with evidence class, criteria tags,
  analysis, problems block, **bid bar** (visual track showing estimate band, current bid,
  target, walk-away), numbers grid, patience line, link to the lot page
- A "screened out in bulk" section — lots reviewed and set aside with a one-line reason,
  so the noise is visible but compressed
- Header strip with working metal prices and per-gram rates

Palette is oyster/spruce/verdigris/oxblood/brass; type is Oswald + Spectral + JetBrains
Mono. **Point thumbnails at the local copies** (`data/{day}/lots/{slug}/images/`), not
Invaluable's CDN — more reliable and works offline in a gallery with bad signal.

### Practical

Don't try to hold 1,500 lots in context. Parse `lots.csv` + the per-lot `meta.json`
files to a structured intermediate file, then work in batches and append. Keep a
manifest of which lot ranges are analysed so gaps stay visible rather than silently
missing.

**Coverage: all 1,500 lots across all three days have been triaged. No gaps.**

- **127 lots written up in full** (9 STRONG BUY, 49 BUY, 1 STRETCH-WORTHY, 33 BUY IF
  CHEAP, 15 CHECK FIRST, 20 PASS). Every one carries all nine required fields.
- **1,373 lots screened in bulk** into 24 reasoned groups, every lot accounted for.
  The largest are: above the budget band (272), general no-fit (177), Maine artists
  reviewed but not pursued (156), listed painters (118), Chinese/Asian decorative (112),
  fine jewellery and watches (98).
- The old 1142–1161 gap is closed; those lots are triaged.

### Where the value landed

The strongest finds, all inside band: **2300** George III sterling mug by William Cripps
(melt sits close under the estimate), **3347–3350** four Carroll Thayer Berry colour
woodblocks (3347 confirmed pencil-signed and artist-printed, "imp"), **2068** 18th-c. pine
sea chest at $300–500, **2139** C.F. Hopf Kennebunk grain-painted stand, **2118** Maine
redware attributed to Norcross, **2093** Rockland-identified ship model, **2295** 17th-c.
carved oak bible box, **2243** 1652 Anatomy of Melancholy, **3487** unsigned late-19th-c.
Maine watercolour.

### Priorities from here

1. **Preview is now the bottleneck, not analysis.** Six of the ten §10 questions need a
   scale, a loupe or an opened album — book the 15–27 August preview or a virtual one.
2. Deepen the bulk-screened groups if wanted — the marine fittings (42) and Maine
   artists (156) buckets are the two most likely to hide something.
3. Re-check `current_bid` before the sale: the figures in `data/` are a scrape-time
   snapshot, not live.

---

## 12. Before the sale

Preview runs weekdays and Saturdays **Aug 15–27**; Thomaston also books **virtual
gallery previews**. Worth using on anything still marked CHECK FIRST after the images
are read.

Thomaston Place Auction Galleries · 51 Atlantic Hwy, Thomaston ME 04861 · 207-354-8141
