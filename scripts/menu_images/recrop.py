"""Re-extract every dish crop from the original menu pages, undoing the destructive
background whitening. Masked brightness-invariant NCC finds each damaged crop's source
box (mask = pixels the whitening left intact, scale is 1:1 per probe); the box is then
re-cut from the untouched original. Coarse search at half-res, refine at full-res."""

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[2]
PAGES_DIR = ROOT / 'assets/data/menu_images'
DISHES_DIR = ROOT / 'src/frontends/customer_ui/public/dishes'
SCRATCH = Path(__file__).resolve().parent / 'work'
OUT_DIR = SCRATCH / 'recropped'
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOWN = 2
ACCEPT = 0.80


def gray(img):
    return np.asarray(img.convert('L'), dtype=np.float32) / 255.0


def masked_ncc_map(page_g, page_g2, tmpl, mask):
    n = mask.sum()
    mt = mask * tmpl
    st, st2 = mt.sum(), (mt * tmpl).sum()
    s_i = fftconvolve(page_g, mask[::-1, ::-1], mode='valid')
    s_i2 = fftconvolve(page_g2, mask[::-1, ::-1], mode='valid')
    cross = fftconvolve(page_g, mt[::-1, ::-1], mode='valid')
    cov = cross - s_i * st / n
    var_i = s_i2 - s_i * s_i / n
    var_t = max(st2 - st * st / n, 1e-9)
    valid = var_i > 0.05 * var_t
    return np.where(valid, cov / np.sqrt(np.maximum(var_i, 1e-9) * var_t), -1.0)


def best_pos(page_g, page_g2, tmpl, mask):
    ncc = masked_ncc_map(page_g, page_g2, tmpl, mask)
    y, x = np.unravel_index(np.argmax(ncc), ncc.shape)
    return float(ncc[y, x]), int(x), int(y)


def shrink(img, f):
    return img.resize((round(img.width / f), round(img.height / f)), Image.LANCZOS)


pages = []
for p in sorted(PAGES_DIR.glob('*.jpg')):
    if p.name.startswith('_'):
        continue
    img = Image.open(p).convert('RGB')
    g_full = gray(img)
    g_half = gray(shrink(img, DOWN))
    pages.append({
        'name': p.name, 'img': img,
        'half': (g_half, g_half * g_half),
        'full': (g_full, g_full * g_full),
    })

report = {}
for crop_path in sorted(DISHES_DIR.glob('*.jpg')):
    img = Image.open(crop_path).convert('RGB')
    w, h = img.size
    mask_full = (~np.all(np.asarray(img) > 240, axis=2)).astype(np.float32)
    t_full = gray(img)

    t_half = gray(shrink(img, DOWN))
    m_half = np.asarray(shrink(Image.fromarray((mask_full * 255).astype(np.uint8)), DOWN), dtype=np.float32) / 255.0
    m_half = (m_half > 0.6).astype(np.float32)
    if m_half.sum() < 200:
        report[crop_path.name] = {'status': 'skipped'}
        continue

    coarse = None
    for page in pages:
        g, g2 = page['half']
        if g.shape[0] < t_half.shape[0] or g.shape[1] < t_half.shape[1]:
            continue
        score, x, y = best_pos(g, g2, t_half, m_half)
        if coarse is None or score > coarse[0]:
            coarse = (score, page, x, y)

    # Refine at full res inside a small window around the upscaled coarse position.
    score, page, cx, cy = coarse
    g, g2 = page['full']
    pad = 6
    x0, y0 = max(cx * DOWN - pad, 0), max(cy * DOWN - pad, 0)
    x1, y1 = min(cx * DOWN + w + pad, g.shape[1]), min(cy * DOWN + h + pad, g.shape[0])
    win, win2 = g[y0:y1, x0:x1], g2[y0:y1, x0:x1]
    fscore, fx, fy = best_pos(win, win2, t_full, mask_full)
    bx, by = x0 + fx, y0 + fy

    entry = {'status': 'ok' if fscore >= ACCEPT else 'no_match',
             'ncc': round(fscore, 3), 'page': page['name'], 'box': [bx, by, w, h]}
    if entry['status'] == 'ok':
        page['img'].crop((bx, by, bx + w, by + h)).save(OUT_DIR / crop_path.name, quality=92)
    report[crop_path.name] = entry
    print(f"{crop_path.name}: {entry['status']} ncc={fscore:.3f} page={page['name'][:18]} box=({bx},{by},{w},{h})")

(SCRATCH / 'recrop_report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False))
ok = sum(1 for e in report.values() if e['status'] == 'ok')
print(f'\n{ok}/{len(report)} matched -> {OUT_DIR}')
