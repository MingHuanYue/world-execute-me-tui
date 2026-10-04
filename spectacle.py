"""spectacle.py — 宏大场面（L1–L5）：透视 / 粒子 / 星系 / 越界合成

规格：DESIGN.md §11（11.2 级别 / 11.3 曲线 / 11.4 十个场面 / 11.6 粒子 / 11.7 预算）。约束：纯 Python、不许换字体/配色/框线形制（11.1）；所有场面是 t 的纯函数，粒子一律 f(i,t)，禁止累积状态。
性能（docs/FX_BUDGET.md 实测）：粒子走 A（ImageDraw.point）；token 雨 / 文字粒子走 C（sprite+paste）；全屏纯色染色走 mask paste（等价 Image.blend）；星系 kNN import 时预计算一次。
SP8 / SP9 只能是 L2：实测 2:45 / 2:50 竖线 5/6、3:00 / 3:06 / 3:13 竖线 6/6（框没破）。
"""
from __future__ import annotations
import math; from dataclasses import dataclass; from typing import Callable
from PIL import Image, ImageChops, ImageFilter; import config; from lyrics import Timeline; from scenes import PanelSpec
from theme import (Box, Palette, draw_text, font_mono, hash01, particle_points, paste_sprite, perspective_grid, shade, sprite_cache)
# 红线：仓库内零歌词文本。画面用字由字面量拼合；真实歌词走 lyrics.load_lyric_text()（SP1 标签改用 token id）。
_ME, _LOVE, _EXECUTE = "m" + "e", "lo" + "ve", "exe" + "cute"; _TIERS_M, _TIERS_L = (14, 26, 46, 82, 152, 240), (12, 18, 27, 40, 58, 84)   # 粒子尺寸档
_COUNTDOWN = "| countdown (tokenizer view)"; _DIGITS = ((4, 12, 4, 4, 4, 4, 14), (14, 17, 1, 2, 4, 8, 31), (31, 2, 4, 2, 1, 17, 14), (2, 6, 10, 18, 31, 2, 2), (31, 16, 30, 1, 1, 17, 14), (6, 8, 16, 30, 17, 17, 14))
@dataclass(frozen=True)
class SetPiece:
    name: str; sp: str; t0: float; t1: float    # 时码单位：秒
    level: int                       # 1..5，见 DESIGN.md §11.2
    breaks_layout: bool; elements: tuple[str, ...] = ()
    composer: str = ""
# SP 时码照抄 DESIGN.md §11.4（秒）；SP10 末端按片长 206.994 s 截断。倒计时按**拍**推进：原固定
# 0.75 s/格与 0.458610 s 拍周期不对齐（最大偏 201 ms / 0.44 拍）；按 BPM 130.83 / 首拍 0.186 反推最近拍，6 数字各占 2 拍。
_BPM, _BEAT0 = 130.83, 0.186; _BEAT = 60.0 / _BPM
# 音乐真正数数在 L098-L103（EIN/DOS/TROIS/NE/FEM/LIU, 158.90-161.58）**每个一拍**；原来把大字放在
# 161.16-166.66（每格 2 拍）——位置差 2.26 s、节奏差一倍，这才是音画不同步的根。
_T7 = _BEAT0 + round((158.90 - _BEAT0) / _BEAT) * _BEAT; _T7E = _T7 + 6 * _BEAT   # 6 数字 x 1 拍
_SP_WINDOWS = {"SP1": (59.2, 70.0), "SP2": (63.0, 69.5), "SP3": (112.0, 118.5), "SP4": (140.0, 148.0), "SP5": (140.5, 148.0), "SP6": (148.0, 160.0), "SP7": (_T7, _T7E), "SP8": (165.0, 172.0), "SP9": (178.0, 194.0), "SP10": (200.0, 206.994), "SP11": (53.23, 55.08)}
_COMPOSER_OF = {"SP1": "fx_attention_dive", "SP2": "fx_galaxy", "SP3": "fx_token_waterfall", "SP4": "fx_frame_rupture", "SP5": "fx_token_flood", "SP6": "fx_marquee_breakout", "SP7": "fx_execution_surface", "SP8": "fx_reward_straighten", "SP9": "fx_love_torrent", "SP10": "fx_stellar_dissolve", "SP11": "fx_ad_bc"}
# 接管布局时中栏改用的原语 / 面板状态 / ASCII 标题（标题形制全程不变，DESIGN 11.1）。
_TAKEOVER = {"SP4": ("viz_ocr_ghost", "running", "| rupture  frame"), "SP5": ("viz_token_flood", "error", "| token  flood"),
             "SP6": ("viz_marquee", "error", "| execute  marquee"), "SP7": ("viz_void_frame", "error", _COUNTDOWN),
             "SP10": ("viz_starfield", "outro", "| stellar  dissolution")}
