"""Create separate installation and source archives with license and hashes."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'font-project.json').read_text());version=config['version']
DIST=ROOT/'dist';DIST.mkdir(exist_ok=True)
font_files=[p for p in (ROOT/'fonts').rglob('*')if p.is_file()]
font_files += [ROOT/n for n in ['LICENSE','ATTRIBUTION.md','docs/USAGE.md','font-project.json']]
source_files=[]
for path in ROOT.iterdir():
    if path.is_file()and path.name not in ['.DS_Store']:
        source_files.append(path)
for folder in ['sources','scripts','fonts','docs','specimen','tests','.github']:
    source_files += [p for p in (ROOT/folder).rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.suffix not in ['.pyc']and not (p.suffix == '.png' and p.name.startswith(('browser-','preview-')))]
# Package the maintained reports, not local scratch results from older builds.
source_files += [ROOT/'qa'/name for name in ['build-manifest.json','validation.json','browser-summary.json']]
archives=[]
for kind,files in [('fonts',font_files),('source',source_files)]:
    target=DIST/f'ValeraSans-{version}-{kind}.zip';prefix=f'ValeraSans-{version}/'
    with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=9)as z:
        for p in sorted(set(files)):z.write(p,prefix+str(p.relative_to(ROOT)))
    with ZipFile(target)as z:
        assert z.testzip()is None
        assert prefix+'LICENSE'in z.namelist()
        if kind == 'source':
            for required in ['tests/browser-expected.json','tests/approved-v0.5.3.json','scripts/build.py','scripts/validate.py']:
                assert prefix+required in z.namelist(), required
        for p in font_files:
            assert z.read(prefix+str(p.relative_to(ROOT)))==p.read_bytes()
    archives.append(target)
lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in archives]
for p in sorted((ROOT/'fonts').rglob('*')):
    if p.suffix in ['.ttf','.otf','.woff2']:lines.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(ROOT)))
(DIST/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
for p in archives:print(p.name,p.stat().st_size,'bytes')
