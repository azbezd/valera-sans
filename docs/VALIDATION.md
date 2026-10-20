# Validation

The first public build packages the approved Valera Hand Draft 0.5 as Valera Sans 0.5.1. The release changes naming, licensing metadata, compatibility fields and packaging, not the letter designs.

`scripts/validate.py` checks every released TTF, CFF OTF and WOFF2:

- Complete author, copyright, naming, style grouping, version, URLs and license records.
- 170 encoded characters, 180 glyphs and approved advance widths.
- Exact quadratic points and contour endpoints for TTF/WOFF2. CFF conversion bounds differ by less than 0.01 font units and signed area by less than 1 square font unit.
- All 28,900 encoded pairs with calt both enabled and disabled, using actual HarfBuzz shaping.
- All 3,300 tabular-digit contexts, plus erX / Xer and representative words to verify the selected glyph and the kerning on both sides.
- Compatibility metrics, positive underline/strikeout dimensions, and no clipping against the declared vertical bounds.
- Relative documentation links.

Results are written to `qa/validation.json`; font hashes and sizes are in `qa/build-manifest.json`. The approved 0.5 validation summary is retained in `docs/validation-v0.5.json` for provenance.

Browser checks load all nine released files and verify real widths against HarfBuzz expectations, context/kerning/weight controls, unsupported-character feedback, and mobile/desktop light/dark layouts. An actual-font specimen is used for README artwork.

## Limits

The complete pair matrix is checked automatically. It is not a claim that every pair was individually tuned by hand. Visual review uses representative pairs, words and sizes.

Mixed Latin/Cyrillic text can be split into separate shaping runs by a browser or application, so a stored cross-script pair may not apply at that boundary. The calt rule only involves Latin lowercase e and r.

Light and Semibold remain experimental derived weights. No dedicated hinting, italics, extended Latin or variable-font interpolation is provided. Third-party desktop applications have not all been tested individually.