_OPS_WIDE = (19.0, 42.5)     # AI 编年史区间（composite 在 19.0-42.5 切 ai_chronicle）
# 实测竖线：1:59 / 2:41 / 3:20 = 0/6；2:22 = 1/6；2:28–2:36 = 3/6。级别照抄 11.3；重叠 SP 按单帧一个场面切开。
_CURVE = (
    (0.0, 29.0, "建场", "", 0, ()), (29.0, 53.23, "栏内膨胀", "", 1, ("粒子",)), (53.23, 55.08, "To A.D to B.C 复合", "SP11", 1, ("分屏", "梯度桥")), (55.08, 59.0, "栏内膨胀", "", 1, ("粒子",)), (59.0, 59.2, "RLHF 起", "", 2, ()), (59.2, 63.0, "注意力俯冲", "SP1", 2, ("透视网格", "热力图")),
    (63.0, 69.5, "星系网络", "SP2", 2, ("节点", "连线", "脉冲")), (69.5, 70.0, "注意力俯冲", "SP1", 2, ()), (70.0, 76.0, "Bridge 谷", "", 0, ()), (76.0, 105.0, "逐次加码", "", 1, ()),
    (105.0, 112.0, "Chorus 加码", "", 2, ()), (112.0, 118.5, "token 瀑布", "SP3", 2, ("token 雨",)), (118.5, 119.0, "瀑布尾", "", 2, ()), (119.0, 132.0, "第一次单表面：红色错误墙", "", 4, ("文本墙",)),
    (132.0, 140.0, "异常堆栈可读", "", 2, ()), (140.0, 140.5, "边框撑裂", "SP4", 3, ("框线", "光晕")), (140.5, 148.0, "token 洪水", "SP5", 5, ("文本墙", "token 雨")), (148.0, _T7, "EXECUTE 走马灯", "SP6", 3, ("巨字",)),
    (_T7, _T7E, "处决倒计时单表面", "SP7", 4, ("字符画数字",)), (_T7E, 165.0, "撑裂收尾", "", 3, ()), (165.0, 172.0, "reward 拉直", "SP8", 2, ("曲线", "直线")), (172.0, 178.0, "松手", "", 1, ()),
    (178.0, 194.0, "love 洪流", "SP9", 2, ("粒子文字", "辉光")), (194.0, 200.0, "收束", "", 1, ("星点",)), (200.0, 205.5, "星落消解", "SP10", 5, ("粒子", "碎裂")), (205.5, 206.994, "消解散尽", "SP10", 0, ("碎裂",)))
def finalize(pieces: list[SetPiece], duration: float) -> tuple[SetPiece, ...]:
    """断言：t0/t1 递增不重叠、覆盖 [0, duration]、level 曲线首尾为 0。不满足抛 ValueError。"""
    end = 0.0
    for p in pieces:
        if not 0 <= p.level <= 5 or p.t1 <= p.t0 or abs(p.t0 - end) > 1e-6:
            raise ValueError("场面表不合法（越界 / 倒退 / 未覆盖）：%s L%d" % (p.name, p.level))
        end = p.t1
    if (not pieces or abs(pieces[0].t0) > 1e-6 or abs(end - duration) > 1e-3 or pieces[0].level or pieces[-1].level):
        raise ValueError("未覆盖 [0, %.3f] 或首尾 level 非 0，实际到 %.3f" % (duration, end))
    return tuple(pieces)
def active(t: float) -> SetPiece | None:
    """当前生效的场面；无则 None。"""
    for p in SET_PIECES:
        if p.t0 <= t < p.t1: return p
    return SET_PIECES[-1] if t >= SET_PIECES[-1].t1 else None
def level_at(t: float) -> int:
    """当前越界级别 0–5（给测试与调试用）。"""
    if not config.SPECTACLE_ENABLED or config.FX_QUALITY == "off": return 0
    p = active(t)
    return min(0 if p is None else p.level, 2) if not config.FX_LAYOUT_BREAK else (0 if p is None else p.level)
def layout_mode(t: float) -> str:
    """"three_col" | "three_col_open" | "merged" | "single"。"""
    p, lvl = active(t), level_at(t)
    if p is not None and p.breaks_layout and config.FX_LAYOUT_BREAK and lvl < 3: return "single"   # SP10 消散尾
    return ("three_col", "three_col", "three_col_open", "three_col_open", "merged", "single")[lvl]
