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

Add `--embed` for a copy with thumbnails inlined as data URIs, or `--artifact` for a publishable
fragment (inlined fonts and images, no document wrapper, no `<html>`/`<head>`/`<body>`). Both take
a few minutes — they encode 1,500 thumbnails, so run them in the background.
`assets/fonts-embedded.css` holds Oswald/Spectral/JetBrains Mono as woff2 data URIs, because a
published artifact's CSP blocks font CDNs and the type would otherwise silently fall back.

**`meta.json` fields:** `url`, `slug`, `lot_number` (string), `title`, `estimate_low`,
`estimate_high`, `current_bid`, `bid_count`, `description`, `image_count`, `images`
(Invaluable CDN URLs), `image_variants`. Lot number → slug mapping lives here; there is
no separate index, so build one when parsing.

**Data realities, verified:**

- **The full catalogue description IS on disk, for all 1,500 lots.** An earlier version of
  this file said the opposite — that `lotDescriptionFields` was empty in every `lot.html`
  and descriptions loaded client-side. That was wrong, and it was wrong for a long time.
  `description` is indeed `null` in every `meta.json`, but the `lotDescriptionFields` div
  in `lot.html` holds the complete text: one `<div>` per paragraph, typically body
  description, then a condition line, then a dimensions line. `tools/parse_lots.py` now
  extracts it to `desc` (list of paragraphs) and `dims` in `build/lots.json`, and every
  card on the page shows it under "Thomaston's description".
  **Do not re-derive from photographs anything the description already states.**
- What the descriptions carry: **1,261 lots with dimensions, 119 with a stated silver or
  gold weight, 442 with a year, 619 noting a signature or mark, 277 with condition notes.**
  They also carry makers, hallmark towns and dates, provenance, and karat marks that the
  titles omit entirely.
- **The photographs are still the second source, not the first.** ~5,200 JPGs, every lot
  covered (see §7). Read the description, then check it against the images — several
  catalogue claims in this sale do not survive that comparison, which is the point.
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

## 7. Read the description first, then the images

**Order matters.** The catalogue description is on disk for every lot (§1) and it states
dimensions, weights, hallmark years, makers, provenance and condition that no photograph
can give you. Read it before forming a view. Then use the images to test it — because a
material share of this catalogue does not survive that test, and finding where it fails is
most of the value in the analysis.

Two worked examples from this sale. Lot **1115** looked Edwardian in the photographs and I
dated it that way; the description gives a Birmingham **1931** hallmark, which fails the
antique line outright. Lot **2402** is catalogued as "16th c."; the plates themselves depict
the Battle of Wimpfen, **1622**. The first is the description correcting me. The second is
me correcting the description. You need both directions.

The photos are local (`data/{day}/lots/{slug}/images/`), every lot has at least one, and
you can open them. Together with the descriptions they convert CHECK FIRST verdicts into
real calls: the description tells you what the house says it is, the photograph tells you
whether that is true.

The images remain the **only** evidence for anything the cataloguer did not choose to
mention — and what a catalogue omits is itself information. The Wyeth block is the case in
point: seven of those lots say only "print" with no process named, and no description
fills that gap. What settled them was looking at the sheets and seeing every one matted
flush to the image with no margin, hence no signature, hence no edition.

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

