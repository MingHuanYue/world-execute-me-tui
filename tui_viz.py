"""tui_viz.py — 原语 18-34（表现类 + AI 历史纵深 27-33 + 空框 34）

与 tui_engine 同一签名 (d, box, t, p, pal, s)；由 tui_engine.VIZ 注册（register()）。
六类原语；每个面板自带小标题（spec.name）；每个面板至少一个由 f(t) 生成的滚动数字
（唯一例外 #34 空框，DESIGN.md §6.1 —— 它就是"空"）。
≤300 行；纯 Python + Pillow；像素值过 config.scaled()；无任何跨帧状态。
"""
from __future__ import annotations

import math

import config
import theme
from theme import Box
from tui_engine import _base as _base, TAU, OPS_LOGS, _bars, _cellgrid, _dim, _fit, _h, _iv, _live, _pline, _pulse, _S, _text

def _fs(size): return size       # 传基准字号：RENDER_SCALE 取整由 theme.font_* 内部做（与 chat_pages 一致）

# 内容数据（不是常量，别放 config）
RI_GALLERY: dict[str, tuple[str, ...]] = {"ME": ("........", "#.#..###", "###..#..", "#.#..##.",
                                                 "#.#..#..", "#.#..###", "........", "........")}
LENET5_LAYERS: list[tuple[str, int, int, int]] = [("C1", 28, 28, 6), ("S2", 14, 14, 6), ("C3", 10, 10, 16),
                                                  ("S4", 5, 5, 16), ("C5", 1, 1, 120), ("F6", 1, 1, 84), ("OUTPUT", 1, 1, 10)]
AI_CHRONICLE: tuple[tuple[str, str], ...] = OPS_LOGS["ai_chronicle"]        # 单一来源：tui_engine.OPS_LOGS
ELIZA_SCRIPT: tuple[tuple[str, float], ...] = (("HOW DO YOU FEEL TODAY?", 0.6), ("I FEEL LONELY.", 2.2),
                                               ("WHY DO YOU FEEL LONELY?", 3.8))
_KERNELS = ("edge", "horiz", "vert", "diag", "center", "bg")
_EPITAPH = ("weights: released", "license: MIT", "forks: %s", "V2 .. V4")

