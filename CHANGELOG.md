# Changelog

## 0.6.4 — 2026-10-22

- Letters no longer touch: a final clearance pass over every pair of forms that occurs in text opens 1,909 / 1,900 / 1,756 pairs (Light / Regular / Semibold) to the stated minimum — 50 units between letters and digits, 40 with punctuation and before Λ-shaped letters, 25 before д. The 0.6.0 pass stopped after opening a pair by 150 units, so pairs such as ee, fe, Ру, ар and йу in some forms came within 1–12 units. Median opening 10 units.
- л is now raised after every form of а, к, ц and щ, as promised (before, only where the lift gained at least 15 units: never after ц in Regular, never after к or ц in Semibold, e.g. «клад»). It moves left as far as the 50-unit gap allows and never further right than before.
- Cyrillic у keeps its loop outside the open-у contexts, as promised: all four у alternates from the scans are loopless, and since 0.6.0 the rotation put them at the start of words and after letters such as Р and т. They now rotate with the open у instead: in the listed contexts and in «ууу» the open у takes one of five loopless shapes, so repeated у always change shape.
- Repeated letters run through all their forms: for 18 of the 150 characters with alternates (e, г, к, т, х, ы, ь, Ж, Ш, Э, S, 0, 1, 2, 5, &, % and the comma) the rotation step divided the number of forms, so «&&&&&» or «22222» alternated just two shapes. Steps are now coprime with the number of forms; this reshuffles which form of these characters follows a given glyph.
- Latin n is lower: all three forms scaled to the height of m (Regular 698 → 640, Light 693 → 635, Semibold 709 → 653), stroke thickness and sidebearings kept. The only outline change in this release.
- Count corrected in README, specimen and docs: 347 alternates of 150 characters; the 348th scan became the degree sign.
- No repeated e before the flowing r: in engineer and eerie the first of two e becomes e.alt2 (e.alt3 after e.alt2); 0.6.3 set both to the default form.
- Promise checks independent of the model (`scripts/promises.py`, run by `validate.py`): every rule above, the open у contexts, plain д after а and repeated letters are checked on HarfBuzz output and real outlines. README, specimen and CONTEXTS now state the one exception to “a repeated letter always changes shape”: Latin i has no alternates.
- Apart from n, features and kerning only. OpenType revision: **0.604**.

## 0.6.3 — 2026-10-22

- Keep the default Latin e before the flowing r (after e): the e alternates joined it badly. Valera, Vera, here, per, every, lever and similar words now always use the default e; in Valeera the first e keeps rotating. Rotation elsewhere is unchanged.
- After the flowing r, Latin a always takes its hooked alternate, which leaves the least space under the arm of the r in all three weights. It is raised 25 units and kerned up to 50 units between the edges (Regular −85, was −20), so era, Valera and opera have no hole between r and a. The lift is part of `kern`, like the raised л.
- Features only: outlines, advance widths and all other kerning are unchanged.
- OpenType revision: **0.603**.

## 0.6.2 — 2026-10-22

- Even out the stroke edges in all glyphs and weights: bumps and waves left from the scans are smoothed by an adaptive low-pass filter (strong on stems and bowls, light on tight curves and stroke ends), corners and joins kept. Edges move at most 8 units; dots, commas and quotes are left as drawn.
- Stroke thickness and counters unchanged: every glyph keeps its number of parts and counters (three Semibold alternates with a pinched gap are frozen locally), median stroke ratio 1.00.
- Simpler outlines: 24–28% fewer points; web WOFF2 203–217 KB per weight (was 232–243 KB).
- Kerning recomputed on the new outlines through the same pipeline as 0.6.0–0.6.1.
- OpenType revision: **0.602**.

## 0.6.1 — 2026-10-22

- Enlarge all figures (default, tabular and alternate forms) to about 95% of the cap height in all three weights: Regular 607 → 696 units, Light 604 → 691, Semibold 624 → 708 (caps 728–745). Previously figures sat between lowercase and caps (~61% of the em) and looked small next to letters, for example in prices.
- Keep the stroke weight: each figure is scaled from the baseline and its outline offset inwards by the stroke growth, so stroke thickness stays within ±3.5% of the original; same points, counters unchanged.
- Thicken the default Semibold zero, drawn with the Regular stroke since 0.5.1 (62 → 88 units, as the other Semibold zeros).
- Proportional figures keep their sidebearings; tabular figures get a common wider advance (Light 527 → 584, Regular 543 → 601, Semibold 576 → 647).
- Recompute kerning of every pair with a figure using the 0.4 spacing formula (2 288 / 2 400 / 2 234 base pairs changed in Light / Regular / Semibold), followed by the usual alternate, clearance and tightening passes.
- OpenType revision: **0.601**.

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
