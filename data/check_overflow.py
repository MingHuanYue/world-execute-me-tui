# -*- coding: utf-8 -*-
"""穿模（越框）自检：面板自己画的内容不许落在自己的框外。

做法：在**统一底色的空白画布**上只跑面板绘制（不掺 chat / spectacle / _dim_side，避免假阳性），
渲两遍 —— 一遍正常，一遍把每个面板裁到自己的 box 内。两者差分 = 真正越界的像素。

720p 与 4K 都测：字号/间距随缩放放大后，越框更容易露出来。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image, ImageChops, ImageDraw  # noqa: E402

import config  # noqa: E402

BRIGHT = 30


def render_panels(t, tl, texts, scale, clip: bool):
    """统一底 + 只画面板；clip=True 时把每个面板裁到自己的框内。"""
    import scenes, tui_engine, theme

    config.RENDER_SCALE = scale
    pal = theme.palette_for(tl.state_at(t))
    w, h = config.scaled(config.WIDTH), config.scaled(config.HEIGHT)
    img = Image.new("RGB", (w, h), pal.bg)
    d = ImageDraw.Draw(img)
    panels = scenes.layout_for(t) or ()
    for p in panels:
        if not clip:
            tui_engine.draw_visual(d, p, tl, t, 0.6)
            continue
        sub = img.copy()
        tui_engine.draw_visual(ImageDraw.Draw(sub), p, tl, t, 0.6)
        b = (p.box.x0, p.box.y0, min(w, p.box.x1 + 1), min(h, p.box.y1 + 1))
        img.paste(sub.crop(b), (b[0], b[1]))
    return img, panels


def main() -> int:
    from lyrics import Timeline, load_lyric_text

    tl = Timeline.load(config.TIMELINE_PATH)
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    ts = np.arange(0.0, 207.0, 0.5)
    bad = []
    for scale in (1.0, 3.0):
        for t in ts:
            try:
                a, panels = render_panels(float(t), tl, texts, scale, False)
                b, _ = render_panels(float(t), tl, texts, scale, True)
            except Exception as e:
                bad.append((scale, float(t), "渲染异常 %s" % str(e)[:70])); continue
            if not panels:
                continue
            df = np.asarray(ImageChops.difference(a.convert("L"), b.convert("L")))
            pts = np.where(df > BRIGHT)
            if pts[0].size < 40:
                continue
            # 判据：只算**落在所有面板框之外**的像素（面板间隙 / 中栏外）。
            # 面板内的差异可能来自 _glow 这类全画布效果，裁剪后必然产生假阳性，一律不算。
            mg = max(3, int(round(4 * scale)))
            outside_all = np.ones(pts[0].shape, dtype=bool)
            for _n, box in [(q.name, q.box) for q in panels]:
                ins = ((pts[1] >= box.x0 - mg) & (pts[1] <= box.x1 + mg)
                       & (pts[0] >= box.y0 - mg) & (pts[0] <= box.y1 + mg))
                outside_all &= ~ins
            names = set()
            if int(outside_all.sum()) >= 40:
                ox, oy = pts[1][outside_all], pts[0][outside_all]
                names.add("间隙溢出 %dpx (x%d-%d y%d-%d)" % (outside_all.sum(), ox.min(), ox.max(), oy.min(), oy.max()))
            bad.append((scale, float(t), "越界: " + ", ".join(sorted(names)) if names else "越界 %d px" % pts[0].size))
        print("scale=%.1f 扫完，累计 %d" % (scale, len(bad)))
    print()
    if bad:
        times = sorted({(s, round(t, 1)) for s, t, _ in bad})
        by = {}
        for s, t in times:
            by.setdefault(s, []).append(t)
        print("**穿模时段**：")
        for s, lst in by.items():
            segs, st, pv = [], lst[0], lst[0]
            for x in lst[1:]:
                if x - pv > 0.6:
                    segs.append((st, pv)); st = x
                pv = x
            segs.append((st, pv))
            print("  scale=%.1f  %s" % (s, "  ".join("%.1f-%.1f" % q for q in segs)))
        print()
        print("样例（前 15 条）：")
        for s, t, m in bad[:15]:
            print("  scale=%.1f t=%7.1f  %s" % (s, t, m))
    else:
        print("  OK：所有面板内容都在自己的框内")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