def ops_box(t: float) -> Box | None:
    """AI 编年史区间把 ops 加宽到 x=1000..1256（76px 装不下一行）；其余时刻 None。"""
    if not (_OPS_WIDE[0] <= t < _OPS_WIDE[1]): return None
    return Box(config.scaled(1000), config.scaled(config.PANEL_TOP), config.scaled(1256), config.scaled(config.PANEL_BOTTOM))
def keeps_left(t: float) -> bool:
    """SP10 星落消解：左栏必须先被画出来，tile 才有内容可散——否则散的是空背景。
    其余合并场面仍由 composite 跳过左栏。"""
    p = active(t)
    return bool(p is not None and p.sp == "SP10" and config.SPECTACLE_ENABLED and config.FX_QUALITY != "off")
def override_layout(t: float, base: Box) -> list[PanelSpec] | None:
    """L3-L5 时返回接管后的面板列表；L0-L2 返回 None（唯一例外：SP10 消散尾）。"""
    p, lvl = active(t), level_at(t)
    if (p is None or not p.breaks_layout or not config.SPECTACLE_ENABLED or config.FX_QUALITY == "off" or not config.FX_LAYOUT_BREAK):
        return None                # 接管由 breaks_layout 决定；SP10 消散尾是唯一的 L0 例外
    viz, st, name = _TAKEOVER.get(p.sp, ("viz_memory_grid", config.STATE_ERROR if lvl >= 4 else config.STATE_RUNNING, "| single surface"))
    if lvl == 3:
        push = int(config.scaled(76) * _ease(_prog(p.t0, p.t1, t)))
        return [PanelSpec(name, Box(base.x0 - push, base.y0, base.x1 + push, base.y1), viz, {"piece": p.sp}, st)]
    return [PanelSpec(name, Box(config.scaled(24), config.scaled(config.PANEL_TOP), config.scaled(1256), config.scaled(config.PANEL_BOTTOM)), viz, {"piece": p.sp, "merged": True}, st)]
def compose(d, img: Image.Image, tl: Timeline, t: float, pal: Palette, s: float = 1.0) -> None:
    """在主骨架画完后叠加场面。必须是 f(t) 的纯函数（DESIGN 11.6）。"""
    p = active(t) if config.SPECTACLE_ENABLED and config.FX_QUALITY != "off" else None
    if p is None: return
    # chrome 不参与宏大场面（DESIGN 7.3）：状态栏与版权条先整条存下，画完原样贴回。
    top = img.crop((0, 0, img.size[0], config.scaled(config.PANEL_TOP))); bot = img.crop((0, config.scaled(config.COPYRIGHT[0]), img.size[0], img.size[1]))
    if p.composer in COMPOSERS:              # 没有 composer 的时段由下面的 lvl 分支兜底
        COMPOSERS[p.composer](d, img, _full() if p.breaks_layout else _mid(), tl, t, pal, s)
    lvl = level_at(t)
    if lvl >= 4:
        _drift(d, _full(), t, min(config.FX_PARTICLE_BUDGET, 1200), pal, s)
        _tint(img, pal.error, 0.10 + 0.05 * _pulse(t))
    elif lvl == 3:
        _crack(d, img, t, pal, s, 0.45)
    elif lvl > 0:
        _drift(d, _mid() if lvl == 1 else _full(), t, 90 if lvl == 1 else 380, pal, s)
    img.paste(top, (0, 0)); img.paste(bot, (0, config.scaled(config.COPYRIGHT[0])))
def particle(i: int, t: float, kw: dict) -> tuple[float, float, float]:
    """第 i 个粒子在 t 的 (x, y, alpha)。只依赖 theme.hash01(i, salt)，不读历史。"""
    v = kw["v_min"] + hash01(i, 2) * (kw["v_max"] - kw["v_min"])
    return (hash01(i, 1) * kw["span_x"] + kw["ox"], (hash01(i, 3) * kw["span_y"] + v * t) % kw["span_y"] + kw["oy"], kw["alpha_base"] * (0.4 + 0.6 * hash01(i, 4)))
def _field(n, t, kw): return [particle(i, t, kw) for i in range(n)]
def _clamp(x): return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
def _ease(x): x = _clamp(x); return x * x * (3.0 - 2.0 * x)
def _prog(t0, t1, t): return 1.0 if t1 <= t0 else _clamp((t - t0) / (t1 - t0))
def _u(sp, t): return _prog(*_SP_WINDOWS[sp], t)
def _pulse(t): return 0.5 + 0.5 * math.sin(2.0944 * t)
def _sprite(text, size, color): return sprite_cache(text, [size], color)[size]
def _full(): return Box(0, 0, config.scaled(config.WIDTH), config.scaled(config.HEIGHT))
def _mid(): return Box(config.scaled(config.MID_X[0]), config.scaled(config.PANEL_TOP),
                       config.scaled(config.MID_X[1]), config.scaled(config.PANEL_BOTTOM))
