# -*- coding: utf-8 -*-
"""稳态剖面：模拟 render.iter_frames 的连续帧循环，分开计 compose 与 apply_post。"""
import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config, composite                      # noqa: E402
from lyrics import Timeline, load_lyric_text  # noqa: E402
from theme import palette_for                 # noqa: E402

tl = Timeline.load(config.TIMELINE_PATH)
texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
config.RENDER_SCALE = 1.0

WINDOWS = [("普通段", 40.0, 44.0), ("RLHF/SP1", 62.0, 66.0), ("me 洪水/SP5", 142.0, 146.0),
           ("星落/SP10", 200.0, 204.0), ("执行段", 150.0, 154.0)]

print("== 稳态连续帧（模拟 iter_frames，prev=上一帧）==")
print("%-14s %8s %8s %8s %8s" % ("窗口", "compose", "post", "合计", "fps"))
tot_c = tot_p = tot_n = 0.0
for name, a, b in WINDOWS:
    c = p = 0.0
    n = int(round((b - a) * config.FPS))
    prev = None
    for i in range(n):
        t = a + i / config.FPS
        t0 = time.perf_counter()
        img = composite.compose_frame(t, tl, texts=texts, scale=1.0)
        t1 = time.perf_counter()
        img = composite.apply_post(img, t, palette_for(tl.state_at(t)), prev)
        t2 = time.perf_counter()
        prev = img
        c += t1 - t0; p += t2 - t1
    tot_c += c; tot_p += p; tot_n += n
    print("%-14s %7.1fms %7.1fms %7.1fms %7.1f" % (name, c / n * 1e3, p / n * 1e3, (c + p) / n * 1e3, n / (c + p)))
print("\n全片外推（5085 帧）：compose %.1f min + post %.1f min = %.1f min（不含编码）" % (
    tot_c / tot_n * 5085 / 60, tot_p / tot_n * 5085 / 60, (tot_c + tot_p) / tot_n * 5085 / 60))
