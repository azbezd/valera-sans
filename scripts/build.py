"""Compile approved quadratic UFO drawings to TTF, CFF OTF and WOFF2."""
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
import os
import re
import ufoLib2
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPointPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'font-project.json').read_text())
EPOCH=int(os.environ.get('SOURCE_DATE_EPOCH',CONFIG['source_date_epoch']))
FONT_TIME=EPOCH+2082844800
LICENCE=('Valera Sans Font License 1.0. Free personal and commercial use with attribution '
         'to Valery Isachenkov. Modifying or renaming the font is not permitted. '
         'Technical embedding exceptions and complete terms: '+CONFIG['repository']+'/blob/main/LICENSE')

def names(style):
    family=CONFIG['family'];author=CONFIG['author']
    legacy=family if style=='Regular' else family+' '+style
    return {0:f'Copyright {CONFIG["year"]} {author}.',1:legacy,2:'Regular',
        3:f'{CONFIG["font_version"]};NONE;ValeraSans-{style}',4:family+' '+style,
        5:'Version '+CONFIG['font_version'],6:'ValeraSans-'+style,
        8:author,9:author,10:(f'Handwriting by {author}. Latin and Cyrillic; contextual r and Cyrillic u, kerning and tabular figures. '
                            f'Website: {CONFIG["website"]}. Telegram: {CONFIG["telegram"]}.'),
        11:CONFIG['website'],12:CONFIG['telegram'],13:LICENCE,
        14:CONFIG['repository']+'/blob/main/LICENSE',16:family,17:style}

def legacy_kern(font,features):
    # Старые программы читают только kern и не делают замен calt, поэтому в таблицу идут
    # пары базовых глифов: группы разворачиваются, варианты (.altN) отбрасываются.
    classes={n:m.split()for n,m in re.findall(r'^(@\S+)\s*=\s*\[([^\]]*)\];',features,re.M)}
    members=lambda x:classes.get(x,[x])
    pairs={}
    for a,b,v in re.findall(r'^\s*pos\s+(\S+)\s+(\S+)\s+(-?\d+);',features,re.M):
        for ga in members(a):
            for gb in members(b):
                if int(v) and '.alt' not in ga+gb:pairs.setdefault((ga,gb),int(v))
    pairs=sorted(pairs.items())
    table=newTable('kern');table.version=0;table.kernTables=[]
    for start in range(0,len(pairs),10000):
        sub=KernTable_format_0();sub.version=0;sub.coverage=1
        sub.kernTable=dict(pairs[start:start+10000]);table.kernTables.append(sub)
    font['kern']=table

def build(style,weight,cff=False):
    ufo=ufoLib2.Font.open(ROOT/f'sources/ValeraSans-{style}.ufo')
    order=ufo.glyphOrder
    fb=FontBuilder(1000,isTTF=not cff)
    fb.setupGlyphOrder(order)
    cmap={cp:g.name for g in ufo for cp in g.unicodes}
    fb.setupCharacterMap(cmap)
    glyphs={};metrics={}
    for name in order:
        g=ufo[name]
        point_pen=TTGlyphPointPen(ufo);g.drawPoints(point_pen)
        quadratic=point_pen.glyph();quadratic.recalcBounds(None)
        if cff:
            pen=T2CharStringPen(g.width,ufo,roundTolerance=0)
            g.draw(pen);glyphs[name]=pen.getCharString()
        else:
            glyphs[name]=quadratic
        metrics[name]=(round(g.width),quadratic.xMin if g.contours else 0)
    if cff:
        fb.setupCFF('ValeraSans-'+style,dict(FullName=CONFIG['family']+' '+style,
            FamilyName=CONFIG['family'],Weight=style,version=CONFIG['font_version'],
            Notice=f'Copyright {CONFIG["year"]} {CONFIG["author"]}. '+LICENCE),glyphs,{})
    else:fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=1100,descent=-550,lineGap=0)
    fb.setupNameTable(names(style))
    # Legacy name families each have one regular face; modern IDs 16/17 group
    # all three weights. fsType 0 permits installation and embedding; the
    # custom no-modification/attribution conditions live in the license.
    fb.setupOS2(version=4,usWeightClass=weight,usWidthClass=5,fsType=0,
        sTypoAscender=1100,sTypoDescender=-550,sTypoLineGap=0,usWinAscent=1100,usWinDescent=550,
        sxHeight=560,sCapHeight=700,fsSelection=64|128|256,achVendID='NONE',
        ySubscriptXSize=650,ySubscriptYSize=600,ySubscriptXOffset=0,ySubscriptYOffset=75,
        ySuperscriptXSize=650,ySuperscriptYSize=600,ySuperscriptXOffset=0,ySuperscriptYOffset=350,
        yStrikeoutSize=50,yStrikeoutPosition=300)
    fb.setupPost(italicAngle=0,underlinePosition=-130,underlineThickness=50,isFixedPitch=0,
                 keepGlyphNames=not cff)
    fb.setupMaxp()
    f=fb.font
    f['head'].fontRevision=float(CONFIG['font_version']);f['head'].macStyle=0
    f['head'].created=FONT_TIME;f['head'].modified=FONT_TIME;f.recalcTimestamp=False
    # Localized author record; never change PostScript identifiers by locale.
    for ident,text in [(0,f'Copyright {CONFIG["year"]} {CONFIG["author_ru"]}.'),(9,CONFIG['author_ru']),
                       (10,f'Автор рукописного шрифта — {CONFIG["author_ru"]}. Кириллица и латиница. '
                           f'Сайт: {CONFIG["website"]}. Telegram: {CONFIG["telegram"]}.')]:
        f['name'].setName(text,ident,3,1,0x419)
    addOpenTypeFeaturesFromString(f,ufo.features.text)
    legacy_kern(f,ufo.features.text)
    ext='otf'if cff else 'ttf';path=ROOT/f'fonts/{ext}/ValeraSans-{style}.{ext}'
    path.parent.mkdir(parents=True,exist_ok=True);f.save(path)
    if not cff:
        # Веб-версия: браузеры берут кернинг из GPOS, старая таблица kern им не нужна.
        if 'kern' in f:del f['kern']
        f.flavor='woff2';(ROOT/'fonts/web').mkdir(exist_ok=True)
        f.save(ROOT/f'fonts/web/ValeraSans-{style}.woff2')
    return path

if __name__=='__main__':
    for style,weight in CONFIG['styles'].items():
        for cff in [False,True]:print(build(style,weight,cff).relative_to(ROOT))
    css='/* Valera Sans — Valery Isachenkov. See LICENSE and ATTRIBUTION.md. */\n'
    for style,weight in CONFIG['styles'].items():
        css+=f'''@font-face {{
  font-family: "Valera Sans";
  src: url("ValeraSans-{style}.woff2") format("woff2");
  font-weight: {weight};
  font-style: normal;
  font-display: swap;
}}\n'''
    (ROOT/'fonts/web/valera-sans.css').write_text(css)
    manifest={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in sorted((ROOT/'fonts').rglob('*'))if p.suffix in ['.ttf','.otf','.woff2']}
    (ROOT/'qa/build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
