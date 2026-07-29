#!/usr/bin/env python3
"""Parse the scraped Thomaston archive into one structured intermediate file.

Reads data/{day}/lots/{slug}/meta.json for all three days, falls back to
data/lots.csv (and finally the slug) for the handful of lots with no title,
resolves local image paths, and applies a first-pass keyword tagger so the
analyst can see where the criteria clusters are before reading titles.

    python3 tools/parse_lots.py

Writes build/lots.json and build/titles-{day}.txt.
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD = ROOT / "build"
DAYS = ("day1", "day2", "day3")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}

# Keyword tags. These only steer attention -- every verdict is still made by
# reading the title and, where it matters, the photographs.
TAGS = {
    "metal": r"sterling|coin silver|silver|\bgold\b|\b(?:10|14|18|22)\s?k\b|karat|gilt silver|vermeil",
    "maine": (
        r"maine|monhegan|ogunquit|rockport|camden|penobscot|casco|kennebec|"
        r"damariscotta|boothbay|thomaston|rockland|bath\b|wyeth|woodbury|"
        r"wengenroth|meissner|carroll thayer berry|jake day|maurice day|"
        r"lawrence sisson|william thon|winslow homer"
    ),
    "marine": (
        r"marine|ship|schooner|whal|scrimshaw|nautical|nantucket|sailor|yacht|"
        r"harbor|harbour|lighthouse|clipper|mariner|sextant|compass|barometer|"
        r"figurehead|half hull|halfhull|sea chest"
    ),
    "nouveau": r"nouveau|gall[eé]|tiffany|loetz|daum|wmf|majorelle|lalique|deco\b",
    "dated": (
        r"1[6789]th c|17\d\d|18\d\d|19[01]\d|georgian|federal|regency|victorian|"
        r"chippendale|hepplewhite|sheraton|queen anne|civil war|colonial"
    ),
    "firearm": r"shotgun|rifle|pistol|revolver|carbine|\bga\.?\b|gauge|\bscope\b|ammo|cartridge|holster|musket",
    "bronze": r"bronze|spelter",
    "sign": r"trade sign|tavern sign|\bsign\b|weathervane|weather vane",
    "pottery": r"roseville|steuben|rookwood|weller|pottery|porcelain|china|stoneware|redware",
    "furniture": r"chair|table|chest|desk|cupboard|sideboard|settee|sofa|bureau|dresser|stand\b|bench|bed\b",
    "rug": r"\brug\b|carpet|kilim|tabriz|heriz|kazak|serapi",
    "print": r"print|litho|etching|engraving|woodblock|wood engraving|serigraph|giclee|gicl[eé]e|collotype|collograph|collagraph",
}
TAGS = {k: re.compile(v, re.I) for k, v in TAGS.items()}


def title_from_slug(slug: str) -> str:
    return re.sub(r"_[0-9a-f]{6,}$", "", slug).replace("-", " ").upper()


def csv_titles() -> dict:
    out = {}
    path = DATA / "lots.csv"
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            slug = (row.get("url") or "").rstrip("/").split("/")[-1]
            if slug and row.get("title"):
                out[slug] = row["title"].strip()
    return out


def tag(title: str) -> list:
    return sorted(name for name, rx in TAGS.items() if rx.search(title))


def main() -> None:
    fallback = csv_titles()
    lots = []

    for day in DAYS:
        lot_dir = DATA / day / "lots"
        if not lot_dir.is_dir():
            continue
        for meta_path in sorted(lot_dir.glob("*/meta.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            slug = meta_path.parent.name
            title = (meta.get("title") or fallback.get(slug) or title_from_slug(slug)).strip()

            img_dir = meta_path.parent / "images"
            images = []
            if img_dir.is_dir():
                images = [
                    f"data/{day}/lots/{slug}/images/{p.name}"
                    for p in sorted(img_dir.iterdir())
                    if p.suffix.lower() in IMAGE_SUFFIXES
                ]

            raw_number = (meta.get("lot_number") or "").strip()
            lots.append(
                {
                    "day": day,
                    "lot": int(raw_number) if raw_number.isdigit() else None,
                    "slug": slug,
                    "title": title,
                    "est_low": meta.get("estimate_low"),
                    "est_high": meta.get("estimate_high"),
                    "current_bid": meta.get("current_bid"),
                    "bid_count": meta.get("bid_count"),
                    "images": images,
                    "url": meta.get("url"),
                    "tags": tag(title),
                }
            )

    lots.sort(key=lambda r: (r["day"], r["lot"] if r["lot"] is not None else 10**9))

    BUILD.mkdir(exist_ok=True)
    (BUILD / "lots.json").write_text(json.dumps(lots, indent=1), encoding="utf-8")

    for day in DAYS:
        rows = [r for r in lots if r["day"] == day]
        lines = [
            "{lot} | {title} | est {lo}-{hi} | bid {bid} | {n}img | {tags}".format(
                lot=r["lot"],
                title=r["title"],
                lo=r["est_low"],
                hi=r["est_high"],
                bid=r["current_bid"],
                n=len(r["images"]),
                tags=",".join(r["tags"]),
            )
            for r in rows
        ]
        (BUILD / f"titles-{day}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"lots: {len(lots)}")
    for day in DAYS:
        rows = [r for r in lots if r["day"] == day]
        nums = [r["lot"] for r in rows if r["lot"] is not None]
        print(f"  {day}: {len(rows)} lots, {min(nums)}-{max(nums)}, "
              f"{sum(len(r['images']) for r in rows)} images")
    counts = {}
    for r in lots:
        for t in r["tags"]:
            counts[t] = counts.get(t, 0) + 1
    print("tags:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
    print("no images:", sum(1 for r in lots if not r["images"]))
    print("no lot number:", sum(1 for r in lots if r["lot"] is None))


if __name__ == "__main__":
    main()
