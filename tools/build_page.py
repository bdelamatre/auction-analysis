#!/usr/bin/env python3
"""Merge the scraped lot data with the hand-written verdicts and emit the page.

    python3 tools/parse_lots.py && python3 tools/build_page.py
    python3 tools/build_page.py --embed      # also write a self-contained copy
                                            # with thumbnails inlined as data URIs

Reads build/lots.json, analysis/verdicts-day*.json and analysis/valuations.json,
assigns every lot that has no written verdict to a bulk-screening group, classifies
all 1,500 lots by category and period, and writes a single HTML file.

--embed additionally writes summer-grandeur-2026.embedded.html, which needs no
local files at all -- for publishing where data/ is not reachable.
"""

import argparse
import base64
import html
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ANALYSIS = ROOT / "analysis"
OUT = ROOT / "summer-grandeur-2026.html"
OUT_EMBED = ROOT / "summer-grandeur-2026.embedded.html"
OUT_ART = ROOT / "summer-grandeur-2026.artifact.html"

PREMIUM, TAX = 1.25, 1.055
ALL_IN = PREMIUM * TAX          # 1.319 -> the brief's 1.32
REFINER = 0.87                  # middle of the 85-90% a refiner pays

# Working spot from the brief -- deliberately below market.
RATES = {
    "sterling": (1.49, "Sterling .925"),
    "coin": (1.449, "Coin silver .900"),
    "fine_silver": (1.61, "Fine silver"),
    "gold_10k": (53.63, "10K gold .417"),
    "gold_14k": (75.23, "14K gold .585"),
    "gold_18k": (96.45, "18K gold .750"),
    "gold_filled": (0.0, "Gold-filled"),
    "plated": (0.0, "Plated"),
    "none": (0.0, "No precious metal"),
}

METALS = [
    ("Gold", "$4,000/ozt", "$128.60/g"), ("Silver", "$50/ozt", "$1.61/g"),
    ("Sterling .925", "-", "$1.49/g"), ("10K .417", "-", "$53.63/g"),
    ("14K .585", "-", "$75.23/g"), ("18K .750", "-", "$96.45/g"),
]

VERDICT_ORDER = ["STRONG BUY", "BUY", "STRETCH-WORTHY", "BUY IF CHEAP", "CHECK FIRST", "PASS"]
VERDICT_SLUG = {v: v.lower().replace(" ", "-") for v in VERDICT_ORDER}

CRITERIA_LABEL = {"antique": "True antique", "metal": "Precious metal", "nouveau": "Art Nouveau",
                  "named": "Named maker", "maine": "Maine coastal", "marine": "Marine"}

CATEGORIES = [
    ("jewellery", "Jewellery"), ("watches", "Watches & clocks"), ("silver", "Silver & gold"),
    ("painting", "Paintings"), ("prints", "Prints & works on paper"), ("furniture", "Furniture & boxes"),
    ("ceramics", "Ceramics & vases"), ("glass", "Glass"), ("sculpture", "Sculpture & bronzes"),
    ("marine", "Marine & whaling"), ("books", "Books, maps & ephemera"), ("textiles", "Textiles & rugs"),
    ("tools", "Tools & instruments"), ("folkart", "Folk art & trade signs"), ("arms", "Arms & militaria"),
    ("toys", "Toys & games"), ("vehicles", "Vehicles & equipment"), ("decorative", "Decorative & other"),
]
PERIODS = [
    ("pre1700", "17th c. & earlier"), ("georgian", "Georgian / 18th c."),
    ("federal", "Federal / early 19th c."), ("victorian", "Victorian / 19th c."),
    ("nouveau", "Art Nouveau & Arts and Crafts"), ("edwardian", "Edwardian / c.1900-1920"),
    ("deco", "Art Deco / 1920s-30s"), ("midcentury", "Mid-century"),
    ("contemporary", "Contemporary"), ("undetermined", "Undetermined"),
]
CAT_LABEL, PER_LABEL = dict(CATEGORIES), dict(PERIODS)

# Category classification from the title, applied in order. Hand-set values in
# valuations.json always win.
CAT_RULES = [
    ("vehicles", r"volkswagen|mercedes|\bbmw\b|canoe|kayak|trailer|log-splitter|slot machine"),
    ("arms", r"shotgun|rifle|pistol|revolver|carbine|derringer|mauser|musket|dagger|sword|"
             r"powder horn|cartridge box|bayonet|\bscope\b|holster|bullet knive|gun belt"),
    ("jewellery", r"\b(?:10|14|18|22)k\b|platinum|brooch|necklace|bracelet|earring|earclip|"
                  r"pendant|\bring\b|locket|lorgnette|intaglio|cameo|solitaire|belt buckle|"
                  r"jewelry suite|dress gent|watch fob|pill box"),
    ("watches", r"\bwatch\b|wristwatch|chronograph|rolex|patek|omega|breitling|seiko|cartier|"
                r"\bclock\b|regulator|atmos|ebel|hamilton cross"),
    ("marine", r"\bship|marine|nautical|whal|scrimshaw|sextant|pelorus|compass|half hull|"
               r"telescope|sea chest|harpoon|blubber|flensing|figurehead|sternboard|schooner|"
               r"yacht|lighthouse|nantucket|sailor|logbook|rigging|mariner|steamship"),
    ("silver", r"sterling|coin silver|\bsilver\b|vermeil|tazza|tankard|flatware|holloware|"
               r"compote|bride'?s basket|condiment set|teaspoon|ladle|skewer"),
    ("prints", r"\bprint\b|prints|litho|etching|engraving|woodblock|wood engraving|serigraph|"
               r"gicl|collograph|collagraph|\bposter\b|portfolio|drawings?\b|currier"),
    ("painting", r"painting|oil on|watercolor|watercolour|\bw/c\b|gouache|pastel|portrait|"
                 r"landscape|still life|harbor scene|seascape"),
    ("sculpture", r"bronze|spelter|sculpture|\bbust\b|statue|figurine|carving|bookends|"
                  r"weathervane|weather vane|maquette|fountainhead"),
    ("textiles", r"\brug\b|carpet|kelim|kilim|runner|sampler|coverlet|needlework|embroider|"
                 r"quilt|textile|\bflag\b|\brobe\b|silk (skirt|panel)|tapestry"),
    ("books", r"\bbook|\bvols?\b|edition|folio|\bmap\b|maps|document|letter|manuscript|ledger|"
              r"diploma|postcard|broadside|ephemera|leaves|prospectus|almanac|catalog"),
    ("tools", r"\btool|instrument|bit brace|caliper|drafting|barometer|hygrometer|microscope|"
              r"\blevel\b|plane\b|watchmaker"),
    ("toys", r"\btoys?\b|\bdoll|kewpie|halloween|game board|checkerboard|puzzle|carousel|"
             r"model train|pull toy|bulldozer|mahjong|dominoes"),
    ("folkart", r"trade sign|tavern sign|\bsign\b|decoy|butter stamp|santos|folk art|"
                r"cigar store|\beagle\b"),
    ("glass", r"\bglass\b|crystal|cloche|goblet|decanter|scent|paperweight|peking|steuben|"
              r"loetz|\bdaum\b|lalique"),
    ("ceramics", r"porcelain|pottery|stoneware|redware|\bchina\b|faience|majolica|delft|"
                 r"\bcrock\b|\bjug\b|ceramic|charger|\bplates?\b|\bvase|meissen|minton|"
                 r"wedgwood|roseville|celadon|iznik|\bbowls?\b|\burns?\b|censer"),
    ("furniture", r"\bchair|table|\bchest\b|\bdesk\b|cupboard|sideboard|settee|\bsofa\b|bureau|"
                  r"dresser|\bstand\b|\bbench\b|\bbed\b|cabinet|highboy|etagere|pedestal|"
                  r"bookcase|\bstool\b|mirror|\bbox\b|caddy|trunk|icebox|easel|coffer|commode"),
]