Both the photographs and — since the descriptions were recovered from `lot.html` (§1) —
the catalogue's own text have been read against every question below. **Eight of the ten
rows are now closed.** Only **1088** (what is actually in the watchmaker's tools) and
**1017** (period Federal or Colonial Revival) still need the room.

Read this table as a worked example of the method: the images closed three, the recovered
descriptions closed five more, and two of those five **reversed a call I had already
made** — 1115 and 1110 both went the wrong way once the catalogue's own words were read.

| Lot | Question | Status |
|---|---|---|
| 1164 | Collotype or collagraph? | **CLOSED — neither.** The sheet carries a printed trademark banner "A COLLOGRAPH Print" plus "© 1993 Aaron Ashley Inc., Yonkers, N.Y." and "Made in U.S.A." No pencil signature, no edition. A 1990s commercial reproduction worth $50–100. **The collotype hypothesis was wrong** and the $1,000–2,000 comps do not apply. |
| 1121 | Actual weight and fineness | **CLOSED — trap confirmed.** Gilt silver Washington Mint Sacagawea novelty in its box and capsule. Quarter pound ≈ 3.6 ozt ≈ $182, and the plating makes a refiner discount it further. Estimate is ~3× melt. |
| 1115 | Net silver weight, less glass liners | **CLOSED — and it sank the lot.** Cooper Brothers & Sons, Birmingham, **1931**, spoons Sheffield 1932; **6.14 ozt tw stated *without* the glass liners** = 191 g, ~$285 melt, $248 refiner. But 1931 is five years past the antique line, so the age criterion fails on a catalogued hallmark. My inferred Edwardian-to-George-V dating was wrong. **BUY IF CHEAP → PASS.** |
| 1033 | Height of the Alvin vase | **CLOSED. Height 8 in. (20.3 cm.), max. diam. 3 1/2 in.** — a desk-scale vase, not the larger form the seamless-white shot implied. The description adds two things the photos could not: the glass is *"possibly by Loetz"* and the overlay is marked **999/1000 Fine**, i.e. fine silver rather than sterling. |
| 1066 | Confirm sterling throughout, get weight | **CLOSED. 3.71 ozt tw = 115 g**, marked Felmore and Sterling, gilt-washed interior, original spring arm, unmonogrammed. ~$172 melt, $149 refiner. Mid-century, so melt-plus-a-little as expected. |
| 1088 | What's actually in the watchmaker's tools? | **Still open, and the only one left.** The description is as thin as the photos: "a variety of early repair implements, plus (3) small wooden boxes containing tiny watch parts." Count it in the room. |
| 1181 | Postcard contents — Maine RPPCs? | **CLOSED, and favourably.** Two albums "both including many Massachusetts, **Maine** and New Hampshire views, one with a nice group of **real photo** images", plus **12 cards of the Old Orchard Beach fire of 1907** published by The Lakeside Press, Portland, and 11 of the San Francisco 1906 earthquake. **CHECK FIRST → BUY.** Still worth counting the Maine cards in the room. |
| 1017 | Period Federal or Colonial Revival? | **Still open.** The description adds form and condition — "American Lobed Top Stand featuring a large knot, acanthus leaf carved urn stanchion, raised on reeded and scrolled legs, **original latch**", checking and stains to the top — but commits to no period. Look for circular saw marks underneath. |
| 1110 | Woodbury — oil, watercolour, or etching? | **CLOSED — it is an oil.** *Crashing Whitecaps*, **oil on upson board**, signed lower right and marked "Maine", 19½ × 29½ in., in a damaged gold gesso frame. Upson board dates it to the second half of Woodbury's career. That puts it **out of band**, not into it. **3467** is now answered too: *Scuttlebutt*, **watercolour and pencil on paper, unsigned**, 8½ × 11½ in., at $300–400 — the only Woodbury in the sale that is reachable. |
| 1069/1070 | Currier originals or later facsimiles? | **CLOSED — originals.** 1069 is *"The Destruction of Tea at Boston Harbor"*, hand-coloured lithograph **by Nathaniel Currier for Saxony & Major at 39 Nassau near Fulton Street** — a checkable 1840s address matching the catalogued 1846. 1070 carries the full 1867 title line and is hand coloured, with "one noticeable spot in sky". **Both CHECK FIRST → BUY.** |

---

## 11. Deliverable

A **single-file browsable HTML page**, mobile-first — it gets used on a phone in the
gallery.

The prior session's page (`summer-grandeur-day1-lots-1001-1181.html`) is **not in the
repo**, so build fresh to the same spec:

- Sticky filter bar: verdict chips, age chips, free-text search, ★ starred list
- Per-lot card: linked thumbnail, title, dateline with evidence class, criteria + category +
  period tags, analysis, problems block, **my market estimate, resale value and margin at
  target**, a **metal and stones block** on precious-metal lots (weight basis, melt range,
  refiner net at 87%, gem resale), **bid bar** (estimate band, current bid, target,
  walk-away), numbers grid, patience line, link to the lot page
- **All 1,500 lots live in one list**, every one a full card. Nothing is collapsed into an
  accordion at the bottom; that earlier arrangement made the page read as 127 lots and was
  the one substantive complaint about it.
- **Thomaston's own description sits on every card**, in a collapsed `<details>` block
  headed "Thomaston's description", visually distinct from my analysis. The buyer sees the
  primary source and my reading of it side by side, and can tell which is which.
- **All value figures are mine, not the house's.** Melt weight is the **catalogued** weight
  on the 119 lots that state one, with a named deduction for stones, glass, enamel and
  liners — the deduction is still my estimate and the basis line says so. On every other
  precious-metal lot the weight is my estimate from the form and the photographs and needs
  the scale at preview. Margin at target is deliberately blank where my market range spans
  more than 3×: that width is unresolved uncertainty (a medium, a period, a print process),
  not value, and averaging it floats the least-known lots to the top of the ranking.
- Rebuild melt from catalogued weights with `python3 tools/melt_from_catalogue.py`, which
  rewrites the `melt` block in `analysis/valuations.json` in place and touches nothing else.
- Header strip with working metal prices and per-gram rates

Palette is oyster/spruce/verdigris/oxblood/brass; type is Oswald + Spectral + JetBrains
Mono. **Point thumbnails at the local copies** (`data/{day}/lots/{slug}/images/`), not
Invaluable's CDN — more reliable and works offline in a gallery with bad signal.

### Practical

Don't try to hold 1,500 lots in context. Parse `lots.csv` + the per-lot `meta.json`
files to a structured intermediate file, then work in batches and append. Keep a
manifest of which lot ranges are analysed so gaps stay visible rather than silently
missing.

**Coverage: complete. All 1,500 lots individually assessed. No gaps, no
category-level calls remaining.**

- **1,500 of 1,500 lots assessed in full** — 13 STRONG BUY, 172 BUY, 1 STRETCH-WORTHY,
  364 BUY IF CHEAP, 35 CHECK FIRST, 915 PASS. Every one carries all nine required fields
  plus my own market and resale estimates, and a melt/stones block where there is metal.
- **Every PASS is now an individual judgement**, not a bucket. The old "category-level PASS"
  device and its 23-reason legend are gone; if a lot is a pass, the card says why for that lot.
- **Date and evidence class on every lot:** 391 antique, 302 border, 695 modern,
  112 unverified. Evidence: 363 Catalogued, 643 Inferred, 494 Unverified. The Inferred
  proportion (43%) is in line with the §6 reference and has not drifted.
- **262 lots are starred** as worth a second look in the room.
- **Melt is worked out on every gold and silver piece.** Three lots are estimated below their
  own metal at the working gold price: **3198** (IWC 18K), **3200** (14K Omega De Ville) and
  **3069** (14K brooch, the only one in band).
- Verdict files are `analysis/verdicts-*.json`, all matched by the same glob. A verdict row may
  be keyed by `slug` instead of `lot` — two lots in the sale have no lot number (the VW Beetle
  and the garden urns), so those two are keyed by slug.

### Findings from the final sweep (the categories the earlier passes had deferred)

- **2294 English Liverpool jug with the Commodore Preble transfer, $400–600.** Edward Preble
  was born in Falmouth (now Portland). A c.1805–15 creamware jug bearing Maine's naval hero,
  in band only because it is chipped — the §2 condition-discount case exactly. STRONG BUY.
- **2194 twenty-eight-piece Chinese export tea service, $500–700.** Catalogued "19th century";
  the drum teapot, the handleless tea bowls with matching coffee cans and the spearhead-and-cell
  border put it c.1800–1820. Hand-painted, not transfer. STRONG BUY.
- **2365 bronze lady's hand** — the wrist face is struck **F. BARBEDIENNE**. Antique plus named
  maker, inside band. The catalogue misspells it "Barbidienne."
- Other buys: **2169** 1793 Newburyport memorial (dated, named), **2131** 1834 Eliza Russell
  sampler, **2402** two Merian-school Wimpfen battle plates (see errors below), **2415** pair of
  17th-c. Spanish brass candlesticks, **2403** c.1900 Schilling/Brill plaster mathematical model,
  **2168** armorial powder horn, **2148** F.B. Norton stoneware jug, **1153** Catelin/Boulenger
  charger, **2134** signed Mundwiler coverlet, **2162** 39-star silk flag, **1231** 18th-c. drum
  canteen, **1485** 1745 Zurich Bible, **1487/1493/1478/2404/1498** the early paper, **2078**
  cased sailmaker's tools, **1187** 19th-c. Mexican santos, **2283** marked Soutter kettle at $100.

### Categories to avoid outright, with the reason on the card

- **Eight ivory lots** (2338, 2342, 2344, 2379, 2392, 2473, 2484, 2504) plus **2505** and the
  walrus tusks at **1304**. All carry **zero resale**: federal and Maine law require documentary
  proof of age for an antique exemption and none of these lots supplies it. A collector who
  might one day let something go loses the whole value.
- **2439** "ancient Assyrian sandstone rubble" and **2429** an unprovenanced Greco-Roman marble
  head. Unprovenanced Mesopotamian and classical antiquities carry import-restriction and
  repatriation exposure as well as authenticity risk.

### Blocks identified and treated as one decision

- The **Wyeth block, 1162–1172**, with one correction. Ten of the eleven are reproductions:
  1163 a giclée, 1164 a 1993 Aaron Ashley commercial print, 1169 three Helga portfolios, and
  1166/1167/1168/1170/1171 each matted flush to the image with no margin, no signature and no
  edition — a signed impression is never matted that way, because the pencil signature in the
  margin is the entire value. **But 1172 is not one of them.** Its description names a process,
  a year and an institutional publisher: *"Young Fisherman and Dory", 1966, **lithograph,
  published by Farnsworth Art Museum, Rockland, Maine**.* That is a genuine edition lithograph
  from the Wyeth museum fifteen minutes up Route 1. I had written that the cataloguer "reverted
  to no description at all" — there was a description; I could not see it. Assume unsigned
  unless the sheet says otherwise.
- **Day 1 Chinese decorative, 1341–1445** — ~30 lots almost all estimated $300–400. The flat rate
  is the tell: a decorator's collection lotted at a default price, not valued individually.
- **Day 2 rug consignment, 2172–2271** — thirty-one carpets, and **not one description carries a
  date**. (2268 is dated "early 20th c." in its *title* only.) That is worth sitting with: the
  same cataloguer dates the paintings and furniture interleaved through the same lot range to the
  year. The oriental rug market has fallen further than almost any decorative category since
  2010; these estimates are at or above it and nearly all are above band.
  The three **Day 1** Caucasian rugs are the exception and are all catalogued to the century in
  their descriptions — **1378** (Karabagh, with an original 19th-c. tag verso), **1380** (Shirvan
  kelim, last quarter 19th c., but with "extensive wear, tears, & holes") and **1475**
  (Daghestan prayer rug, late 19th c., end loss and selvage damage).
- **Studio pottery, 1135–1151** — nine lots, all post-war, gallery-priced.
- **Riflescopes 1243–1265, Remington bullet knives 1245–1267 (six lots), RIAA awards 1323–1327,
  Irish pub fittings 3026/3029/3031, anonymous animal bronzes 1180/3018/3023/3173** — each one
  consignment, each better read as a block than lot by lot.

### Cataloguing errors found so far

Worth knowing because they show how much of this catalogue is not specialist work, and
because several affect attribution directly. Note the asymmetry now that the descriptions
are readable: the **descriptions** are generally careful and factual — hallmarks, weights,
dimensions, provenance — while the **titles** are where the errors cluster. Trust the
description over the title where they disagree, then test both against the photograph.

- **1112** dates John Manship 1977-2000 (he lived 1927-2000)
- **1122** places William Meyerowitz in California (Massachusetts/New York)
- **1424** gives Tony Bell's death year as a truncated "199"
- **1455** catalogues a $400-500 lot as Walt Kuhn, a major Armory Show modernist — check, don't believe
- **3002** reverses Jules Moigniez's dates as 1935-1894
- **3425/3426 vs 3427/3428** give two irreconcilable identities for "Waldo Peirce"
- **3451** places Don Stone in Iowa; **3443** misspells Sweden; **1022** misspells Hungary
- **3477/3478/3479** give Andrew Wyeth's death year as 2019 (he died 2009)
- **2371** dates Daubigny 1870–1878 (he lived 1817–1878); **2353** gives Renoir's death as 1914 (1919)
- **2201, 2216, 2218, 2385** put Cole, Remington, Inness and Guardi at estimates an order of
  magnitude below a genuine work, with no "attributed to" qualifier — the estimate is the
  house telling you what it actually thinks
- **2358** attributes an "18th-century" painting to an artist who died in 1652
- **2402** catalogues two "16th c. German battle maps" that are Merian-school engravings of the
  Battle of Wimpfen, **1622** — wrong by a century, and it cuts both ways: it suppresses
  specialist interest and it means nothing else in the description can be relied on
- **2364** sells a **c.1875–1900** Boulenger-manner faience platter as "Lille 1737". "Lille 1737"
  is a retro-mark used by late-19th-c. French decorators; the plate is signed H. Clerc, the
  catalogue reads it M. Clerc. Same consignment as **1153** (Boulenger & Cie, Montereau)
- **2365** misspells the Barbedienne foundry as "Barbidienne" — the mark on the piece is correct
- **2160** catalogues a $800–1,200 lot as a **1792 Washington Indian Peace Medal**. Genuine ones
  are six-figure objects; a handful survive. The estimate is the house telling you it is a copy
- **1182/1184/1185/1186** describe H.E. Luhrs and related **1930s–50s** Halloween diecuts as
  "antique"; **2165** calls an American silk-embroidered eagle a "woolie" (woolies are British
  sailors' wool-on-wool ship pictures)
- **1378** gives a "Karabagh prayer rug" dimensions of 11'2" x 4' — those are runner dimensions,
  not prayer-rug dimensions; **1380** and **2187** both have obvious dimension typos
- **2240** titles a lot "letters ... 1939–1946, including JFK in May 1958"
- **1494** offers a 1976 Danish royal appointment "signed by the King & Queen" — Denmark had no
  King in 1976 (Margrethe II acceded 1972; Prince Henrik was never King)
- **2275** describes a "Seal of the Duke of Rochester". There has never been a Duke of Rochester
- **3171** attributes a stone mermaid to "Wilerid Ciricus", which resolves to no documented
  sculptor and reads as a garbled signature transcription
- **2318** offers an 1807 Royal Academy letter "signed by David as Secretary" — establish which
  David; Jacques-Louis David was French, in Paris, and never a Royal Academician
- **1230** offers a percussion long rifle by "Jackie Brown", a name that does not resolve to any
  documented 19th-c. gunsmith and reads much more like a living contemporary-longrifle maker
- **3249** gives the Frederick Lynch label as "Baridoff Gallery of **Portsmouth, Maine**". Baridoff
  Galleries was in **Portland**; Portsmouth is in New Hampshire
- **1498** is titled a "1824 edition" but the description gives the imprint as **Paris, Chez Arthus
  Bertrand, 1826**
- **2062** letters the liner **"Mauritania"**; the Cunard ship was *Mauretania*, with an "e"

### Where the value landed

The thirteen STRONG BUYs, all inside band: **2300** George III sterling mug by William Cripps
(melt sits close under the estimate), **2294** Liverpool jug with the Commodore Preble
transfer, **2194** 28-piece Chinese export tea service c.1800–20, **3347** Carroll Thayer
Berry colour woodblock (confirmed pencil-signed and artist-printed, "imp"; **3348–3350** are
the others in the group), **2068** 18th-c. pine sea chest at $300–500, **2139** C.F. Hopf
Kennebunk grain-painted stand, **2118** Maine redware attributed to Norcross, **2093**
Rockland-identified ship model, **2295** 17th-c. carved oak bible box, **2243** 1652 Anatomy
of Melancholy, **2398/2399** two consecutive Piranesi plates at $500–800 each, **3487**
unsigned late-19th-c. Maine watercolour.

Note that **Day 2 carries nearly all of it.** Ten of the thirteen STRONG BUYs are Day 2 lots.
Plan the sale around 29 August.

### Priorities from here

1. **Preview is the only remaining bottleneck, and the list is now short.** Recovering the
   descriptions closed most of what used to be on it. Answered by the catalogue and no longer
   needing the room: **3147** (says "**Solid** 14K"), **1101** (bone and bamboo, not ivory —
   no legal problem), **2340/2346** (ivory, confirmed — avoid), **3198/3200** (cases stated as
   solid 18K and 14K, though **no weight is given, so the scale is still needed**).
   **Still needs preview:** §10's **1088** and **1017**; **3094** (25 ct star ruby — the
   estimate says synthetic, confirm with a loupe); **2498** (Type A jadeite or dyed?);
   **3243–3245** (ancient intaglios or modern casts?); **2273** (count the apothecary bottles
   against the recesses); **2078** (count the sailmaker's tools, and check the handles for
   marine-mammal material); **2294** (UV the Preble jug's spout for restoration); **2438**
   (open the three boxes of Iznik tiles and count what is whole); and the **119 catalogued
   weights** are the house's figures, not mine — spot-check the important ones on a scale.
2. Re-check `current_bid` before the sale: the figures in `data/` are a scrape-time
   snapshot, not live.
3. If further depth is wanted, the honest answer is that it now needs objects in hand rather
   than more reading. The photographs have been worked as far as they go.

---

## 12. Before the sale

Preview runs weekdays and Saturdays **Aug 15–27**; Thomaston also books **virtual
gallery previews**. Worth using on anything still marked CHECK FIRST after the images
are read.

Thomaston Place Auction Galleries · 51 Atlantic Hwy, Thomaston ME 04861 · 207-354-8141
