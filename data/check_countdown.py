# -*- coding: utf-8 -*-
"""倒计时（SP7）音画同步自检 —— 数字切换帧 vs 重拍。

用法：
  python data/check_countdown.py              # 只算：从代码推出切换时刻，与拍点比对
  python data/check_countdown.py --clip X.mp4 # 再从渲染出的片段里**实测**切换帧并比对
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageChops, ImageStat  # noqa: E402

import config        # noqa: E402
import spectacle     # noqa: E402

BPM, FIRST = 130.83, 0.186
PERIOD = 60.0 / BPM
T0, T1 = spectacle._SP_WINDOWS["SP7"]
DIGIT_REGION = (24, 38, 1256, 604)      # 单表面：数字占满中栏


def nearest_beat(t: float) -> tuple[float, float]:
    k = round((t - FIRST) / PERIOD)
    b = FIRST + k * PERIOD
    return b, t - b


def code_switches() -> list[tuple[int, float]]:
    """从代码推出每个数字的起始时刻：idx = int(u*6)，u 在 [T0, T1] 上线性。"""
    out, cur = [], None
    import math
    for f in range(int(math.ceil(T0 * config.FPS)), int(T1 * config.FPS) + 2):   # 从窗口内第一帧起算
        t = f / config.FPS
        idx = min(5, int(max(0.0, min(1.0, (t - T0) / (T1 - T0))) * 6 + 1e-9))
        if idx != cur:
            out.append((idx + 1, t)); cur = idx
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", default=None)
    ap.add_argument("--clip-start", type=float, default=160.0, help="片段内容在音频里的起始秒")
    a = ap.parse_args()

    print("=" * 84)
    print("SP7 倒计时音画同步自检")
    print("=" * 84)
    print("BPM %.2f -> 拍周期 %.6f s；首拍 %.3f s" % (BPM, PERIOD, FIRST))
    print("SP7 窗口 %.4f - %.4f（%.3f s = %.2f 拍）" % (T0, T1, T1 - T0, (T1 - T0) / PERIOD))
    print()
    print("数字切换（由代码推出）与最近重拍的偏差：")
    worst = 0.0
    for n, t in code_switches():
        b, d = nearest_beat(t)
        worst = max(worst, abs(d))
        print("  %d -> t=%8.4f  最近拍 %8.4f  偏差 %+7.1f ms  (%+.3f 拍)" % (n, t, b, d * 1000, d / PERIOD))
    print("  最大偏差 %.1f ms（%.3f 拍）%s" % (
        worst * 1000, worst / PERIOD, "  OK 全部落在拍点（阈值 = 半帧 = %.1f ms）" % (500.0 / config.FPS) if worst <= 0.5 / config.FPS else "  <<< 未对齐"))

    if not a.clip:
        return 0
    print()
    print("=" * 84)
    print("从渲染片段实测：%s" % a.clip)
    print("=" * 84)
    tmp = os.path.join(config.OUT_DIR, "_cd")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)      # 必须清干净：上次残留会把帧号错位
    os.makedirs(tmp, exist_ok=True)
    exe = config.ffmpeg_exe()
    t0, t1 = 160.6, 168.0
    off = t0 - a.clip_start                      # 片段自己的时间轴从 0 起，要换算
    n0, n1 = int(round(t0 * config.FPS)), int(round(t1 * config.FPS))
    subprocess.run([exe, "-y", "-v", "error", "-ss", str(off), "-i", a.clip, "-t", str(t1 - t0),
                    "-vsync", "0", os.path.join(tmp, "f%05d.png")], check=True)
    files = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
    print("  片段 %.1f-%s 起，抽到 %d 帧" % (a.clip_start, t1, len(files)))
    prev = None
    print("帧号 / 音频 t / 与上一帧的差异（数字切换时该值会跳）")
    hits = []
    for i, fn in enumerate(files):
        img = Image.open(os.path.join(tmp, fn)).convert("L").crop(DIGIT_REGION)
        if prev is not None:
            dv = ImageStat.Stat(ImageChops.difference(img, prev)).mean[0]
            if dv > 3.5 and n0 + i >= int(T0 * config.FPS):
                t = (n0 + i) / config.FPS
                b, d = nearest_beat(t)
                hits.append((n0 + i, t, dv, d))
        prev = img
    for fr, t, dv, d in hits[:14]:
        print("  #%-5d t=%8.4f  差异 %6.2f  最近拍偏差 %+7.1f ms  (%+.3f 拍)" % (fr, t, dv, d * 1000, d / PERIOD))
    if hits:
        w = max(abs(h[3]) for h in hits)
        print("  实测切换点 %d 个，最大偏差 %.1f ms（%.3f 拍）" % (len(hits), w * 1000, w / PERIOD))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
