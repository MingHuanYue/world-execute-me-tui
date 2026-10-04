"""mathviz.py — 01 PRETRAIN「数学自比」段的 11 个中栏原语

与 tui_engine / tui_viz 同一签名 (d, box, t, p, pal, s)；由 tui_engine.VIZ 注册（尾部兜底）。
每个原语：f(t) 纯函数（抖动一律 hash01，无 random、无跨帧状态）；只用调色板色；
底部固定一行滚动数字（_live/_iv 驱动）。所有坐标经 _xy() 夹进 box，保证不越框。
≤300 行；纯 Python + Pillow。
"""
from __future__ import annotations

import math

import theme
from theme import Box
from tui_engine import TAU, _cellgrid, _dim, _F, _fit, _h, _iv, _live, _pulse, _S, _text

import tui_viz  # noqa: F401  —— 触发 tui_viz 的注册兜底，保证三种 import 次序都齐


def _xy(box, u, v):
    """0..1 归一化坐标 -> 像素；clamp 进 box（不越框的唯一出口）。"""
    return (box.x0 + int(min(0.999, max(0.0, u)) * (box.width() - 1)),
            box.y0 + int(min(0.999, max(0.0, v)) * (box.height() - 1)))


def _cap(d, box, text, pal, s, color=None):
    """底部滚动数字行（统一出口：每个原语都必须调到）。"""
    _text(d, (box.x0, box.y1 - _S(16)), _fit(text, theme.font_mono(_F(11)), box.width()), pal, s, 11, color or pal.highlight)


def _dots(d, box, n, fn, color, s):
    """dots：fn(i) -> (u, v, alpha) 或 None。"""
    for i in range(n):
        q = fn(i)
        if q is not None:
            d.point(_xy(box, q[0], q[1]), fill=_dim(color, s * q[2]))


def viz_point_set(d, box, t, p, pal, s):         # 1 深蓝底散落点云
    d.rectangle((box.x0, box.y0, max(box.x0, box.x1 - 1), max(box.y0, box.y1 - 1)), fill=_dim(pal.accent, s * 0.10))
    f = lambda i: (0.34 + (0.06 + 0.52 * _h(i, 3) ** 0.55) * math.cos(TAU * _h(i, 4) + t * 0.02) * 0.95,
                   0.44 + (0.06 + 0.52 * _h(i, 3) ** 0.55) * math.sin(TAU * _h(i, 4) + t * 0.02) * 0.60,
                   0.45 + 0.55 * _h(i, 5))
    _dots(d, box, 1000, f, pal.accent_dim, s)
    _cap(d, box, "point set · N = 1000 / counting = %s" % format(_iv(t, 120, 640, 0.11), ","), pal, s)


def viz_grid_3d(d, box, t, p, pal, s):           # 2 点云被坐标轴拉扯、展开为 3D 网格
    W, H = box.width(), box.height()
    P = lambda u, v, w: (box.x0 + int(W * (0.46 + 0.46 * (u - 0.5 * v))), box.y0 + int(H * (0.82 - 0.24 * (v + 1.7 * w))))
    n = 6
    for k in range(n + 1):
        a, b = P(0, k / n, 0), P(1, k / n, 0)
        d.line((a[0], a[1], b[0], b[1]), fill=_dim(pal.accent_dim, s * (0.30 + 0.6 * (1 - k / n))))
        a, b = P(k / n, 0, 0), P(k / n, 1, 0)
        d.line((a[0], a[1], b[0], b[1]), fill=_dim(pal.accent_dim, s * 0.55))
    for u, v in ((0, 0), (1, 0), (0, 1), (1, 1)):
        h = 0.35 + 0.5 * _h(int(u * 2 + v * 3), 11)
        a, b = P(u, v, 0), P(u, v, h)
        d.line((a[0], a[1], b[0], b[1]), fill=_dim(pal.accent, s * (0.4 + 0.5 * _pulse(t, 0.5, _h(int(u + v * 2), 12)))))
    _dots(d, box, 220, lambda i: (0.10 + 0.60 * _h(i, 13), 0.78 - 0.34 * _h(i, 14), 0.3 + 0.5 * _h(i, 15)), pal.highlight, s)
    _cap(d, box, "dims: 3 · basis: (x, y, z) · nodes %s" % format(_iv(t, 200, 1000, 0.09), ","), pal, s)


