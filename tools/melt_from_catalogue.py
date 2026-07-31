#!/usr/bin/env python3
"""Rebuild the melt block from the catalogue's own stated weights.

The catalogue description carries a stated total weight on 119 lots. Until the
descriptions were recovered from lot.html every melt figure in analysis/
valuations.json was my estimate from the form and the photographs, and the audit
showed many were badly wrong in both directions -- one lot's estimated net
exceeded the catalogued gross by 4.6x, several ethnographic silver lots were
estimated at a fifth of their actual weight.

This rewrites analysis/valuations.json in place for those lots only. Everything
else -- market, resale, gems, verdicts -- is untouched.

Catalogue weights are gross (brief section 3), so a deduction is applied for
whatever is not precious metal. The factor is still a judgement, but it is now a
judgement applied to a real number instead of a guessed one, and the basis line
on every card says so.

    python3 tools/melt_from_catalogue.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOTS = ROOT / "build" / "lots.json"
VALS = ROOT / "analysis" / "valuations.json"

OZT_G, DWT_G = 31.1035, 1.5552
WEIGHT = re.compile(r"(\d+(?:\.\d+)?)\s*(ozt|dwt)\b", re.I)

# Metal, most specific first. Karat marks beat the word "gold"; "coin silver"
# and the Chinese/Continental standards beat plain "sterling".
METAL_RULES = [
    ("gold_22k", r"\b22\s?K\b"),
    ("gold_18k", r"\b18\s?K\b"),
    ("gold_14k", r"\b14\s?K\b"),
    ("gold_10k", r"\b10\s?K\b"),
    ("platinum", r"\bplatinum\b"),
    # Chinese export silver is stamped 90 or 900 for .900 fine, the same standard
    # as American coin silver. Continental 800 is lower and gets its own rate.
    ("coin", r"coin silver|stamped \"?90\b|\b900\b|\b\.?900 ?silver\b|950[- ]silver"),
    ("fine_silver", r"\.999|999/1000|fine silver"),
    ("sterling", r"sterling|\b925\b|\b950[- ]silver\b|hallmark|silver"),
]

# Non-metal deduction. The catalogue weight is gross unless it says otherwise.
MAJOR_STONE = re.compile(
    r"\bsolitaire\b|three[- ]stone|\bcluster\b|\d+(?:\.\d+)?\s*ct\b|"
    r"carat|centre stone|center stone|cabochon|mabe|south sea|star ruby|"
    r"tanzanite|aquamarine|tourmaline|jadeite", re.I)
MANY_STONES = re.compile(
    r"carnelian|coral|turquoise|enamel|glass cabochon|colored glass|"
    r"\(\s*\d\d\s*\)\s*(?:oval|round|square)", re.I)
ANY_STONE = re.compile(
    r"diamond|sapphire|ruby|emerald|jade|opal|pearl|amethyst|topaz|garnet|"
    r"onyx|\bstone\b|\bstones\b|enamel|\bglass\b", re.I)
# The catalogue occasionally states the weight already net of the non-metal part.
STATED_NET = re.compile(r"without (?:the )?(?:glass liner|base weight|weighted)", re.I)


def metal_for(text):
    for name, pattern in METAL_RULES:
        if re.search(pattern, text, re.I):
            return name
    return "none"


def factor_for(text, metal):
    """-> (low, high) fraction of gross that is precious metal, plus a basis note."""
    if STATED_NET.search(text):
        return 1.0, 1.0, "catalogue states the weight net of the non-metal part"
    if metal in ("none", "platinum"):
        return 1.0, 1.0, "gross as catalogued"
    if re.search(r"verge|fusee|movement|pocket watch|watch case", text, re.I):
        return 0.35, 0.55, "case silver only; movement, dial and glass deducted"
    if MANY_STONES.search(text):
        return 0.70, 0.85, "heavy applied stone, glass and enamel deducted"
    if MAJOR_STONE.search(text):
        return 0.68, 0.82, "a named principal stone and its setting deducted"
    if ANY_STONE.search(text):
        return 0.86, 0.95, "small accent stones deducted"
    return 0.97, 1.0, "solid metal, only findings and solder deducted"


def main():
    lots = {str(r["lot"]): r for r in json.loads(LOTS.read_text()) if r["lot"]}
    data = json.loads(VALS.read_text())
    rows = {r["lot"]: r for r in data["lots"]}

    changed = 0
    for lot_no, row in lots.items():
        # The metal is sometimes only named in the title ("COIN SILVER\n        # TEASPOONS") and sometimes only in the description.
        text = row["title"] + " " + " ".join(row.get("desc") or [])
        found = WEIGHT.findall(text)
        if not found:
            continue
        # "Each weighs 16.59 ozt" on a set means per piece; multiply by the count.
        gross_unit = max(float(a) * (OZT_G if b.lower() == "ozt" else DWT_G)
                         for a, b in found)
        count = 1
        each = re.search(r"each weighs?\b", text, re.I)
        if each:
            head = re.match(r"\s*(?:cased )?(?:set|lot|group|pair) of \((\d+)\)",
                            text, re.I) or re.match(r"\s*\((\d+)\)", text)
            if head:
                count = int(head.group(1))
        gross = gross_unit * count

        metal = metal_for(text)
        lo_f, hi_f, basis = factor_for(text, metal)
        lot = int(lot_no)
        entry = rows.setdefault(lot, {"lot": lot})
        weights = ", ".join(f"{a} {b.lower()}" for a, b in found)
        entry["melt"] = {
            "metal": metal,
            "net_g": [round(gross * lo_f, 1), round(gross * hi_f, 1)],
            "basis": ("Catalogued weight {}{} = {:.0f} g gross; {}."
                      .format(weights,
                              f" each x {count}" if count > 1 else "",
                              gross, basis)),
        }
        if metal == "platinum":
            entry["melt"]["note"] = (
                "Platinum. The brief sets no working platinum price and I have not "
                "sourced one, so no melt is computed here.")
        changed += 1

    data["lots"] = [rows[k] for k in sorted(rows)]
    data["_method"]["melt"] = (
        "Weights on the 119 lots whose catalogue description states one are now the "
        "CATALOGUED weight, taken from the lot page and shown on the card. The "
        "catalogue weight is gross, so a deduction for stones, glass, enamel and "
        "liners is applied and named in the basis line -- that deduction is still my "
        "estimate. On every other precious-metal lot the weight remains my own "
        "estimate from the form and the photographs and needs the scale at preview. "
        "Rates are the brief's deliberately conservative working figures; a refiner "
        "pays about 87% of calculated melt.")
    VALS.write_text(json.dumps(data, indent=1) + "\n")
    print(f"rewrote melt from catalogued weights on {changed} lots")


if __name__ == "__main__":
    main()