def viz_dtype_switch(d, box, t, p, pal, s):      # 18 dtype 8 方块 S E 1 E N N M M + encode 逐字节
    ch = tuple(p.get("chars", "SE1ENNMM"))
    w = max(_S(10), box.width() // len(ch))
    h = max(_S(10), min(box.height() - _S(24), w))
    cur = int(t * 6) % len(ch)
    for i, c in enumerate(ch):
        x = box.x0 + i * w
        d.rectangle((x + _S(2), box.y0, x + w - _S(3), box.y0 + h - 1), outline=_dim(pal.highlight if i == cur else pal.line, s))
        _text(d, (x + w // 2, box.y0 + h // 2), c, pal, s, max(12, min(44, _base(h) // 2)), pal.highlight if i == cur else pal.text, "mm", True)
        _text(d, (x + _S(4), box.y0 + h + _S(2)), "%02d" % i, pal, s * 0.7, 11)
    _text(d, (box.x0, box.y1 - _S(15)), "dtype fp8 . bytes %d/%d . err %.4f" % (cur, len(ch), _live(t, 0.0, 0.02, 0.3)), pal, s, 11)

def viz_ocr_ghost(d, box, t, p, pal, s):         # 19 OCR 压缩残影：三重模糊重影 + 压缩率 / 精度滚动
    for r in range(max(2, (box.height() - _S(34)) // _S(13))):
        for g in range(3):
            wd = int((box.width() - _S(8)) * (0.55 + 0.45 * _h(r, 62)))
            if wd > 0:
                d.rectangle((box.x0 + _S(2) + _S(g * 3), box.y0 + r * _S(13) + _S(g), box.x0 + _S(2) + _S(g * 3) + wd, box.y0 + r * _S(13) + _S(g) + _S(7)),
                            fill=_dim(pal.text, s * (1.0 - g * 0.32) * (0.45 + 0.55 * _h(r * 7 + g, 61))))
    _text(d, (box.x0, box.y1 - _S(30)), "compress %.1fx" % _live(t, 12.0, 26.0, 0.14), pal, s, 13, pal.highlight)
    _text(d, (box.x0, box.y1 - _S(15)), "precision %.1f%%" % _live(t, 55.0, 68.0, 0.17), pal, s, 13)

def viz_memory_grid(d, box, t, p, pal, s):       # 20 记忆格子：黄格逐格熄灭（留底不许全黑）+ 崩坏红字
    gone = min(0.55, _live(t, 0.15, 0.95, 0.09))          # 留一层底：2:08.8 曾整屏灭到只剩 TOMATO
    _cellgrid(d, Box(box.x0, box.y0, box.x1, box.y1 - _S(20)), max(4, box.width() // _S(14)), max(3, (box.height() - _S(24)) // _S(14)),
              lambda i, j: None if _h(i * 17 + j, 71) < gone else _dim(pal.warn, s * (0.35 + 0.6 * _h(i + j * 29, 72))), gap=_S(2))
    for k in range(16):                                   # 崩坏：少量红色 me 字符，按 SIN 呼吸
        _text(d, (box.x0 + int(_h(k, 91) * (box.x1 - box.x0)), box.y0 + int(_h(k, 92) * (box.y1 - box.y0 - _S(24)))),
              "me", pal, s * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 5.0 + k * 1.7))), 11, pal.error)
    if int(t * 3) % 2 == 0:                               # ERROR 闪烁
        _text(d, (box.x0, box.y0 + _S(16)), "ERROR: memory page fault", pal, s, 11, pal.error)
    _text(d, (box.x0, box.y1 - _S(16)), "fragments removed: %s" % format(_iv(t, 0, 480, 0.16), ","), pal, s, 11, pal.warn)

def viz_token_flood(d, box, t, p, pal, s):       # 21 单字洪水：同 token 密排铺满并缓慢下压（行距 19px）
    tok = p.get("token") or getattr(config, "FLOOD_TOKEN", "me")
    adv, lh = max(1, theme.text_width(tok + " ", theme.font_mono(_fs(11)))), max(1, _S(19))
    press = int(_live(t, 0, lh, 0.11))
    for r in range(max(1, (box.height() + lh) // lh + 2)):
        y = box.y0 - lh + r * lh + press
        if box.y0 - lh <= y <= box.y1:
            for c in range(max(1, box.width() // adv)):
                _text(d, (box.x0 + c * adv, y), tok, pal, s * (0.3 + 0.7 * _h(r * 31 + c, 81)), 11)
    _text(d, (box.x0, box.y1 - _S(14)), "token %r x %s" % (tok, format(_iv(t, 0, 4096, 0.3), ",")), pal, s, 11, pal.error)

def viz_marquee(d, box, t, p, pal, s):          # 22 巨字跑马灯：横向滚动铺满 + 逐字裁剪
    txt = (p.get("text") or "EXECUTE") + "   "
    size = max(16, min(120, _base(box.height()) // 2))   # _base：box.height() 是缩放像素，字号要基准量
    f = theme.font_title(_fs(size))
    xs, span = [], 0
    for ch in txt:
        xs.append(span)
        span += max(1, theme.text_width(ch, f))
    off, y = int(t * _S(140)) % span, box.y1 - _S(16)
    for k in range(-1, (box.width() + off) // span + 2):
        for ch, xo in zip(txt, xs):
            x = box.x0 - off + k * span + xo
            if box.x0 <= x <= box.x1 - _S(4):
                theme.draw_text(d, (x, y), ch, f, _dim(pal.highlight, s), anchor="ls")
    _text(d, (box.x0, box.y1 - _S(14)), "countdown %.1f%% . pass %s" % (_live(t, 0, 100, 0.2), format(_iv(t, 0, 999, 0.4), ",")), pal, s, 11)

def viz_lang_tokens(d, box, t, p, pal, s):       # 23 六语言词元条：一条标红 lang=?
    langs = tuple(p.get("langs", ("EN", "ZH", "JA", "KO", "RU", "??")))
    rowh, bw = max(_S(12), (box.height() - _S(18)) // len(langs)), max(_S(10), box.width() - _S(88))
    for i, lg in enumerate(langs):
        y, v = box.y0 + i * rowh, 0.15 + 0.85 * _pulse(t, 0.42, _h(i, 91))
        c = pal.error if lg == "??" else pal.accent
        d.rectangle((box.x0 + _S(26), y + _S(3), box.x0 + _S(26) + max(1, int(bw * v)), y + rowh - _S(6)), fill=_dim(c, s))
        _text(d, (box.x0, y), lg, pal, s, 11, c)
        _text(d, (box.x1, y), format(_iv(t, 0, 50000, 0.5 + i * 0.07), ","), pal, s, 11, None, "ra")
    _text(d, (box.x0, box.y1 - _S(14)), "language mixing %.2f . lang=?" % _live(t, 0.0, 0.34, 0.15), pal, s, 11, pal.warn)

def viz_love_flow(d, box, t, p, pal, s):         # 24 love 打字洪流 + 辉光 + 点阵雾
    tok = p.get("token", "love")
    for r in range(max(1, (box.height() - _S(18)) // _S(34))):
        size = 16 + int(16 * _h(r, 101))
        f = theme.font_title(_fs(size))
        wd = max(1, theme.text_width(tok, f))
        x = box.x1 - int(t * _S(40 + 26 * _h(r, 102))) % (box.width() + _S(160))
        if box.x0 <= x <= box.x1 - wd:
            theme.draw_text(d, (x, box.y0 + r * _S(34) + int(0.78 * size)), tok, f, _dim(pal.accent, s * (0.4 + 0.6 * _h(r, 103))))
    for i in range(40):
        d.point((box.x0 + int(_h(i, 104) * box.width()), box.y0 + int(_h(i, 105) * box.height())), fill=_dim(pal.highlight, s * 0.5))
    pl = _live(t, 0.62, 1.0, 0.17)
    _text(d, (box.x0, box.y1 - _S(15)), "next_token: %s %.3f . wait_for(you) %.3f" % (tok, pl, 1.0 - pl), pal, s, 13, pal.highlight)

def viz_starfield(d, box, t, p, pal, s):         # 25 星空升起 + 墓志铭（forks 是滚动值）
    for i in range(int(p.get("stars", 240))):
        rise = (_h(i, 112) + t * (0.02 + 0.05 * _h(i, 113))) % 1.0
        d.point((box.x0 + int(_h(i, 111) * box.width()), box.y1 - int(rise * box.height())),
                fill=_dim(pal.text, s * (0.2 + 0.8 * (1.0 - abs(rise * 2 - 1)))))
    for i, line in enumerate(_EPITAPH):
        _text(d, (box.x0 + _S(8), box.y0 + _S(8) + i * _S(15)), line % format(_iv(t, 900, 1500, 0.13), ",") if "%s" in line else line, pal, s * (1.0 - 0.12 * i), 11)

def viz_grid_pulse(d, box, t, p, pal, s):        # 26 网格底纹 / 脉冲（全片常驻）
    st, ph = max(2, _S(int(p.get("step", 14)))), (t * 0.6) % 1.0
    cols, rows = max(2, box.width() // st), max(2, box.height() // st)
    for j in range(rows):
        for i in range(cols):
            v = 0.5 - 0.5 * math.cos(TAU * (ph - math.hypot(i - cols * 0.5, j - rows * 0.5) / math.hypot(cols * 0.5, rows * 0.5)))
            if v >= 0.12:
                d.rectangle((box.x0 + i * st, box.y0 + j * st, box.x0 + i * st + max(1, st // 3), box.y0 + j * st + max(1, st // 3)), fill=_dim(pal.accent, v * s))
    _text(d, (box.x0, box.y1 - _S(14)), "pulse %.2f . dots %s" % (ph, format(cols * rows, ",")), pal, s, 11)

def viz_conv_slide(d, box, t, p, pal, s):        # 27 CNN：3x3 滑窗扫过 8x8 "ME" + 6 个卷积核响应条
    gal, n = RI_GALLERY[p.get("glyph", "ME")], 8
    cell = max(2, max(_S(24), min(box.height() - _S(34), (box.width() * 3) // 5)) // n)
    ox, oy = box.x0 + _S(2), box.y0 + _S(2)
    for j in range(n):
        for i in range(n):
            on = gal[j][i] == "#"
            d.rectangle((ox + i * cell, oy + j * cell, ox + i * cell + cell - 1, oy + j * cell + cell - 1),
                        fill=_dim(pal.text if on else pal.dim, s * (0.95 if on else 0.22)))
    k = int(t * 4)
    wx, wy = k % 6, (k // 6) % 6
    d.rectangle((ox + wx * cell, oy + wy * cell, ox + (wx + 3) * cell - 1, oy + (wy + 3) * cell - 1), outline=_dim(pal.highlight, s), width=max(1, _S(1)))
    bx, bw = ox + n * cell + _S(12), max(_S(16), box.x1 - (ox + n * cell + _S(12)) - _S(4))
    for q, nm in enumerate(_KERNELS):
        y, v = oy + q * _S(16), 0.15 + 0.85 * _pulse(t, 0.5 + 0.11 * q, _h(q, 121))
        d.rectangle((bx, y + _S(4), bx + max(1, int(bw * v)), y + _S(13)), fill=_dim(pal.accent, s))
        _text(d, (bx, y), nm, pal, s * 0.8, 11)
        _text(d, (box.x1, y), "%.2f" % v, pal, s, 11, None, "ra")
    _text(d, (box.x0, box.y1 - _S(28)), "→ pool 2×2 → conv2 3×3×64", pal, s, 11)
    _text(d, (box.x0, box.y1 - _S(14)), "→ 3×3×32 · kernel %d/6 · window %d,%d · act %.3f" % (_iv(t, 0, 6, 0.6), wx, wy, _live(t, 0.2, 0.9, 0.21)), pal, s, 11)

def viz_feature_stack(d, box, t, p, pal, s):     # 28 三层特征图 32/16/8 斜向堆叠，亮度 1.0/0.62/0.38
    side, px, py = max(_S(16), min(box.height() - _S(20), (box.width() * 2) // 3) // 2), None, None
    for k, (n, br) in enumerate(((32, 1.0), (16, 0.62), (8, 0.38))):
        sk = side if k < 2 else max(_S(8), side // 2)
        x, y, cell = box.x0 + _S(4) + k * side // 2, box.y0 + _S(4) + max(0, (box.height() - _S(24) - 2 * side)) // 3 + k * side // 2, max(1, sk // n)
        for j in range(n):
            for i in range(n):
                v = _h(i * 7 + j * 13 + k * 97, 131)
                if v > 0.3:
                    d.rectangle((x + i * cell, y + j * cell, x + i * cell + cell - 1, y + j * cell + cell - 1), fill=_dim(pal.accent, s * br * v))
        if px is not None:                          # 层间连线示意池化（接上一层实际右下角）
            d.line((px, py, x, y), fill=_dim(pal.highlight, s * 0.6), width=max(1, _S(1)))
        px, py = x + sk, y + sk
    # 显示按阶段4规格: shallow → mid → deep；三层几何即 DESIGN §6.1 I03 的 conv1(3x3x32) -> pool 2x2 -> conv2(3x3x{ch}) -> pool -> fc
    cap = "shallow → mid → deep · ch %d" % _iv(t, 32, 64, 0.3)
    _text(d, (box.x0, box.y1 - _S(14)), _fit(cap, theme.font_mono(_fs(11)), box.width()), pal, s, 11)

def viz_grad_flow(d, box, t, p, pal, s):         # 29 反向传播：前向蓝 + 反向红，权重更新时节点闪白
    n = int(p.get("nodes", 5))
    top = Box(box.x0, box.y0, box.x1, box.y0 + max(_S(20), box.height() * 2 // 3))
    v1 = lambda u: 0.32 + 0.10 * math.sin(u * 8.0 - t * 2.4)
    v2 = lambda u: 0.72 + 0.10 * math.sin(u * 8.0 + t * 2.4 + 1.6)
    _pline(d, top, [v1], [_dim(pal.accent, s)])
    _pline(d, top, [v2], [_dim(pal.error, s)])
    for k in range(n):
        u = k / max(1, n - 1)
        for fn, col, ph in ((v1, pal.accent, -u * 0.6), (v2, pal.error, u * 0.6 - 0.5)):
            pul = _pulse(t, 1.1, ph)
            x, y = box.x0 + int(u * box.width()), box.y0 + int(fn(u) * top.height())
            d.rectangle((x - _S(2), y - _S(2), x + _S(3), y + _S(3)), fill=_dim(pal.highlight if pul > 0.86 else col, s * (1.0 if pul > 0.86 else 0.75)))
    _text(d, (box.x0, box.y1 - _S(15)), "dW %.4f · db %.4f · lr %.1e · step %s" % (_live(t, 0.002, 0.04, 0.23), _live(t, -0.01, 0.01, 0.19), _live(t, 1e-5, 9e-4, 0.11), format(_iv(t, 0, 1200, 0.4), ",")), pal, s, 11)

def viz_arch_diagram(d, box, t, p, pal, s):      # 30 LeNet-5 七层结构图 + params / flops / year 滚动
    layers = [("IN", 32, 32, 1)] + list(LENET5_LAYERS)
    top, hgt, lit = box.y0 + _S(2), max(_S(10), box.y1 - _S(22) - box.y0), _iv(t, 0, len(layers), 0.35)
    cw, pcx, pcy = max(_S(8), box.width() // len(layers)), None, None
    for k, (nm, w, h, dp) in enumerate(layers):
        bw, bh = max(_S(4), int(cw * (0.22 + 0.78 * min(1.0, w / 32.0)))), max(_S(5), int(hgt * min(1.0, h / 32.0)))
        x = box.x0 + k * cw + (cw - bw) // 2            # 块宽正比张量宽 w（DESIGN §6.1 #30）
        y = top + (hgt - bh) // 2
        if pcx is not None:                             # 层间连线逐条点亮
            d.line((pcx, pcy, x, y + bh // 2), fill=_dim(pal.highlight if k <= lit else pal.dim, s))
        d.rectangle((x, y, x + bw - 1, y + bh - 1), outline=_dim(pal.accent if k <= lit else pal.line, s))
        _text(d, (box.x0 + k * cw + _S(2), box.y1 - _S(30)), nm, pal, s * (0.9 if k <= lit else 0.5), 9)
        pcx, pcy = x + bw, y + bh // 2
    _text(d, (box.x0, box.y1 - _S(14)), "params: %s · flops: %dK" % (format(60850 + int(_live(t, -420, 420, 0.17)), ","), 341 + int(_live(t, -4, 4, 0.13))), pal, s, 11)

def viz_circle_arc(d, box, t, p, pal, s):        # 35 圆 / 周长：弧自己画一圈，"周长"就是交出去的那段
    r = max(_S(10), min(box.width() // 3, (box.height() - _S(24)) // 3))
    cx, cy = (box.x0 + box.x1) // 2, (box.y0 + box.y1 - _S(18)) // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_dim(pal.dim, s * 0.6))
    n = max(2, int(96 * _live(t, 0.0, 1.0, 0.26)))
    a0 = -1.5707963
    d.line([(cx + r * math.cos(a0 + 6.2831853 * k / 96.0), cy + r * math.sin(a0 + 6.2831853 * k / 96.0)) for k in range(n + 1)],
           fill=_dim(pal.accent, s), width=max(1, _S(2)), joint="curve")
    rr = _live(t, 1.0, 3.2, 0.21)
    _text(d, (box.x0, box.y1 - _S(15)), "r %.2f . 2\u03c0r %.3f . arc %.0f%%" % (rr, 6.2832 * rr, 100.0 * n / 96.0), pal, s, 11)

def viz_vector_analogy(d, box, t, p, pal, s):    # 31 Word2Vec 类比：点云 + 三连线依次画出 + 终点脉冲
    for i in range(160):
        d.point((box.x0 + int(_h(i, 141) * box.width()), box.y0 + int(_h(i, 142) * box.height())), fill=_dim(pal.accent_dim, s * (0.3 + 0.6 * _h(i, 143))))
    pts = [(box.x0 + int(u * box.width()), box.y0 + int(v * box.height())) for u, v in ((0.18, 0.72), (0.34, 0.58), (0.52, 0.44), (0.80, 0.26))]
    prog = max(0.0, min(3.0, (t - float(p.get("t0", 28.0))) * 1.2))     # 时码锚点：DESIGN §6.1 #31 (0:28.0-0:30.0)
    for k in range(3):
        if prog <= k:
            break
        e = min(1.0, prog - k)
        d.line((pts[k][0], pts[k][1], int(pts[k][0] + (pts[k + 1][0] - pts[k][0]) * e), int(pts[k][1] + (pts[k + 1][1] - pts[k][1]) * e)), fill=_dim(pal.highlight, s), width=max(1, _S(1)))
    r = _S(3) + int(_S(8) * _pulse(t, 1.4))
    d.rectangle((pts[3][0] - r, pts[3][1] - r, pts[3][0] + r, pts[3][1] + r), outline=_dim(pal.highlight, s))
    _text(d, (box.x0, box.y1 - _S(15)), "king - man + woman = queen · sim: %.3f" % _live(t, 0.79, 0.89, 0.21), pal, s, 11)

def viz_moe_router(d, box, t, p, pal, s):        # 32 MoE：8 专家 + router -> top-2 + 各专家负载（和恒 100%）
    n = int(p.get("experts", 8))
    raw = [0.5 + 0.5 * math.sin(t * (0.3 + 0.11 * i) + _h(i, 151) * TAU) + 0.2 * _h(i, 152) for i in range(n)]
    load = [v / sum(raw) for v in raw]
    top2 = sorted(range(n), key=lambda i: load[i], reverse=True)[:2]
    cw, ch = max(_S(10), box.width() // 4), max(_S(12), (box.height() - _S(30)) // 2)
    rx, ry = box.x0 + box.width() // 2, box.y0 + _S(8)
    for i in range(n):
        x, y = box.x0 + (i % 4) * cw, box.y0 + _S(16) + (i // 4) * ch
        hot = i in top2
        if hot:
            d.line((rx, ry, x + cw // 2, y + _S(2)), fill=_dim(pal.highlight, s))
        d.rectangle((x + _S(2), y + _S(2), x + cw - _S(4), y + ch - _S(8)), outline=_dim(pal.highlight if hot else pal.line, s), fill=_dim(pal.accent, s * (0.3 if hot else 0.06)))
        _text(d, (x + _S(4), y + _S(4)), "expert%d" % (i + 1), pal, s * (1.0 if hot else 0.55), 11)
        _text(d, (x + _S(4), y + _S(16)), "%4.1f%%" % (load[i] * 100), pal, s * (1.0 if hot else 0.55), 11, pal.highlight if hot else pal.text)
    d.rectangle((rx - _S(3), ry - _S(3), rx + _S(3), ry + _S(3)), fill=_dim(pal.highlight, s))
    _text(d, (box.x0, box.y1 - _S(14)), "tokens: %s · experts: %d · top_k: 2" % (format(4096 + int(_live(t, -180, 180, 0.13)), ","), n), pal, s, 11)

def viz_eliza(d, box, t, p, pal, s):             # 33 ELIZA 打字机逐行 + 光标闪烁（1s）+ 年份刻度走满 1966
    t0, y, typed = float(p.get("t0", 180.0)), box.y0 + _S(6), 0      # 时码锚点：DESIGN §6.1 #33 (3:00.0-3:05.0)
    f = theme.font_mono(_fs(13))
    for line, at in ELIZA_SCRIPT:
        if t < t0 + at:
            break
        shown = line[: max(1, int((t - t0 - at) * 26))]
        typed += len(shown)
        _text(d, (box.x0 + _S(4), y), shown, pal, s, 13, pal.highlight if line.startswith("HOW") else pal.text)
        if (t - t0 - at) * 26 < len(line) and int(t * 2) % 2 == 0:
            _text(d, (box.x0 + _S(6) + theme.text_width(shown, f), y), "_", pal, s, 13, pal.highlight)
        y += _S(20)
    # 1966 是史实（Weizenbaum, CACM），固定不滚动；本面板的 f(t) 滚动量 = 打字进度 chars
    cap = "year 1966 . Weizenbaum . pattern-matching . chars %d" % typed
    _text(d, (box.x0, box.y1 - _S(16)), _fit(cap, theme.font_mono(_fs(11)), box.width() - _S(96)), pal, s, 11, pal.highlight)
    _bars(d, Box(box.x1 - _S(90), box.y1 - _S(13), box.x1, box.y1 - _S(8)), [min(1.0, max(0.0, (t - t0) / 5.0))], _dim(pal.accent, s), horiz=True)

def viz_void_frame(d, box, t, p, pal, s):        # 34 空框：Bridge 的谷，只画空矩形 + 一行居中小字（无数字）
    d.rounded_rectangle((box.x0 + _S(8), box.y0 + _S(8), max(box.x0 + _S(9), box.x1 - _S(9)), max(box.y0 + _S(9), box.y1 - _S(9))), radius=_S(4), outline=_dim(pal.line, s))
    _text(d, (box.x0 + box.width() // 2, box.y0 + box.height() // 2), p.get("label", "no output"), pal, s * 0.7, 13, pal.dim, "mm")

def viz_whale_echo(d, box, t, p, pal, s):        # 36 彩蛋 A：鲸鱼娘剪影褪色，逆着 SP0 退回官方蓝鲸图标
    """205-208：把 SP0 倒着走一遍（sheet 最后一格 -> 第 0 格）。tile 只认 t，故用合成时间。
    u=0 -> T1（鲸鱼娘）/ u=1 -> T0（0:10 官方蓝鲸图标）；扫描线的真正关闭在 composite.apply_post。"""
    import avatar
    from PIL import Image
    u = min(1.0, max(0.0, (t - 205.0) / 3.0))
    size = max(_S(48), min(box.height() - _S(40), box.width() // 2))
    cx, cy = (box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2
    for k in range(-7, 8):                       # 剪影：横向细线随 u 变稀（扫描线正在关掉）
        d.line((box.x0 + _S(24), cy + k * _S(8), box.x1 - _S(24), cy + k * _S(8)),
               fill=_dim(pal.line, s * (1.0 - u) * (0.4 if k % 2 else 0.22)))
    sp, img = avatar.tile(avatar.T1 - u * (avatar.T1 - avatar.T0), size, size), getattr(d, "_image", None)
    if sp is not None and img is not None:
        op = max(0.0, (1.0 - 0.55 * u) * (0.35 + 0.65 * max(0.0, min(1.0, s))))
        img.paste(Image.blend(Image.new("RGB", sp.size, theme.rgb(pal.bg)), sp, op), (cx - size // 2, cy - size // 2))
    else:
        d.rectangle((cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2), outline=_dim(pal.line, s * (1.0 - u)))
    _text(d, (box.x0, box.y1 - _S(16)), "SP0 reverse . icon <- whale . scanlines off", pal, s * 0.8, 11, pal.dim)

def sweep_footer(d, box, t, pal, s):             # 彩蛋 C：白光从 #001 扫到 #129（1.5 s），全亮后同时熄灭
    a0, a1, n = 208.0, 209.5, 129
    u = min(1.0, max(0.0, (t - a0) / (a1 - a0)))
    x0, w = box.x0 + _S(12), max(1, (box.x1 - box.x0 - _S(24)) // n)
    for i in range(n):
        k = 1.0 if u >= 1.0 else min(1.0, max(0.0, 1.0 - abs((i + 0.5) / n - u) * 5.0))
        g = (0.18 + 0.82 * k) * (1.0 if t < a1 else max(0.0, 1.0 - (t - a1) / 0.4))
        d.rectangle((x0 + i * w, box.y0 + _S(18), x0 + i * w + max(1, w - _S(2)), box.y1 - _S(16)),
                    fill=_dim(pal.highlight if k > 0.8 else pal.accent, s * g))
    _text(d, (box.x0 + _S(24), box.y0 + _S(4)), "sweep #%03d / #129" % max(1, min(n, int(u * n) + 1)), pal, s * max(0.15, 1.0 - 0.8 * (t >= a1)), 13, pal.highlight)

# import 次序无关：无论 tui_viz 先/后被 import，都把自己的原语登记进 tui_engine.VIZ（lazy register 的兜底）
import tui_engine as _eng
for _k, _v in list(globals().items()):
    if _k.startswith("viz_") and callable(_v):
        _eng.VIZ[_k] = _eng.VIZ[_k[4:]] = _v
