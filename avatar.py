"""avatar.py — SP0「自我成形」：左栏头像从官方鲸鱼图标长成鲸鱼娘（DESIGN.md §11.10）

职责：读 assets/avatar/morph_sheet.png（由 data/build_avatar.py 离线烘焙），按 f(t) 取格贴进头像框。
约束：<= 300 行；纯 Pillow；**无跨帧状态**（整条演化是 t 的纯函数，§11.6）；不做任何每帧图像合成。
"""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image

import config
from theme import Box, Palette

SHEET_REL = "assets/avatar/morph_sheet.png"
COLS, ROWS, TILE = 12, 8, 64      # 96 格，每格 64x64（= 左栏头像框的设计尺寸，1:1 贴合）
T0, T1 = 10.0, 22.0               # 演化窗口（DESIGN §11.10）
DIM_AT = 194.0                    # 之后熄灭为光标（DESIGN §1.2）
AVA_DIM = 0.62                    # 头像单独压暗系数：它比画面其它部分亮得多，不能跟着一起提亮


@lru_cache(maxsize=1)
def _sheet():
    """装载期读一次 sprite sheet；缺文件返回 None（布局照常，退化成一个空框）。"""
    p = config.ROOT / SHEET_REL
    return Image.open(p).convert("RGB") if p.exists() else None


def morph_alpha(t: float) -> float:
    """0:10–0:22 从官方图标长成鲸鱼娘；窗口外夹到 0 / 1。"""
    if t <= T0:
        return 0.0
    if t >= T1:
        return 1.0
    return (t - T0) / (T1 - T0)


def frame_index(t: float) -> int:
    return int(morph_alpha(t) * (COLS * ROWS - 1) + 0.5)


def tile(t: float, w: int, h: int):
    """当前演化格的 w x h 版本（NEAREST 放大 -> 保留块状硬边）。"""
    sh = _sheet()
    if sh is None:
        return None
    i = frame_index(t)
    x, y = (i % COLS) * TILE, (i // COLS) * TILE
    return sh.crop((x, y, x + TILE, y + TILE)).resize((w, h), Image.NEAREST)


def draw(d, box: Box, t: float, pal: Palette, hint: str, s: float = 1.0) -> None:
    """把当前演化格贴进 box：状态染色 -> 贴图 -> 框线 -> 故障划线；194s 后熄灭为光标。"""
    sc = config.scaled
    if t >= DIM_AT:
        if int(t * 2.0) % 2 == 0:
            cx, cy = (box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2
            d.rectangle([cx - sc(4), cy - sc(7), cx + sc(4), cy + sc(7)], fill=pal.text)
        return
    w, h = box.x1 - box.x0, box.y1 - box.y0
    sp = tile(t, w, h)
    img = getattr(d, "_image", None)
    if sp is None or img is None:
        d.rectangle([box.x0, box.y0, box.x1, box.y1], fill=pal.bg, outline=pal.line)
        return
    sp = sp.point(lambda v: int(v * AVA_DIM))          # 单独压暗：全局 GAIN=1.14 会把头像顶到过曝
    if hint in ("error", "outro"):                     # 状态染色：金 -> 红 / 星白
        tint = pal.error if hint == "error" else pal.highlight
        sp = Image.blend(sp, Image.new("RGB", (w, h), tint), 0.35)
    img.paste(sp, (box.x0, box.y0))
    d.rectangle([box.x0, box.y0, box.x1, box.y1], outline=pal.line)
    if hint == "error":                                # 故障：叠一道抖动划线
        j = int(sc(3) * math.sin(t * 13.0))
        mid = (box.y0 + box.y1) // 2 + j
        d.line([box.x0, mid, box.x1, mid], fill=pal.error)