def viz_circumference(d, box, t, p, pal, s):     # 3 圆周边缘高亮 -> 像弹簧一样展开成直线
    r, n, u = _live(t, 8.2, 9.4, 0.17), 40, _pulse(t, 0.085)
    for i in range(n):
        a = TAU * i / n
        v = (0.30 + 0.16 * math.cos(a)) + (0.10 + 0.78 * i / (n - 1) - (0.30 + 0.16 * math.cos(a))) * u
        w = (0.40 + 0.20 * math.sin(a)) + (0.68 - (0.40 + 0.20 * math.sin(a))) * u
        x, y = _xy(box, v, w)
        d.rectangle((x, y, min(box.x1 - 1, x + max(1, _S(2))), min(box.y1 - 1, y + max(1, _S(2)))),
                    fill=_dim(pal.highlight if u > 0.5 else pal.accent, max(0.45, s * (0.35 + 0.65 * (0.5 + 0.5 * math.cos(a))))))
    _cap(d, box, "C = 2πr = %.2f" % (TAU * r), pal, s)


def viz_tangent(d, box, t, p, pal, s):           # 4 正弦波上切线短线段闪动，斜率随 t 变
    x0 = _live(t, 0.12, 0.88, 0.13)
    y_of = lambda u: 0.44 + 0.24 * math.sin(TAU * u)
    for i in range(200):
        d.point(_xy(box, i / 199.0, y_of(i / 199.0)), fill=_dim(pal.accent_dim, s * 0.85))
    hl, k = 0.10, math.cos(TAU * x0) * 0.24
    a, b = _xy(box, x0 - hl, y_of(x0) + k * hl), _xy(box, x0 + hl, y_of(x0) - k * hl)
    d.line((a[0], a[1], b[0], b[1]), fill=_dim(pal.highlight, s * (0.45 + 0.55 * _pulse(t, 1.6))), width=max(1, _S(1)))
    d.rectangle((a[0] - _S(1), a[1] - _S(1), a[0] + _S(1), a[1] + _S(1)), fill=_dim(pal.warn, s))
    _cap(d, box, "slope = cos(x) = %.3f · tangent: 1" % math.cos(TAU * x0), pal, s)


def viz_asymptote(d, box, t, p, pal, s):         # 5 曲线无限向右延伸逼近渐近线
    L, y_as = _live(t, 0.96, 1.04, 0.13), 0.30
    for i in range(0, box.width(), max(2, _S(7))):
        d.point((box.x0 + i, box.y0 + int(y_as * (box.height() - 1))), fill=_dim(pal.dim, s))
    _dots(d, box, 180, lambda i: (i / 179.0, y_as + 0.52 * math.exp(-3.4 * (i / 179.0)) + 0.01 * math.sin(t * 2 + i * 0.3), 0.85), pal.accent, s)
    d.rectangle((box.x1 - _S(5), box.y0 + int((y_as + 0.52 * math.exp(-3.4)) * (box.height() - 1)) - _S(2),
                 box.x1 - _S(2), box.y0 + int((y_as + 0.52 * math.exp(-3.4)) * (box.height() - 1)) + _S(2)), fill=_dim(pal.highlight, s))
    _cap(d, box, "lim(x→∞) f(x) = %.3f" % L, pal, s)


def viz_limits(d, box, t, p, pal, s):            # 6 渐近线高亮 + 极值点 + 上下界
    env = _live(t, 0.32, 0.86, 0.13)
    for i in range(160):
        u = i / 159.0
        d.point(_xy(box, u, 0.50 - env * 0.30 * math.sin(TAU * u)), fill=_dim(pal.accent, s * 0.8))
    for y, c in ((0.18, pal.dim), (0.82, pal.dim)):
        for i in range(0, box.width(), max(2, _S(8))):
            d.point((box.x0 + i, box.y0 + int(y * (box.height() - 1))), fill=_dim(c, s))
    hot = 0.5 - env * 0.30 * math.sin(TAU * 0.25)
    d.rectangle((box.x0 + int(0.25 * (box.width() - 1)) - _S(2), box.y0 + int(hot * (box.height() - 1)) - _S(2),
                 box.x0 + int(0.25 * (box.width() - 1)) + _S(2), box.y0 + int(hot * (box.height() - 1)) + _S(2)), fill=_dim(pal.warn, s))
    for i in range(0, box.width(), max(2, _S(8))):
        d.point((box.x0 + i, box.y0 + int(0.18 * (box.height() - 1))), fill=_dim(pal.highlight, s * (0.4 + 0.6 * _pulse(t, 0.9))))
    _cap(d, box, "upper: +∞ · lower: -∞ · |f| ≤ %.2f" % env, pal, s)