PER_RULES = [
    ("pre1700", r"1[45]\d\d|16[0-9]\d|1[567]th c|16th century|17th century|renaissance|"
                r"elizabethan|jacobean|cromwell|habsburg"),
    ("nouveau", r"nouveau|gall[eé]|tiffany studios|loetz|majorelle|arts (and|&) crafts|"
                r"secession|jugendstil"),
    ("deco", r"\bdeco\b|192\d|193\d|1920'?s|1930'?s"),
    ("georgian", r"18th c|17[0-9]\d|george i{1,3}\b|george (i|ii|iii)\b|queen anne|chippendale|"
                 r"hepplewhite|sheraton|colonial|william (and|&) mary|rococo|louis x[vi]+"),
    ("federal", r"federal|early 19th|18[0-2]\d|empire|regency|napoleonic|war of 1812"),
    ("victorian", r"victorian|19th c|18[3-9]\d|eastlake|civil war|gothic revival|qajar|"
                  r"late 19th|mid 19th|mid-19th"),
    ("edwardian", r"edwardian|circa 1900|ca\.? 1900|c\.1900|19[01]\d|early 20th"),
    ("midcentury", r"mid-?century|194\d|195\d|196\d|197\d|danish modern|atomic"),
    ("contemporary", r"contemporary|198\d|199\d|20[0-2]\d|\bb\. 19[4-9]\d"),
]
CAT_RULES = [(k, re.compile(v, re.I)) for k, v in CAT_RULES]
PER_RULES = [(k, re.compile(v, re.I)) for k, v in PER_RULES]
ARTIST_DATES = re.compile(r"\b(1[5-9]\d{2})\s*[-–]\s*(1[5-9]\d{2}|20[0-2]\d)\b")


def classify(row):
    """(category, period) from the title. Hand-set values override this."""
    title = row["title"]
    cat = "decorative"
    for key, rx in CAT_RULES:
        if rx.search(title):
            cat = key
            break
    per = None
    for key, rx in PER_RULES:
        if rx.search(title):
            per = key
            break
    if per is None:
        m = ARTIST_DATES.search(title)
        if m:                      # bucket a listed artist by their death year
            d = int(m.group(2))
            per = ("georgian" if d < 1800 else "federal" if d < 1840 else
                   "victorian" if d < 1901 else "edwardian" if d < 1915 else
                   "deco" if d < 1940 else "midcentury" if d < 1975 else "contemporary")
    return cat, per or "undetermined"


def money(n):
    return "--" if n is None else "${:,.0f}".format(n)


def rng(pair):
    if not pair:
        return "--"
    lo, hi = pair
    return money(lo) if lo == hi else "{} - {}".format(money(lo), money(hi))


