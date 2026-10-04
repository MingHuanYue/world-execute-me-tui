# -*- coding: utf-8 -*-
"""底栏对齐全片审计 —— 逐行检查 token 点亮是否覆盖完整、有没有句首空窗。

**直接调用渲染端的 chat_pages._lit_at**，不重复实现公式，避免两边跑偏。

用法：python data/check_align.py
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chat_pages  # noqa: E402
import config       # noqa: E402
from lyrics import Timeline, load_lyric_text  # noqa: E402

LRC = r"D:\CloudMusic\Mili - world.execute (me) ;.lrc"
TS = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")


def read_lrc(path: str) -> list[float]:
    if not os.path.exists(path):
        return []
    out = []
    for raw in io.open(path, encoding="utf-8", errors="replace").read().splitlines():
        m = TS.match(raw.strip())
        if m and m.group(3).strip():
            out.append(round(int(m.group(1)) * 60 + float(m.group(2)), 3))
    return sorted(out)


def main() -> int:
    tl = Timeline.load(config.TIMELINE_PATH)
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    print("=" * 90)
    print("A) 行时间 vs LRC 原始时间戳")
    print("=" * 90)
    lrc = read_lrc(LRC)
    if lrc:
        dev = [abs(L.t - min(lrc, key=lambda x: abs(x - L.t))) for L in tl.lines]
        print("  LRC %d 条 / 时间轴 %d 行   最大偏差 %.4f s   >0.05s 的行 %d" % (
            len(lrc), len(tl.lines), max(dev), sum(1 for d in dev if d > 0.05)))
    else:
        print("  （找不到 LRC，跳过）")

    print()
    print("=" * 90)
    print("B) 逐词行：点亮覆盖 / 句首空窗（调 chat_pages._lit_at）")
    print("=" * 90)
    rows = []
    for L in tl.lines:
        en = (texts[L.i][0] if L.i < len(texts) else "") or ""
        toks = en.split()
        if not (L.words or ()) or not toks:
            continue
        M = len(toks)
        at_end = chat_pages._lit_at(L, toks, L.end - 1e-6)[0]
        t_first = next((L.t + (L.end - L.t) * k / 100.0 for k in range(101)
                        if chat_pages._lit_at(L, toks, L.t + (L.end - L.t) * k / 100.0)[0] > 0), None)
        rows.append((L.i, M, at_end, 0.0 if t_first is None else t_first - L.t, L.end - L.t, en))
    full = sum(1 for r in rows if r[2] >= r[1])
    print("  逐词行 %d 行   窗口走完**全部点亮** %d 行   未覆盖 %d 行" % (len(rows), full, len(rows) - full))
    print("  句首空窗 >0.25 s：%d 行   最大空窗 %.2f s" % (
        sum(1 for r in rows if r[3] > 0.25), max((r[3] for r in rows), default=0.0)))
    bad = [r for r in rows if r[2] < r[1] or r[3] > 0.25]
    if bad:
        print("  有问题的行：")
        for i, M, ae, gap, dur, en in bad[:20]:
            print("    L%03d  %d token  末亮 %d  空窗 %.2fs  时长 %.2fs  %s" % (i, M, ae, gap, dur, en[:32]))
    else:
        print("  全部逐词行：窗口内依次点亮、无空窗、无漏词。")

    print()
    print("=" * 90)
    print("C) 整行模式（timeline 无 word 时间的行）")
    print("=" * 90)
    now = [L.i for L in tl.lines if not (L.words or ())]
    print("  共 %d 行：%s" % (len(now), ", ".join("L%03d" % i for i in now)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