def viz_current(d, box, t, p, pal, s):           # 7 电流脉冲在网格中跳动
    cols, rows = 9, 5
    head = int(t * 8) % (cols * rows)
    def cell(i, j):
        d_ = abs(i + j * cols - head) % (cols * rows)
        return _dim(pal.highlight if d_ == 0 else pal.accent_dim, s * (0.9 if d_ == 0 else max(0.12, 0.5 - d_ * 0.03)))
    _cellgrid(d, Box(box.x0, box.y0, box.x1, box.y1 - _S(18)), cols, rows, cell, gap=_S(7))
    _cap(d, box, "current · AC · I = %.3f" % _live(t, 0.2, 1.8, 0.23), pal, s)


def viz_rectifier(d, box, t, p, pal, s):         # 8 正弦被整流成平稳直线
    u = _live(t, 0.0, 1.0, 0.09)
    for i in range(180):
        x = i / 179.0
        sn = math.sin(TAU * x * 1.5)
        v = 0.50 - 0.30 * (sn * (1 - u) + abs(sn) * u * (1 - 0.6 * u))
        d.point(_xy(box, x, v), fill=_dim(pal.accent if u < 0.55 else pal.highlight, s * 0.9))
    d.line((box.x0, box.y0 + int(0.50 * (box.height() - 1)), box.x1 - 1, box.y0 + int(0.50 * (box.height() - 1))), fill=_dim(pal.dim, s))
    _cap(d, box, "AC → DC · rectifier: on · ripple %.3f" % (0.30 * max(0.0, 1.0 - u)), pal, s)