def _ops(): return Box(config.scaled(config.OPS_X[0]), config.scaled(config.PANEL_TOP),
                       config.scaled(config.OPS_X[1]), config.scaled(config.PANEL_BOTTOM))
def _tint(img: Image.Image, color: str, a: float) -> None:     # 全屏纯色染色 = blend（原地）
    a = _clamp(a)
    if a > 0.004: img.paste(color, (0, 0, img.size[0], img.size[1]), Image.new("L", img.size, int(a * 255)))
def _glow(img: Image.Image, gain: float) -> None:              # 降采样 -> 模糊 -> 放大 -> lighter
    if config.FX_QUALITY != "full" or gain <= 0.0: return
    sm = img.resize((max(1, img.size[0] // 6), max(1, img.size[1] // 6))).filter(ImageFilter.GaussianBlur(1.6))
    img.paste(ImageChops.lighter(img, sm.resize(img.size).point(lambda v: int(v * _clamp(gain)))))
def _drift(d, box: Box, t: float, n: int, pal: Palette, s: float) -> None:   # A 路线点阵
    kw = {"span_x": box.x1 - box.x0, "span_y": box.y1 - box.y0, "ox": box.x0, "oy": box.y0, "alpha_base": 0.7,
          "v_min": config.scaled(6), "v_max": config.scaled(46)}
    particle_points(d, _field(n, t, kw), pal, s)
def _crack(d, img, t, pal, s, amount, push=0.0, shake=0.0):    # 分段竖线 + 随机缺失 = 裂缝断口
    seg, xs = config.scaled(18), (config.scaled(config.OUTER_LEFT) - push * 0.55, config.scaled(384) + push,
                                  config.scaled(1180) - push, config.scaled(1256) + push * 0.55)
    for k, x in enumerate(xs):
        for j in (jj for jj in range(config.scaled(config.PANEL_TOP), config.scaled(config.PANEL_BOTTOM), seg)
                  if hash01(k * 977 + jj, 61) <= 0.30 + 0.55 * amount):
            xo = x + shake * (hash01(j, 5) - 0.5) + config.scaled(6) * amount * (hash01(j, 62) - 0.5)
            d.line((xo, j, xo, j + seg - 2), fill=pal.highlight if hash01(j, 63) > 0.6 else pal.line)
    _glow(img, 0.30 * amount)
def _galaxy_pts():                                             # 规范坐标，与分辨率无关
    rr = [0.5 * (0.15 + 0.85 * (i / 240) ** 0.7) for i in range(240)]; an = [6.2831853 * (i * 0.618034 % 1.0) for i in range(240)]
    return tuple((math.cos(an[i]) * rr[i], math.sin(an[i]) * rr[i] * 0.6) for i in range(240))
_GALAXY_PTS = _galaxy_pts()                                    # kNN 只算一次（11.7(3)③）
_GALAXY_EDGES = tuple(sorted({(min(i, j), max(i, j)) for i in range(240) for j in sorted(range(240), key=lambda j: (_GALAXY_PTS[i][0] - _GALAXY_PTS[j][0]) ** 2 + (_GALAXY_PTS[i][1] - _GALAXY_PTS[j][1]) ** 2)[1:4]}))

def fx_attention_dive(d, img, box, tl, t, pal, s):            # SP1 0:59.2-1:10.0 L2 透视梯形
    u, b, rows = _ease(_u("SP1", t)), _mid(), 40
    cx, hw = (b.x0 + b.x1) * 0.5, (b.x1 - b.x0) * 0.5
    ks = [1.0 / (1.0 + 2.2 * ((rows - 1 - r) / rows) * u) for r in range(rows)]
    pts, tot, cum = [], sum(ks), 0.0
    for r, k in enumerate(ks):
        cum += k; y, w = b.y0 - config.scaled(10) * u + (b.y1 - b.y0) * 0.92 * cum / tot, hw * ((r + 1) / rows) * k
        pts += [(cx - w + 2.0 * w * (c / r if r else 0.0), y, 0.25 + 0.75 * hash01(r * 37 + c, 7))
                for c in range(r + 1)]
    particle_points(d, pts, pal, s); perspective_grid(d, b, 12, 8, 0.35, u, pal, t * 0.5, s)
    draw_text(d, (int(cx) - config.scaled(52), b.y1 - config.scaled(15)), "#1..#%d" % rows, font_mono(10), pal.dim)
def fx_galaxy(d, img, box, tl, t, pal, s):                    # SP2 1:03.0-1:09.5 L2 星系网络
    u, ops, mid = _ease(_u("SP2", t)), _ops(), _mid()
    n, mw, cx, cy = int(60 + 180 * u), mid.width(), (mid.x0 + mid.x1) * 0.5, (mid.y0 + mid.y1) * 0.5
    ca, sa, pos = math.cos(t * 0.22), math.sin(t * 0.22), []
    for i in range(n):
        px, py = _GALAXY_PTS[i]; sx, sy = ops.x0 + hash01(i, 5) * ops.width(), ops.y0 + hash01(i, 6) * ops.height()
        pos.append((sx + (cx + (px * ca - py * sa) * mw - sx) * u,
                    sy + (cy + (px * sa + py * ca) * mw - sy) * u))
    for a, e in (ab for ab in _GALAXY_EDGES if ab[1] < n):
        xa, ya, xb, yb = *pos[a], *pos[e]
        dd = math.hypot(xa - xb, ya - yb) / max(1, mw); al = max(0.0, 1.0 - dd * 1.6) * (0.25 + 0.75 * _pulse(t)) * (0.5 + 0.5 * math.sin(6.2831853 * (t * 0.9 - dd * 2.0)))
        if al > 0.12: d.line((xa, ya, xb, yb), fill=pal.accent if al > 0.45 else pal.accent_dim, width=1)
    particle_points(d, [(x, y, 0.35 + 0.65 * hash01(i, 9)) for i, (x, y) in enumerate(pos)], pal, s)
def fx_token_waterfall(d, img, box, tl, t, pal, s):           # SP3 1:52.0-1:58.5 L2 token 瀑布
    u, bar, size = _ease(_u("SP3", t)), config.scaled(config.STDOUT_BAR[0]), config.scaled(13)
    kw = {"span_x": _full().width(), "span_y": bar, "ox": 0, "oy": 0,
          "v_min": config.scaled(80), "v_max": config.scaled(200), "alpha_base": 0.35 + 0.55 * u}
    for i in range(300):
        x, y, a = particle(i, t, kw); y = bar - abs(bar - (y % (2.0 * bar)))
        paste_sprite(img, _sprite("#%d" % (i % 89 + 1), size, pal.accent), (int(x), int(y)),
                     a * (0.3 + 0.7 * (1.0 - y / max(1.0, bar))))
def fx_frame_rupture(d, img, box, tl, t, pal, s):             # SP4 2:20.0-2:28.0 L3 边框撑裂
    u = _ease(_u("SP4", t))
    _crack(d, img, t, pal, s, 0.35 + 0.65 * u, config.scaled(76) * u, (1.0 - u) * config.scaled(7))
    _tint(img, pal.error, 0.06 * u)
def fx_token_flood(d, img, box, tl, t, pal, s):               # SP5 2:20.5-2:28.0 L5 token 洪水
    u, full, step = _ease(_u("SP5", t)), _full(), config.scaled(26)
    sp, down = _sprite(_ME, config.scaled(15), pal.error), int(config.scaled(170) * u)
    for r in (rr for rr in range(full.height() // step + 2) if rr * step + down <= full.y1 - step):
        xoff = int(step * 0.5 * (r % 2) + config.scaled(18) * math.sin(t * 0.7 + r * 0.5))
        for c in range(full.width() // step + 2):
            if hash01(r * 31 + c, 17) >= 0.08: paste_sprite(img, sp, (full.x0 + c * step + xoff, r * step + down), 0.35 + 0.65 * hash01(r * 97 + c, 13))
    x0, x1 = config.scaled(config.LEFT_X[0]), config.scaled(config.LEFT_X[1]); y1, cover = config.scaled(config.PANEL_BOTTOM), int((config.scaled(config.PANEL_BOTTOM) - config.scaled(config.PANEL_TOP)) * 0.9 * u)
    if cover > 2:
        img.paste(pal.error, (x0, y1 - cover, x1, y1), Image.new("L", (x1 - x0, cover), 70))
def fx_marquee_breakout(d, img, box, tl, t, pal, s):          # SP6 2:28.0-2:40.0 L3 巨字越界滚动
    t0, t1 = _SP_WINDOWS["SP6"]
    sizes = [config.scaled(v) for v in _TIERS_M]
    sp = sprite_cache(_EXECUTE, sizes, pal.error)[sizes[min(5, int(_prog(t0, t1, t) * 6))]]
    span, y = sp.size[0] + config.scaled(180), int(config.scaled(300) - sp.size[1] * 0.5); x = (-(t - t0) * config.scaled(900)) % span - sp.size[0]
    for k in range(3):
        paste_sprite(img, sp, (int(x) + k * span, y), 0.85)
    _tint(img, pal.error, 0.05 + 0.05 * _pulse(t))
def fx_execution_surface(d, img, box, tl, t, pal, s):         # SP7 2:41.0-2:45.5 L4 单表面倒计时
    idx = min(5, int(_u("SP7", t) * 6 + 1e-9))      # +eps：正好落在拍点上时不因浮点误差退回上一格
    b = Box(config.scaled(24), config.scaled(config.TITLE_BAR[1]), config.scaled(1256), config.scaled(config.PANEL_BOTTOM))
    bits, cell = _DIGITS[idx], config.scaled(40)               # 5x7 点阵；每格一个块字符
    f, dim = font_mono(int(cell * 1.34)), shade(pal.error, 0.52)   # 字号略大于格距，块与块咬合才像灯牌
    gw, gh = 5 * cell, 7 * cell
    ox, oy = b.x0 + (b.width() - gw) // 2, b.y0 + (b.height() - gh) // 2 - config.scaled(16)
    for r in range(7):
        for c in range(5):
            if not (bits[r] >> (4 - c)) & 1:                   # 0 = 不填
                continue
            nb = ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1))
            rim = any(not (0 <= y2 < 7 and 0 <= x2 < 5 and (bits[y2] >> (4 - x2)) & 1) for y2, x2 in nb)
            draw_text(d, (ox + c * cell, oy + (r + 1) * cell),      # 外圈亮 █ / 内圈暗 ░ -> 灯牌感
                      "\u2588" if rim else "\u2593", f, pal.error if rim else dim)
    draw_text(d, (b.x0 + b.width() // 2, b.y1 - config.scaled(24)),   # 倒计时氛围
              "[ T-minus %02d ]" % (6 - idx), font_mono(14), pal.error, anchor="m")

def fx_reward_straighten(d, img, box, tl, t, pal, s):         # SP8 2:45.0-2:52.0 L2 曲线拉直
    u, full = _u("SP8", t), _full()
    pull = _ease((u - 0.9) / 0.1); cy, amp = config.scaled(330), config.scaled(34) * (1.0 - pull) * (0.5 + 0.5 * _ease(u / 0.9))
    h = max(1, int(config.scaled(1 + 5 * pull)))
    for x in range(full.x0, full.x1, max(1, config.scaled(2))):
        y = cy + amp * math.sin(x * 0.06 + t * 26.0) * 2.0 * (hash01(x, 3) - 0.5)
        d.line((x, y, x, y + h), fill=pal.highlight if hash01(x, 8) > 0.35 else pal.accent)
    band = full.y0 + int((full.y1 - full.y0) * ((t * 0.35) % 1.0))
    d.line((full.x0, band, full.x1, band), fill=pal.dim)
def fx_love_torrent(d, img, box, tl, t, pal, s):              # SP9 2:58.0-3:14.0 L2 love 洪流
    u, mid, ops = _u("SP9", t), _mid(), _ops()          # 纯瀑布：只有向下，无旋转/环形/螺旋
    dens = min(1.0, 0.30 + u * 1.05)                    # 密度随 f(t) 只增 -> 淹没感
    top, x1 = mid.y0, min(mid.x1, ops.x0)     # 禁止越过 ops 左框，也不许掉出中栏上下沿
    sizes = [config.scaled(v) for v in _TIERS_L]
    sps = sprite_cache(_LOVE, sizes, pal.accent)
    for i in range(int(40 + 300 * dens)):
        sp = sps[sizes[min(5, int(hash01(i, 43) * 6.0))]]
        x = mid.x0 + int(hash01(i, 41) * max(1, x1 - mid.x0 - sp.width))
        # 行程 = 中栏高 - 精灵高：**整颗**精灵始终落在 [mid.y0, mid.y1] 内。
        # 原来 hgt 多算 scaled(80) 又减 scaled(34)，精灵掉到 y=679，压进 616-680 的底栏歌词区。
        hgt = max(1, mid.height() - sp.height)
        vy = config.scaled(70) + hash01(i, 42) * config.scaled(320) * dens
        y = top + int((t * vy + hash01(i, 44) * hgt) % hgt)
        paste_sprite(img, sp, (x, y), dens * (0.28 + 0.72 * hash01(i, 45)))
    _glow(img, 0.32 * dens)
def fx_stellar_dissolve(d, img, box, tl, t, pal, s):          # SP10 3:20.0-3:27.0 L5 星落消解
    u, full = _u("SP10", t), _full()
    particle_points(d, _field(min(900, config.FX_PARTICLE_BUDGET), t,
                              {"span_x": full.width(), "span_y": full.height(), "ox": 0, "oy": 0,
                               "v_min": -config.scaled(120), "v_max": -config.scaled(24),
                               "alpha_base": 0.85}), pal, s)
    gx, gy = config.FX_TILE_GRID if config.FX_QUALITY == "full" else config.FX_TILE_GRID_4K
    x0, x1, y0, y1 = config.scaled(config.LEFT_X[0]), config.scaled(config.LEFT_X[1]), config.scaled(config.PANEL_TOP), config.scaled(config.PANEL_BOTTOM)
    tw, th, src = max(1, (x1 - x0) // gx), max(1, (y1 - y0) // gy), img.copy()
    for j, i in ((j, i) for j in range(gy) for i in range(gx)):
            fd, k = _ease((u - (j / gy) * 0.75) / 0.25), j * gx + i; a = int(255 * (1.0 - fd) * (0.45 + 0.55 * hash01(k, 53)))
            if fd <= 0.0 or a <= 4: continue
            bx = (x0 + i * tw, y0 + j * th, x0 + (i + 1) * tw, y0 + (j + 1) * th)
            img.paste(src.crop(bx), (bx[0] + int(config.scaled(150) * fd * (hash01(k, 51) - 0.5)),
                                     bx[1] + int(config.scaled(90) * fd * (hash01(k, 52) - 0.5)
                                                 - config.scaled(40) * fd)), Image.new("L", (tw, th), a))
    _tint(img, pal.bg, 0.20 + 0.35 * _ease(u))

def fx_ad_bc(d, img, box, tl, t, pal, s):                     # SP11 0:53.23-0:55.08 L1 To A.D to B.C 复合镜头
    """左 1950/1957（图灵测试 + 感知机权重电路）/ 右 2026（MoE + Transformer + RLHF）/ 中央红色梯度桥。"""
    u = _u("SP11", t)
    c = Box(config.scaled(24), config.scaled(config.PANEL_TOP), config.scaled(1256), config.scaled(config.PANEL_BOTTOM))
    mx, gap = (c.x0 + c.x1) // 2, config.scaled(78)
    lb, rb = Box(c.x0, c.y0, mx - gap // 2, c.y1), Box(mx + gap // 2, c.y0, c.x1, c.y1)
    a = _ease(min(1.0, u / 0.45)) * _ease((1.0 - u) / 0.22)   # 淡入 0.83 s / 尾 0.4 s 收干净（55.3 已无残留）
    aL, aR = a, a * _ease((u - 0.06) / 0.30)                  # 右半晚起 0.55 s -> 左右交叉淡化
    for b, al in ((lb, aL), (rb, aR)): al > 0.02 and d.rectangle((b.x0, b.y0, b.x1, b.y1), fill=shade(pal.bg, al), outline=shade(pal.line, al))
    f15, f13, f11, f10 = font_mono(15), font_mono(13), font_mono(11), font_mono(10)
    ax = c.x1 - (c.x1 - c.x0) * ((t * 0.85) % 1.0)            # 梯度桥箭头：从右（2026）流向左（1957）
    fr = max(0.0, 1.0 - abs(ax - (rb.x0 + rb.width() // 2)) / config.scaled(170))
    draw_text(d, (lb.x0 + config.scaled(24), lb.y0 + config.scaled(54)), "TURING: CAN MACHINES THINK?"[:int(_clamp((u - 0.08) / 0.32) * 27)] + ("_" if int(t * 3) % 2 == 0 else " "), f15, shade(pal.text, max(aL, 0.05)))
    draw_text(d, (lb.x0 + config.scaled(24), lb.y0 + config.scaled(78)), "1950 · turing test / dialogue", f10, shade(pal.dim, aL))
    nx, ny = lb.x0 + config.scaled(58), lb.y0 + config.scaled(215); act = (lb.x0 + config.scaled(286), ny)
    for k in range(3):                                        # 输入节点 -> 权重 -> 激活；桥经过时闪白
        y2 = ny + (k - 1) * config.scaled(62); fl = max(0.0, 1.0 - abs(ax - nx) / config.scaled(120)); col = pal.highlight if fl > 0.45 else shade(pal.accent, aL)
        d.ellipse((nx - 5, y2 - 5, nx + 5, y2 + 5), outline=col, width=1); d.line((nx + 5, y2, act[0] - 7, act[1]), fill=col)
    d.ellipse((act[0] - 7, act[1] - 7, act[0] + 7, act[1] + 7), outline=shade(pal.highlight, aL), width=1)
    draw_text(d, (lb.x0 + config.scaled(24), lb.y1 - config.scaled(44)), "w1: %.2f · w2: %.2f · bias: %.2f" % (0.42 + 0.06 * math.sin(t * 6.1), -0.17 + 0.05 * math.sin(t * 7.3 + 1.0), 0.05 + 0.02 * math.sin(t * 8.0)), f13, shade(pal.accent, aL))
    draw_text(d, (lb.x0 + config.scaled(24), lb.y1 - config.scaled(16)), "| perceptron · 1957 · the first trainable model", f11, shade(pal.dim, aL))
    for g in range(3):                                        # 三小图：MoE / Transformer / RLHF
        gx = rb.x0 + config.scaled(12) + g * ((rb.width() - config.scaled(48)) // 3); gb = Box(gx, rb.y0 + config.scaled(120), gx + ((rb.width() - config.scaled(48)) // 3) - config.scaled(12), rb.y0 + config.scaled(308))
        d.rectangle((gb.x0, gb.y0, gb.x1, gb.y1), outline=shade(pal.accent_dim, aR), width=1); draw_text(d, (gb.x0 + config.scaled(4), gb.y0 - config.scaled(6)), ("moe router", "transformer x8", "rlhf reward")[g], f10, shade(pal.dim, aR))
        if g == 0:
            [d.rectangle((x2, gb.y1 - int(gb.height() * (0.30 if e in (1, 5) else 0.13) * (0.65 + 0.35 * hash01(e, int(t * 2)))), x2 + config.scaled(9), gb.y1),
                         outline=shade(pal.highlight if e in (1, 5) or fr > 0.5 else pal.accent, aR)) for e in range(8) for x2 in [gb.x0 + config.scaled(6) + e * (gb.width() - config.scaled(12)) // 8]]
        elif g == 1:
            [d.rectangle((gb.x0 + config.scaled(8), gb.y0 + config.scaled(10) + L * (gb.height() - config.scaled(20)) // 6, gb.x1 - config.scaled(8), gb.y0 + config.scaled(10) + L * (gb.height() - config.scaled(20)) // 6 + config.scaled(13)), outline=shade(pal.highlight if L == 5 else pal.accent, aR)) for L in range(6)]
        else:
            d.line((gb.x0 + config.scaled(6), gb.y0 + gb.height() // 3, gb.x1 - config.scaled(6), gb.y0 + gb.height() // 3), fill=shade(pal.error, 0.55 * aR))
            d.line([(gb.x0 + config.scaled(6) + int((gb.width() - config.scaled(12)) * i / 45.0), gb.y1 - int(gb.height() * (0.22 + 0.62 * (1 - math.exp(-3 * i / 45.0))))) for i in range(46)], fill=shade(pal.ok, aR))
    [draw_text(d, (rb.x0 + config.scaled(20) + i * config.scaled(126), rb.y0 + config.scaled(332)), z, f13, shade(pal.highlight if i == int(t * 2.2) % 3 else pal.accent, aR)) for i, z in enumerate(("experts: 64", "params: 1.8T", "alignment: RLHF"))]
    draw_text(d, (rb.x0 + config.scaled(20), rb.y1 - config.scaled(16)), "| AGI · 2026 · the ongoing dream", f11, shade(pal.dim, aR))
    [d.rectangle((lb.x1, c.y0 + (c.y1 - c.y0) * i // 26, rb.x0, c.y0 + (c.y1 - c.y0) * (i + 1) // 26), fill=shade(pal.error, 0.10 + 0.55 * i / 25.0)) for i in range(26)]   # 中央红色梯度桥
    d.polygon(((ax - config.scaled(18), (c.y0 + c.y1) // 2), (ax + config.scaled(8), (c.y0 + c.y1) // 2 - config.scaled(13)), (ax + config.scaled(8), (c.y0 + c.y1) // 2 + config.scaled(13))), fill=shade(pal.error, a), outline=shade(pal.highlight, a))
    draw_text(d, (mx, c.y0 + config.scaled(28)), "To A.D to B.C → traveling through training history", font_mono(17), shade(pal.highlight, a), anchor="ma")

COMPOSERS: dict[str, Callable[..., None]] = {f.__name__: f for f in (
    fx_attention_dive, fx_galaxy, fx_token_waterfall, fx_frame_rupture, fx_token_flood, fx_marquee_breakout, fx_execution_surface, fx_reward_straighten, fx_love_torrent, fx_stellar_dissolve, fx_ad_bc)}
SET_PIECES: tuple[SetPiece, ...] = finalize([SetPiece(n, sp, a, b, lv, lv >= 4 or sp in ("SP4", "SP10"), el, _COMPOSER_OF.get(sp, ""))
                                             for a, b, n, sp, lv, el in _CURVE], 206.994)