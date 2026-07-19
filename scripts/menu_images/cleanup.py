"""Clean the re-cropped dish images: keep the dish and the natural paper background,
remove only menu clutter — text glyphs, price digits, underline dashes, crop ticks,
and the pale-orange accent blocks the crop box drags in from the page layout.

The paper background is found by connectivity to the border (tight tolerance, closed
morphologically so paper speckle stays one region — white plates with their edge
shadows do NOT join it). Remaining components: the big ones are food; small ones and
border-touching flat/orange ones are layout graphics and get painted with paper color.
Crops sitting on a colored band get that band normalized to the shared paper color."""

import colorsys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SCRATCH = Path(__file__).resolve().parent / 'work'
IN_DIR = SCRATCH / 'recropped'
OUT_DIR = SCRATCH / 'final'
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAPER_TOL = 14
SMALL_FRAC = 0.02   # non-main components smaller than this are clutter
EDGE_FRAC = 0.06    # border-touching non-main components smaller than this are clutter
BG_MIN_FRAC = 0.08  # less background than this = full-bleed photo, leave untouched
STD_PAPER = np.array([237.0, 235.0, 230.0])  # shared paper tone for normalized fills


def hsv(rgb):
    return colorsys.rgb_to_hsv(*(np.clip(rgb, 0, 255) / 255.0))


