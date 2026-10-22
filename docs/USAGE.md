# Installation and use

## Desktop

Install one format: **TTF** for broad desktop compatibility or **OTF** for a CFF-flavored OpenType font. They contain the same characters, advances and OpenType behavior. Installing both formats of the same style can create duplicate entries.

On macOS, open a font in Font Book and install it. On Windows, use the font file's Install action. If replacing a previous version, remove or replace duplicates and restart applications holding the old font in memory.

Modern applications group the family as **Valera Sans → Light / Regular / Semibold**. Older applications using four-style family grouping may show **Valera Sans Light** and **Valera Sans Semibold** as separate families. This is intentional naming compatibility.

## Web

Copy `fonts/web/` and load `valera-sans.css`. It supplies 300, 400 and 600 through WOFF2. Avoid browser-synthesized weights or italics when the corresponding style is absent.

```css
.handwriting {
  font-family: "Valera Sans", sans-serif;
  font-weight: 400;
  font-synthesis: none;
  font-kerning: normal;
  font-feature-settings: "calt" 1;
  letter-spacing: 0;
}
.prices { font-variant-numeric: tabular-nums; }
```

`calt` drives all contextual forms: it rotates the 348 handwritten alternates (a repeated letter always changes shape), uses the open Cyrillic у in the contexts listed in [CONTEXTS.md](CONTEXTS.md), keeps the plain д after а, and selects the flowing Latin r immediately after lowercase Latin e (`Er`, `re`, Cyrillic е, spaces and punctuation do not trigger the r). With `calt` off every character keeps its default form. The raised л after letters with a bottom tail is part of `kern`. `tnum` gives digits equal advances. Tracking is a typesetting setting, not a replacement for pair kerning.

## Credit and embedding

Include a credit using [ATTRIBUTION.md](../ATTRIBUTION.md). Web/app/document embedding and normal editing of text are allowed. The license distinguishes normal technical embedding/subsetting from editing the font itself; see [LICENSE](../LICENSE).

## Coverage

Basic Latin A–Z/a–z, Russian Cyrillic including Ё/ё, digits and selected symbols. It is not a complete pan-European or pan-Cyrillic character set. Unsupported characters use the application's fallback font. No variable font or italic is included.
