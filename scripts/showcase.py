"""Render HTML specimens with the actual font and encode README images as WebP."""
from pathlib import Path
import subprocess
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['node',str(ROOT/'scripts/render-showcase.cjs')],cwd=ROOT,check=True)
for name in ['banner','features']:
    image=Image.open(ROOT/f'qa/preview-{name}.png')
    output=ROOT/f'docs/assets/{name}.webp'
    image.save(output,'WEBP',quality=92,method=6)
    print(output.relative_to(ROOT),image.size,output.stat().st_size,'bytes')
