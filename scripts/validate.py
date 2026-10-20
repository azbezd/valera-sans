"""Check approved geometry, names, licensing, shaping and public file links."""
from pathlib import Path
from io import BytesIO
import hashlib
import json
import re
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.areaPen import AreaPen

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'font-project.json').read_text())
APPROVED=json.loads((ROOT/'tests/approved-v0.5.json').read_text())
BROWSER=json.loads((ROOT/'tests/browser-expected.json').read_text())
BASE,ALT='uni0072','uni0072.after_e'

def load_hb(font):
    font.flavor=None;data=BytesIO();font.save(data)
    hf=hb.Font(hb.Face(data.getvalue()));hf.scale=(1000,1000);hb.ot_font_set_funcs(hf);return hf

def shape(font,text,kern=True,calt=True,tab=False):
    b=hb.Buffer();b.add_str(text);b.guess_segment_properties();b.script='Latn';b.direction='ltr'
    hb.shape(font,b,{'kern':kern,'calt':calt,'tnum':tab})
    return [g.codepoint for g in b.glyph_infos],sum(p.x_advance for p in b.glyph_positions)

def geometry(font,name):
    gs=font.getGlyphSet();bounds=BoundsPen(gs);area=AreaPen(gs)
    gs[name].draw(bounds);gs[name].draw(area)
    return bounds.bounds,area.value

results={}
for style,weight in CONFIG['styles'].items():
    approved=APPROVED[style];reference=TTFont(ROOT/f'fonts/ttf/ValeraSans-{style}.ttf')
    pair_tables={True:json.loads((ROOT/f'tests/pairs-{style}.json').read_text()),False:json.loads((ROOT/f'tests/base-pairs-{style}.json').read_text())}
    tabs=json.loads((ROOT/f'tests/tabular-pairs-{style}.json').read_text())
    glyph_rows=json.loads((ROOT/f'tests/glyph-pairs-{style}.json').read_text())
    kern_map={(r['left'],r['right']):r['adjustment']for r in glyph_rows}
    chars=''.join(chr(int(p))for p in approved['cmap'])
    for ext,folder in [('ttf','ttf'),('otf','otf'),('woff2','web')]:
        path=ROOT/f'fonts/{folder}/ValeraSans-{style}.{ext}';f=TTFont(path)
        order=f.getGlyphOrder();cmap=f.getBestCmap()
        assert len(order)==180 and {str(k):v for k,v in cmap.items()}==approved['cmap']
        assert f['name'].getDebugName(16)=='Valera Sans'
        assert f['name'].getDebugName(17)==style
        assert f['name'].getDebugName(6)=='ValeraSans-'+style
        assert f['name'].getDebugName(5)=='Version '+CONFIG['font_version']
        for name_id in [0,1,2,3,4,5,6,8,9,10,11,12,13,14,16,17]:assert f['name'].getDebugName(name_id)
        assert 'Valery Isachenkov'in f['name'].getDebugName(0)
        assert f['name'].getDebugName(11)==CONFIG['website']
        assert f['name'].getDebugName(12)==CONFIG['telegram']
        for record in f['name'].names:
            if record.nameID==10:
                assert CONFIG['website'] in record.toUnicode()
                assert CONFIG['telegram'] in record.toUnicode()
        assert 'not permitted'in f['name'].getDebugName(13)
        assert f['name'].getDebugName(14).endswith('/valera-sans/blob/main/LICENSE')
        assert f['OS/2'].usWeightClass==weight and f['OS/2'].fsType==0
        assert f['post'].underlineThickness>0 and f['OS/2'].yStrikeoutSize>0
        assert f['OS/2'].usWinAscent>=f['head'].yMax and f['OS/2'].usWinDescent>=-f['head'].yMin
        for name,rec in approved['glyphs'].items():
            assert list(f['hmtx'][name])==rec['metrics'],(style,ext,name,'metrics')
            if ext!='otf':
                coords,ends,flags=f['glyf'][name].getCoordinates(f['glyf'])
                assert [list(p)for p in coords]==rec['coords']and list(ends)==rec['ends'],(style,ext,name,'outline')
                assert [x&1 for x in flags]==[x&1 for x in rec['flags']]
            else:
                bounds,area=geometry(f,name);rb,ra=geometry(reference,name)
                assert (bounds is None)==(rb is None)
                if bounds:assert max(abs(a-b)for a,b in zip(bounds,rb))<.01,(style,name,'CFF bounds')
                assert abs(area-ra)<1,(style,name,'CFF area',area-ra)
        hf=load_hb(f)
        for calt,pairs in pair_tables.items():
            for pair,record in pairs.items():
                _,on=shape(hf,pair,calt=calt);_,off=shape(hf,pair,kern=False,calt=calt)
                assert on-off==record['adjustment'],(style,ext,pair,calt)
        for pair,record in tabs.items():
            assert shape(hf,pair,tab=True)[1]-shape(hf,pair,kern=False,tab=True)[1]==record['adjustment']
        contexts=sorted(set(['er'+c for c in chars]+[c+'er'for c in chars]+[c['text']for c in BROWSER[style]]))
        for text in contexts:
            for calt in [True,False]:
                names=[ALT if c=='r'and i>0 and text[i-1]=='e'and calt else cmap[ord(c)]for i,c in enumerate(text)]
                gids,width=shape(hf,text,calt=calt)
                assert [order[i]for i in gids]==names,(style,ext,text,'GSUB')
                expected=sum(f['hmtx'][n][0]for n in names)+sum(kern_map.get(p,0)for p in zip(names,names[1:]))
                assert width==expected,(style,ext,text,'GPOS')
        for case in BROWSER[style]:
            assert shape(hf,case['text'],calt=case['calt'],kern=case['kern'])[1]==case['width_units']
        results[str(path.relative_to(ROOT))]=dict(glyphs=180,characters=170,pairs_per_calt_state=28900,
            tabular_pairs=len(tabs),contextual_cases=len(contexts)*2,approved_geometry=True,
            complete_metadata=True,shaping_mismatches=0,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        print(style,ext,'passed',flush=True)

links_checked=0
for path in list(ROOT.glob('*.md'))+list((ROOT/'docs').glob('*.md')):
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
        if '://'in target or target.startswith('#'):continue
        target=target.split('#')[0]
        if target:assert (path.parent/target).exists(),(path,target);links_checked+=1
(ROOT/'qa/validation.json').write_text(json.dumps(dict(fonts=results,relative_document_links_checked=links_checked),indent=2)+'\n')
print('All 9 font files passed. Relative documentation links:',links_checked)
