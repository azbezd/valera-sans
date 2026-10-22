# Build and release

The source is three independent quadratic UFO masters in `sources/`. They do not have compatible interpolation topology; this project does not produce a variable font. Their `features.fea` files contain contextual substitutions, kerning and tabular figures.

## Reproduce an official build

Python 3.12 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/build.py
python scripts/validate.py
python scripts/package.py
```

The build uses FontTools and ufoLib2; no system FontForge, Potrace or proprietary font editor is needed. A fixed source timestamp produces reproducible files. CFF OTF is generated from the same quadratic geometry, without autohinting or overlap removal. WOFF2 compresses the TTF.

`font-project.json` is the authoritative family, version, author and license metadata. The small `tests/` fixtures record approved 0.5.3 outlines and pair behavior. Changing drawings intentionally requires an authorized maintainer to review the new glyphs and update these approval fixtures; do not bypass failed geometry checks.

Serve the repository for a local specimen:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://127.0.0.1:8000/specimen/. For browser QA, run `npm ci`, `npx playwright install chromium`, then `npm run check:browser`. Screenshots are local QA outputs, not required to install the font.

## Official versioning

Only the author or an explicitly authorized maintainer may modify the Font Software under this project's license.

1. Create a work branch, review the glyph or metadata change and run the checks.
2. Update `version` and `font_version` in `font-project.json`, and the matching UFO metadata. For 0.6.1 the OpenType revision is 0.601 (0.6.0 used 0.600, 0.5.5 used 0.505, 0.5.1 used 0.501). Record the mapping explicitly for every release.
3. Update `CHANGELOG.md`, download links, specimens and license metadata as needed.
4. Build, validate, review desktop/mobile specimens, and run `python scripts/package.py`.
5. Commit the approved sources and generated fonts, then create an annotated tag such as `v0.6.1`. Never move a published tag.
6. Publish a GitHub release from that tag and upload the font ZIP, source ZIP and `SHA256SUMS.txt` from `dist/`.

CI rebuilds and validates every push and pull request. GitHub Pages deploys the specimen after successful checks on `main`. Publishing a new release remains an explicit maintainer action; a branch push does not create a release.

## Alternates (0.6.0)

The UFO masters are the source of truth. The 348 alternates, rotation, polishing and alternate kerning were produced by `qa/alternates-2026-10-21/integrate.py` from the outlines in `qa/alternates-2026-10-21/vector/` and the 0.5.5 masters; its README lists every step. Editing a glyph by hand in the UFO is fine; rerun `integrate.py` only to regenerate the alternate set as a whole, then `scripts/build.py`, `qa/alternates-2026-10-21/fixtures.py` and `scripts/validate.py`.

Since 0.6.1 `integrate.py` also enlarges the figures (`qa/digits-2026-10-22/scale_digits.py`, ratio `RATIO = 0.95` of the cap height) and recomputes the pairs with figures before the alternate kerning.

