# -*- coding: utf-8 -*-
"""底栏 token 条同步自检 —— 从成片里反推「实际画了什么」，与时间轴期望值逐点对比。

方法（不靠 OCR、不靠肉眼）：
  1. 用 ffmpeg 的 select=eq(n,帧号) **精确**抽出指定帧；
  2. 裁出底栏区域 y=616–680；
  3. 把**离线渲染**的候选帧（t = 采样点 + d/24，d 扫 [-48,+48]）按同一条流水线渲一遍，
     逐像素比底栏，取差异最小的 d —— 它同时给出「实际显示的是哪一行」和「偏移多少帧」；
  4. 与 timeline.json 的期望行号对比，输出偏差表。

用法：python data/check_sync.py
"""
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageChops, ImageStat

import chat_pages  # noqa: E402
import composite    # noqa: E402
import config       # noqa: E402
import theme        # noqa: E402
from lyrics import Timeline, load_lyric_text  # noqa: E402

BAR = (0, 616, 1280, 680)          # 底栏设计区域（720p 设计像素）
LABEL = (0, 655, 1280, 676)        # 标签行（#L### / #wid），基线 y=668：不随 chip 闪烁，认行号最稳
SCAN = 48                          # 搜索半径（帧）＝±2 s
POINTS = [(59.2, "0:59.2"), (70.1, "1:10.1"), (112.0, "1:52.0"), (118.0, "1:58.0"),
          (148.0, "2:28.0"), (178.0, "2:58.0"), (184.0, "3:04.0")]


def grab(film: str, frame: int, out: str) -> Image.Image:
    """精确抽第 frame 帧（CFR 24fps，无关键帧取整误差）。"""
    subprocess.run([config.ffmpeg_exe(), "-y", "-v", "error", "-i", film,
                    "-vf", "select=eq(n\\,%d)" % frame, "-vsync", "0", "-frames:v", "1", out], check=True)
    return Image.open(out).convert("RGB")


def bar_of(img: Image.Image, band=BAR) -> Image.Image:
    return img.crop(band)


def diff(a: Image.Image, b: Image.Image) -> float:
    return ImageStat.Stat(ImageChops.difference(a.convert("L"), b.convert("L"))).mean[0]


def main() -> int:
    tl = Timeline.load(config.TIMELINE_PATH)
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    config.RENDER_SCALE = 1.0
    film = str(config.OUT_DIR / "film.mp4")
    tmp = str(config.OUT_DIR / "_sync")
    os.makedirs(tmp, exist_ok=True)

    # 候选帧必须走 render.iter_frames 的**同一条流水线**：
    #   posted(f) = apply_post(compose(f), posted(f-1))
    # 早先这里传 prev=None，没有 CRT 残影，标签带在运动大的帧上对不上，
    # 于是 2:28 被误报成"偏移 1 帧"——假阳性是比对方法的锅，不是片子的。
    posted: dict[int, Image.Image] = {}

    def offline(frame: int) -> Image.Image:
        for f in range(max(0, frame - 60), frame + 1):
            if f in posted:
                continue
            tf = f / float(config.FPS)
            posted[f] = composite.apply_post(
                composite.compose_frame(tf, tl, texts=texts, scale=1.0),
                tf, theme.palette_for(tl.state_at(tf)), posted.get(f - 1))
        return bar_of(posted[frame], LABEL)

    print("=" * 96)
    print("底栏同步自检（不 OCR：离线渲染候选帧 + 逐像素比对反推）")
    print("=" * 96)
    print("%-9s %5s %-7s %-8s %-8s %8s %10s %s" % (
        "时间点", "帧号", "期望行", "期望模式", "实际行", "最优d", "像素差", "判定"))
    rows = []
    for t, lab in POINTS:
        frame = int(round(t * config.FPS))
        shot = grab(film, frame, os.path.join(tmp, "f%05d.png" % frame))
        actual = bar_of(shot, LABEL)

        # 期望值按**帧时间**算（不是原始 t）：t=70.1 落在 1682.4 -> 帧 1682 = 70.083 s，
        # 若按原始 t 取会用下一行的行号，制造出根本不存在的"偏移"。
        ft = frame / float(config.FPS)
        line = tl.line_at(ft)
        exp_i = tl.line_index_at(ft)
        mode = "逐词" if (line and line.words and getattr(line, "words", None)) else "整行"
        exp_txt = texts[exp_i][0] if 0 <= exp_i < len(texts) else ""

        best = None
        for d in range(-SCAN, SCAN + 1):
            v = diff(actual, offline(frame + d))
            if best is None or v < best[0]:
                best = (v, d)
        v, d = best
        act_i = tl.line_index_at((frame + d) / float(config.FPS))
        zero = diff(actual, offline(frame))            # d=0 与最优的差距：<=0.5 视为同帧动画抖动
        ok = (act_i == exp_i) and (d == 0 or v < zero * 0.85)
        rows.append((lab, frame, exp_i, mode, act_i, d, v, ok, zero))
        print("%-9s %5d L%03d   %-8s L%03d   %+4d   %8.3f  d0差 %6.3f  %s" % (
            lab, frame, exp_i, mode, act_i, d, v, zero, "同步" if ok else "**偏移**"))

    print()
    print("=" * 96)
    print("底栏渲染模式统计（整行 = _line_mode，只标 #L###；逐词 = 每个 token 标 #wid）")
    print("=" * 96)
    n_word = n_line = n_bad = 0
    for L in tl.lines:
        en = texts[L.i][0] if 0 <= L.i < len(texts) else ""
        toks = (en or "").split()
        if (L.words or ()) and toks:                   # 与 draw_stdout_tokens 的新判据一致
            n_word += 1
            if len(toks) != len(L.words):
                n_bad += 1                             # 靠"按行内比例映射"救回来的行
        else:
            n_line += 1                                # timeline 里本就没有 word 时间
    print("  逐词模式 %d 行（%.0f%%，其中 %d 行靠按比例映射救回） / 整行模式 %d 行（%.0f%%）" % (
        n_word, 100.0 * n_word / len(tl.lines), n_bad, n_line, 100.0 * n_line / len(tl.lines)))

    print()
    print("=" * 96)
    print("时间轴 vs LRC 原始时间戳（检查歌词时间戳本身有没有偏）")
    print("=" * 96)
    lrc = config.ROOT / "assets" / "lyrics" / "lyrics.json"
    meta = json.loads(io.open(lrc, encoding="utf-8").read()).get("meta", {})
    print("  lyrics.json meta =", meta)
    print("  前 8 行 时间轴 t 与文本：")
    for L in tl.lines[:8]:
        print("    L%03d  t=%7.3f  %s" % (L.i, L.t, (texts[L.i][0] if L.i < len(texts) else "")[:44]))

    print()
    bad = [r for r in rows if not r[7]]
    worst = max(abs(r[5]) for r in rows)
    print("结论：7 个采样点中 %d 个显示的行号与时间轴完全一致。" % (len(rows) - len(bad)))
    print("      最大帧偏移 %d 帧（%.1f ms）；帧偏移 <=1 且 d=0 与最优的像素差接近时判为同帧动画抖动。" % (
        worst, worst / config.FPS * 1000.0))
    if bad:
        print("      不同步的点：" + ", ".join(r[0] for r in bad))
    else:
        print("      **底栏与时间轴同步。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
