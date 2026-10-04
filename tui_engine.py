"""tui_engine.py — 注册表 / 分发 / 右栏 ops + 原语 1-17

只允许六类绘制原语：dots / grid / bars / wall / big / pline（DESIGN.md §6）。
每个面板用 spec.name 作小标题；面板内至少一个滚动数字，全部由 f(t) 生成（严禁写死）。
≤300 行；纯 Python + Pillow；像素值过 config.scaled()；无任何跨帧状态。
"""
from __future__ import annotations

import math
from typing import Callable

from PIL import ImageDraw

import config
import theme
from lyrics import Timeline
from scenes import PanelSpec
from theme import Box, Palette

TAU = math.tau
_BG = (5, 8, 19)                      # = config.PALETTE_FILM["bg"]
# ==================== 通用工具（tui_viz 复用）====================
def _S(v): return config.scaled(v)
def _dim(c, k):                        # 亮度系数：k>=1 原色，k<=0 落到背景
    k = 0.0 if k < 0.0 else (1.0 if k > 1.0 else k)
    v = int(c[1:], 16)
    return "#%02x%02x%02x" % tuple(int(_BG[b] + (((v >> sh) & 255) - _BG[b]) * k) for b, sh in ((0, 16), (1, 8), (2, 0)))
def _h(i, salt=0):                     # 确定性伪随机 f(i, salt)：纯函数，无状态
    x = math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
    return x - math.floor(x)
def _live(t, a, b, hz, ph=0.0):        # 滚动数字的唯一来源：a..b 之间随 t 平滑往返
    return a + (b - a) * (0.5 - 0.5 * math.cos(TAU * (t * hz + ph)))
def _pulse(t, hz=1.0, ph=0.0): return 0.5 - 0.5 * math.cos(TAU * (t * hz + ph))
def _iv(t, a, b, hz, ph=0.0): return int(_live(t, a, b, hz, ph))
def _F(size): return size       # 传基准字号：RENDER_SCALE 的取整由 theme.font_* 内部做（与 chat_pages 一致）
def _text(d, xy, text, pal, s=1.0, size=11, color=None, anchor="la", title=False):
    # y 传行顶：theme.draw_text 的 y 是基线 -> 补 0.78em（anchor 只有水平位有意义）；文字留 0.78 亮度地板保可读
    theme.draw_text(d, (xy[0], xy[1] + int(0.78 * size)), text, (theme.font_title if title else theme.font_mono)(_F(size)), _dim(color or pal.text, 0.78 + 0.22 * min(1.0, s)), anchor=anchor)
def _fit(text, f, px):
    while text and theme.text_width(text, f) > px:
        text = text[:-1]
    return text
