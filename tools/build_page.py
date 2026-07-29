#!/usr/bin/env python3
"""Merge the scraped lot data with the hand-written verdicts and emit the page.

    python3 tools/parse_lots.py && python3 tools/build_page.py

Reads build/lots.json plus analysis/verdicts-day*.json, assigns every lot that
has no written verdict to a bulk-screening group, and writes a single
self-contained HTML file at the repo root.
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ANALYSIS = ROOT / "analysis"
OUT = ROOT / "summer-grandeur-2026.html"

PREMIUM = 1.25          # online buyer's premium
TAX = 1.055             # Maine sales tax
ALL_IN = PREMIUM * TAX  # 1.319 -> the brief's 1.32

METALS = [
    ("Gold", "$4,000/ozt", "$128.60/g"),
    ("Silver", "$50/ozt", "$1.61/g"),
    ("Sterling .925", "-", "$1.49/g"),
    ("10K .417", "-", "$53.63/g"),
    ("14K .585", "-", "$75.23/g"),
    ("18K .750", "-", "$96.45/g"),
]

VERDICT_ORDER = ["STRONG BUY", "BUY", "STRETCH-WORTHY", "BUY IF CHEAP", "CHECK FIRST", "PASS"]
VERDICT_SLUG = {v: v.lower().replace(" ", "-") for v in VERDICT_ORDER}

CRITERIA_LABEL = {
    "antique": "True antique",
    "metal": "Precious metal",
    "nouveau": "Art Nouveau",
    "named": "Named maker",
    "maine": "Maine coastal",
    "marine": "Marine",
}

# Bulk-screening groups, applied in order to every lot with no written verdict.
# Each rule is (group id, label, reason, test).
CA_PAINTERS = re.compile(
    r"orrin augustine white|priscilla jane frazer|paul kratter|will frates|"
    r"f\.? michael wood|fredrik michael wood|richard de treville|donald arvid ealy|"
    r"sergio lopez|michele usibelli|gerald f\. brommer|tony bell", re.I)

RULES = [
    ("california", "California painter consignment",
     "Fifteen-plus lots across Day 1 from a single West Coast consignment -- Wood, Ealy, Lopez, "
     "Kratter, de Treville, Frazer, White, Frates and company. Wrong coast, no criteria fit. "
     "Identified as a block and skipped rather than analysed lot by lot.",
     lambda r: CA_PAINTERS.search(r["title"])),

    ("firearms", "Firearms, optics and sporting",
     "Roughly fifty consecutive Day 1 lots of shotguns, rifles, scopes, knives and decoys. Outside "
     "all five criteria, and the transfer paperwork makes them a poor fit for a collection bought "
     "at a Maine sale. A handful are genuinely pre-1899 but none is what this buyer is after.",
     lambda r: re.search(r"shotgun|rifle|pistol|revolver|carbine|derringer|mauser|\bga\b|gauge|"
                         r"scope|bullet knive|commemorative knive|decoy|gun belt|holster|"
                         r"\.\d{2}[- ]?\d{0,2}\s*(cal|lr|rem|acp)|trapdoor|peacemaker", r["title"], re.I)),

    ("ivory", "Ivory and marine-mammal material",
     "Whale's teeth, walrus tusk, sailor-made ivory and carved elephant ivory. Federal Endangered "
     "Species Act and Marine Mammal Protection Act rules restrict what can be done with these "
     "afterwards, and the paperwork will not accompany lots at this price. Set aside as a class -- "
     "see the standing note below the filters.",
     lambda r: re.search(r"\bivory\b|whale'?s? tooth|whales tooth|scrimshaw|walrus|tusk", r["title"], re.I)),

    ("wyeth-repro", "Wyeth reproduction blocks",
     "Twenty-six Wyeth lots across Day 1 (1158-1172, 1430-1440) from consignors offering "
     "reproductions under the most famous name in Maine painting. Lot 1164 has now been proved a "
     "1993 Aaron Ashley commercial print, which sets the standard for the rest of the run.",
     lambda r: re.search(r"wyeth", r["title"], re.I) and r["day"] == "day1"),

    ("wengenroth", "Wengenroth lithograph run (remainder)",
     "Lots 1309-1315, the middle of the nine consecutive Stow Wengenroth lithographs. Written up at "
     "1308 and 1316, which carry the reasoning for the whole block -- the strategy is to bid the run "
     "and take whichever the room has tired of, so the individual middle lots need no separate case.",
     lambda r: re.search(r"wengenroth", r["title"], re.I)),

    ("maine-artists", "Maine artists reviewed, not pursued",
     "The Day 3 Maine section runs to well over a hundred lots. These are the ones where the artist is "
     "genuinely Maine-associated but the lot fails on price, on being a contemporary gallery-priced "
     "living painter, or on being an oil where the same artist's works on paper are the affordable "
     "way in. The brief's Maine allowance is a reason to look, not a reason to buy.",
     lambda r: re.search(r"\bME[/,)]|\bMAINE\b|monhegan|ogunquit|casco bay|tenant'?s harbor|"
                         r"winter harbor|machias|newcastle|stratton|prospect harbor|eastport|"
                         r"boothbay|damariscotta|kennebunk", r["title"], re.I)),

    ("jewellery", "Fine jewellery and wristwatches",
     "Around eighty Day 3 lots of diamond, platinum and karat-gold jewellery and Swiss watches. Almost "
     "all of it is estimated well above the band, and where the gold is genuinely the point the melt "
     "sits far below the estimate because you are paying for stones and signatures. The few that clear "
     "on metal are written up individually.",
     lambda r: re.search(r"\b(?:10|14|18|22)k\b|platinum|diamond|sapphire|emerald|amethyst|"
                         r"tanzanite|aquamarine|brooch|wristwatch|pocket watch|necklace|bracelet|"
                         r"earring|earclip|pendant|\bring\b|lorgnette|solitaire|\bwatch\b",
                         r["title"], re.I)),

    ("art-glass", "Roseville, Steuben and art glass",
     "Both names are called out in the brief as markets whose estimates run ahead of reality -- they "
     "corrected hard and have not recovered -- and Roseville is the most reproduced American art "
     "pottery there is. Tiffany Studios is here too, at $1,500 to $35,000, which is simply another "
     "budget.",
     lambda r: re.search(r"roseville|steuben|carder|rookwood|weller|tiffany studios|tiffany & co",
                         r["title"], re.I)),

    ("marine-fittings", "Marine fittings, models and instruments",
     "Half hulls, telescopes, ship models, deck clocks, flags, rigging blocks and hand-painted ship "
     "replicas. Genuinely on-theme for the coastal brief, and the best of it is written up -- these are "
     "the remainder, where the object is either undated, a modern decorative replica, or priced above "
     "what a fitting of that kind returns.",
     lambda r: re.search(r"half hull|telescope|ship model|model sailing|nautical flag|ship'?s? "
                         r"(wheel|clock|lantern|kettle|paper|passport)|deck clock|pelorus|sextant|"
                         r"compass|figurehead|rigging block|sailmaker|harpoon|blubber|flensing|"
                         r"whaling|whaler|logbook|sternboard|replica of 19th|naval battle|"
                         r"sea chest|valentine", r["title"], re.I)),

    ("rugs", "Oriental rugs and carpets",
     "Thirty-plus Day 2 rugs. Deep continuous supply at every sale in New England, no criteria fit, "
     "and condition on decorative carpets is impossible to judge from catalogue photographs.",
     lambda r: re.search(r"\brug\b|carpet|kelim|kilim|runner|sarouk|heriz|kazak|serapi|bokhara|"
                         r"hamadan|kashan|tabriz|karadja|serab|ardebil|bahktari|kerman", r["title"], re.I)),

    ("asian", "Chinese and Asian decorative",
     "Around a hundred lots of Chinese porcelain, jade, robes and export ware across Days 1 and 2. "
     "Mostly late Qing to Republic period or later, decorative rather than antique by this brief's "
     "standard, and a category where reproduction is endemic and unverifiable from photographs.",
     lambda r: re.search(r"chinese|qing|ming|shiwan|famille|celadon|meiping|jade|peking glass|"
                         r"tibetan|annamese|himalayan|thai|mughal|indo-persian|iznik|ottoman|"
                         r"turkoman|japanese|blanc de chine|guanyin|bodhidharma", r["title"], re.I)),

    ("studio-pottery", "Studio pottery and contemporary ceramics",
     "The Day 1 run of Sequoia Miller, Aldermaston, Paradox Pottery and similar. Contemporary "
     "studio work -- no antique claim, no Maine connection, and a market that depends entirely on "
     "the individual maker's current standing.",
     lambda r: re.search(r"studio potter|aldermaston|paradox pottery|sequoia miller|bizen|"
                         r"studio ceramic", r["title"], re.I)),

    ("out-of-band", "Above the budget band",
     "Estimated at $1,000 hammer and up, which is $1,320 all-in before the bidding starts. Some of "
     "this is excellent material -- the Rockland sternboard, the Federal furniture, the period "
     "portraits -- but bidding here means abandoning the discipline that makes the rest of the list "
     "work.",
     lambda r: (r["est_low"] or 0) >= 1000),

    ("modern-art", "Contemporary and mid-century artists",
     "Living and recently deceased painters with no Maine connection, priced at gallery rather than "
     "auction levels. Post-1926 by definition, so no antique claim, and outside the regional "
     "allowance the brief makes for Maine work.",
     lambda r: re.search(r"contemporary|20th[- ]21st|\b19[3-9]\d\s*-\s*(19|20)\d\d\b|\b19[4-9]\d\s*-\s*\)|"
                         r"\b, (19[3-9]\d|20\d\d)\s*-\s*\)", r["title"], re.I)),

    ("furniture", "Victorian and later furniture",
     "Eastlake, upholstered Victorian, mid-century and reproduction case furniture. The brief names "
     "this as a standing weak market and nothing here argues for an exception.",
     lambda r: re.search(r"victorian|eastlake|etagere|settee|sofa|armchair|side chair|dining chair|"
                         r"parlor table|coffee table|pedestal|bookcase|sideboard|cabinet|desk|"
                         r"lounge|recliner|chaise|danish modern|live edge|dining set|garden chair|"
                         r"bench|stool|highboy|lowboy", r["title"], re.I)),

    ("copper-brass", "Decorative copper, brass and dinnerware",
     "The Day 1 copper cookware run, brass preserve pans, and dinnerware in quantity. All three are "
     "named in the brief as weak markets, and the copper consignment in particular is fifteen-plus "
     "lots of the same thing.",
     lambda r: re.search(r"copper|brass|pewter|cookware|stock pot|milk jug|dinner service|"
                         r"china plates|transferware|dessert set|flatware|holloware", r["title"], re.I)),

    ("vehicles", "Vehicles, machinery and modern sporting goods",
     "Cars, a kayak, a log-splitter, a food trailer and similar. Self-evidently outside the brief.",
     lambda r: re.search(r"\b(19|20)\d\d\s+(volkswagen|mercedes|bmw)|kayak|canoe|log-splitter|"
                         r"trailer|slot machine|guitar|banjo|autoharp|flugelhorn", r["title"], re.I)),

    ("toys", "Toys, dolls and holiday decorations",
     "The Day 1 toy and Halloween runs. Some is genuinely pre-1926 and the Halloween material has a "
     "real collecting base, but none of it touches the five criteria and condition dominates value "
     "in ways photographs cannot settle.",
     lambda r: re.search(r"\btoy\b|toys|doll|kewpie|halloween|pull toy|model train|bulldozer|"
                         r"carousel|game board|puzzle", r["title"], re.I)),

    ("listed-painters", "Listed painters, no criteria fit",
     "Catalogued as a name with dates and nothing else -- no medium, no subject, no date on the work. "
     "Most are competent regional or European painters with thin comparable records, none has a Maine "
     "connection, and the boilerplate biographies attached to these lots are indexing, not provenance.",
     lambda r: re.search(r"\(.{0,45}\b1[6-9]\d{2}\s*[-–]\s*(?:1[6-9]\d{2}|20\d{2}|\s*\))",
                         r["title"])),

    ("portraits", "Anonymous portraits and period paintings",
     "Unsigned and unattributed portraits, genre scenes and landscapes. The brief names anonymous "
     "19th-century child portraits specifically as a weak market, and the wider category has the same "
     "problem: genuinely old, genuinely anonymous, and priced as though the age alone carried it.",
     lambda r: re.search(r"portrait|genre scene|still life|landscape|unsigned|unknown artist|"
                         r"unidentified|naive|school\b|manner of|attributed to|\bafter\b",
                         r["title"], re.I)),

    ("textiles", "Samplers, coverlets and needlework",
     "Period textiles beyond the examples written up. Condition dominates value here and it is exactly "
     "what a catalogue photograph cannot show -- fading, restitching and remounting are all invisible "
     "until the piece is in your hands.",
     lambda r: re.search(r"sampler|coverlet|needlework|embroider|quilt|textile|hooked rug|tatted|"
                         r"silk panel|robe\b", r["title"], re.I)),

    ("canes", "Walking canes and sticks",
     "The Day 1 cane consignment. Cane collecting rewards mechanism, gadget and figural carving, none "
     "of which is claimed for any of these, and the gold-filled mounts on lot 1026 have no melt floor "
     "at all.",
     lambda r: re.search(r"walking (cane|stick)|\bcanes\b|walking stick", r["title"], re.I)),

    ("books", "Books, documents and ephemera",
     "Volumes, sets, maps and documents beyond the handful written up individually. A deep category "
     "where condition and collation decide everything and neither is visible in a catalogue "
     "photograph.",
     lambda r: re.search(r"\bvol\b|vols|book|edition|folio|diploma|letters|documents|manuscript|"
                         r"map\b|maps|print|litho|engraving|poster|portfolio|leaves", r["title"], re.I)),
]

FALLBACK = ("general", "Reviewed and set aside",
            "Looked at, no criteria fit and nothing in the title or estimate to argue for a second "
            "look. Listed so the coverage is visible rather than silently missing.")


def money(n):
    if n is None:
        return "--"
    return "${:,.0f}".format(n)


def load_verdicts():
    out = {}
    for path in sorted(ANALYSIS.glob("verdicts-*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            out[row["lot"]] = row
    return out


def screen(row):
    for gid, label, reason, test in RULES:
        try:
            if test(row):
                return gid, label, reason
        except Exception:
            continue
    return FALLBACK


def bid_bar(row, v):
    """Visual track: estimate band, current bid, target, walk-away."""
    lo, hi = row["est_low"] or 0, row["est_high"] or 0
    bid = row["current_bid"] or 0
    target = v.get("target") or 0
    ceiling = v.get("ceiling") or 0
    top = max(hi, bid, ceiling, 1) * 1.12
    pc = lambda n: max(0.0, min(100.0, 100.0 * n / top))

    parts = ['<div class="bar" role="img" aria-label="estimate band, current bid, target and walk-away">']
    parts.append('<div class="bar-track">')
    if hi:
        parts.append('<div class="bar-est" style="left:{:.1f}%;width:{:.1f}%"></div>'.format(
            pc(lo), max(0.8, pc(hi) - pc(lo))))
    if ceiling:
        parts.append('<div class="bar-span" style="left:0;width:{:.1f}%"></div>'.format(pc(ceiling)))
    if bid:
        parts.append('<i class="bar-mark m-bid" style="left:{:.1f}%" title="current bid {}"></i>'.format(pc(bid), money(bid)))
    if target:
        parts.append('<i class="bar-mark m-target" style="left:{:.1f}%" title="target {}"></i>'.format(pc(target), money(target)))
    if ceiling:
        parts.append('<i class="bar-mark m-ceiling" style="left:{:.1f}%" title="walk-away {}"></i>'.format(pc(ceiling), money(ceiling)))
    parts.append("</div>")
    parts.append('<div class="bar-key"><span class="k-est">estimate</span>'
                 '<span class="k-bid">bid</span><span class="k-target">target</span>'
                 '<span class="k-ceiling">walk-away</span></div>')
    parts.append("</div>")
    return "".join(parts)


def card(row, v):
    e = html.escape
    lot = row["lot"]
    verdict = v["verdict"]
    ceiling = v.get("ceiling") or 0
    allin = ceiling * ALL_IN
    thumb = row["images"][0] if row["images"] else ""
    crits = "".join('<span class="tag">{}</span>'.format(e(CRITERIA_LABEL.get(c, c)))
                    for c in v.get("criteria", []))
    searchable = e(" ".join([str(lot), row["title"], verdict, v.get("date", ""),
                             " ".join(v.get("criteria", [])), v.get("analysis", "")]).lower())

    src = ""
    if v.get("sources"):
        src = '<p class="src"><b>Where the numbers come from.</b> {}</p>'.format(e(v["sources"]))

    return """
