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

`font-project.json` is the authoritative family, version, author and license metadata. The small `tests/` fixtures record approved 0.5 outlines and pair behavior. Changing drawings intentionally requires an authorized maintainer to review the new glyphs and update these approval fixtures; do not bypass failed geometry checks.

Serve the repository for a local specimen:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://127.0.0.1:8000/specimen/. For browser QA, run `npm ci`, `npx playwright install chromium`, then `npm run check:browser`. Screenshots are local QA outputs, not required to install the font.

## Official versioning

Only the author or an explicitly authorized maintainer may modify the Font Software under this project's license.

1. Create a work branch, review the glyph or metadata change and run the checks.
2. Update `version` and `font_version` in `font-project.json`, and the matching UFO metadata. For 0.5.1 the OpenType revision is 0.501. Record the mapping explicitly for every release.
3. Update `CHANGELOG.md`, download links, specimens and license metadata as needed.
4. Build, validate, review desktop/mobile specimens, and run `python scripts/package.py`.
5. Commit the approved sources and generated fonts, then create an annotated tag such as `v0.5.2`. Never move a published tag.
6. Publish a GitHub release from that tag and upload the font ZIP, source ZIP and `SHA256SUMS.txt` from `dist/`.

CI rebuilds and validates every push and pull request. GitHub Pages deploys the specimen after successful checks on `main`. Publishing a new release remains an explicit maintainer action; a branch push does not create a release.
