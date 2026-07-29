# auction-analysis

Analysis of Thomaston Place Auction Galleries' Summer Grandeur 2026 sale
(August 28–30, 2026). See `CLAUDE.md` for the working brief — buyer profile,
evaluation criteria, and deliverable spec.

The deliverable is `summer-grandeur-2026.html`, a single-file mobile-first
buying page. Rebuild it with:

```sh
python3 tools/parse_lots.py && python3 tools/build_page.py
```

## Getting the images

Lot photographs (2.06 GB, 5,222 files) live in Cloudflare R2 rather than git.
Everything else — `lots.csv`, the 1,500 `meta.json` files, and the raw HTML
captures — is in the repo.

```sh
cp .env.r2.example .env.r2 && $EDITOR .env.r2
scripts/r2.sh pull
```

The page's thumbnails point at these local paths, so pull before taking it
into the gallery. Full setup, including S3 browser settings:
[`docs/R2-SETUP.md`](docs/R2-SETUP.md).
