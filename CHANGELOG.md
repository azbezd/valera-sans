# Changelog

## 0.6.0 — 2026-10-22

- Remove scanned ink drips from 5, 9, a, j, }, а, б, д and э (and tabular 5/9) in the weights where they occurred; remove a detached speck under } in Regular.
- Redraw the clipped loop of the ц descender and smooth the dent under the щ tail in all three weights.
- Local contour edits only: advance widths and kerning are unchanged; approved geometry updated for the 13 edited glyphs.
- Add 348 handwritten alternates of 151 characters selected by the author from the scans, in all three weights: traced from the scans, stroke weight matched to each master, burrs and drips removed.
- Rotate alternates automatically in `calt` after the contextual r/у rules: a repeated letter always changes shape; tabular figures map every digit form to its `.tab` glyph.
- Kern alternates with the 0.4 spacing formula: profile-based kerning groups reproduce every approved base pair; per-pair exceptions where an alternate needs different spacing (Latin↔Cyrillic pairs are skipped, as shapers split such runs).
- Add the degree sign °. Remove a stray dot (from the neighbouring i on the scan) from Latin j and refit the pairs before j.
- Polish outlines in all glyphs and weights: narrow drips, spikes and chopped stroke ends replaced by smooth curves (inner corners of strokes kept); hook of j cleaned by hand. Alternates keep the counters of their scans.
- Tighten pairs before Λ-shaped letters (л, Л, д, Д, А, A and their alternates) where the white space collects in a triangle at the top: up to 30 units, keeping the stroke ends at least 40 units apart.
- Keep letters from touching: wherever the real distance between the edges of two glyphs (any forms) is below 50 units for letters and digits or 40 for punctuation, the pair is opened exactly to that limit (228 base pairs and 8 759 alternate combinations in Regular).
- After lowercase Cyrillic letters with a bottom tail (а, к, ц, щ and some alternates) the л sits 25 units higher and further left, where this gains at least 15 units without the edges coming closer than 50 (a separate contextual lookup, so kerning of the next pair is kept).
- Tighten loose letter pairs (same script, all form combinations): white space between letters is brought down to the 40th percentile of its case group, never closer than 50 units between edges.
- After any form of а the plain д is used, and pairs before д keep the 0.5.5 values so its baseline stroke tucks under the previous letter (opened only where an alternate would come closer than 25 units).
- Validation follows `tests/alternates-spec.json` through `scripts/alternates_model.py`; the legacy `kern` table keeps the base glyph pairs only.
- Web WOFF2 files no longer carry the legacy `kern` table (browsers use GPOS); TTF and OTF keep it with the base pairs.
- Alternate outlines simplified after tracing (deviation ≤ 2.5 units).
- OpenType revision: **0.600**.

## 0.5.5 — 2026-10-21

- Expand the reviewed open Cyrillic у contexts to reduce excessive gaps, including ду, лу, му, ну, чу, шу and consecutive у.
- Refine 23 / 21 / 15 glyph kerning pairs in Light / Regular / Semibold where the previous tightening limit left excessive space.
- Preserve all letter contours, glyph metrics, looped defaults and Latin r alternates.
- Add full XуY context checks and updated browser/spacing fixtures.
- OpenType revision: **0.505**.

## 0.5.4 — 2026-10-21

- Use the approved open Cyrillic у after к and К, including «Как купить», in all three weights.
- Retain the existing alternate kerning, contours, glyph metrics and all other contextual rules.
- Extend shaping and browser checks for ку / Ку and neighboring characters.
- OpenType revision: **0.504**.

## 0.5.3 — 2026-10-21

- Added a contextual open Cyrillic у after ц, щ, Ц and Щ in all three weights.
- Matched its stroke weight and softened its terminals; retained the looped default and Latin r after e.
- Conservatively reduced outline points while preserving advance widths; retained o/о outlines for rasterizer compatibility.
- Updated approved geometry and kerning fixtures, all nine font files and download links.
- OpenType revision: **0.503**.

## 0.5.2 — 2026-10-21

- Added the author's Telegram channel, https://t.me/valerasketch, to project metadata, all nine font files, the UFO sources, author links and attribution guidance.
- The OpenType designer URL now points to Telegram; the website remains in the vendor URL and font description. Descriptions include both links in English and Russian.
- Included revised Russian project text and bilingual attribution instructions in the downloadable packages.
- OpenType revision: **0.502**. Letterforms, spacing, kerning and contextual substitutions are unchanged.

## 0.5.1 — 2026-10-20

First public release as **Valera Sans**.

- Three static weights in desktop TTF, CFF OpenType OTF and web WOFF2.
- Author, copyright, family/style grouping, PostScript identifiers, version, project URLs and custom license embedded in every font.
- Attribution-required personal and commercial use; font modifications and renaming require permission.
- Editable UFO sources, reproducible builds, validation, a specimen, CSS and release archives.
- Approved 0.5 letterforms, advances and pair behavior preserved. No new character designs in this release.

## Local development before public releases

These milestones were local prototypes, not historical GitHub releases or fabricated commits. Their working family name was Valera Hand Draft.

### 0.5 — 2026-10-20

Upright Latin r from scan sample 03 became the default; original sample 01 became a contextual alternate after lowercase Latin e. Kerning was checked on both sides of both forms in all weights.

### 0.4 — 2026-10-20

Full encoded-pair coverage, all case combinations, tabular figures, tracking controls and a pair inspector.

### 0.3 — 2026-10-20

Selected Cyrillic а sample 02 and Latin a sample 05 with characteristic tails.

### 0.2 — 2026-10-20

Refined sidebearings and kerning; added tabular figures and before/after specimens.

### 0.1 — 2026-10-20

First vectorization of the author's handwriting into Light, Regular and Semibold.