def load_verdicts():
    out = {}
    for path in sorted(ANALYSIS.glob("verdicts-*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            out[row["lot"]] = row
    return out


def load_valuations():
    data = json.loads((ANALYSIS / "valuations.json").read_text(encoding="utf-8"))
    return {r["lot"]: r for r in data["lots"]}, data["_method"]


def melt_figures(spec):
    """-> (label, melt range, refiner range, basis) with melt ranges as ints."""
    rate, label = RATES.get(spec.get("metal", "none"), (0.0, "Unknown metal"))
    if not rate or not spec.get("net_g"):
        return label, None, None, spec.get("note") or spec.get("basis", "")
    lo, hi = spec["net_g"]
    factor = spec.get("refiner", REFINER)
    melt = [round(lo * rate), round(hi * rate)]
    refined = [round(melt[0] * factor), round(melt[1] * factor)]
    return label, melt, refined, spec.get("basis", "")
# ---------------------------------------------------------------------------
# Bulk screening. Applied in order to every lot with no written verdict.
# ---------------------------------------------------------------------------
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
    ("jewellery-screen", "Fine jewellery and wristwatches",
     "Around eighty Day 3 lots of diamond, platinum and karat-gold jewellery and Swiss watches. Almost "
     "all of it is estimated well above the band, and where the gold is genuinely the point the melt "
     "sits far below the estimate because you are paying for stones and signatures. The few that clear "
     "on metal are written up individually with their melt worked out.",
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
    ("listed-painters", "Listed painters, no criteria fit",
     "Catalogued as a name with dates and nothing else -- no medium, no subject, no date on the work. "
     "Most are competent regional or European painters with thin comparable records, none has a Maine "
     "connection, and the boilerplate biographies attached to these lots are indexing, not provenance.",
     lambda r: re.search(r"\(.{0,45}\b1[6-9]\d{2}\s*[-–]\s*(?:1[6-9]\d{2}|20\d{2}|\s*\))", r["title"])),
    ("portraits", "Anonymous portraits and period paintings",
     "Unsigned and unattributed portraits, genre scenes and landscapes. The brief names anonymous "
     "19th-century child portraits specifically as a weak market, and the wider category has the same "
     "problem: genuinely old, genuinely anonymous, and priced as though the age alone carried it.",
     lambda r: re.search(r"portrait|genre scene|still life|landscape|unsigned|unknown artist|"
                         r"unidentified|naive|school\b|manner of|attributed to|\bafter\b",
                         r["title"], re.I)),
    ("textiles-screen", "Samplers, coverlets and needlework",
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
    ("furniture-screen", "Victorian and later furniture",
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
    ("vehicles-screen", "Vehicles, machinery and modern sporting goods",
     "Cars, a kayak, a log-splitter, a food trailer and similar. Self-evidently outside the brief.",
     lambda r: re.search(r"\b(19|20)\d\d\s+(volkswagen|mercedes|bmw)|kayak|canoe|log-splitter|"
                         r"trailer|slot machine|guitar|banjo|autoharp|flugelhorn", r["title"], re.I)),
    ("toys-screen", "Toys, dolls and holiday decorations",
     "The Day 1 toy and Halloween runs. Some is genuinely pre-1926 and the Halloween material has a "
     "real collecting base, but none of it touches the five criteria and condition dominates value "
     "in ways photographs cannot settle.",
     lambda r: re.search(r"\btoy\b|toys|doll|kewpie|halloween|pull toy|model train|bulldozer|"
                         r"carousel|game board|puzzle", r["title"], re.I)),
    ("books-screen", "Books, documents and ephemera",
     "Volumes, sets, maps and documents beyond the handful written up individually. A deep category "
     "where condition and collation decide everything and neither is visible in a catalogue "
     "photograph.",
     lambda r: re.search(r"\bvol\b|vols|book|edition|folio|diploma|letters|documents|manuscript|"
                         r"map\b|maps|print|litho|engraving|poster|portfolio|leaves", r["title"], re.I)),
]
FALLBACK = ("general", "Reviewed and set aside",
            "Looked at, no criteria fit and nothing in the title or estimate to argue for a second "
            "look. Listed so the coverage is visible rather than silently missing.")


def screen(row):
    for gid, label, reason, test in RULES:
        try:
            if test(row):
                return gid, label, reason
        except Exception:
            continue
    return FALLBACK


def bid_bar(row, v):
    lo, hi = row["est_low"] or 0, row["est_high"] or 0
    bid, target = row["current_bid"] or 0, v.get("target") or 0
    ceiling = v.get("ceiling") or 0
    top = max(hi, bid, ceiling, 1) * 1.12
    pc = lambda n: max(0.0, min(100.0, 100.0 * n / top))
    p = ['<div class="bar"><div class="bar-track">']
    if hi:
        p.append('<div class="bar-est" style="left:{:.1f}%;width:{:.1f}%"></div>'.format(
            pc(lo), max(0.8, pc(hi) - pc(lo))))
    if ceiling:
        p.append('<div class="bar-span" style="width:{:.1f}%"></div>'.format(pc(ceiling)))
    for cls, val in (("m-bid", bid), ("m-target", target), ("m-ceiling", ceiling)):
        if val:
            p.append('<i class="bar-mark {}" style="left:{:.1f}%"></i>'.format(cls, pc(val)))
    p.append('</div><div class="bar-key"><span class="k-est">estimate</span><span class="k-bid">bid</span>'
             '<span class="k-target">target</span><span class="k-ceiling">walk-away</span></div></div>')
    return "".join(p)


def metal_block(val):
    spec = val.get("melt")
    if not spec:
        return ""
    label, melt, refined, basis = melt_figures(spec)
    gems = val.get("gems")
    rows = ['<div class="metal"><div class="metal-h">Metal &amp; stones</div>']
    if melt:
        rows.append('<div class="mrow"><span>{}</span><b>{}</b></div>'.format(html.escape(label), rng(melt)))
        rows.append('<div class="mrow"><span>Refiner net (87%)</span><b>{}</b></div>'.format(rng(refined)))
    else:
        rows.append('<div class="mrow"><span>{}</span><b class="nil">no melt floor</b></div>'.format(
            html.escape(label)))
    if gems and gems.get("resale"):
        g = gems["resale"]
        rows.append('<div class="mrow"><span>Stones, resale</span><b>{}</b></div>'.format(
            "nil" if g == [0, 0] else rng(g)))
    if basis:
        rows.append('<p class="mnote"><b>Weight basis (my estimate, not catalogued).</b> {}</p>'.format(
            html.escape(basis)))
    if gems and gems.get("note"):
        rows.append('<p class="mnote"><b>Stones.</b> {}</p>'.format(html.escape(gems["note"])))
    rows.append("</div>")
    return "".join(rows)


def card(row, v, val, thumb_src):
    e = html.escape
    lot, verdict = row["lot"], v["verdict"]
    ceiling = v.get("ceiling") or 0
    allin = ceiling * ALL_IN
    market, resale = val.get("market"), val.get("resale")
    cat, per = val.get("category"), val.get("period")
    if not cat or not per:
        c2, p2 = classify(row)
        cat, per = cat or c2, per or p2

    spec = val.get("melt") or {}
    _, melt, refined, _ = melt_figures(spec) if spec else (None, None, None, None)
    # Midpoint of my market range, not the low end: the low end is the pessimistic
    # case and made almost every lot look negative. But where the range spans more
    # than 3x it encodes UNCERTAINTY (an unresolved medium, period or process), not
    # market variance, and a midpoint there is meaningless -- so no margin is shown
    # and the lot is kept out of the value ranking rather than topping it.
    margin = None
    if market and v.get("target") and market[0] and market[1] / market[0] <= 3:
        margin = sum(market) / 2 - v["target"] * ALL_IN

    crits = "".join('<span class="tag">{}</span>'.format(e(CRITERIA_LABEL.get(c, c)))
                    for c in v.get("criteria", []))
    spread = ('<p class="spread"><b>Why the range is wide.</b> {}</p>'.format(e(val["spread"]))
              if val.get("spread") else "")
    src = ('<p class="src"><b>Where the numbers come from.</b> {}</p>'.format(e(v["sources"]))
           if v.get("sources") else "")
    searchable = e(" ".join([str(lot), row["title"], verdict, v.get("date", ""),
                             CAT_LABEL.get(cat, ""), PER_LABEL.get(per, ""),
                             " ".join(v.get("criteria", [])), v.get("analysis", "")]).lower())

    return """
<article class="entry card" data-lot="{lot}" data-verdict="{vslug}" data-status="{status}" data-day="{day}"
  data-category="{cat}" data-period="{per}" data-vrank="{vrank}" data-market="{mkt}" data-resale="{rsl}"
  data-est="{est}" data-bid="{bidv}" data-melt="{meltv}" data-margin="{marg}" data-search="{search}">
  <div class="lot-head">
    <a class="thumb" href="{url}" target="_blank" rel="noopener">{img}</a>
    <div class="lot-id">
      <div class="lot-no">Lot {lot}<span class="day">{dayname}</span></div>
      <h3>{title}</h3>
      <div class="dateline"><b>{date}</b> &middot; <span class="ev ev-{evslug}">{evidence}</span>
        &middot; <span class="st st-{status}">{status}</span></div>
      <div class="tags"><span class="tag cat">{catlabel}</span><span class="tag per">{perlabel}</span>{crits}</div>
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
    <div class="vals">
      <div class="v-mkt"><span>My market estimate</span><b>{market}</b></div>
      <div class="v-rsl"><span>If you resold it</span><b>{resale}</b></div>
      {marginrow}
    </div>
    {spread}
    {metal}
    {bar}
    <div class="grid">
      <div><span>House estimate</span><b>{est_r}</b></div>
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
        lot=lot, vslug=VERDICT_SLUG.get(verdict, "pass"), status=e(v.get("status", "border")),
        day=row["day"], dayname={"day1": "Day 1", "day2": "Day 2", "day3": "Day 3"}[row["day"]],
        cat=e(cat), per=e(per), catlabel=e(CAT_LABEL.get(cat, cat)), perlabel=e(PER_LABEL.get(per, per)),
        vrank=VERDICT_ORDER.index(verdict), mkt=(market[1] if market else 0),
        rsl=(resale[1] if resale else 0), est=(row["est_low"] or 0), bidv=(row["current_bid"] or 0),
        meltv=(melt[1] if melt else 0), marg=(round(margin) if margin is not None else -99999),
        search=searchable, url=e(row["url"] or "#"),
        img='<img loading="lazy" src="{}" alt="Lot {}">'.format(e(thumb_src), lot) if thumb_src else "",
        title=e(row["title"]), date=e(v.get("date", "undated")),
        evidence=e(v.get("evidence", "Unverified")), evslug=e(v.get("evidence", "unverified").lower()),
        crits=crits, verdict=e(verdict),
        keyflag='<div class="keyflag">key lot</div>' if v.get("star") else "",
        analysis=e(v.get("analysis", "")), problems=e(v.get("problems", "")),
        market=rng(market), resale=rng(resale),
        marginrow=('<div class="v-mar"><span>Margin at target</span><b class="{}">{}</b></div>'.format(
            "good" if margin and margin > 0 else "stop",
            ("+" if margin and margin > 0 else "") + money(round(margin)))
            if margin is not None else ""),
        spread=spread, metal=metal_block(val), bar=bid_bar(row, v),
        est_r="{} - {}".format(money(row["est_low"]), money(row["est_high"])),
        bid=money(row["current_bid"]),
        target=money(v.get("target")) if v.get("target") else "--",
        ceiling=money(ceiling) if ceiling else "--", allin=money(allin) if ceiling else "--",
        patience=e(v.get("patience", "")), src=src)


def screened_row(row, gid, label, thumb_src):
    """A compact, filterable, sortable row for a lot that was screened in bulk.

    These live in the same list as the full write-ups so the page genuinely
    browses all 1,500 lots rather than hiding 1,373 of them in an accordion.
    """
    e = html.escape
    cat, per = classify(row)
    return (
        '<div class="entry srow" data-lot="{lot}" data-verdict="screened" data-status="screened"'
        ' data-day="{day}" data-category="{cat}" data-period="{per}" data-group="{gid}"'
        ' data-vrank="9" data-market="0" data-resale="0" data-est="{est}" data-bid="{bid}"'
        ' data-melt="0" data-margin="-99999" data-search="{search}">'
        '<a class="rthumb" href="{url}" target="_blank" rel="noopener">{img}</a>'
        '<div class="rmain"><div class="rtop"><b>Lot {lotn}</b>'
        '<span class="rday">{dayname}</span><span class="rest">est {est_r}</span></div>'
        '<h4>{title}</h4>'
        '<div class="tags"><span class="tag cat">{catlabel}</span>'
        '<span class="tag per">{perlabel}</span><span class="tag grp">{grp}</span></div>'
        '</div></div>'
    ).format(
        lot=row["lot"] or 9999, lotn=row["lot"] or "--", day=row["day"],
        dayname={"day1": "Day 1", "day2": "Day 2", "day3": "Day 3"}[row["day"]],
        cat=cat, per=per, gid=gid, est=(row["est_low"] or 0), bid=(row["current_bid"] or 0),
        est_r="{} - {}".format(money(row["est_low"]), money(row["est_high"])),
        search=e(" ".join([str(row["lot"]), row["title"], label,
                           CAT_LABEL.get(cat, ""), PER_LABEL.get(per, "")]).lower()),
        url=e(row["url"] or "#"),
        img=('<img loading="lazy" src="{}" alt="Lot {}">'.format(e(thumb_src), row["lot"])
             if thumb_src else ""),
        title=e(row["title"]), catlabel=e(CAT_LABEL.get(cat, cat)),
        perlabel=e(PER_LABEL.get(per, per)), grp=e(label))


def thumb_data_uri(path, box=420, quality=58):
    """420 px gives 2x for the 210 px display size without bloating the file."""
    from PIL import Image
    with Image.open(ROOT / path) as im:
        im = im.convert("RGB")
        im.thumbnail((box, box), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def render(lots, verdicts, valuations, method, embed=False):
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

    cards = []
    for row, v in analysed:
        val = valuations.get(row["lot"], {})
        src = ""
        if row["images"]:
            src = thumb_data_uri(row["images"][0]) if embed else row["images"][0]
        cards.append(card(row, v, val, src))

    # Screened lots join the same list, ordered by lot number after the write-ups.
    flat = []
    for gid, g in screened.items():
        for r in g["rows"]:
            flat.append((r, gid, g["label"]))
    flat.sort(key=lambda t: (t[0]["day"], t[0]["lot"] or 0))
    for r, gid, label in flat:
        src = ""
        if r["images"]:
            src = thumb_data_uri(r["images"][0], box=88, quality=52) if embed else r["images"][0]
        cards.append(screened_row(r, gid, label, src))

    legend = "".join(
        '<details class="lg"><summary><b>{label}</b><span class="n">{n}</span></summary>'
        '<p>{reason}</p></details>'.format(
            label=html.escape(g["label"]), n=len(g["rows"]), reason=html.escape(g["reason"]))
        for gid, g in sorted(screened.items(), key=lambda kv: -len(kv[1]["rows"])))
    grp_opts = "".join(
        '<option value="{}">{} ({})</option>'.format(gid, html.escape(g["label"]), len(g["rows"]))
        for gid, g in sorted(screened.items(), key=lambda kv: -len(kv[1]["rows"])))

    metals = "".join('<div><span>{}</span><b>{}</b><i>{}</i></div>'.format(*m) for m in METALS)
    chips = "".join('<button class="chip" data-filter="verdict" data-value="{}">{} '
                    '<span class="n">{}</span></button>'.format(VERDICT_SLUG[v], v, counts[v])
                    for v in VERDICT_ORDER if counts[v])
    cat_opts = "".join('<option value="{}">{}</option>'.format(k, lbl) for k, lbl in CATEGORIES)
    per_opts = "".join('<option value="{}">{}</option>'.format(k, lbl) for k, lbl in PERIODS)

    return TEMPLATE.format(
        cards="\n".join(cards), legend=legend, metals=metals, chips=chips,
        cat_opts=cat_opts, per_opts=per_opts, grp_opts=grp_opts,
        n_analysed=len(analysed), n_screened=sum(len(g["rows"]) for g in screened.values()),
        n_total=len(lots),
        m_market=html.escape(method["market"]), m_resale=html.escape(method["resale"]),
        m_melt=html.escape(method["melt"]), m_gems=html.escape(method["gems"])), analysed, screened, counts


def to_fragment(page):
    """Strip the document wrapper for publishing as an Artifact.

    The Artifact host supplies its own doctype/head/body and a strict CSP that
    blocks font CDNs, so the webfont <link> is replaced with the locally stored
    woff2 data URIs -- otherwise the specified type silently falls back.
    """
    fonts = (ROOT / "assets" / "fonts-embedded.css").read_text(encoding="utf-8")
    for junk in ('<!doctype html>\n', '<html lang="en">\n', "<head>\n", "</head>\n",
                 "<body>\n", "</body>\n", "</html>\n", '<meta charset="utf-8">\n',
                 '<meta name="viewport" content="width=device-width, initial-scale=1">\n'):
        page = page.replace(junk, "", 1)
    page = re.sub(r'<link href="https://fonts\.googleapis\.com[^>]*>\n', "", page, count=1)
    return page.replace("<style>\n", "<style>\n" + fonts + "\n", 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", action="store_true",
                    help="also write a copy with thumbnails inlined as data URIs")
    ap.add_argument("--artifact", action="store_true",
                    help="also write an Artifact-ready fragment (inlined fonts and images,"
                         " no document wrapper)")
    args = ap.parse_args()

    lots = json.loads((BUILD / "lots.json").read_text(encoding="utf-8"))
    verdicts = load_verdicts()
    valuations, method = load_valuations()

    page, analysed, screened, counts = render(lots, verdicts, valuations, method, embed=False)
    OUT.write_text(page, encoding="utf-8")
    print("wrote {} ({:,} bytes)".format(OUT.name, OUT.stat().st_size))

    missing = [r["lot"] for r, _ in analysed if r["lot"] not in valuations]
    if missing:
        print("WARNING: analysed lots with no valuation:", missing)

    if args.embed or args.artifact:
        page2, _, _, _ = render(lots, verdicts, valuations, method, embed=True)
        if args.embed:
            OUT_EMBED.write_text(page2, encoding="utf-8")
            print("wrote {} ({:,} bytes)".format(OUT_EMBED.name, OUT_EMBED.stat().st_size))
        if args.artifact:
            OUT_ART.write_text(to_fragment(page2), encoding="utf-8")
            print("wrote {} ({:,} bytes)".format(OUT_ART.name, OUT_ART.stat().st_size))

    print("analysed: {}  screened: {}  total: {}".format(
        len(analysed), sum(len(g["rows"]) for g in screened.values()), len(lots)))
    for v in VERDICT_ORDER:
        if counts[v]:
            print("  {:<15} {}".format(v, counts[v]))


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Summer Grandeur 2026 - Auction Analysis</title>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600&family=Spectral:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{
  --oyster:#EFE8DC; --oyster-2:#E3D9C8; --paper:#FBF7F0; --panel:#FFFFFF;
  --spruce:#1E3A33; --spruce-2:#2C4F45;
  --verdigris:#4F8F7E; --oxblood:#7A1F2B; --brass:#A8853C;
  --ink:#1A1F1D; --ink-2:#4A4038; --ink-3:#3A423E; --muted:#5C6560; --line:#CFC4B0;
  --on:#EFE8DC; --on-dim:#A9C0B6; --on-faint:#9FB8AD;
  --warm-panel:#F5EEE2; --cool-panel:#F2F6F3; --track:#E8E0D2;
  --cat-bg:#D8E6DF; --cat-fg:#1E3A33; --per-bg:#EDE0C6; --per-fg:#6A5320; --unv-bg:#EFD9D9;
  --sb-bg:#4F8F7E; --buy-bg:#2C4F45; --stretch-bg:#A8853C; --cheap-bg:#8FA89C;
  --check-bg:#C08A2E; --pass-bg:#7A1F2B; --badge-fg:#FFFFFF;
  --good:#3F7A69; --stop:#7A1F2B; --link:#1E3A33;
  --sans:"Oswald",Impact,"Haettenschweiler","Arial Narrow",sans-serif;
  --serif:"Spectral",Georgia,"Times New Roman",serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;
}}
/* Dark is the same oyster-and-spruce world seen at dusk, not an inversion:
   deep spruce grounds, warm oyster ink, brass and verdigris lifted to carry. */
@media (prefers-color-scheme:dark){{
  :root{{
    --oyster:#121917; --oyster-2:#1B2321; --paper:#19211F; --panel:#212B28;
    --spruce:#0D1413; --spruce-2:#2A6555;
    --verdigris:#6FBFA6; --oxblood:#C4626F; --brass:#CFA85A;
    --ink:#E9E3D7; --ink-2:#D6CDBE; --ink-3:#C6D0CB; --muted:#98A39E; --line:#33403C;
    --on:#E9E3D7; --on-dim:#9FBBB0; --on-faint:#8FAaa0;
    --warm-panel:#251F18; --cool-panel:#17211F; --track:#28312D;
    --cat-bg:#22403A; --cat-fg:#A9D6C6; --per-bg:#382F1E; --per-fg:#E2CB92; --unv-bg:#3A2326;
    --sb-bg:#3E8C76; --buy-bg:#2A6555; --stretch-bg:#8A6C2C; --cheap-bg:#4C6A5F;
    --check-bg:#96691D; --pass-bg:#8E2A38; --badge-fg:#F4EFE5;
    --good:#6FBFA6; --stop:#E08A95; --link:#7FCBB2;
  }}
}}
:root[data-theme=dark]{{
  --oyster:#121917; --oyster-2:#1B2321; --paper:#19211F; --panel:#212B28;
  --spruce:#0D1413; --spruce-2:#2A6555;
  --verdigris:#6FBFA6; --oxblood:#C4626F; --brass:#CFA85A;
  --ink:#E9E3D7; --ink-2:#D6CDBE; --ink-3:#C6D0CB; --muted:#98A39E; --line:#33403C;
  --on:#E9E3D7; --on-dim:#9FBBB0; --on-faint:#8FAaa0;
  --warm-panel:#251F18; --cool-panel:#17211F; --track:#28312D;
  --cat-bg:#22403A; --cat-fg:#A9D6C6; --per-bg:#382F1E; --per-fg:#E2CB92; --unv-bg:#3A2326;
  --sb-bg:#3E8C76; --buy-bg:#2A6555; --stretch-bg:#8A6C2C; --cheap-bg:#4C6A5F;
  --check-bg:#96691D; --pass-bg:#8E2A38; --badge-fg:#F4EFE5;
  --good:#6FBFA6; --stop:#E08A95; --link:#7FCBB2;
}}
:root[data-theme=light]{{
  --oyster:#EFE8DC; --oyster-2:#E3D9C8; --paper:#FBF7F0; --panel:#FFFFFF;
  --spruce:#1E3A33; --spruce-2:#2C4F45;
  --verdigris:#4F8F7E; --oxblood:#7A1F2B; --brass:#A8853C;
  --ink:#1A1F1D; --ink-2:#4A4038; --ink-3:#3A423E; --muted:#5C6560; --line:#CFC4B0;
  --on:#EFE8DC; --on-dim:#A9C0B6; --on-faint:#9FB8AD;
  --warm-panel:#F5EEE2; --cool-panel:#F2F6F3; --track:#E8E0D2;
  --cat-bg:#D8E6DF; --cat-fg:#1E3A33; --per-bg:#EDE0C6; --per-fg:#6A5320; --unv-bg:#EFD9D9;
  --sb-bg:#4F8F7E; --buy-bg:#2C4F45; --stretch-bg:#A8853C; --cheap-bg:#8FA89C;
  --check-bg:#C08A2E; --pass-bg:#7A1F2B; --badge-fg:#FFFFFF;
  --good:#3F7A69; --stop:#7A1F2B; --link:#1E3A33;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--oyster);color:var(--ink);font-family:var(--serif);font-size:16px;line-height:1.55;-webkit-text-size-adjust:100%}}
header{{background:var(--spruce);color:var(--on);padding:18px 16px 14px}}
header h1{{font-family:var(--sans);font-weight:600;letter-spacing:.06em;text-transform:uppercase;font-size:1.25rem;margin:0 0 2px}}
header .sub{{font-size:.85rem;color:var(--on-dim);margin:0 0 12px}}
.metals{{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}}
.metals div{{background:rgba(255,255,255,.07);border-left:2px solid var(--brass);padding:5px 8px}}
.metals span{{display:block;font-family:var(--sans);font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:var(--on-faint)}}
.metals b{{font-family:var(--mono);font-size:.82rem;color:var(--on);display:block}}
.metals i{{font-family:var(--mono);font-size:.7rem;color:var(--brass);font-style:normal}}
.note{{background:var(--oyster-2);border-bottom:1px solid var(--line);padding:10px 16px;font-size:.83rem;color:var(--ink-2)}}
.note b{{font-family:var(--sans);letter-spacing:.04em;text-transform:uppercase;font-size:.72rem}}
.note details{{margin-top:8px}}
.note summary{{cursor:pointer;font-family:var(--sans);font-size:.72rem;letter-spacing:.04em;text-transform:uppercase;color:var(--link)}}
.note dl{{margin:8px 0 0}}
.note dt{{font-family:var(--sans);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;color:var(--oxblood);margin-top:7px}}
.note dd{{margin:2px 0 0}}
.filters{{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:2px solid var(--spruce);padding:8px 10px;box-shadow:0 2px 8px rgba(0,0,0,.09)}}
.row{{display:flex;gap:5px;overflow-x:auto;padding-bottom:5px;scrollbar-width:thin}}
.chip{{flex:0 0 auto;font-family:var(--sans);font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;
  background:var(--panel);border:1px solid var(--line);color:var(--ink);padding:5px 8px;cursor:pointer;white-space:nowrap;border-radius:2px}}
.chip .n{{font-family:var(--mono);color:var(--muted);font-size:.62rem}}
.chip[aria-pressed=true]{{background:var(--spruce);color:var(--on);border-color:var(--spruce)}}
.chip[aria-pressed=true] .n{{color:var(--on-dim)}}
.selects{{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:5px}}
.selects .wide{{grid-column:1/-1}}
.selects label,.sorts label{{display:block}}
.selects span,.sorts span{{font-family:var(--sans);font-size:.56rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}}
select{{width:100%;font-family:var(--serif);font-size:.85rem;padding:5px 6px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:2px}}
.sorts{{display:grid;grid-template-columns:1fr 1fr auto;gap:5px;margin-top:5px;align-items:end}}
#dir{{font-family:var(--sans);font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;background:var(--panel);
  border:1px solid var(--line);color:var(--ink);padding:6px 8px;cursor:pointer;white-space:nowrap;border-radius:2px}}
#q{{width:100%;font-family:var(--serif);font-size:.95rem;padding:7px 9px;border:1px solid var(--line);background:var(--panel);color:var(--ink);margin-top:5px;border-radius:2px}}
.count{{font-family:var(--mono);font-size:.7rem;color:var(--muted);padding:5px 2px 0}}
main{{padding:12px 10px 40px;max-width:880px;margin:0 auto}}
.card{{background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--muted);margin:0 0 14px;border-radius:2px}}
.card[data-verdict=strong-buy]{{border-left-color:var(--verdigris)}}
.card[data-verdict=buy]{{border-left-color:var(--spruce-2)}}
.card[data-verdict=stretch-worthy]{{border-left-color:var(--brass)}}
.card[data-verdict=buy-if-cheap]{{border-left-color:var(--cheap-bg)}}
.card[data-verdict=check-first]{{border-left-color:var(--check-bg)}}
.card[data-verdict=pass]{{border-left-color:var(--oxblood);opacity:.9}}
.lot-head{{display:grid;grid-template-columns:130px minmax(0,1fr);grid-template-areas:"thumb id" "thumb verdict";gap:6px 12px;padding:10px;border-bottom:1px solid var(--line)}}
.lot-id{{min-width:0;grid-area:id}}
.thumb{{grid-area:thumb}}
.lot-id h3,.lot-body p,.problems,.patience{{overflow-wrap:break-word}}
.thumb img{{width:130px;height:130px;object-fit:cover;border:1px solid var(--line);background:var(--panel);display:block}}
.lot-no{{font-family:var(--mono);font-size:.72rem;color:var(--muted)}}
.lot-no .day{{color:var(--brass);margin-left:6px}}
.lot-id h3{{font-family:var(--sans);font-weight:400;font-size:.94rem;line-height:1.25;margin:2px 0 4px;letter-spacing:.02em}}
.dateline{{font-size:.76rem;color:var(--muted)}}
.dateline b{{color:var(--ink)}}
.ev{{font-family:var(--sans);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;padding:1px 5px;border-radius:2px}}
.ev-catalogued{{background:var(--cat-bg);color:var(--cat-fg)}}
.ev-inferred{{background:var(--per-bg);color:var(--per-fg)}}
.ev-unverified{{background:var(--unv-bg);color:var(--oxblood)}}
.st{{font-family:var(--mono);font-size:.66rem;text-transform:uppercase}}
.st-antique{{color:var(--verdigris)}} .st-border{{color:var(--brass)}} .st-modern{{color:var(--muted)}}
.tags{{margin-top:5px;display:flex;flex-wrap:wrap;gap:4px}}
.tag{{font-family:var(--sans);font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;background:var(--oyster-2);color:var(--ink-2);padding:2px 6px;border-radius:2px}}
.tag.cat{{background:var(--cat-bg);color:var(--cat-fg)}}
.tag.per{{background:var(--per-bg);color:var(--per-fg)}}
.verdict-wrap{{grid-area:verdict;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.verdict{{font-family:var(--sans);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;padding:4px 7px;color:var(--badge-fg);white-space:nowrap;border-radius:2px}}
.v-strong-buy{{background:var(--sb-bg)}} .v-buy{{background:var(--buy-bg)}}
.v-stretch-worthy{{background:var(--stretch-bg)}} .v-buy-if-cheap{{background:var(--cheap-bg)}}
.v-check-first{{background:var(--check-bg)}} .v-pass{{background:var(--pass-bg)}}
.star{{background:none;border:none;font-size:1.2rem;color:var(--line);cursor:pointer;padding:4px 0 0}}
.star[aria-pressed=true]{{color:var(--brass)}}
.keyflag{{font-family:var(--sans);font-size:.55rem;letter-spacing:.1em;text-transform:uppercase;color:var(--oxblood)}}
.lot-body{{padding:10px}}
.lot-body p{{margin:0 0 9px}}
.problems{{background:var(--warm-panel);border-left:2px solid var(--brass);padding:7px 9px;font-size:.9rem;margin:0 0 10px}}
.problems b,.patience b,.src b,.spread b,.mnote b{{font-family:var(--sans);font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;color:var(--oxblood)}}
.vals{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:0 0 10px}}
.vals div{{background:var(--cool-panel);padding:6px 8px}}
.vals span{{display:block;font-family:var(--sans);font-size:.58rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}}
.vals b{{font-family:var(--mono);font-size:.9rem}}
.v-rsl{{background:var(--warm-panel) !important}}
.spread{{font-size:.86rem;color:var(--ink-2);margin:0 0 10px}}
.metal{{border:1px solid var(--line);background:var(--panel);margin:0 0 10px}}
.metal-h{{font-family:var(--sans);font-size:.62rem;letter-spacing:.09em;text-transform:uppercase;background:var(--spruce);color:var(--oyster);padding:4px 8px}}
.mrow{{display:flex;justify-content:space-between;padding:4px 8px;border-bottom:1px dotted var(--line);font-size:.86rem}}
.mrow span{{color:var(--muted)}}
.mrow b{{font-family:var(--mono)}}
.mrow b.nil{{color:var(--oxblood)}}
.mnote{{font-size:.8rem;color:var(--ink-2);margin:6px 8px}}
.patience{{font-size:.87rem;color:var(--ink-3)}}
.src{{font-size:.83rem;color:var(--muted);border-top:1px dotted var(--line);padding-top:7px}}
.bar{{margin:10px 0 8px}}
.bar-track{{position:relative;height:16px;background:var(--track);border:1px solid var(--line);border-radius:2px}}
.bar-span{{position:absolute;top:0;bottom:0;left:0;background:rgba(79,143,126,.14)}}
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
.grid b{{font-family:var(--mono);font-size:.86rem;overflow-wrap:break-word}}
.grid .good,.vals .good{{color:var(--good)}} .grid .stop,.vals .stop{{color:var(--stop)}}
.lotlink{{font-family:var(--sans);font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--link)}}
h2.sec{{font-family:var(--sans);font-weight:600;letter-spacing:.08em;text-transform:uppercase;font-size:.9rem;
  border-bottom:2px solid var(--spruce);padding-bottom:5px;margin:30px 0 12px}}
/* Compact row: a screened lot, in the same list as the write-ups. */
.srow{{display:grid;grid-template-columns:56px minmax(0,1fr);gap:9px;align-items:start;
  background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--line);
  padding:7px 9px;margin:0 0 5px;border-radius:2px}}
.srow img{{width:56px;height:56px;object-fit:cover;border:1px solid var(--line);background:var(--panel);display:block}}
.rmain{{min-width:0}}
.rtop{{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;font-family:var(--mono);font-size:.7rem;color:var(--muted)}}
.rtop b{{color:var(--ink)}}
.rtop .rday{{color:var(--brass)}}
.srow h4{{font-family:var(--sans);font-weight:400;font-size:.82rem;line-height:1.25;
  margin:2px 0 4px;letter-spacing:.02em;overflow-wrap:break-word}}
.tag.grp{{background:transparent;border:1px solid var(--line);color:var(--muted)}}
.lead{{font-size:.87rem;color:var(--ink-2);margin-top:0}}
.legend{{display:grid;gap:5px}}
.lg{{background:var(--paper);border:1px solid var(--line);border-radius:2px}}
.lg summary{{padding:7px 9px;cursor:pointer;font-family:var(--sans);font-size:.76rem;letter-spacing:.03em}}
.lg summary .n{{font-family:var(--mono);font-size:.7rem;color:var(--muted);float:right}}
.lg p{{padding:0 9px 8px;margin:0;font-size:.86rem;color:var(--ink-2)}}
footer{{background:var(--spruce);color:var(--on-dim);padding:18px 16px;font-size:.8rem}}
footer b{{color:var(--on)}}
a{{color:var(--link)}}
@media(min-width:700px){{
  .metals{{grid-template-columns:repeat(6,1fr)}}
  .grid{{grid-template-columns:repeat(5,1fr)}}
  .lot-head{{grid-template-columns:210px minmax(0,1fr) auto;grid-template-areas:"thumb id verdict"}}
  .thumb img{{width:210px;height:210px}}
  .verdict-wrap{{align-items:flex-start;flex-direction:column;text-align:right}}
  header h1{{font-size:1.6rem}}
  .selects{{grid-template-columns:repeat(2,1fr)}}
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
  clears if metals slip before 28 August.
  <details>
    <summary>How I arrived at the value numbers &mdash; read this before trusting them</summary>
    <dl>
      <dt>My market estimate</dt><dd>{m_market}</dd>
      <dt>If you resold it</dt><dd>{m_resale}</dd>
      <dt>Melt values</dt><dd>{m_melt}</dd>
      <dt>Stones</dt><dd>{m_gems}</dd>
      <dt>Margin at target</dt><dd>The midpoint of my market range minus the all-in cost at my target
      bid. Positive means you are buying under market after premium and tax; negative means you are
      paying up for it. Sort by this to rank the whole list on value rather than on my verdict.
      Deliberately blank where my market range spans more than three-fold &mdash; that width is
      unresolved uncertainty (a medium, a period, a print process), not value, and averaging it would
      float the least-known lots to the top of the ranking.</dd>
      <dt>Category and period</dt><dd>Hand-set on the 127 written-up lots. On the 1,373 bulk-screened
      lots they are assigned automatically from the catalogue title, so treat those as a rough index
      rather than a considered judgement. Value estimates are NOT given for screened lots &mdash;
      I have not analysed them individually and will not put a number on something I have not looked at.</dd>
    </dl>
  </details>
  <br>
  <b>Standing caution on ivory.</b> This sale carries a great deal of whale&rsquo;s tooth, walrus,
  sailor-made and carved elephant ivory. Federal Endangered Species Act and Marine Mammal Protection Act
  rules restrict what can be done with these afterwards and the documentation will not accompany lots at
  this price. That is why resale on ivory-content lots is marked well below market.
</div>

<div class="filters">
  <div class="row">
    <button class="chip" data-filter="all" aria-pressed="true">All</button>
    {chips}
  </div>
  <div class="row">
    <button class="chip" data-filter="day" data-value="day1">Day 1</button>
    <button class="chip" data-filter="day" data-value="day2">Day 2</button>
    <button class="chip" data-filter="day" data-value="day3">Day 3</button>
    <button class="chip" data-filter="starred">&#9733; Starred</button>
  </div>
  <div class="row">
    <button class="chip" data-filter="detail" data-value="full">Full write-ups</button>
    <button class="chip" data-filter="detail" data-value="screened">Screened only</button>
    <button class="chip" data-filter="status" data-value="antique">Antique</button>
    <button class="chip" data-filter="status" data-value="border">Border</button>
    <button class="chip" data-filter="status" data-value="modern">Modern</button>
  </div>
  <div class="selects">
    <label><span>Category</span>
      <select id="fcat"><option value="">All categories</option>{cat_opts}</select></label>
    <label><span>Period / style</span>
      <select id="fper"><option value="">All periods</option>{per_opts}</select></label>
    <label class="wide"><span>Screening group</span>
      <select id="fgrp"><option value="">All screening groups</option>{grp_opts}</select></label>
  </div>
  <div class="sorts">
    <label><span>Sort by</span><select id="s1">
      <option value="vrank">Verdict</option>
      <option value="lot">Lot number</option>
      <option value="market">My market estimate</option>
      <option value="resale">Resale value</option>
      <option value="margin">Margin at target</option>
      <option value="melt">Melt value</option>
      <option value="est">House estimate</option>
      <option value="bid">Current bid</option>
    </select></label>
    <label><span>Then by</span><select id="s2">
      <option value="lot">Lot number</option>
      <option value="vrank">Verdict</option>
      <option value="market">My market estimate</option>
      <option value="resale">Resale value</option>
      <option value="margin">Margin at target</option>
      <option value="melt">Melt value</option>
      <option value="est">House estimate</option>
    </select></label>
    <button id="dir" aria-pressed="false">&uarr; Asc</button>
  </div>
  <input id="q" type="search" placeholder="Search lots, makers, materials&hellip;" autocomplete="off">
  <div class="count" id="count"></div>
</div>

<main>
<div id="lots">
{cards}
</div>

<h2 class="sec">Why lots were set aside</h2>
<p class="lead">The compact rows above each carry one of these reasons as their third tag. Filter to any
one of them with the screening-group menu. They carry no value estimates, because I have not analysed
them individually and will not put a number on something I have not looked at.</p>
<div class="legend">{legend}</div>
</main>

<footer>
  <b>Before the sale.</b> Preview runs weekdays and Saturdays 15&ndash;27 August; Thomaston also books
  virtual gallery previews. Worth using on anything still marked CHECK FIRST.<br>
  Thomaston Place Auction Galleries &middot; 51 Atlantic Hwy, Thomaston ME 04861 &middot; 207-354-8141
</footer>

<script>
(function(){{
  var state={{verdict:null,status:null,day:null,detail:null,category:"",period:"",group:"",
              starred:false,q:""}};
  var box=document.getElementById("lots");
  var lots=[].slice.call(document.querySelectorAll(".entry"));
  var countEl=document.getElementById("count");
  var s1=document.getElementById("s1"), s2=document.getElementById("s2"), dir=document.getElementById("dir");
  var desc=false, stars={{}};
  try{{stars=JSON.parse(localStorage.getItem("sg26stars")||"{{}}");}}catch(e){{stars={{}};}}

  lots.forEach(function(el){{
    var b=el.querySelector(".star"), id=el.dataset.lot;
    if(!b) return;                       // compact rows carry no star button
    if(stars[id]) b.setAttribute("aria-pressed","true");
    b.addEventListener("click",function(){{
      var on=b.getAttribute("aria-pressed")==="true";
      b.setAttribute("aria-pressed",String(!on));
      if(on){{delete stars[id];}} else {{stars[id]=1;}}
      try{{localStorage.setItem("sg26stars",JSON.stringify(stars));}}catch(e){{}}
      apply();
    }});
  }});

  function num(el,k){{ var v=parseFloat(el.dataset[k]); return isNaN(v)?0:v; }}

  function sortLots(){{
    var k1=s1.value, k2=s2.value;
    // "Verdict" and "Lot number" read best ascending; money reads best descending.
    var money={{market:1,resale:1,margin:1,melt:1,est:1,bid:1}};
    var flip=desc?-1:1;
    var arr=lots.slice().sort(function(a,b){{
      var d=(num(a,k1)-num(b,k1))*(money[k1]?-1:1)*flip;
      if(d) return d;
      d=(num(a,k2)-num(b,k2))*(money[k2]?-1:1);
      if(d) return d;
      return num(a,"lot")-num(b,"lot");
    }});
    arr.forEach(function(el){{ box.appendChild(el); }});
  }}

  function apply(){{
    var full=0, scr=0;
    lots.forEach(function(el){{
      var ok=true, d=el.dataset, isScr=d.verdict==="screened";
      if(state.detail==="full" && isScr) ok=false;
      if(state.detail==="screened" && !isScr) ok=false;
      if(state.verdict && d.verdict!==state.verdict) ok=false;
      if(state.status && d.status!==state.status) ok=false;
      if(state.day && d.day!==state.day) ok=false;
      if(state.category && d.category!==state.category) ok=false;
      if(state.period && d.period!==state.period) ok=false;
      if(state.group && d.group!==state.group) ok=false;
      if(state.starred && !stars[d.lot]) ok=false;
      if(state.q && d.search.indexOf(state.q)===-1) ok=false;
      el.style.display=ok?"":"none";
      if(ok){{ if(isScr) scr++; else full++; }}
    }});
    countEl.textContent=(full+scr)+" of 1500 lots shown \\u2014 "+full+
      " written up, "+scr+" screened";
  }}

  document.querySelectorAll(".chip").forEach(function(c){{
    c.addEventListener("click",function(){{
      var f=c.dataset.filter;
      if(f==="all"){{ state.verdict=state.status=state.day=state.detail=null; state.starred=false;
        state.category=state.period=state.group="";
        document.getElementById("fcat").value=""; document.getElementById("fper").value="";
        document.getElementById("fgrp").value=""; }}
      else if(f==="starred"){{ state.starred=!state.starred; }}
      else {{ state[f]=(state[f]===c.dataset.value)?null:c.dataset.value; }}
      document.querySelectorAll(".chip").forEach(function(o){{
        var of=o.dataset.filter, on=false;
        if(of==="all") on=!state.verdict&&!state.status&&!state.day&&!state.detail&&!state.starred
                          &&!state.category&&!state.period&&!state.group;
        else if(of==="starred") on=state.starred;
        else on=state[of]===o.dataset.value;
        o.setAttribute("aria-pressed",String(on));
      }});
      apply();
    }});
  }});

  document.getElementById("fcat").addEventListener("change",function(e){{ state.category=e.target.value; apply(); }});
  document.getElementById("fper").addEventListener("change",function(e){{ state.period=e.target.value; apply(); }});
  document.getElementById("fgrp").addEventListener("change",function(e){{ state.group=e.target.value; apply(); }});
  s1.addEventListener("change",sortLots);
  s2.addEventListener("change",sortLots);
  dir.addEventListener("click",function(){{
    desc=!desc; dir.setAttribute("aria-pressed",String(desc));
    dir.innerHTML=desc?"&darr; Desc":"&uarr; Asc"; sortLots();
  }});
  document.getElementById("q").addEventListener("input",function(e){{
    state.q=e.target.value.trim().toLowerCase(); apply();
  }});
  sortLots(); apply();
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