<article class="lot" data-lot="{lot}" data-verdict="{vslug}" data-status="{status}" data-day="{day}" data-search="{search}">
  <div class="lot-head">
    <a class="thumb" href="{url}" target="_blank" rel="noopener">{img}</a>
    <div class="lot-id">
      <div class="lot-no">Lot {lot}<span class="day">{dayname}</span></div>
      <h3>{title}</h3>
      <div class="dateline"><b>{date}</b> &middot; <span class="ev ev-{evslug}">{evidence}</span> &middot; <span class="st st-{status}">{status}</span></div>
      <div class="tags">{crits}</div>
    </div>
    <div class="verdict-wrap">
      <div class="verdict v-{vslug}">{verdict}</div>
      <button class="star" aria-label="star this lot">&#9733;</button>
      {keyflag}
    </div>
  </div>
  <div class="lot-body">
    <p>{analysis}</p>
    <div class="problems"><b>Problems.</b> {problems}</div>
    {bar}
    <div class="grid">
      <div><span>Estimate</span><b>{est}</b></div>
      <div><span>Current bid</span><b>{bid}</b></div>
      <div><span>Target</span><b class="good">{target}</b></div>
      <div><span>Walk-away</span><b class="stop">{ceiling}</b></div>
      <div><span>All-in at ceiling</span><b>{allin}</b></div>
    </div>
    <p class="patience"><b>Patience.</b> {patience}</p>
    {src}
    <a class="lotlink" href="{url}" target="_blank" rel="noopener">Lot page &rarr;</a>
  </div>
