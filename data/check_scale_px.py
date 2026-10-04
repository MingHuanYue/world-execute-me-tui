# -*- coding: utf-8 -*-
"""缩放像素级自检：**4K 帧缩回 720p 后必须和 720p 帧一致**。

布局单测只覆盖面板框；这个测的是整帧像素——能抓到字体二次缩放、坐标漏缩放、越框等一切问题。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageChops, ImageStat  # noqa: E402

import config  # noqa: E402

TS = [23.4, 30.0, 53.6, 77.9, 80.4, 158.9, 162.0, 186.0, 208.5, 210.5]
LIMIT = 14.0      # 缩放的抗锯齿差异允许到这个程度；几何错了会远大于此


def main() -> int:
    from lyrics import Timeline, load_lyric_text
    import composite

    tl = Timeline.load(config.TIMELINE_PATH)
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    worst = 0.0
    bad = []
    for t in TS:
        config.RENDER_SCALE = 1.0
        a = composite.compose_frame(t, tl, texts=texts, scale=1.0)
        config.RENDER_SCALE = 3.0
        b = composite.compose_frame(t, tl, texts=texts, scale=3.0).resize(a.size, Image.LANCZOS)
        d = ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean
        m = sum(d) / 3.0
        worst = max(worst, m)
        flag = "OK" if m < LIMIT else "<<< 不一致"
        if m >= LIMIT:
            bad.append((t, m))
        print("  t=%6.1f  4K(缩回720p) vs 720p  平均差 %5.2f  %s" % (t, m, flag))
    print("  最大 %.2f（阈值 %.1f）-> %s" % (worst, LIMIT, "4K 与 720p 一致" if not bad else "**有 %d 处异常**" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
