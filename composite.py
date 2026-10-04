"""composite.py — 整帧骨架合成

职责：按固定顺序拼整帧：背景 -> 网格底纹 -> 状态栏 -> 左栏 -> 中栏 panels -> ops
      -> stdout 条 -> 版权条 -> spectacle.compose -> finalize_frame。
      3:20-3:32 的关机序列（归档 -> 彩蛋 A/B -> 白光扫过 -> 墓碑）也在这里收口；
      chrome（状态栏 / 版权条）由 apply_post 最后重画一次，永不被 spectacle 覆盖。
约束：<= 300 行；纯 Python + Pillow；所有坐标过 config.scaled()；
      compose_frame 是 f(t) 纯函数（不读写模块级可变状态）；
      唯一允许的跨帧状态是 apply_post 的 prev，由 render.py 持有并传入（DESIGN.md 0.3 / 7.5）。
"""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

import chat_pages
import config
import scenes
import spectacle
import theme
import tui_engine
import tui_viz
from lyrics import Timeline
from theme import Box, Palette, palette_for
# 6 处 shell 命令插帧（DESIGN.md 2.4）：2 处整屏终端 + 4 处只换顶栏左段
SHELL_CMDS: tuple[tuple[float, str, str], ...] = (
    (2.5, "./protect", "full"), (7.5, "neofetch", "full"), (42.5, "ulimit -a", "hdr"),
    (113.5, "ping you", "hdr"), (118.5, "ls -la ~/memory/you/", "hdr"), (183.5, "dsh chat", "hdr"),
)
PROMPT = "whale@deepseek:~$"
BRAND = "WORLD.EXECUTE(ME);"
STATUS_WORD = {"running": "RUNNING", "warn": "WARN", "error": "ERROR", "outro": "RUNNING"}
SHUT_ARCH, SHUT_EGG, SHUT_SWEEP, SHUT_OFF, SHUT_TOMB = 200.0, 205.0, 208.0, 210.0, 210.0
PROTECT_STEPS = ("mount /proc;load kernel modules;init network;verify audio device;load model weights;scan memory;"
                 "open /dev/you;attach avatar;check license;start tui;ping localhost;seed rng;mount lyrics;"
                 "prepare stdout;ready").split(";")
NEOFETCH_ROWS = (("OS", "dsh web 0.2.0"), ("Host", "deepseek-desktop"), ("Kernel", "6.9.7-tui"),
                 ("Uptime", "0 days, 3 hours, 26 mins"), ("Shell", "me-sh 1.4"),
                 ("Resolution", "1280x720"), ("WM", "world.execute(me)"), ("Terminal", "dsh-tui"),
                 ("CPU", "i5-12490F (12) @ 3.00GHz"), ("Memory", "7448MiB / 31860MiB"),
                 ("me.color", "#4D6BFE"))
COPYRIGHT = ("dsh \u00b7 world.execute(me); TUI MV \u00b7 fan-made tech demo \u00b7 character: dsh "
             "\u00b7 music: owner-provided (assets/audio/song.mp3) \u00b7 MIT")
def _S(v: float) -> int: return config.scaled(v)
GAIN = 1.14        # apply_post 整体提亮（普通显示器可读性）
DIM_SIDE = 0.62    # LEAD 时非主栏的亮度系数（原 0.42 太黑）
def _fade(t: float) -> float:
    """关机亮度：3:25 起下滑 -> 3:28 扫光 -> 3:29.5 #001-#129 全亮 -> 0.5 s 内熄到全黑。"""
    if t < SHUT_EGG: return 1.0
    if t < SHUT_SWEEP: return 1.0 - 0.45 * (t - SHUT_EGG) / (SHUT_SWEEP - SHUT_EGG)
    if t < 209.5: return 0.55 - 0.15 * (t - SHUT_SWEEP) / (209.5 - SHUT_SWEEP)
    return 0.40 * max(0.0, 1.0 - (t - 209.5) / (SHUT_OFF - 209.5))
