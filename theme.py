"""theme.py — 配色 / 字体 / 绘图原语。所有绘制都经过这里，保证全片质感统一。
（为满足 300 行上限，顶层定义之间只用 1 个空行。）

坐标约定：Box / xy / pts 是设备像素（构造方调 config.scaled() 换算）；字号 / step / radius /
笔宽是标量设计值，本模块内部换算。s 参数是亮度系数，不是缩放系数。

中英混排（DESIGN 5.5）：Pillow 无字形回退，draw_text 逐字符选 mono(Consolas) -> cjk(SimHei)
-> sym(Segoe UI Symbol)；判缺字用 .notdef 对照，不能靠 getlength()==0。实测反查
（_ref/_d_cjk2.py）：聊天行 拉丁 18 / CJK 17、版权条 11 / 10，都差 1px => 中英同一 nominal
size；DESIGN 5.2 的 "SimHei 16 + Consolas 12" 是欠定解，已作废。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
TODO = "TODO(阶段2): 实现"   # 保留名字；本文件已全部实现
_MISSING = "\uFFFF"          # 非字符哨兵：三套字体都只有 .notdef（U+E123 在 Segoe UI Symbol 里是真字形，不能当哨兵）
_RADIUS = 4                  # 面板圆角（设计像素）
@dataclass(frozen=True)
class Box:
    x0: int; y0: int; x1: int; y1: int
    def inset(self, dx: int, dy: int = 0) -> "Box":
        return Box(self.x0 + dx, self.y0 + dy, self.x1 - dx, self.y1 - dy)
    def width(self) -> int: return self.x1 - self.x0
    def height(self) -> int: return self.y1 - self.y0
@dataclass(frozen=True)
class Palette:
    bg: str; line: str; text: str; dim: str; accent: str
    accent_dim: str; warn: str; error: str; ok: str; highlight: str
    def __getitem__(self, k: str) -> str:    # 兼容 dict 写法
        return getattr(self, k)
    def get(self, k: str, default=None):     # 兼容 dict.get
        return getattr(self, k, default)
_F, _S = config.PALETTE_FILM, config.PALETTE_SRC
PALETTE_RUNNING: dict = {
    "bg": _F["bg"], "line": _F["line"], "text": _F["text"], "dim": _F["dim"],
    "accent": _F["bar_to"], "accent_dim": _F["bar_from"],
    "warn": _F["warn"], "error": _F["error"], "ok": _S["ok"], "highlight": "#e8eeff"}
PALETTE_WARN: dict = {**PALETTE_RUNNING, "text": _F["warn_text"], "warn": _F["warn"], "highlight": _F["warn"]}
PALETTE_ERROR: dict = {**PALETTE_RUNNING, "line": "#7a4a4a", "accent": _F["error"],
                       "accent_dim": _F["error_text"], "text": _F["error_text"], "highlight": "#ff8a80"}
PALETTE_OUTRO: dict = {**PALETTE_RUNNING, "accent": _S["accent2"], "accent_dim": _S["panel2"], "highlight": "#f2f6ff"}
_PALETTES: dict = {config.STATE_RUNNING: Palette(**PALETTE_RUNNING), config.STATE_WARN: Palette(**PALETTE_WARN),
                   config.STATE_ERROR: Palette(**PALETTE_ERROR), config.STATE_OUTRO: Palette(**PALETTE_OUTRO)}

def palette_for(state: str) -> Palette:
    "state 取 running / warn / error / outro；未知值抛 ValueError。"
    if state not in _PALETTES:
        raise ValueError("未知状态 " + repr(state) + "；只接受 " + repr(sorted(_PALETTES)))
    return _PALETTES[state]

def rgb(c) -> tuple:
    "#rrggbb 或 RGB(A) 元组 -> (r, g, b)。"
    if isinstance(c, (tuple, list)):
        return (int(c[0]), int(c[1]), int(c[2]))
    s = str(c).lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))

def mix(a, b, u: float) -> tuple:
    "a 到 b 线性插值，u 已 clamp。"
    u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
    ca, cb = rgb(a), rgb(b)
    return tuple(int(ca[i] + (cb[i] - ca[i]) * u) for i in range(3))

def shade(c, k: float) -> tuple:
    "亮度系数：k=1 不变，k<1 变暗（可 >1，clamp 255）。s 参数就用这个。"
    k = 0.0 if k < 0.0 else k
    return tuple(min(255, int(v * k)) for v in rgb(c))

_FONT_CANDIDATES: dict = {
    "mono": [os.environ.get("DSH_FONT_MONO"), "C:/Windows/Fonts/consola.ttf"],
    "cjk": [os.environ.get("DSH_FONT_CJK"), "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc"],
    "sym": [os.environ.get("DSH_FONT_SYM"), "C:/Windows/Fonts/seguisym.ttf"],
    "title": [os.environ.get("DSH_FONT_TITLE"),
              str(config.ROOT / "assets" / "fonts" / "Anton-Regular.ttf"),
              "C:/Windows/Fonts/Anton-Regular.ttf"]}
@lru_cache(maxsize=8)
def _font_path(fam: str) -> str:
    """字体路径；找不到直接抛错，绝不静默降级（DESIGN 5.1）。"""
    got = next((x for x in _FONT_CANDIDATES[fam] if x and os.path.isfile(x)), None)
    if got:
        return got
    raise FileNotFoundError(
        "字体缺失 " + fam + "，试过 " + repr(_FONT_CANDIDATES[fam]) + "。套件里的 Anton 是 SIL OFL，"
        "从 Google Fonts 取一份放到 assets/fonts/Anton-Regular.ttf；其余可用 DSH_FONT_* 覆盖。")

@lru_cache(maxsize=256)
def _raw(fam: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_font_path(fam), max(1, int(px)))   # px 是设备像素

def font_mono(size: int) -> ImageFont.FreeTypeFont:
    "设计字号 -> mono 字体（内部已按 RENDER_SCALE 换算）。"
    return _raw("mono", config.scaled(size))

def font_cjk(size: int) -> ImageFont.FreeTypeFont:
    return _raw("cjk", config.scaled(size))

_SPIN = ("|", "/", "-", chr(92))    # 旋转指示：运行中


def font_title(size: int) -> ImageFont.FreeTypeFont:
    return _raw("title", config.scaled(size))

@lru_cache(maxsize=4096)
def _fam_for(cp: int) -> str:
    "码位 -> 字体族。比 .notdef 的**像素**判缺字：bbox 不可靠（Consolas 的 .notdef 与 'A' 同 bbox）。"
    ch = chr(cp)
    if ch.isspace():
        return "mono"
    for fam in ("mono", "cjk", "sym"):
        f = _raw(fam, 32)
        m = f.getmask(ch)
        if m.size[0] > 0 and m.size[1] > 0 and bytes(m) != bytes(f.getmask(_MISSING)):
            return fam
    return "mono"     # 三套都没有：按缺字画出来，让问题可见

def _layout(text: str, f: ImageFont.FreeTypeFont, scale: float = 1.0):
    "拆成 [(char, font)]，CJK / 符号自动换族。返回 (items, mono_font)。"
    px = int(getattr(f, "size", 13))
    if scale != 1.0:
        f = _raw("mono", px := max(1, int(round(px * scale))))
    cache, items = {}, []
    for ch in text.replace("\r", "").replace("\n", ""):
        fam = _fam_for(ord(ch))
        items.append((ch, f if fam == "mono" else cache.setdefault(fam, _raw(fam, px))))
    return items, f

def text_width(text: str, f: ImageFont.FreeTypeFont) -> int:
    "混排字符串的显示宽度（设备像素）。"
    items, _ = _layout(text, f, 1.0)
    return int(round(sum(fo.getlength(ch) for ch, fo in items)))

def _stamp(td: ImageDraw.ImageDraw, xy: tuple, text: str,
           f: ImageFont.FreeTypeFont, fill, scale: float = 1.0) -> float:
    "在任意 ImageDraw 上逐字符画混排文本；xy 的 y 是基线。返回结束 x。"
    items, _ = _layout(text, f, scale)
    x = float(xy[0])
    for ch, fo in items:
        td.text((round(x), xy[1]), ch, font=fo, fill=fill, anchor="ls")
        x += fo.getlength(ch)
    return x

def draw_text(d: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
              f: ImageFont.FreeTypeFont, fill: str,
              scale: float = 1.0, anchor: str = "la") -> None:
    """中英混排：按字符区间自动切换 font_mono / font_cjk（Pillow 无字形回退）。
    y 恒为基线；anchor 只有水平位（l/m/r）有意义——DESIGN 5.5 第 4 条：SimHei 与 Consolas 的
    ascent 不同，逐字按上沿对齐会让中英基线差 3-4 px。scale 是几何缩放（字号 + advance）。"""
    if not text: return None
    items, _ = _layout(text, f, scale)
    total = sum(fo.getlength(ch) for ch, fo in items)
    x, h = float(xy[0]), (anchor or "l")[0]
    x -= total / 2.0 if h == "m" else total if h == "r" else 0.0
    for ch, fo in items:
        d.text((round(x), xy[1]), ch, font=fo, fill=fill, anchor="ls")
        x += fo.getlength(ch)

def draw_frame_box(d: ImageDraw.ImageDraw, box: Box, name: str | None,
                   pal: Palette, s: float = 1.0, spin: float | None = None) -> Box:
    """面板外框 + 标题标签；返回去掉标题栏后的内容区 Box。s 是框线/标题的亮度系数
    （一般传 0.45 + 0.35*pulse(t)），不做坐标缩放。形制：圆角 1px 描边 + 四角加重 +
    上边框内叠 "| name" 标签。"""
    w1 = max(1, config.scaled(1))
    d.rounded_rectangle([box.x0, box.y0, box.x1, box.y1], radius=config.scaled(_RADIUS),
                        outline=shade(pal.line, 0.45 + 0.55 * max(0.0, min(1.0, s))), width=w1)
    L, w2 = config.scaled(7), max(1, config.scaled(2))
    hi = shade(pal.line, min(1.0, 0.80 + 0.55 * s))
    for px, py, sx, sy in ((box.x0, box.y0, 1, 1), (box.x1, box.y0, -1, 1),
                           (box.x0, box.y1, 1, -1), (box.x1, box.y1, -1, -1)):
        d.line([px, py, px + sx * L, py], fill=hi, width=w2)
        d.line([px, py, px, py + sy * L], fill=hi, width=w2)
    if name:
        f = font_mono(13)
        ty = box.y0 + config.scaled(config.TITLE_BAR_H - 1)
        d.rectangle([box.x0 + config.scaled(10), box.y0, box.x0 + config.scaled(14)
                     + text_width(name, f), ty + config.scaled(2)], fill=pal.bg)
        pre = _SPIN[int(spin * 9) % 4] if spin is not None else "|"   # 传了 spin 就是运行中的转圈
        draw_text(d, (box.x0 + config.scaled(12), ty), pre + " " + name, f,
                  shade(pal.line, min(1.0, 0.5 + 0.5 * s)))
    return Box(box.x0 + w1, box.y0 + config.scaled(config.TITLE_BAR_H) + w1,
               box.x1 - w1, box.y1 - w1)

def draw_bar(d: ImageDraw.ImageDraw, box: Box, frac: float, color: str,
             s: float = 1.0) -> None:
    "横向条：填充部分用 color（乘亮度 s），其余为同色暗轨。frac 已 clamp。"
    u = 0.0 if frac < 0.0 else (1.0 if frac > 1.0 else float(frac))
    d.rectangle([box.x0, box.y0, box.x1, box.y1], fill=mix(color, "#050813", 0.82))
    full = int(round(box.width() * u))
    if full > 0:
        d.rectangle([box.x0, box.y0, box.x0 + full - 1, box.y1], fill=shade(color, s))

def draw_grid_bg(d: ImageDraw.ImageDraw, box: Box, pal: Palette,
                 step: int = 16, s: float = 1.0) -> None:
    "点阵底纹（step 是设计像素，内部换算）。参考片实测：UI 色 10% 混底。"
    st, col = max(2, config.scaled(step)), shade(mix(pal.bg, pal.line, 0.10), s)
    for yy in range(box.y0 + st // 2, box.y1, st):
        for xx in range(box.x0 + st // 2, box.x1, st):
            d.point((xx, yy), fill=col)

def draw_glow_text(d: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                   f: ImageFont.FreeTypeFont, color: str, radius: int = 3) -> None:
    "标题辉光：字渲到 bbox 小图 -> 高斯模糊 -> 贴回 -> 再压实心字（DESIGN 11.5）。"
    r = max(1, config.scaled(radius))
    asc, desc = f.getmetrics()
    w, h = text_width(text, f) + 4 * r + 4, asc + desc + 4 * r + 4
    bx, by = 2 * r + 2, asc + 2 * r + 2
    m = Image.new("L", (w, h), 0)
    _stamp(ImageDraw.Draw(m), (bx, by), text, f, 255)
    m = m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: min(255, int(v * 1.5)))
    img = getattr(d, "_image", None)
    if img is None:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            draw_text(d, (xy[0] + dx * r, xy[1] + dy * r), text, f, shade(color, 0.25))
    else:
        ox, oy = xy[0] - bx, xy[1] - by
        img.paste(Image.composite(Image.new("RGB", (w, h), rgb(color)),
                                  img.crop((ox, oy, ox + w, oy + h)), m), (ox, oy))
    draw_text(d, xy, text, f, color)

@lru_cache(maxsize=4096)
def hash01(i: int, salt: int = 0) -> float:
    """确定性伪随机，纯函数。同一 (i, salt) 永远同值——粒子唯一随机源（DESIGN 11.6）。"""
    x = (i * 2654435761 ^ salt * 40503) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return x / 4294967296.0

def particle_points(d: ImageDraw.ImageDraw, pts, pal: Palette, s: float) -> None:
    """pts = (x, y, alpha)，设备像素。1px 点——DESIGN 11.7 的 A 路线（0.10 ms/2000 粒，约是
    sprite 路线 C 的 1/50；RGBA 椭圆路线 B 在 4K 下 33 ms，禁止使用）。"""
    if s <= 0.0: return None
    r0, g0, b0 = rgb(pal.bg)
    r1, g1, b1 = rgb(pal.accent)
    for p in pts:
        a = p[2] * s
        a = 0.0 if a < 0.0 else (1.0 if a > 1.0 else a)
        if a <= 0.0: continue
        d.point((int(p[0]), int(p[1])),
                fill=(int(r0 + (r1 - r0) * a), int(g0 + (g1 - g0) * a), int(b0 + (b1 - b0) * a)))

def perspective_grid(d: ImageDraw.ImageDraw, box: Box, cols: int, rows: int,
                     horizon: float, depth: float, pal: Palette,
                     phase: float, s: float) -> None:
    """逐行缩放 + 行偏移模拟透视。horizon 0=盒底 / 1=盒顶（消失线）；depth 是透视强度指数
    （建议 0.6-1.6）；phase 是 0..1 滚动相位，由 f(t) 驱动，不累积状态。"""
    cx, half = (box.x0 + box.x1) / 2.0, box.width() / 2.0
    hz = box.y1 - max(0.0, min(1.0, horizon)) * box.height()
    span = max(1.0, box.y1 - hz)
    col = shade(mix(pal.bg, pal.line, 0.35), s)
    dpt, ph = max(0.1, depth), phase - int(phase)
    for r in range(max(1, rows)):
        yy = int(box.y0 + (r + ph) / max(1, rows) * box.height())
        t = (yy - hz) / span
        if t <= 0.02: continue
        hw = half * (1.0 if t >= 1.0 else t ** dpt)
        step = 2.0 * hw / max(1, cols - 1)
        for c in range(max(1, cols)):
            xx = int(cx - hw + c * step)
            if box.x0 <= xx <= box.x1:
                d.point((xx, yy), fill=col)

@lru_cache(maxsize=128)
def _sprite_cache(text: str, sizes: tuple, color: str) -> dict:
    out: dict = {}
    for sz in sizes:
        f = _raw("mono", max(1, config.scaled(sz)))
        asc, desc = f.getmetrics()
        w = int(sum(fo.getlength(ch) for ch, fo in _layout(text, f)[0])) + 2
        sp = Image.new("RGBA", (w, asc + desc + 2), (0, 0, 0, 0))
        _stamp(ImageDraw.Draw(sp), (1, asc + 1), text, f, rgb(color) + (255,))
        out[int(sz)] = sp
    return out

def sprite_cache(text: str, sizes, color: str) -> dict:
    """预渲染字形 sprite，返回 {size: RGBA 图}（size 是设计字号，键 int）。xy 是 sprite 左上角；
    Anton 巨字请用 font_title 自行渲染后 paste_sprite。比每帧 draw_text 快一个量级。"""
    return dict(_sprite_cache(text, tuple(int(x) for x in sizes), color))

def paste_sprite(img: Image.Image, sp: Image.Image, xy: tuple[int, int],
                 alpha: float) -> None:
    """带 mask 贴图。img 是 RGBA 时走 alpha_composite（不会把 alpha 乘两次）。"""
    a = 0.0 if alpha < 0.0 else (1.0 if alpha > 1.0 else float(alpha))
    if sp is None or a <= 0.01:
        return None
    cut = sp
    if a < 0.999:
        cut = sp.copy()
        cut.putalpha(sp.getchannel("A").point(lambda v: int(v * a)))
    pos = (int(xy[0]), int(xy[1]))
    img.alpha_composite(cut, pos) if img.mode == "RGBA" else img.paste(cut, pos, cut)