for path in sorted(IN_DIR.glob('*.jpg')):
    img = Image.open(path).convert('RGB')
    a = np.asarray(img, dtype=np.float64)
    H, W = a.shape[:2]
    total = H * W

    ring = np.concatenate([a[:3].reshape(-1, 3), a[-3:].reshape(-1, 3),
                           a[:, :3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)])
    paper = np.median(ring, axis=0)
    colored_bg = hsv(paper)[1] > 0.12

    raw_paperlike = np.abs(a - paper).max(axis=2) <= PAPER_TOL
    paperlike = raw_paperlike
    # Bridge the paper's speckle so it labels as one region; without this, text and
    # tick marks chain to the dish through broken background and survive the purge.
    # (Edge-pad first: closing with the default zero border would eat the mask at the
    # image edges and disconnect the background from the border.)
    pad = 4
    padded = np.pad(paperlike, pad, mode='edge')
    padded = ndimage.binary_closing(padded, structure=np.ones((3, 3)), iterations=2)
    paperlike = padded[pad:-pad, pad:-pad]
    lbl, _ = ndimage.label(paperlike)
    border_labels = np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))
    border_labels = border_labels[border_labels != 0]
    bg = np.isin(lbl, border_labels)

    if bg.sum() / total < BG_MIN_FRAC:
        img.save(OUT_DIR / path.name, quality=92)
        print(f'{path.name}: full-bleed, untouched')
        continue

    flbl, n = ndimage.label(~bg, structure=np.ones((3, 3)))
    idx = np.arange(1, n + 1)
    areas = ndimage.sum_labels(np.ones_like(flbl), flbl, index=idx)
    main = int(np.argmax(areas)) + 1
    on_border = set(np.unique(np.concatenate([flbl[0], flbl[-1], flbl[:, 0], flbl[:, -1]])))
    mean_rgb = np.stack([ndimage.mean(a[:, :, c], flbl, index=idx) for c in range(3)], axis=1)
    # Per-component std (graphic blocks are flat, food photos are busy).
    std_rgb = np.stack([ndimage.standard_deviation(a[:, :, c], flbl, index=idx) for c in range(3)], axis=1)

    erase = np.zeros(n + 1, dtype=bool)
    removed = []
    for i in idx:
        if i == main:
            continue
        frac = areas[i - 1] / total
        h, s, v = hsv(mean_rgb[i - 1])
        flat = std_rgb[i - 1].mean() < 10
        orange = 10 / 360 <= h <= 55 / 360 and s > 0.15 and v > 0.55
        if frac < SMALL_FRAC or (i in on_border and (frac < EDGE_FRAC or flat or orange)):
            erase[i] = True
            if frac > 0.001:
                removed.append(round(float(frac), 4))

    noise = np.random.default_rng(0).normal(0, 2.0, (H, W, 3))
    fill_color = STD_PAPER if colored_bg else paper
    fill = np.clip(fill_color[None, None, :] + noise, 0, 255)
    out = a.copy()

    if erase.any():
        kill = erase[flbl]
        # A touch of dilation so JPEG halos around glyphs go too — but never into the dish.
        kill = ndimage.binary_dilation(kill, structure=np.ones((3, 3)), iterations=2)
        kill &= flbl != main
        out[kill] = fill[kill]

    # Thin strokes (underlines, dashes, price digits) get swallowed into the background
    # by the closing above and would survive untouched — paint every bg pixel that isn't
    # genuinely paper-colored, plus a small halo confined to the background.
    stray = bg & ~raw_paperlike
    stray = ndimage.binary_dilation(stray, structure=np.ones((3, 3)), iterations=2) & bg
    out[stray] = fill[stray]

    # Ink pass: printed marks (digits, dashes, underline segments) often chain to the
    # dish component through its soft shadow and dodge the component rules. Ink is
    # dark, desaturated, small, and sits on paper — food details are not (and a plate's
    # blue rim pattern is surrounded by plate, not by background, so it stays).
    lum = a @ np.array([0.299, 0.587, 0.114])
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    # Menu accent orange (bullet icons): vivid warm hue, only trusted as tiny blobs.
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    orange_px = (r > 180) & (r - b > 70) & (g > b) & (g < r) & (sat > 0.35)
    dark_ink = (lum < 150) & (sat < 0.3)
    ink = (dark_ink | orange_px) & ~bg
    bgish = bg | raw_paperlike
    near_edge = np.zeros((H, W), dtype=bool)
    near_edge[:12], near_edge[-12:], near_edge[:, :12], near_edge[:, -12:] = True, True, True, True
    ilbl, ni = ndimage.label(ink, structure=np.ones((3, 3)))
    if ni:
        iareas = ndimage.sum_labels(np.ones_like(ilbl), ilbl, index=np.arange(1, ni + 1))
        for i in range(1, ni + 1):
            frac = iareas[i - 1] / total
            if frac > 0.02:
                continue
            blob = ilbl == i
            ringm = ndimage.binary_dilation(blob, structure=np.ones((3, 3)), iterations=3) & ~blob
            ring_bg = bg[ringm].mean()
            ring_bgish = bgish[ringm].mean()
            blob_lum = lum[blob].mean()
            is_orange_blob = orange_px[blob].mean() > 0.5
            hit = (
                ring_bg > 0.55
                or (is_orange_blob and ring_bgish > 0.75 and frac < 0.004)
                or (not is_orange_blob and blob_lum < 120 and ring_bgish > 0.75)
                or (not is_orange_blob and blob_lum < 120 and near_edge[blob].any() and ring_bg > 0.25)
            )
            if hit:
                paint = ndimage.binary_dilation(blob, structure=np.ones((3, 3)), iterations=2)
                out[paint] = fill[paint]

    # Last sweep: strokes fused into the dish's soft shadow band (so neither component
    # rules nor ring tests see them). A mark is dark, thin, sits within a few px of the
    # background, and its neighborhood is bright — dark food details (snails on a plate,
    # shells) are big blobs or far from the background, and stay.
    dist_bg = ndimage.distance_transform_edt(~bg)
    local_bright = ndimage.median_filter(lum, size=15) > 195
    mark = (lum < 135) & (sat < 0.28) & ~bg
    mlbl, nm = ndimage.label(mark, structure=np.ones((3, 3)))
    if nm:
        mareas = ndimage.sum_labels(np.ones_like(mlbl), mlbl, index=np.arange(1, nm + 1))
        mdist = ndimage.minimum(dist_bg, mlbl, index=np.arange(1, nm + 1))
        for i in range(1, nm + 1):
            if mareas[i - 1] / total > 0.006 or mdist[i - 1] > 12:
                continue
            blob = mlbl == i
            if local_bright[blob].mean() > 0.6:
                paint = ndimage.binary_dilation(blob, structure=np.ones((3, 3)), iterations=2)
                out[paint] = fill[paint]

    if colored_bg:
        out[bg] = fill[bg]
        # Soften the leftover colored fringe hugging the dish outline.
        fringe = ndimage.binary_dilation(bg, structure=np.ones((3, 3)), iterations=2) & ~bg
        out[fringe] = (out[fringe] + fill[fringe]) / 2

    Image.fromarray(out.astype(np.uint8)).save(OUT_DIR / path.name, quality=92)
    note = ' bg normalized' if colored_bg else ''
    print(f'{path.name}: erased {int(erase.sum())} comps, notable {removed[:6]}{note}')
