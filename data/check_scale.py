# -*- coding: utf-8 -*-
"""缩放一致性自检：**4K 布局必须等于 720p 布局的 3 倍**。

这类 bug 在 720p 下永远看不出来（RENDER_SCALE=1 时 scaled(x)==x），只有严格比对两个 scale 才能抓到。
逐帧扫全片，任何一处布局/坐标不一致都报出来。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

SCALES = (1.0, 3.0)
TOL = 1          # 容许的取整误差（像素）


def snapshot(scale: float, t: float):
    config.RENDER_SCALE = scale
    import scenes
    out = []
    for p in (scenes.layout_for(t) or ()):
        b = p.box
        out.append((p.name, p.viz, b.x0, b.y0, b.x1, b.y1))
    return out


def main() -> int:
    import numpy as np
    ts = np.arange(0.0, 207.0, 0.5)
    bad = []
    checked = 0
    for t in ts:
        a = snapshot(1.0, float(t))
        b = snapshot(3.0, float(t))
        if len(a) != len(b):
            bad.append((t, "面板数不同 %d vs %d" % (len(a), len(b))))
            continue
        for pa, pb in zip(a, b):
            if pa[0] != pb[0]:
                bad.append((t, "面板名不同 %s vs %s" % (pa[0], pb[0])))
                continue
            for i in range(2, 6):
                want = pa[i] * 3
                if abs(pb[i] - want) > TOL:
                    bad.append((t, "%s 第%d个坐标: 4K=%d  720p*3=%d  差 %d" % (pa[0], i, pb[i], want, pb[i] - want)))
            checked += 1
    print("扫描 %.1f-%.1f s，每 %.1f s 一点，共 %d 个面板" % (ts[0], ts[-1], 0.5, checked))
    if bad:
        print("  **发现 %d 处缩放不一致**（只列前 12 条）：" % len(bad))
        for t, msg in bad[:12]:
            print("    t=%7.1f  %s" % (t, msg))
        return 1
    print("  OK：4K 布局处处等于 720p 布局的 3 倍（容差 %d px）" % TOL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
