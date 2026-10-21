# Validation

The first public build packages the approved Valera Hand Draft 0.5 as Valera Sans 0.5.1. The release changes naming, licensing metadata, compatibility fields and packaging, not the letter designs. Version 0.5.2 adds the author’s Telegram channel to the metadata and preserves the same approved geometry and shaping.

Version 0.5.3 adds the open Cyrillic у, calibrates its stroke, softens its terminals and conservatively simplifies outlines. Approved geometry is stored in `tests/approved-v0.5.3.json`; the previous baseline remains available for provenance. All advance widths of existing glyphs are preserved. Smoothing is an intentional small shape refinement, not a lossless operation.

`scripts/validate.py` checks every released TTF, CFF OTF and WOFF2:

- Complete author, copyright, naming, style grouping, version, URLs and license records.
- 170 encoded characters, 181 glyphs and approved advance widths.
- Exact quadratic points and contour endpoints for TTF/WOFF2. CFF conversion bounds differ by less than 0.01 font units and signed area by less than 1 square font unit.
- All 28,900 encoded pairs with calt both enabled and disabled, using actual HarfBuzz shaping.
- All 3,300 tabular-digit contexts, plus erX / Xer, цуX / Xцу and щуX / Xщу, куX / Xку and КуX / XКу in Latin, Cyrillic and default shaping scripts, and representative words to verify the selected glyph and the kerning on both sides.
- Compatibility metrics, positive underline/strikeout dimensions, and no clipping against the declared vertical bounds.
- Relative documentation links.

Results are written to `qa/validation.json`; font hashes and sizes are in `qa/build-manifest.json`. The approved 0.5 validation summary is retained in `docs/validation-v0.5.json` for provenance.

Browser checks load all nine released files and verify real widths against HarfBuzz expectations, context/kerning/weight controls, unsupported-character feedback, and mobile/desktop light/dark layouts. An actual-font specimen is used for README artwork.

## Limits

The complete pair matrix is checked automatically. It is not a claim that every pair was individually tuned by hand. Visual review uses representative pairs, words and sizes.

Mixed Latin/Cyrillic text can be split into separate shaping runs by a browser or application, so a stored cross-script pair may not apply at that boundary. The calt rules select Latin r after lowercase e and open Cyrillic у in the [reviewed contexts](CONTEXTS.md).

Light and Semibold remain experimental derived weights. No dedicated hinting, italics, extended Latin or variable-font interpolation is provided. Third-party desktop applications have not all been tested individually.

Version 0.5.4 extends only the contextual selection to к/К. The approved 0.5.3 geometry and all glyph-level kerning remain unchanged.

Version 0.5.5 adopts the approved pair audit: 43 preceding character contexts, and 23 / 21 / 15 targeted kerning changes across Light / Regular / Semibold. All 28,900 XуY triples are checked with calt on and off, in addition to the encoded pair matrix. The approved outline baseline remains 0.5.3.