def _pulse(t: float, tl: Timeline) -> float:
    beats = getattr(tl, "beats", ()) or ()
    return 0.5 if not beats else math.exp(-min(abs(t - b) for b in beats) / 0.14)
def _timecode(t: float) -> str:
    m = int(t // 60)
    return "%02d:%04.1f" % (m, t - 60 * m)
def _glitch_brand(t: float) -> str:
    """72 s 章节故障：**逐字置换**（位置与长度都不动），不是两条字符串叠印。"""
    noise = "!<>-_/[]{}=+*^?#"
    return "".join(ch if theme.hash01(i * 31 + int(t * 24), 17) <= 0.3
                   else noise[int(theme.hash01(i, 5) * 997) % len(noise)] for i, ch in enumerate(BRAND))
def _status_color(st: str, pal: Palette) -> str:
    """状态字色（DESIGN 2.3 实测：RUNNING #979dad / WARN #b1951f / ERROR #a63e41）。"""
    return (theme.shade(pal.warn, 0.76) if st == "warn" else theme.shade(pal.error, 0.68) if st == "error" else theme.mix(pal.text, pal.dim, 0.35))
def _shell_frame(t: float) -> tuple[str, str]:
    """6 处插帧（DESIGN 2.4）+ S01 整屏终端（scenes 里 0-10.1 s 的 cover=False 段）。"""
    if 7.25 <= t < 8.65:
        return "full", "neofetch"
    if 0.0 <= t < 10.10:
        return "full", "./protect"
    for ts, cmd, kind in SHELL_CMDS:
        if ts - 0.25 <= t < ts + 0.75:
            return kind, cmd
    return "", ""
def _left_title(tl: Timeline, t: float) -> str:
    return "dsh web"                                 # 左栏标题固定；theme.draw_frame_box 自己加 "| " 前缀
def _ops_params(tl: Timeline, t: float) -> dict:
    return {"log": "ai_chronicle" if 19.0 <= t < 42.5 else "opcodes"}
def _bar_box() -> Box:
    return Box(_S(24), _S(config.STDOUT_BAR[0]), _S(1256), _S(config.STDOUT_BAR[1]))
_REJECTS = (77.9, 80.8, 83.8, 85.0)      # 左栏返回 REJECTED: identity_lock 的时刻
def _reject_glitch(img, t: float, pal: Palette) -> None:
    """变形失败的瞬间反馈：中栏三段水平错位、3 帧内衰减归零 —— 表示「试着变形，没成功」。"""
    for rt in _REJECTS:
        dt = t - rt
        if not 0.0 <= dt < 3.0 / config.FPS: continue
        k, a, b = 1.0 - dt * config.FPS / 3.0, _S(config.MID_X[0]), _S(config.MID_X_WIDE[1])
        y0, y1 = _S(config.PANEL_TOP), _S(config.PANEL_BOTTOM)
        band, h = img.crop((a, y0, b, y1)), (y1 - y0) // 3
        img.paste(pal.bg, (a, y0, b, y1))
        for i, dx in enumerate((9, -6, 4)):
            img.paste(band.crop((0, i * h, b - a, (i + 1) * h)), (a + int(dx * k), y0 + i * h))
        return

def _draw_ops(d, tl: Timeline, t: float, pal: Palette, sb: float) -> None:
    """右栏：x=1189 分隔线 + 面板框（框归 composite，内容归 tui_engine.draw_ops）。
    AI 编年史区间（0:19–0:42）spectacle.ops_box 会把 ops 加宽到 256px——76px 装不下一行。"""
    ob = spectacle.ops_box(t) if (config.SPECTACLE_ENABLED and config.FX_LAYOUT_BREAK) else None
    x0, x1 = (ob.x0, ob.x1) if ob is not None else (_S(config.OPS_X[0]), _S(config.OPS_X[1]))
    # 不透明底板：theme.draw_frame_box 只描边不填充，中栏面板溢出的像素会穿透到 ops 栏里。
    d.rectangle([x0, _S(config.PANEL_TOP), x1, _S(config.PANEL_BOTTOM)], fill=pal.bg)
    d.line([x0 + _S(9), _S(config.PANEL_TOP), x0 + _S(9), _S(config.PANEL_BOTTOM)], fill=pal.line)
    box = Box(x0, _S(config.PANEL_TOP), x1, _S(config.PANEL_BOTTOM))
    title = "ops ai_chronicle" if _ops_params(tl, t)["log"] == "ai_chronicle" else "ops"
    tui_engine.draw_ops(d, theme.draw_frame_box(d, box, title, pal, sb), tl, t, pal, sb, _ops_params(tl, t))

def _dim_side(img: Image.Image, lead: str) -> None:
    """LEAD=left/right 时另一边的亮度系数，帧内现算，不读历史。"""
    w = img.size[0]
    box = ((max(0, _S(config.MID_X[0]) - _S(config.GUTTER_LR)), _S(config.PANEL_TOP), w, _S(config.PANEL_BOTTOM)) if lead == "left"
           else (0, _S(config.PANEL_TOP), min(w, _S(config.LEFT_X[1]) + _S(config.GUTTER_LR)), _S(config.PANEL_BOTTOM)))
    if box[2] > box[0] and box[3] > box[1]:
        img.paste(ImageEnhance.Brightness(img.crop(box)).enhance(DIM_SIDE), box[:2])

def _spectrum(d, t: float, tl: Timeline, pal: Palette) -> None:
    """顶栏音频频谱：由拍点脉冲 + 确定性哈希合成（时间轴没有频谱字段，见给 lead 的说明）。"""
    x0, p, frame = _S(560), _pulse(t, tl), int(t * 8)
    for i in range(7):
        v, bx = theme.hash01(i, frame) * (0.35 + 0.65 * p), x0 + i * _S(6)
        d.rectangle([bx, _S(20) - max(_S(2), int(v * _S(14))), bx + _S(4), _S(20)], fill=pal.accent if v > 0.5 else pal.accent_dim)

def _protect(d, t: float, pal: Palette) -> None:
    if 5.9 <= t < 6.3:                               # QA：0:06 有一帧近乎空白
        return
    for i, step in enumerate(PROTECT_STEPS[:max(0, min(len(PROTECT_STEPS), int((t - 2.35) / 0.06) + 1))]):
        y = _S(52) + i * _S(24)
        theme.draw_text(d, (_S(40), y), "[ OK ]", theme.font_mono(13), pal.ok, anchor="l"); theme.draw_text(d, (_S(110), y), step, theme.font_mono(13), pal.text, anchor="l")

def _neofetch(d, t: float, pal: Palette, s: float) -> None:
    x0, y0, x1, y1 = _S(120), _S(70), _S(430), _S(330)
    theme.draw_frame_box(d, Box(x0, y0, x1, y1), None, pal, s)
    theme.draw_text(d, (x0 + _S(20), y0 + _S(44)), "me@deepseek", theme.font_mono(13), pal.text, anchor="l"); theme.draw_text(d, (x0 + _S(20), y0 + _S(64)), "-" * 22, theme.font_mono(13), pal.line, anchor="l")
    theme.draw_text(d, (x0 + _S(20), y0 + _S(92)), "me.color = #4D6BFE", theme.font_mono(13), pal.accent, anchor="l")
    for i, (k, v) in enumerate(NEOFETCH_ROWS[:max(0, min(len(NEOFETCH_ROWS), int((t - 7.5) * 10) + 1))]):
        theme.draw_text(d, (_S(500), _S(84) + i * _S(17)), k, theme.font_mono(13), pal.highlight, anchor="l"); theme.draw_text(d, (_S(620), _S(84) + i * _S(17)), v, theme.font_mono(13), pal.text, anchor="l")

def _full_terminal(d, t: float, cmd: str, pal: Palette, s: float) -> None:
    d.rectangle([0, 0, _S(config.WIDTH), _S(config.HEIGHT)], fill=pal.bg)
    theme.draw_text(d, (_S(24), _S(22)), PROMPT + " " + cmd, theme.font_mono(13), pal.text, anchor="l")
    _neofetch(d, t, pal, s) if cmd == "neofetch" else _protect(d, t, pal)

def _chronicle_big(d, t: float, pal: Palette, s: float) -> None:
    """01 PRETRAIN：每 2-3 秒抽一条 AI 编年史在中栏用大字展示 2 秒（DESIGN §11 致敬段）。
    XOR CRITIQUE 用 WARN 黄，与全局颜色切换机制对齐。"""
    for t0, t1, year, name, tone in config.AI_BIG_CHRONICLE:
        if not (t0 <= t <= t1):
            continue
        a = min(1.0, (t - t0) / 0.22) * min(1.0, (t1 - t) / 0.22)      # 淡入淡出
        ob = spectacle.ops_box(t) if config.SPECTACLE_ENABLED else None
        # 右对齐到 **ops 真正的左边界**（编年史期 ops 会加宽到 x=1000），否则会被它的底板吃掉。
        xr, y0 = min(_S(config.MID_X[1]), (ob.x0 if ob else _S(config.OPS_X[0])) - _S(16)), _S(config.PANEL_TOP) + _S(4)
        col = theme.shade(pal.warn if tone == "warn" else pal.dim, 0.45 + 0.55 * a)
        theme.draw_text(d, (xr, y0), "%s · %s" % (year, name), theme.font_title(15), col, anchor="r")
        theme.draw_text(d, (xr, y0 + _S(17)), "// ai chronicle", theme.font_mono(9), theme.shade(pal.dim, 0.3 + 0.6 * a), anchor="r")

def compose_frame(t: float, tl: Timeline,
                  texts: list[tuple[str, str]] | None = None,
                  scale: float | None = None,
                  pixelate: bool = False) -> Image.Image:
    """纯函数 f(t)。分层顺序固定（DESIGN.md 7.3），不得调换。
    后期（CRT）由 render.py 调 apply_post；3:20 起 SP 不再接管布局，保证左栏归档与 chrome 在。"""
    sc = float(config.RENDER_SCALE if scale is None else scale)
    if config.RENDER_SCALE != sc:         # 集成护栏：theme/scenes 全走 config.scaled()
        config.RENDER_SCALE = sc
    w, h = max(1, int(round(config.WIDTH * sc))), max(1, int(round(config.HEIGHT * sc)))
    pal = palette_for(tl.state_at(t))
    sb = 0.45 + 0.35 * _pulse(t, tl)
    img = Image.new("RGB", (w, h), pal.bg)
    d = ImageDraw.Draw(img)
    if t >= SHUT_TOMB:                                # 3:30-3:32 墓碑：全片最暗，只剩 _ 光标 + 版权条
        d.rectangle([0, 0, w, h], fill=(0, 0, 0))     # 比 3:29 的全黑帧更暗：接得上，不闪
        if 210.10 <= t < 210.55 or 210.85 <= t < 211.30:
            theme.draw_text(d, (_S(24), _S(28)), "_", theme.font_mono(16), pal.text, anchor="l")
        draw_copyright(d, pal, sb)
        return finalize_frame(img, pixelate)
    theme.draw_grid_bg(d, Box(0, 0, w, h), pal, 16, sb)   # step 是设计像素，theme 内部换算
    draw_status_bar(d, tl, t, pal, sb)
    if _shell_frame(t)[0] == "full":
        chat_pages.draw_stdout_tokens(d, _bar_box(), tl, t, pal, sb, texts)
        draw_copyright(d, pal, sb)
        return finalize_frame(img, pixelate)
    shut = t >= SHUT_ARCH                             # 关机序列：布局交回 scenes，SP 不再越界
    shot = scenes.active_shot(t)
    panels = tuple(shot.panels) if shut else tuple(scenes.layout_for(t) or ())
    cover = bool(getattr(shot, "cover", True))        # False = 左栏交给镜头自己画
    merged = bool(panels) and min(p.box.x0 for p in panels) <= _S(config.LEFT_X[0]) + _S(2)
    keep_left = (config.SPECTACLE_ENABLED and config.FX_QUALITY != "off"
                 and spectacle.keeps_left(t))         # SP10：先画左栏，tile 才有内容可散
    if cover and (not merged or keep_left):
        lb = Box(_S(config.LEFT_X[0]), _S(config.PANEL_TOP), _S(config.LEFT_X[1]), _S(config.PANEL_BOTTOM))
        chat_pages.draw_chat(d, theme.draw_frame_box(d, lb, _left_title(tl, t), pal, sb, t),
                             tl, t, pal, texts or [], sb)
    if SHUT_EGG <= t < SHUT_SWEEP:                    # 彩蛋 A：中栏鲸鱼娘剪影退回官方蓝鲸图标
        eb = Box(_S(config.MID_X[0]), _S(config.PANEL_TOP), _S(config.MID_X_WIDE[1]), _S(config.PANEL_BOTTOM))
        tui_viz.viz_whale_echo(d, theme.draw_frame_box(d, eb, "SP0 reverse", pal, sb), t, {}, pal, sb)
    elif t < SHUT_SWEEP:
        for p in panels:
            tui_engine.draw_visual(d, p, tl, t, sb)
    if cover and not merged:
        _draw_ops(d, tl, t, pal, sb)
    _chronicle_big(d, t, pal, sb)         # 必须在 ops 之后：编年史期 ops 底板会盖到 x=1000
    _reject_glitch(img, t, pal)          # 变形失败闪断（3 帧错位，随即恢复）
    lead = scenes.lead_at(t)
    if lead in ("left", "right") and cover and not merged:
        _dim_side(img, lead)
    chat_pages.draw_stdout_tokens(d, _bar_box(), tl, t, pal, sb, texts)
    draw_copyright(d, pal, sb)
    if config.SPECTACLE_ENABLED and config.FX_QUALITY != "off" and not shut:
        spectacle.compose(d, img, tl, t, pal, sb)
    return finalize_frame(img, pixelate)

def draw_status_bar(d, tl: Timeline, t: float, pal: Palette, s: float = 1.0) -> None:
    """片名 + 提示符 + 音频频谱条 + 章节 + 时码 + 状态字；6 处 shell 命令插帧也在这里。"""
    kind, cmd = _shell_frame(t)
    if kind == "full":
        _full_terminal(d, t, cmd, pal, s)
        return
    x, base = _S(24), _S(16)
    if kind == "hdr":                                # 只换顶栏左段，双栏 UI 不撤
        theme.draw_text(d, (x, base), PROMPT + " " + cmd, theme.font_mono(13), pal.highlight, anchor="l")
    else:
        glitch = abs(t - 72.0) < 0.6                 # 章节故障插曲：顶栏染红乱码（DESIGN 2.2）
        theme.draw_text(d, (x, base), PROMPT, theme.font_mono(13), pal.dim, anchor="l")
        theme.draw_text(d, (x + _S(130), base), _glitch_brand(t) if glitch else BRAND,
                        theme.font_mono(12), pal.error if glitch else pal.text, anchor="l")
    _spectrum(d, t, tl, pal)
    st, (code, name) = tl.state_at(t), tl.chapter_at(t)
    if code != "--":                                 # 05 缺席：整条状态栏空白
        col = _status_color(st, pal)
        theme.draw_text(d, (_S(880), base), code + " / " + name, theme.font_mono(13), col, anchor="l")
        theme.draw_text(d, (_S(1060), base), _timecode(t), theme.font_mono(13), pal.text, anchor="l")
        word = STATUS_WORD.get(st, "RUNNING")
        theme.draw_text(d, (_S(1256) - theme.text_width(word, theme.font_mono(13)), base), word, theme.font_mono(13), col, anchor="l")
        if _pulse(t, tl) > 0.45:
            theme.draw_text(d, (_S(1170), base), "\u25c6", theme.font_mono(12), pal.accent, anchor="l")

def draw_copyright(d, pal: Palette, s: float = 1.0) -> None:
    theme.draw_text(d, (_S(24), _S(config.COPYRIGHT_BASELINE)), COPYRIGHT, theme.font_mono(11), pal.dim, anchor="l")

def _post_params(pal: Palette) -> tuple[float, float, bool]:
    if pal.accent == "#f4534c": return 0.5, 0.45, False
    return (0.25, 0.30, True) if pal.accent == "#6b8cff" else (0.42, 0.35, False)

def apply_post(img: Image.Image, t: float, pal: Palette,
               prev: Image.Image | None = None) -> Image.Image:
    """残影 / 辉光 / 扫描线 / 渐晕（prev 由 render.py 持有）。3:25 起扫描线关闭、辉光收敛，
    3:30 起只剩最暗一帧；最后**重画版权条**——chrome 永不被 spectacle 覆盖、永不消失。"""
    trail, bloom, lift = _post_params(pal)
    if t >= SHUT_EGG:
        trail, bloom = 0.0, 0.0
    if t >= SHUT_TOMB:
        draw_copyright(ImageDraw.Draw(img), pal)
        return img
    img = ImageEnhance.Brightness(img).enhance(GAIN * _fade(t))
    if prev is not None and trail > 0.0:
        p = prev if prev.size == img.size else prev.resize(img.size)
        img = ImageChops.lighter(img, p.point(lambda v: int(v * trail)))
    if bloom > 0.0:
        glow = img.filter(ImageFilter.GaussianBlur(max(1, _S(4))))
        img = ImageChops.add(img, glow.point(lambda v: int(v * bloom)))
    if t < SHUT_EGG:
        rgba = img.convert("RGBA")
        rgba.alpha_composite(_scanlines(*img.size))
        rgba.alpha_composite(_vignette(img.size[0], img.size[1], lift))
        img = rgba.convert("RGB")
    draw_copyright(ImageDraw.Draw(img), pal)
    return img

def finalize_frame(img: Image.Image, pixelate: bool) -> Image.Image:
    """PIXELATE_FOR_TERMINAL：4K = 720p 最近邻 3 倍；尺寸不变（render.py 按 WIDTH*scale 写管道）。"""
    if not pixelate or img.size[0] <= config.WIDTH:
        return img
    return img.resize((config.WIDTH, config.HEIGHT), Image.NEAREST).resize(img.size, Image.NEAREST)

@lru_cache(maxsize=4)
def _scanlines(w: int, h: int) -> Image.Image:
    """静态贴图：每 3 行一条黑线（DESIGN 7.5 允许的 lru_cache 静态层）。"""
    img, d = Image.new("RGBA", (w, h), (0, 0, 0, 0)), None
    d = ImageDraw.Draw(img)
    for y in range(0, h, max(1, _S(3))): d.line([0, y, w, y], fill=(0, 0, 0, 18))
    return img

@lru_cache(maxsize=8)
def _vignette(w: int, h: int, lift: bool) -> Image.Image:
    """64x36 的 L 图双线性放大；底部三条（stdout / 版权）不压暗。"""
    sw, sh, strength = 64, 36, 18 if lift else 32
    cut = int(sh * max(0.0, 1.0 - (config.HEIGHT - config.COPYRIGHT[0]) / float(config.HEIGHT)))
    small = Image.new("L", (sw, sh), 255); px = small.load()
    for y in range(cut):
        for x in range(sw):
            r = min(1.0, (((x - sw / 2.0) / (sw / 2.0)) ** 2 + ((y - sh / 2.0) / (sh / 2.0)) ** 2) ** 0.5)
            px[x, y] = max(0, 255 - int(strength * (r ** 2.5)))
    alpha = small.resize((w, h), Image.BILINEAR).point(lambda v: 255 - v)
    return Image.merge("RGBA", (Image.new("L", (w, h), 0), Image.new("L", (w, h), 0),
                                Image.new("L", (w, h), 0), alpha))