def viz_vision_mask(d, box, t, p, pal, s):       # 9 中栏被像素块遮蔽（黑屏）
    cover = _live(t, 0.55, 0.95, 0.07)
    cols, rows = max(4, box.width() // _S(24)), max(3, (box.height() - _S(20)) // _S(24))
    _cellgrid(d, Box(box.x0, box.y0, box.x1, box.y1 - _S(20)), cols, rows,
              lambda i, j: _dim(pal.dim, s * 0.16) if _h(i * 13 + j * 7, 21) < cover else None)
    _cap(d, box, "vision: masked · n_ctx: 0 · cover %d%%" % int(cover * 100), pal, s, pal.warn)


def viz_dizzy(d, box, t, p, pal, s):             # 10 相位错位 + 字符抖动（hash01 驱动）
    chars = "@#*+·xo"
    for i in range(48):
        a = TAU * i / 48.0 + t * 0.25
        rr = 0.10 + 0.26 * (0.6 + 0.4 * _h(i, 31))
        u = min(0.92, max(0.05, 0.50 + rr * math.cos(a) * 1.35 + (_h(i, 32) - 0.5) * 0.05 + 0.02 * math.sin(t * 2.1 + i)))
        v = min(0.86, max(0.06, 0.44 + rr * math.sin(a) * 0.85 + (_h(i, 33) - 0.5) * 0.05 + 0.02 * math.cos(t * 1.7 + i * 0.7)))
        x, y = _xy(box, u, v)
        theme.draw_text(d, (x, y), chars[int(_h(i, 34) * len(chars)) % len(chars)], theme.font_mono(_F(11)),
                        _dim(pal.accent if i % 3 else pal.highlight, s * (0.4 + 0.6 * _h(i, 35))), anchor="ls")
    _cap(d, box, "dizzy: %.2f" % _live(t, 0.6, 1.4, 0.19), pal, s)


def viz_timeline(d, box, t, p, pal, s):          # 11 向后滚动的时间轴
    y = box.y0 + box.height() * 2 // 3
    d.line((box.x0, y, box.x1 - 1, y), fill=_dim(pal.accent_dim, s))
    step = box.width() / 8.0
    off = (t * _live(t, 60.0, 340.0, 0.09)) % step
    for k in range(-1, 11):
        x = int(box.x1 - off - k * step)
        if box.x0 + _S(1) <= x < box.x1 - _S(1):
            d.line((x, y - _S(6), x, y + _S(6)), fill=_dim(pal.accent, s))
            if x - _S(14) >= box.x0 and x <= box.x1 - _S(34):
                _text(d, (x - _S(14), y - _S(34)), "%d" % (2024 - k), pal, s * 0.8, 9, pal.dim)
    _cap(d, box, "timeline · traveling · t = %.1fs" % math.fmod(t, 100.0), pal, s)


# import 次序无关：三种次序下都把 11 个原语（全名 + 短名）登记进 tui_engine.VIZ
import tui_engine as _eng
for _k, _v in list(globals().items()):
    if _k.startswith("viz_") and callable(_v):
        _eng.VIZ[_k] = _eng.VIZ[_k[4:]] = _v

_ATTEMPTS = ((76.4, 77.9, "tomato"), (79.2, 80.8, "cat"), (82.1, 83.8, "tomato"), (84.2, 85.0, "cat"))


def _silhouette(n, shape, sd):
    """目标点阵（归一化 -1..1），带 z 以便 3D 旋绕。**sd = 本次尝试的种子** -> 每次形状都不同。"""
    out = []
    ra = TAU * _h(sd, 41)                                        # 每次尝试整体转一个独立角度
    sq = 0.55 + 0.35 * _h(sd, 43)                                # 每次盖扁/拉长的比例不同
    ca, sa = math.cos(ra), math.sin(ra)
    for i in range(n):
        th = TAU * _h(i * 7 + sd, sd)
        rr = math.sqrt(0.10 + 0.90 * _h(i * 13 + sd, sd + 1))     # sqrt：盘内均匀，不然只堆边缘成环
        x, y = math.cos(th) * rr * 0.94, math.sin(th) * rr * sq
        z = (_h(i * 17 + sd, sd + 2) - 0.5) * 1.2 * rr            # 盘面起伏
        if shape == "tomato" and i % 12 == 0: x, y, z = (i % 3 - 1) * 0.15 * sq, -0.80 - 0.07 * ((i * 7) % 5), 0.0
        if shape == "cat" and i % 10 == 0: x, y, z = (0.44 if i % 20 else -0.44), -0.70, 0.0
        out.append((x * ca - y * sa, x * sa + y * ca, z))         # 整体旋转
    return out


def viz_self_anchor(d, box, t, p, pal, s):       # 36 变形尝试：粒子 3D 旋绕聚合，**每次都不一样**
    """f(t) 纯函数。种子 sd 由尝试次序决定：散落起点 / 目标形状 / 到达先后各不相同，所以不会重复。"""
    cx, cy = (box.x0 + box.x1) // 2, (box.y0 + box.y1 - _S(16)) // 2
    at = next(((k, a0, a1, sh) for k, (a0, a1, sh) in enumerate(_ATTEMPTS) if a0 <= t <= a1 + 0.34), None)
    sd = at[0] * 977 + 13 if at else 0                           # 本次尝试的种子（先于 R/n 定义）
    ca, sa = math.cos(t * 1.05), math.sin(t * 1.05)              # 原地绕 y 轴旋绕
    R, n = min(box.width(), box.height() - _S(20)) // 2, 800 + int(200 * _h(sd, 47))
    pts = _silhouette(n, at[3], sd) if at else None
    alpha = max(0.0, 1.0 - (t - at[2]) / 0.34) if (at and t > at[2]) else 1.0
    for i in range(n):
        th, rad = TAU * _h(i * 7 + sd, sd + 3), 0.45 + 0.55 * _h(i * 11 + sd, sd + 4)
        sx, sy = math.cos(th) * rad * 1.85, math.sin(th) * rad * 1.30
        sz = (_h(i * 5 + sd, sd + 6) - 0.5) * 1.6
        if at is None:
            u, tx, ty, tz = 0.0, sx, sy, sz
        else:
            _k, a0, a1, _sh = at
            raw = min(1.0, max(0.0, (t - a0) / (a1 - a0) * 1.62))  # 60% 处刚看出轮廓
            dly = 0.42 * _h(i + sd, sd + 9)                        # 每个粒子到达先后不同 -> 更乱更活
            u = min(1.0, max(0.0, (raw - dly) / max(1e-6, 1.0 - dly)))
            tx, ty, tz = pts[i]
            if t > a1:                                             # 锁死：向外推 + 抬升 + 拉深
                kk = min(1.0, (t - a1) / 0.34)
                tx, ty, tz = tx + (1.9 * kk if tx >= 0 else -1.9 * kk), ty - 0.6 * kk, tz * (1.0 + 2.4 * kk)
        w = 1.0 - u
        px, py, pz = tx + (sx - tx) * w, ty + (sy - ty) * w, tz + (sz - tz) * w
        rx, rz = px * ca - pz * sa, px * sa + pz * ca              # 绕 y 轴 3D 旋转
        dep = 1.0 / (1.0 + rz * 0.42)                              # 透视：近大远小
        x, y = cx + int(rx * dep * R), cy + int(py * dep * R)
        if box.x0 <= x < box.x1 and box.y0 <= y < box.y1 - _S(14):
            d.point((x, y), fill=_dim(pal.text, (0.30 + 0.45 * dep) * (0.6 + 0.4 * s) * alpha))
    cap = "art: none · reason: identity_lock" if (at and t > at[2]) else ("attempts: %d/3 · %s" % (1 + sum(1 for a0, a1, _ in _ATTEMPTS if t > a1), at[3]) if at else "art: none · attempts: 0/3")
    _text(d, (box.x0, box.y1 - _S(14)), cap, pal, s, 11)