def _cellgrid(d, box, cols, rows, fn, gap=0):
    """grid：每格一个矩形，fn(i, j) -> 颜色 或 None。"""
    cw, ch = max(1, (box.width() - gap * (cols - 1)) // cols), max(1, (box.height() - gap * (rows - 1)) // rows)
    for j in range(rows):
        for i in range(cols):
            c, x, y = fn(i, j), box.x0 + i * (cw + gap), box.y0 + j * (ch + gap)
            if c is not None:
                d.rectangle((x, y, x + cw - 1, y + ch - 1), fill=c)
def _bars(d, box, vals, col, horiz=False, gap=1):
    """bars：vals 每项 0..1；col 为颜色或 col(i)->颜色。"""
    n = max(1, len(vals))
    for i, v in enumerate(vals):
        c = col(i) if callable(col) else col
        v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
        if v <= 0.0:
            continue
        if horiz:
            h = max(1, (box.height() - gap * (n - 1)) // n)
            d.rectangle((box.x0, box.y0 + i * (h + gap), box.x0 + max(1, int(box.width() * v)) - 1, box.y0 + i * (h + gap) + h - 1), fill=c)
        else:
            w = max(1, (box.width() - gap * (n - 1)) // n)
            d.rectangle((box.x0 + i * (w + gap), box.y1 - max(1, int(box.height() * v)), box.x0 + i * (w + gap) + w - 1, box.y1 - 1), fill=c)
def _pline(d, box, fns, cols, dot=False, width=1):
    """pline：逐列取 y 连线；dot=True 用点线。"""
    st = max(1, _S(2 if dot else 1))
    for f, c in zip(fns, cols):
        prev = None
        for x in range(box.x0, box.x1, st):
            y = box.y1 - int(min(1.0, max(0.0, f((x - box.x0) / max(1, box.width() - 1)))) * box.height())
            if prev is not None:
                d.line((prev[0], prev[1], x, y), fill=c, width=width)
                if dot:
                    d.point(prev, fill=c)
            prev = (x, y)
# ==================== 右栏 ops ====================
_OPC = ("ALLGATHER;ALLREDUCE;DISPATCH;COMBINE;PREFILL;FLASH_ATTN;RMSNORM;ROUTER;KV_CACHE;DECODE;SAMPLER;"
        "LOGITS;OPTIM_STEP;CHECKPOINT;ACK;SERVE;BARRIER;OVERLAP;ZERO_STAGE;EP_GROUP;TP_GROUP;PP_STAGE;GRAD_SYNC;"
        "COMM_SCHED;WEIGHT_SWAP;ACT_RECOMP;SHARD_RESHARD;MOE_GATE;MOE_DISPATCH;EXPERT_FFN;TOPK_SOFTMAX;ROPE_APPLY;"
        "QKV_PROJ;PAGED_ATTN;CONT_BATCH;SPEC_DECODE;DRAFT_HEAD;TOKENIZER_BATCH;PROMPT_CACHE;KV_EVICT;SLIDING_WIN;"
        "LOGIT_BIAS;PENALTY_TOPK;REPETITION_MASK;TEMP_SCHEDULE;TOP_P_FILTER;MIN_P_FILTER;NUMERIC_GUARD;NAN_CHECK;"
        "OOM_RETRY;ECC_SCAN;THERMAL_THROTTLE;CLOCK_SYNC;HEALTH_PROBE;WATCHDOG;TRACE_FLUSH;METRIC_PUSH;LOG_ROTATE;"
        "-INF MASK;LANG_CONSISTENCY;YOU.LEAVE();GRACEFUL_DRAIN").split(";")
_OPC_WARN = {"NAN_CHECK", "OOM_RETRY", "ECC_SCAN", "THERMAL_THROTTLE", "WATCHDOG", "GRACEFUL_DRAIN",
             "LANG_CONSISTENCY", "TRACE_FLUSH"}
_OPC_ERR = {"-INF MASK", "YOU.LEAVE()", "OOM_RETRY"}
_CHRON = ("1943 MCCULLOCH-PITTS;1950 TURING TEST;1956 DARTMOUTH;1957 PERCEPTRON;1959 ADALINE;1961 UNIMATE;"
          "1965 DENDRAL;1966 ELIZA;1969 XOR CRITIQUE;1971 AI WINTER;1974 MYCIN;1979 BACKPROP DRAFT;"
          "1980 COGNITRON;1982 HOPFIELD;1986 BACKPROP;1987 NETTALK;1989 LECUN CNN;1990 AI WINTER II;"
          "1995 SVM;1997 LSTM;1998 LENET-5;2006 DEEP BELIEF;2009 IMAGENET;2011 DROPOUT;2012 ALEXNET;"
          "2013 WORD2VEC;2014 GAN;2015 RESNET;2016 ALPHAGO;2017 TRANSFORMER;2018 BERT;2018 GPT-1;"
          "2019 GPT-2;2020 SCALING LAWS;2020 GPT-3;2021 CLIP;2021 CHINCHILLA;2022 RLHF ALIGNMENT;"
          "2023 GPT-4;2024 MOE ROUTING;2025 AGENT LOOPS;2026 DSH TUI").split(";")
OPS_LOGS: dict[str, tuple[tuple[str, str], ...]] = {
    "opcodes": tuple((n, "ERROR" if n in _OPC_ERR else ("WARN" if n in _OPC_WARN else "OK")) for n in _OPC),
    "ai_chronicle": tuple((s, "WARN" if ("XOR" in s or "AI WINTER" in s) else "OK") for s in _CHRON),
}
VIZ: dict[str, Callable[..., None]] = {}
_BOOT = ("protect", "mmap", "gpu", "tokenizer", "weights", "kv_cache", "router", "sampler", "embed", "attn", "dtype", "shard", "nccl", "optim", "serve")

def viz(name: str):
    """把原语注册进 VIZ 的装饰器。"""
    def deco(fn): VIZ[name] = fn; return fn
    return deco

def register(mod=None) -> None:
    """把 tui_viz 里的原语登记进 VIZ（import 时调用一次；可重复调用）。"""
    if mod is None:
        import tui_viz as mod
    for k, v in vars(mod).items():
        if k.startswith("viz_") and callable(v):
            VIZ[k] = VIZ[k[4:]] = v

def draw_visual(d: ImageDraw.ImageDraw, spec: PanelSpec, tl: Timeline, t: float, s: float = 1.0) -> None:
    """画 panel 外框 + 小标题，再按 spec.viz 分发；找不到抛 KeyError。"""
    pal = theme.palette_for(spec.state)
    inner = theme.draw_frame_box(d, spec.box, spec.name, pal, s)
    if spec.viz not in VIZ:
        register()
    VIZ[spec.viz](d, inner, t, spec.params or {}, pal, s)

def draw_ops(d: ImageDraw.ImageDraw, box: Box, tl: Timeline, t: float, pal: Palette,
             s: float = 1.0, params: dict | None = None) -> None:
    """右栏日志自下而上匀速滚动。三段对齐：年份(左)/名称(中)/状态字(右)；截断按运行时 box 宽度算
    （0:19-0:42 的 ops 栏被 spectacle 加宽到 256px 也不裁错）。params={"log": ..., "speed": 条/秒}。"""
    q = params or {}
    key = q.get("log", "opcodes")
    rows = OPS_LOGS.get(key) or OPS_LOGS["opcodes"]
    spd = float(q.get("speed", 0.0)) or (len(rows) / 23.0 if key == "ai_chronicle" else 3.0)
    f, lh, head = theme.font_mono(_F(11)), max(1, _S(13)), t * spd      # 行距 13px -> 满铺 43 行
    for i in range(int(head) - max(0, (box.height() - _S(2)) // lh - 1) - 1, int(head) + 2):
        sch = head - i
        y = int(box.y1 - (sch + 1) * lh)
        if y < box.y0 or y + lh > box.y1:
            continue
        text, st = rows[i % len(rows)]
        k = 1.0 if sch < 0.5 else max(0.3, 1.0 - 0.26 * sch)
        col = pal.warn if st == "WARN" else (pal.error if st == "ERROR" else pal.text)
        year, _, nm = text.partition(" ")           # "1957 PERCEPTRON" -> "1957" + "PERCEPTRON"
        x = box.x0
        if year.isdigit():
            _text(d, (x, y), year, pal, s * k, 11, col)
            x += theme.text_width(year, f) + _S(4)
        _text(d, (x, y), _fit(nm or year, f, box.x1 - x - theme.text_width(st, f) - _S(4)), pal, s * k, 11, col)
        _text(d, (box.x1, y), st, pal, s * k, 11, col, "ra")

# ==================== 原语 1-17（统一签名 d, box, t, p, pal, s；p=spec.params）====================
def viz_boot_check(d, box, t, p, pal, s):        # 1 启动自检：15 行 [ OK ] + 右侧虚线鲸鱼
    n = int(p.get("rows", 15))
    done = int(min(1.0, max(0.0, (t - float(p.get("t0", 2.5))) / 1.5)) * n)
    lh = _S(13)
    for i in range(min(n, max(1, (box.height() - _S(24)) // lh))):
        _text(d, (box.x0 + _S(6), box.y0 + _S(4) + i * lh), "[ %s ] %s" % ("OK" if i < done else "  ", _BOOT[i % len(_BOOT)]),
              pal, s * (1.0 if i < done else 0.45), 11, pal.highlight if i < done else pal.dim)
    wx, wy = box.x0 + box.width() * 5 // 8, box.y0 + box.height() // 3
    for k, (a, b, c, e) in enumerate(((0, 0, 30, 3), (6, 7, 36, 10), (12, 14, 40, 17), (3, 21, 24, 24), (30, 28, 46, 31), (34, 35, 40, 38))):
        if _pulse(t, 0.45, k * 0.11) > 0.2:
            d.rectangle((wx + _S(a), wy + _S(b), wx + _S(c), wy + _S(e + 2)), outline=_dim(pal.line, s))
    _text(d, (box.x0 + _S(6), box.y1 - _S(16)), "checks %d/%d" % (done, n), pal, s, 13, pal.highlight)

def viz_loss_curve(d, box, t, p, pal, s):        # 2 loss 曲线（点线下降）+ lr 三角调度
    base, top = float(p.get("loss", 0.60)), Box(box.x0, box.y0, box.x1, box.y0 + box.height() * 2 // 3)
    _pline(d, top, [lambda u: 0.35 + 0.55 * base + (1.0 - base) * math.exp(-2.6 * u) * 0.75 + 0.03 * math.sin(t * 3.1 + u * 38) + 0.02 * _h(int(u * 240), 7)], [_dim(pal.accent, s)], dot=True)
    lr = _live(t, 1.0e-5, 9.0e-4, 0.09)
    _bars(d, Box(box.x0, top.y1 + _S(3), box.x1, box.y1 - _S(16)),
          [min(1.0, lr / 9.0e-4) * (0.25 + 0.75 * _pulse(t, 0.37, i * 0.16)) for i in range(12)], _dim(pal.accent_dim, s))
    _text(d, (box.x0, box.y1 - _S(15)), "loss %.3f . lr %.1e . step %s" % (base * 0.9 + 0.06, lr, format(_iv(t, 0, 90000, 0.4), ",")), pal, s, 11)

def viz_pipeline_grid(d, box, t, p, pal, s):     # 3 DualPipe：8 PP x 20 micro-batch，蓝斜纹沿对角波前推进
    rows, cols, head = int(p.get("rows", 8)), int(p.get("cols", 20)), 0.0
    head = _live(t, 0, rows + cols, 0.3)
    cell = lambda i, j: _dim(pal.highlight if int((i + j) - head) % 3 == 2 else pal.accent, s * (0.3 + 0.7 * max(0.0, 1.0 - abs((i + j) - head) * 0.5))) if (i + j) - head >= -1.0 else _dim(pal.dim, s * 0.3)
    _cellgrid(d, Box(box.x0, box.y0, box.x1, box.y1 - _S(16)), cols, rows, cell, gap=_S(1))
    _text(d, (box.x0, box.y1 - _S(15)), "%d PP ranks . %d micro-batches . step %s" % (rows, cols, format(_iv(t, 0, 19200, 0.25), ",")), pal, s, 11)

def viz_embedding_matrix(d, box, t, p, pal, s):  # 4 词嵌入扁平格阵（与 #3 同族，格数远少）
    cols, rows = int(p.get("cols", 14)), int(p.get("rows", 7))
    cell = lambda i, j: _dim(pal.accent, s * (0.15 + (_h(i * 31 + j * 7, 0) * 0.55 + 0.45 * _pulse(t, 0.18, _h(i + j * 37, 3))) * 0.8)) if _h(i * 31 + j * 7, 0) * 0.55 + 0.45 * _pulse(t, 0.18, _h(i + j * 37, 3)) >= 0.24 else None
    _cellgrid(d, Box(box.x0, box.y0, box.x1, box.y1 - _S(16)), cols, rows, cell, gap=_S(2))
    _text(d, (box.x0, box.y1 - _S(15)), "vocab %s . d_model %s" % (format(_iv(t, 32000, 50257, 0.05), ","), format(_iv(t, 2048, 4096, 0.07), ",")), pal, s, 11)

def viz_point_cloud(d, box, t, p, pal, s):       # 5 嵌入空间点云：counting 是滚动值
    cx, cy, n = (0.30, 0.55, 0.75), (0.42, 0.60, 0.35), _iv(t, 320, 1000, 0.06)
    for i in range(n):
        d.point((box.x0 + int((cx[i % 3] + (_h(i, 1) - 0.5) * 0.34 + 0.02 * math.sin(t + i)) * box.width()),
                 box.y0 + int((cy[i % 3] + (_h(i, 2) - 0.5) * 0.34) * box.height())), fill=_dim(pal.accent, s * (0.35 + 0.65 * _h(i, 5))))
    _text(d, (box.x0, box.y1 - _S(15)), "[points] = 1000 . counting = %s" % format(n, ","), pal, s, 11, pal.highlight)

def viz_dials(d, box, t, p, pal, s):             # 6 QA 修正：不是三分圆盘，是密集棋盘格 + shots given 计数
    on = lambda i, j: _h(i + j * 53, 11) + 0.45 * _pulse(t, 0.5, _h(i * 3 + j, 2)) > 0.62
    _cellgrid(d, Box(box.x0, box.y0, box.x1, box.y1 - _S(18)), max(4, box.width() // _S(9)), max(3, (box.height() - _S(18)) // _S(9)),
              lambda i, j: _dim(pal.text if on(i, j) else pal.dim, s * (0.8 if on(i, j) else 0.3)))
    _text(d, (box.x0, box.y1 - _S(15)), "shots given %s / 4096" % format(_iv(t, 900, 4096, 0.22), ","), pal, s, 11)

def viz_sine_stack(d, box, t, p, pal, s):        # 7 正弦波：0:36 单条 -> 0:44 堆叠
    n = int(p.get("n", 1 if t < 44 else 5))
    _pline(d, box, [lambda u, k=k: 0.5 + (0.30 - 0.02 * k) * math.sin((u * (2.2 + 0.6 * k) + t * (0.8 + 0.15 * k)) * TAU) for k in range(n)],
           [_dim(pal.accent, s * (0.55 + 0.45 * k / max(1, n))) for k in range(n)])
    r = _live(t, 1.0, 4.0, 0.1)
    _text(d, (box.x0, box.y1 - _S(15)), "r = %.5f . C = 2 pi r = %.5f" % (r, TAU * r), pal, s, 11)

def _base(v):       # 已缩放像素 -> 基准字号（font_* 内部还会再 scaled 一次，必须先换回来）
    return max(1, int(round(float(v) / max(1e-9, float(config.RENDER_SCALE or 1.0)))))

def _big_size(txt, w, hi, lo=11):
    """巨字缩到面板宽度以内。**必须用 font_title 量** —— _text(title=True) 画的是 Anton，
    Anton 的字宽约为 Consolas 的三倍，用 font_mono 量会严重低估。阈值 w 传进来是**缩放像素**，
    必须换成基准再比 —— 否则 4K 下阈值宽 3 倍，字被放任长到 3 倍，越界压住 ops 栏。"""
    w, n = _base(w), hi
    while n > lo and theme.text_width(txt, theme.font_title(_F(n))) > w: n -= 2
    return n

def viz_ctx_growth(d, box, t, p, pal, s):        # 8 上下文增长条：n_ctx 滚动 + 超长进度条
    exp = _live(t, 9.0, 29.5, 0.04)
    _bars(d, Box(box.x0, box.y0 + _S(6), box.x1, box.y0 + _S(20)), [min(1.0, 2.0 ** exp / 2.0 ** 30), 1.0],
          lambda i: _dim(pal.accent if i == 0 else pal.dim, s), horiz=True)
    txt = format(int(2.0 ** exp), ",")
    _text(d, (box.x0, box.y0 + box.height() // 3), txt, pal, s,
          _big_size(txt, box.width() - _S(8), max(18, min(64, _base(box.height()) // 4))), pal.highlight, title=True)
    _text(d, (box.x0, box.y1 - _S(15)), "n_ctx (2^%.1f) . budget 1,073,741,824" % exp, pal, s, 11)

def viz_epoch_bars(d, box, t, p, pal, s):        # 9 时空刻度巨字（滚动年份）+ 柱状均衡器
    yr = _iv(t, -1200, 2016, 0.05)
    txt = "%d %s" % (abs(yr), "AD" if yr >= 0 else "BC")
    _text(d, (box.x0 + _S(4), box.y0 + _S(4)), txt, pal, s,
          _big_size(txt, box.width() - _S(8), max(20, min(72, _base(box.height()) // 4))), pal.highlight, title=True)
    _bars(d, Box(box.x0, box.y0 + box.height() * 2 // 3, box.x1, box.y1 - _S(16)),
          [0.25 + 0.7 * _pulse(t, float(p.get("bpm", 116.0)) / 60.0 * (1 + i % 3), _h(i, 4)) for i in range(24)], _dim(pal.accent, s))
    _text(d, (box.x0, box.y1 - _S(15)), "t = %s yr . epoch %s" % (format(int(_live(t, 1e-3, 4.5e9, 0.031)), ","), format(_iv(t, 0, 1600, 0.09), ",")), pal, s, 11)

def viz_recursive_tiles(d, box, t, p, pal, s):   # 10 递归俯冲：一层套一层
    b = box
    for lv in range(6):
        d.rectangle((b.x0, b.y0, b.x1 - 1, b.y1 - 1), outline=_dim(pal.accent if lv % 2 == 0 else pal.line, s * (1.0 - 0.11 * lv)))
        u, v = 0.30 + 0.10 * _h(lv, 1) + 0.03 * math.sin(t * 0.4 + lv), 0.28 + 0.10 * _h(lv, 2)
        b = Box(b.x0 + int(b.width() * u), b.y0 + int(b.height() * v), b.x0 + int(b.width() * (u + 0.55)), b.y0 + int(b.height() * (v + 0.55)))
        if b.width() < _S(24) or b.height() < _S(14):
            break
    _text(d, (box.x1 - _S(34), box.y1 - _S(17)), "L%d" % _iv(t, 40, 58, 0.12), pal, s, 13, pal.highlight)

def viz_tsne_avatars(d, box, t, p, pal, s):      # 11 t-SNE 头像阵：小头像按簇排布，密度渐变
    for c in range(28):
        ax, ay = box.x0 + int(_h(c, 21) * (box.width() - _S(10))), box.y0 + int(_h(c, 22) * (box.height() - _S(10)))
        _cellgrid(d, Box(ax, ay, ax + _S(7), ay + _S(7)), 4, 4, lambda i, j: _dim(pal.accent, s * (0.2 + 0.8 * _h(c, 23))) if _h(i * 4 + j + c * 17, 24) > 0.34 else None, gap=_S(1))
    _text(d, (box.x0, box.y1 - _S(15)), "clusters %d . perplexity %.1f" % (_iv(t, 8, 24, 0.08), _live(t, 5.0, 50.0, 0.11)), pal, s, 11)

def viz_ascii_art(d, box, t, p, pal, s):         # 12 待定位：参考片此处是标题 + 空白矩形，不是番茄字符画
    d.rectangle((box.x0 + _S(10), box.y0 + _S(26), max(box.x0 + _S(11), box.x1 - _S(11)), max(box.y0 + _S(27), box.y1 - _S(27))), outline=_dim(pal.line, s))
    _text(d, (box.x0 + _S(4), box.y0), "TOMATO", pal, s, max(14, min(40, _base(box.height()) // 6)), pal.dim, title=True)
    _text(d, (box.x0 + _S(4), box.y1 - _S(15)), "art: none . frames %d/6" % _iv(t, 0, 6, 0.5), pal, s, 11)

def viz_big_number(d, box, t, p, pal, s):        # 13 大数字横幅：77% 是滚动值
    pct = _live(t, 62.0, 88.0, 0.16)
    _text(d, (box.x0 + _S(6), box.y0 + box.height() // 5), "%.0f%%" % pct, pal, s, max(28, min(96, _base(box.height()) // 3)), pal.highlight, title=True)
    _bars(d, Box(box.x0 + _S(6), box.y1 - _S(30), box.x1 - _S(6), box.y1 - _S(22)), [pct / 100.0], _dim(pal.accent, s), horiz=True)
    _text(d, (box.x0 + _S(6), box.y1 - _S(17)), "%s conf %.3f" % (p.get("label", "eval"), _live(t, 0.5, 0.99, 0.19)), pal, s, 11)

def viz_attn_tri(d, box, t, p, pal, s):          # 14 注意力下三角矩阵，右侧 future: masked
    n = int(p.get("n", 16))
    cell, ox, oy, lit = max(2, min(box.width() * 2 // 3, box.height() - _S(22)) // n), box.x0 + _S(2), box.y0 + _S(3), _iv(t, 0, n * n, 0.09)
    _cellgrid(d, Box(ox, oy, ox + n * cell, oy + n * cell), n, n,
              lambda i, j: _dim(pal.accent if i <= j else pal.dim, s * ((1.0 if i == j else (max(0.12, 0.85 - 0.08 * (j - i)) if i < j else 0.16)) * (0.45 if j * n + i > lit else 1.0))))
    _text(d, (ox + n * cell + _S(10), oy + _S(16)), "future: masked", pal, s, max(12, min(30, (_base(box.width()) - n * _base(cell)) // 13)), pal.warn, title=True)
    _text(d, (box.x0, box.y1 - _S(14)), "head %d/32 . attn sum %.3f" % (_iv(t, 1, 32, 0.13), _live(t, 0.94, 1.0, 0.21)), pal, s, 11)

def viz_prob_bars(d, box, t, p, pal, s):         # 15 概率排名条：6 行候选 + rolling temperature
    n, temp = int(p.get("n", 6)), _live(t, 0.55, 1.45, 0.2)
    lg = [_h(i, 31) * 3.2 for i in range(n)]
    ex, rowh = [math.exp((v - max(lg)) / temp) for v in lg], max(_S(13), min(_S(19), (box.height() - _S(16)) // n))
    for i, v in enumerate([e / sum(ex) for e in ex]):
        y = box.y0 + i * rowh
        _text(d, (box.x0, y), "tok%02d" % i, pal, s * (1.0 if i == 0 else 0.7), 11)
        d.rectangle((box.x0 + _S(44), y + _S(3), box.x0 + _S(44) + max(1, int(max(_S(4), box.width() - _S(96)) * v)), y + rowh - _S(5)), fill=_dim(pal.highlight if i == 0 else pal.accent, s))
        _text(d, (box.x1, y), "%5.1f%%" % (v * 100), pal, s, 13, None, "ra")
    _text(d, (box.x0, box.y1 - _S(14)), "temperature %.2f" % temp, pal, s, 11)

def viz_reward_curve(d, box, t, p, pal, s):      # 16 奖励模型曲线（点阵上升）+ KL 竖条
    top = Box(box.x0, box.y0, box.x1, box.y0 + box.height() * 3 // 4)
    _pline(d, top, [lambda u: 0.2 + 0.62 * u ** 0.6 + 0.04 * math.sin(u * 9 + t * 2)], [_dim(pal.accent, s)], dot=True)
    _bars(d, Box(box.x0, top.y1 + _S(3), box.x1, box.y1 - _S(16)), [_pulse(t, 0.8, _h(i, 41)) for i in range(9)], _dim(pal.error, s * 0.8))
    _text(d, (box.x0, box.y1 - _S(15)), "reward[you] %.3f . kl %.3f" % (_live(t, 0.62, 0.94, 0.17), _live(t, 0.004, 0.09, 0.23)), pal, s, 11)

def viz_causal_mask(d, box, t, p, pal, s):       # 17 因果掩码：下三角矩阵 + -inf 滚动计数
    n = int(p.get("n", 12))
    cell, lit = max(1, min(box.width() // n, (box.height() - _S(22)) // n)), _iv(t, 0, n * n, 0.11)
    _cellgrid(d, Box(box.x0, box.y0, box.x0 + n * cell, box.y0 + n * cell), n, n,
              lambda i, j: _dim(pal.accent, s * (0.3 + 0.45 * _h(i * 13 + j, 51))) if i > j else _dim(pal.dim, s * (0.5 if j * n + i <= lit else 0.2)))
    _text(d, (box.x0, box.y1 - _S(14)), "-inf %s masked . n %d" % (format(_iv(t, 0, 4096, 0.22), ","), n), pal, s, 11, pal.dim)

# ==================== 注册 ====================
for _k, _v in list(globals().items()):
    if _k.startswith("viz_") and callable(_v):
        VIZ[_k] = VIZ[_k[4:]] = _v
for _mod in ("tui_viz", "mathviz"):     # 两个原语模块都在这里登记。
    try:                               # **必须惰性 import**：mathviz 顶部 import tui_engine，
        register(__import__(_mod))     # tui_engine 顶部又 import scenes —— 谁先谁就炸一半。
    except ImportError:                # pragma: no cover
        pass