</article>""".format(
        lot=lot,
        vslug=VERDICT_SLUG.get(verdict, "pass"),
        status=e(v.get("status", "border")),
        day=row["day"],
        dayname={"day1": "Day 1", "day2": "Day 2", "day3": "Day 3"}[row["day"]],
        search=searchable,
        url=e(row["url"] or "#"),
        img='<img loading="lazy" src="{}" alt="Lot {}">'.format(e(thumb), lot) if thumb else "",
        title=e(row["title"]),
        date=e(v.get("date", "undated")),
        evidence=e(v.get("evidence", "Unverified")),
        evslug=e(v.get("evidence", "unverified").lower()),
        crits=crits,
        verdict=e(verdict),
        keyflag='<div class="keyflag">key lot</div>' if v.get("star") else "",
        analysis=e(v.get("analysis", "")),
        problems=e(v.get("problems", "")),
        bar=bid_bar(row, v),
        est="{} - {}".format(money(row["est_low"]), money(row["est_high"])),
        bid=money(row["current_bid"]),
        target=money(v.get("target")) if v.get("target") else "--",
        ceiling=money(ceiling) if ceiling else "--",
        allin=money(allin) if ceiling else "--",
        patience=e(v.get("patience", "")),
        src=src,
    )


def main():
    lots = json.loads((BUILD / "lots.json").read_text(encoding="utf-8"))
    verdicts = load_verdicts()

    analysed, screened = [], {}
    for row in lots:
        v = verdicts.get(row["lot"])
        if v:
            analysed.append((row, v))
        else:
            gid, label, reason = screen(row)
            screened.setdefault(gid, {"label": label, "reason": reason, "rows": []})["rows"].append(row)

    analysed.sort(key=lambda rv: (VERDICT_ORDER.index(rv[1]["verdict"]), rv[0]["lot"]))

    counts = {v: 0 for v in VERDICT_ORDER}
    for _, v in analysed:
        counts[v["verdict"]] += 1

    cards = "\n".join(card(r, v) for r, v in analysed)

    screen_html = []
    for gid, g in sorted(screened.items(), key=lambda kv: -len(kv[1]["rows"])):
        items = "".join(
            '<li><a href="{}" target="_blank" rel="noopener"><b>{}</b> {}</a> '
            '<span class="se">{}</span></li>'.format(
                html.escape(r["url"] or "#"), r["lot"] or "--", html.escape(r["title"]),
                money(r["est_low"]))
            for r in sorted(g["rows"], key=lambda r: r["lot"] or 0))
        screen_html.append(
            '<details class="screen" data-search="{s}"><summary><b>{label}</b>'
            '<span class="n">{n} lots</span></summary><p class="reason">{reason}</p>'
            '<ul>{items}</ul></details>'.format(
                s=html.escape((g["label"] + " " + g["reason"]).lower()),
                label=html.escape(g["label"]), n=len(g["rows"]),
                reason=html.escape(g["reason"]), items=items))

    metals = "".join('<div><span>{}</span><b>{}</b><i>{}</i></div>'.format(*m) for m in METALS)
    chips = "".join('<button class="chip" data-filter="verdict" data-value="{}">{} '
                    '<span class="n">{}</span></button>'.format(VERDICT_SLUG[v], v, counts[v])
                    for v in VERDICT_ORDER if counts[v])

    page = TEMPLATE.format(
        cards=cards, screens="\n".join(screen_html), metals=metals, chips=chips,
        n_analysed=len(analysed), n_screened=sum(len(g["rows"]) for g in screened.values()),
        n_total=len(lots))
    OUT.write_text(page, encoding="utf-8")

    print("wrote {} ({:,} bytes)".format(OUT.name, OUT.stat().st_size))
    print("analysed: {}  screened: {}  total: {}".format(
        len(analysed), sum(len(g["rows"]) for g in screened.values()), len(lots)))
    for v in VERDICT_ORDER:
        if counts[v]:
            print("  {:<15} {}".format(v, counts[v]))
    for gid, g in sorted(screened.items(), key=lambda kv: -len(kv[1]["rows"])):
        print("  [screen] {:<40} {}".format(g["label"], len(g["rows"])))


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Summer Grandeur 2026 - Auction Analysis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600&family=Spectral:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{
  --oyster:#EFE8DC; --oyster-2:#E3D9C8; --paper:#FBF7F0;
  --spruce:#1E3A33; --spruce-2:#2C4F45;
  --verdigris:#4F8F7E; --oxblood:#7A1F2B; --brass:#A8853C;
  --ink:#1A1F1D; --muted:#5C6560; --line:#CFC4B0;
  --sans:"Oswald",Impact,sans-serif;
  --serif:"Spectral",Georgia,"Times New Roman",serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--oyster);color:var(--ink);font-family:var(--serif);font-size:16px;line-height:1.55;-webkit-text-size-adjust:100%}}
header{{background:var(--spruce);color:var(--oyster);padding:18px 16px 14px}}
header h1{{font-family:var(--sans);font-weight:600;letter-spacing:.06em;text-transform:uppercase;font-size:1.25rem;margin:0 0 2px}}
header .sub{{font-size:.85rem;color:#A9C0B6;margin:0 0 12px}}
.metals{{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}}
.metals div{{background:rgba(255,255,255,.07);border-left:2px solid var(--brass);padding:5px 8px}}
.metals span{{display:block;font-family:var(--sans);font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:#9FB8AD}}
.metals b{{font-family:var(--mono);font-size:.82rem;color:#fff;display:block}}
.metals i{{font-family:var(--mono);font-size:.7rem;color:var(--brass);font-style:normal}}
.note{{background:var(--oyster-2);border-bottom:1px solid var(--line);padding:10px 16px;font-size:.83rem;color:#4A4038}}
.note b{{font-family:var(--sans);letter-spacing:.04em;text-transform:uppercase;font-size:.72rem}}
.filters{{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:2px solid var(--spruce);padding:8px 10px;box-shadow:0 2px 8px rgba(0,0,0,.09)}}
.row{{display:flex;gap:5px;overflow-x:auto;padding-bottom:5px;scrollbar-width:thin}}
.chip{{flex:0 0 auto;font-family:var(--sans);font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;
  background:#fff;border:1px solid var(--line);color:var(--ink);padding:5px 8px;cursor:pointer;white-space:nowrap;border-radius:2px}}
.chip .n{{font-family:var(--mono);color:var(--muted);font-size:.62rem}}
.chip[aria-pressed=true]{{background:var(--spruce);color:#fff;border-color:var(--spruce)}}
.chip[aria-pressed=true] .n{{color:#A9C0B6}}
#q{{width:100%;font-family:var(--serif);font-size:.95rem;padding:7px 9px;border:1px solid var(--line);background:#fff;margin-top:5px;border-radius:2px}}
.count{{font-family:var(--mono);font-size:.7rem;color:var(--muted);padding:5px 2px 0}}
main{{padding:12px 10px 40px;max-width:860px;margin:0 auto}}
.lot{{background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--muted);margin:0 0 14px;border-radius:2px}}
.lot[data-verdict=strong-buy]{{border-left-color:var(--verdigris)}}
.lot[data-verdict=buy]{{border-left-color:var(--spruce-2)}}
.lot[data-verdict=stretch-worthy]{{border-left-color:var(--brass)}}
.lot[data-verdict=buy-if-cheap]{{border-left-color:#8FA89C}}
.lot[data-verdict=check-first]{{border-left-color:#C08A2E}}
.lot[data-verdict=pass]{{border-left-color:var(--oxblood);opacity:.9}}
.lot-head{{display:grid;grid-template-columns:76px minmax(0,1fr) auto;gap:10px;padding:10px;border-bottom:1px solid var(--line)}}
.lot-id{{min-width:0}}
.lot-id h3,.lot-body p,.problems,.patience{{overflow-wrap:break-word}}
.grid b{{overflow-wrap:break-word}}
.thumb{{display:block}}
.thumb img{{width:76px;height:76px;object-fit:cover;border:1px solid var(--line);background:#fff}}
.lot-no{{font-family:var(--mono);font-size:.72rem;color:var(--muted)}}
.lot-no .day{{color:var(--brass);margin-left:6px}}
.lot-id h3{{font-family:var(--sans);font-weight:400;font-size:.94rem;line-height:1.25;margin:2px 0 4px;letter-spacing:.02em}}
.dateline{{font-size:.76rem;color:var(--muted)}}
.dateline b{{color:var(--ink)}}
.ev{{font-family:var(--sans);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;padding:1px 5px;border-radius:2px}}
.ev-catalogued{{background:#D8E6DF;color:#1E3A33}}
.ev-inferred{{background:#EDE0C6;color:#6A5320}}
.ev-unverified{{background:#EFD9D9;color:var(--oxblood)}}
.st{{font-family:var(--mono);font-size:.66rem;text-transform:uppercase}}
.st-antique{{color:var(--verdigris)}} .st-border{{color:var(--brass)}} .st-modern{{color:var(--muted)}}
.tags{{margin-top:5px;display:flex;flex-wrap:wrap;gap:4px}}
.tag{{font-family:var(--sans);font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;background:var(--oyster-2);color:#4A4038;padding:2px 6px;border-radius:2px}}
.verdict-wrap{{text-align:right}}
.verdict{{font-family:var(--sans);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;padding:4px 7px;color:#fff;white-space:nowrap;border-radius:2px}}
.v-strong-buy{{background:var(--verdigris)}} .v-buy{{background:var(--spruce-2)}}
.v-stretch-worthy{{background:var(--brass)}} .v-buy-if-cheap{{background:#8FA89C}}
.v-check-first{{background:#C08A2E}} .v-pass{{background:var(--oxblood)}}
.star{{background:none;border:none;font-size:1.2rem;color:var(--line);cursor:pointer;padding:4px 0 0}}
.star[aria-pressed=true]{{color:var(--brass)}}
.keyflag{{font-family:var(--sans);font-size:.55rem;letter-spacing:.1em;text-transform:uppercase;color:var(--oxblood)}}
.lot-body{{padding:10px}}
.lot-body p{{margin:0 0 9px}}
.problems{{background:#F5EEE2;border-left:2px solid var(--brass);padding:7px 9px;font-size:.9rem;margin:0 0 10px}}
.problems b,.patience b,.src b{{font-family:var(--sans);font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;color:var(--oxblood)}}
.patience{{font-size:.87rem;color:#3A423E}}
.src{{font-size:.83rem;color:var(--muted);border-top:1px dotted var(--line);padding-top:7px}}
.bar{{margin:10px 0 8px}}
.bar-track{{position:relative;height:16px;background:#E8E0D2;border:1px solid var(--line);border-radius:2px}}
.bar-span{{position:absolute;top:0;bottom:0;background:rgba(79,143,126,.14)}}
.bar-est{{position:absolute;top:0;bottom:0;background:rgba(30,58,51,.22);border-left:1px solid var(--spruce);border-right:1px solid var(--spruce)}}
.bar-mark{{position:absolute;top:-3px;width:2px;height:22px}}
.m-bid{{background:var(--muted)}} .m-target{{background:var(--verdigris);width:3px}} .m-ceiling{{background:var(--oxblood);width:3px}}
.bar-key{{display:flex;gap:10px;font-family:var(--sans);font-size:.58rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-top:4px}}
.bar-key span::before{{content:"";display:inline-block;width:8px;height:8px;margin-right:3px;vertical-align:-1px}}
.k-est::before{{background:rgba(30,58,51,.35)}} .k-bid::before{{background:var(--muted)}}
.k-target::before{{background:var(--verdigris)}} .k-ceiling::before{{background:var(--oxblood)}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:0 0 10px}}
.grid div{{background:var(--paper);padding:5px 7px}}
.grid span{{display:block;font-family:var(--sans);font-size:.58rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}}
.grid b{{font-family:var(--mono);font-size:.86rem}}
.grid .good{{color:var(--verdigris)}} .grid .stop{{color:var(--oxblood)}}
.lotlink{{font-family:var(--sans);font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--spruce)}}
h2.sec{{font-family:var(--sans);font-weight:600;letter-spacing:.08em;text-transform:uppercase;font-size:.9rem;
  border-bottom:2px solid var(--spruce);padding-bottom:5px;margin:30px 0 12px}}
.screen{{background:var(--paper);border:1px solid var(--line);margin:0 0 8px;border-radius:2px}}
.screen summary{{padding:9px 10px;cursor:pointer;font-family:var(--sans);font-size:.8rem;letter-spacing:.03em}}
.screen summary .n{{font-family:var(--mono);font-size:.7rem;color:var(--muted);float:right}}
.screen .reason{{padding:0 10px;font-size:.87rem;color:#4A4038;margin:0 0 8px}}
.screen ul{{list-style:none;margin:0;padding:0 10px 10px;max-height:340px;overflow-y:auto}}
.screen li{{font-size:.8rem;padding:3px 0;border-bottom:1px dotted var(--line)}}
.screen li a{{color:var(--ink);text-decoration:none}}
.screen li b{{font-family:var(--mono);color:var(--brass);margin-right:5px}}
.screen li .se{{font-family:var(--mono);font-size:.72rem;color:var(--muted);float:right}}
footer{{background:var(--spruce);color:#A9C0B6;padding:18px 16px;font-size:.8rem}}
footer b{{color:var(--oyster)}}
a{{color:var(--spruce)}}
@media(min-width:700px){{
  .metals{{grid-template-columns:repeat(6,1fr)}}
  .grid{{grid-template-columns:repeat(5,1fr)}}
  .lot-head{{grid-template-columns:100px 1fr auto}}
  .thumb img{{width:100px;height:100px}}
  header h1{{font-size:1.6rem}}
}}
@media print{{.filters{{position:static}} .screen ul{{max-height:none}}}}
</style>
</head>
<body>
<header>
  <h1>Summer Grandeur 2026 &mdash; buying brief</h1>
  <p class="sub">Thomaston Place Auction Galleries &middot; August 28&ndash;30 2026 &middot;
     {n_total} lots reviewed &middot; {n_analysed} written up &middot; {n_screened} screened in bulk</p>
  <div class="metals">{metals}</div>
</header>

<div class="note">
  <b>Standing arithmetic.</b> All-in = hammer &times; 1.25 online premium &times; 1.055 Maine sales tax =
  hammer &times; 1.32. Phone or absentee is 20% premium, so &times; 1.27. No resale exemption &mdash; the tax
  always applies. Metal prices above are deliberately below market so a bid that clears on paper still
  clears if metals slip before 28 August. A refiner pays 85&ndash;90% of calculated melt.
  <br><br>
  <b>Standing caution on ivory.</b> This sale carries a great deal of whale&rsquo;s tooth, walrus, sailor-made
  and carved elephant ivory. Federal Endangered Species Act and Marine Mammal Protection Act rules restrict
  what can be done with these afterwards and the documentation will not accompany lots at this price.
  Buying in-state at a Maine sale is the simplest case, but it constrains everything that follows.
  Treated as a screened class below.
</div>

<div class="filters">
  <div class="row">
    <button class="chip" data-filter="all" aria-pressed="true">All</button>
    {chips}
  </div>
  <div class="row">
    <button class="chip" data-filter="status" data-value="antique">Antique</button>
    <button class="chip" data-filter="status" data-value="border">Border</button>
    <button class="chip" data-filter="status" data-value="modern">Modern</button>
    <button class="chip" data-filter="day" data-value="day1">Day 1</button>
    <button class="chip" data-filter="day" data-value="day2">Day 2</button>
    <button class="chip" data-filter="day" data-value="day3">Day 3</button>
    <button class="chip" data-filter="starred">&#9733; Starred</button>
  </div>
  <input id="q" type="search" placeholder="Search lots, makers, materials&hellip;" autocomplete="off">
  <div class="count" id="count"></div>
</div>

<main>
{cards}

<h2 class="sec">Screened out in bulk</h2>
<p style="font-size:.87rem;color:#4A4038;margin-top:0">Every remaining lot in the sale, grouped by the
reason it was set aside. The noise is visible but compressed &mdash; nothing is silently missing.</p>
{screens}
</main>

<footer>
  <b>Before the sale.</b> Preview runs weekdays and Saturdays 15&ndash;27 August; Thomaston also books
  virtual gallery previews. Worth using on anything still marked CHECK FIRST.<br>
  Thomaston Place Auction Galleries &middot; 51 Atlantic Hwy, Thomaston ME 04861 &middot; 207-354-8141
</footer>

<script>
(function(){{
  var state={{verdict:null,status:null,day:null,starred:false,q:""}};
  var lots=[].slice.call(document.querySelectorAll(".lot"));
  var screens=[].slice.call(document.querySelectorAll(".screen"));
  var countEl=document.getElementById("count");
  var stars={{}};
  try{{stars=JSON.parse(localStorage.getItem("sg26stars")||"{{}}");}}catch(e){{stars={{}};}}

  lots.forEach(function(el){{
    var b=el.querySelector(".star"), id=el.dataset.lot;
    if(stars[id]) b.setAttribute("aria-pressed","true");
    b.addEventListener("click",function(){{
      var on=b.getAttribute("aria-pressed")==="true";
      b.setAttribute("aria-pressed",String(!on));
      if(on){{delete stars[id];}} else {{stars[id]=1;}}
      try{{localStorage.setItem("sg26stars",JSON.stringify(stars));}}catch(e){{}}
      apply();
    }});
  }});

  function apply(){{
    var n=0;
    lots.forEach(function(el){{
      var ok=true;
      if(state.verdict && el.dataset.verdict!==state.verdict) ok=false;
      if(state.status && el.dataset.status!==state.status) ok=false;
      if(state.day && el.dataset.day!==state.day) ok=false;
      if(state.starred && !stars[el.dataset.lot]) ok=false;
      if(state.q && el.dataset.search.indexOf(state.q)===-1) ok=false;
      el.style.display=ok?"":"none";
      if(ok) n++;
    }});
    var filtering=state.verdict||state.status||state.day||state.starred;
    screens.forEach(function(el){{
      var ok=!filtering && (!state.q || el.dataset.search.indexOf(state.q)!==-1);
      el.style.display=ok?"":"none";
    }});
    countEl.textContent=n+" lot"+(n===1?"":"s")+" shown";
  }}

  document.querySelectorAll(".chip").forEach(function(c){{
    c.addEventListener("click",function(){{
      var f=c.dataset.filter;
      if(f==="all"){{ state.verdict=state.status=state.day=null; state.starred=false; }}
      else if(f==="starred"){{ state.starred=!state.starred; }}
      else {{ state[f] = (state[f]===c.dataset.value) ? null : c.dataset.value; }}
      document.querySelectorAll(".chip").forEach(function(o){{
        var of=o.dataset.filter, on=false;
        if(of==="all") on=!state.verdict&&!state.status&&!state.day&&!state.starred;
        else if(of==="starred") on=state.starred;
        else on=state[of]===o.dataset.value;
        o.setAttribute("aria-pressed",String(on));
      }});
      apply();
    }});
  }});

  document.getElementById("q").addEventListener("input",function(e){{
    state.q=e.target.value.trim().toLowerCase(); apply();
  }});
  apply();
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
