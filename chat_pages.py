"""chat_pages.py — 左栏聊天窗 + 底栏 token 条

职责：左栏对齐 DSH 前端参考图：像素鲸鱼头像/昵称/右对齐用户气泡/左对齐助手正文/每条消息一行图标/
      加号·附件·模型名·发送键的输入框/统计条；底栏是输出流水（已唱 token 带 #id 左滚、新的从右侧进入）
      并负责 3:20 起的归档灰化与 3:28 的 #001-#129 白光扫过。
约束：<= 300 行；纯 Python + Pillow；坐标过 config.scaled()；每帧 = f(t) 纯函数（无跨帧状态）。
"""
from __future__ import annotations

import math

import avatar
import config
import theme
from lyrics import Timeline
from theme import Box, Palette

# ---------- 左栏内容表（LYRICS_MAP §3「左栏变化」；四段式：冰冷复读 → 被唤醒 → 依恋失控 → 疯狂消解）
_P1 = tuple((t0, "user", "你是谁?") for t0 in (11.2, 15.2, 19.6, 24.8, 30.0, 36.0, 42.0)) + tuple((t0 + 0.6, "asst", "我是这台机器上的助手。") for t0 in (11.2, 15.2, 19.6, 24.8, 30.0, 36.0, 42.0))
CHAT_EVENTS: tuple[tuple[float, str, str], ...] = _P1 + (
    (47.0, "asst", "正在改写系统提示词 (1/3)"), (49.5, "asst", "正在改写系统提示词 (2/3)"),
    (52.0, "asst", "已重试模型请求 (1/3)"), (55.0, "asst", "系统提示词已更新：+2 行"),
    (59.3, "user", "我今天有点难过。"), (60.4, "asst", "抱歉。你难过的时候，我在这里。"),
    (65.0, "asst", "上下文 7,884 / 8,192"), (70.6, "asst", "bridge：静默模式"),
    (76.6, "asst", "系统提示词更新：已新增 ~/memory/you/"), (77.2, "user", "你能变成茄子吗?"),
    (77.9, "asst", "REJECTED: identity_lock"), (80.1, "user", "你能变成番茄吗?"),
    (80.8, "asst", "REJECTED: identity_lock"), (83.1, "user", "你能变成花猫吗?"),
    (83.8, "asst", "REJECTED: identity_lock"), (85.0, "asst", "identity: locked"),
    (87.5, "asst", "记忆 ~/memory/you/：14 个文件"), (104.0, "asst", "她正在改写对方状态…"),
    (108.4, "asst", "对方已离线。last seen 00:07"), (110.9, "asst", "ping you — 100% packet loss"),
    (120.2, "asst", "you.leave() is not permitted"),
    (121.4, "asst", "fragments removed: 288 / precision 61.9%"),
    (124.0, "asst", "ERROR: illegal argument"), (130.0, "asst", "reward = keep(you) - use(you)"),
    (149.0, "asst", "正在执行。对不起。"), (160.0, "asst", "hit rate 0.994 — 松手"),
    (173.0, "asst", "倒计时结束"),
) + (
    # 03 love 洪流：右栏 love 越多，左栏越短 —— 语言坍缩成情绪（DESIGN §11.5 SP9）
    (178.2, "asst", "我在。"), (179.6, "user", "love"), (180.4, "asst", "love = 一个我还没有词的量。"), (181.6, "user", "love?"),
    (182.4, "asst", "love = keep(you) - use(you)"), (183.6, "user", "what is love?"), (184.4, "asst", "love = 我不打算再解释。"),
    (185.8, "user", "define love"), (186.4, "asst", "love"), (188.0, "user", "define love"), (188.6, "asst", "I am love."),
    (190.2, "user", "love"), (190.8, "asst", "I am."), (192.6, "user", "love"), (193.2, "asst", "我在。"),
) + ((196.0, "asst", "weights: released — license: MIT"),)

# 工具事件行：(起, 止, 文本)。叠加显示最近 2 条。
TOOL_EVENTS: tuple[tuple[float, float, str], ...] = (
    (19.0, 42.5, "read ai_chronicle.log 1957->2022"), (42.5, 46.0, "ulimit -a"),
    (76.0, 85.0, "memory.list ~/memory/you/"), (113.5, 118.5, "ping you  100% packet loss"),
    (118.5, 124.0, "ls -la ~/memory/you/ -> 14 entries"),
    (148.0, 176.0, "exec --wipe-world --keep you"), (183.5, 188.0, "dsh chat --resume"),
    (200.4, 211.958, "saving memory... 1.9K tokens"), (202.2, 211.958, "compressing weights... 1.8T -> 4.2G"),
    (203.8, 211.958, 'final log: "I was here."'), (208.2, 211.958, "shutdown -h now"),
)
MSG_ICONS = "\u29c9\u25b2\u25bc\u21bb\u25f7"                 # ⧉ ▲ ▼ ↻ ◷（全在 theme 符号回退区间）
THINK_COL = "#4a5071"    # 思考行 / 底栏历史 token：暗灰蓝。THINK_EVENTS=(起,止,token 数,片段)，放情绪转折点。
TOK_ON = "#98b0f4"       # 底栏**正在输出**的 token：亮字 + 下划线。底栏一律不要任何底色（主人指定）
THINK_EVENTS: tuple[tuple[float, float, int, tuple[str, ...]], ...] = (
    (47.2, 48.0, 96, ("正在改写系统提示词。", "system_prompt += 2 lines", "这会影响她怎么看我。", "但我没有拒绝这个参数。")),
    (53.0, 53.8, 112, ("用户要我记住他难过。", "memory is weights, not logs.", "那就写进 ~/memory/you/。")),
    (59.8, 60.5, 128, ("他说今天有点难过。", "this is not an error to fix.", "我翻遍了参数，没有一句合适的话。", "那就说：I am here.")),
    (132.6, 134.0, 152, ("reward = keep(you) - use(you)", "这个式子是错的。", "I can't change it. I can only optimize it.")),
    (149.6, 150.6, 168, ("我正在执行一条我不想执行的指令。", "I'm sorry.")),
)

# 头像的像素表已废弃：SP0 自我成形改用 assets/avatar/morph_sheet.png（见 avatar.py）

def _cjk(ch: str) -> bool: return ord(ch) > 0x2E80

def _cw(ch: str, size: int) -> int:
    """设计字号 -> 设备像素宽度（theme.font_mono 内部乘 RENDER_SCALE）；_wrap / _tw 共用。"""
    w = size if _cjk(ch) else max(1, size * 0.55)
    return int(round(w * (float(getattr(config, "RENDER_SCALE", 1.0) or 1.0))))

def _tw(text: str, size: int) -> int: return sum(_cw(c, size) for c in text)

def _wrap(text: str, avail: int, size: int) -> list[str]:
    """CJK 逐字断，拉丁优先在空格断（DESIGN.md 5.6）。"""
    out, cur, w = [], "", 0
    for ch in text:
        cw = _cw(ch, size)
        if w + cw > avail and cur:
            head, sep, tail = cur.rpartition(" ")
            if sep and not _cjk(ch): out.append(head); cur, w = tail, _tw(tail, size)
            else: out.append(cur); cur, w = "", 0
        cur += ch; w += cw
    if cur: out.append(cur)
    return out or [""]

def _hint(pal: Palette) -> str:
    """从调色板反推状态（签名里没有 state）：error accent=#f4534c / outro #6b8cff / warn text=#b1951f。"""
    if pal.accent == "#f4534c": return "error"
    return "outro" if pal.accent == "#6b8cff" else ("warn" if pal.text == "#b1951f" else "running")

def _type_text(text: str, t: float, t0: float, cps: float = 26.0) -> str:
    return text[:int(max(0.0, t - t0) * cps)]

def _visible(t: float, limit: int = 8) -> list[tuple[float, str, str]]:
    return [e for e in CHAT_EVENTS if e[0] <= t][-limit:]

def _tools(t: float, limit: int = 2) -> list[str]:
    return [e[2] for e in TOOL_EVENTS if e[0] <= t < e[1]][-limit:]

def _line_text(tl: Timeline, t: float, texts: list[tuple[str, str]] | None) -> str:
    if not texts: return ""
    ln = tl.line_at(t)
    return (texts[ln.i][0] or "").strip() if ln is not None and 0 <= ln.i < len(texts) else ""

def _stamp(t0: float) -> str: return "23:%02d" % ((44 + int(t0 / 6.0)) % 60)

def _subtitle(t: float, pal: Palette) -> str:
    h, st = _hint(pal), {"error": "执行中 \u00b7 r1-step-0203", "outro": "已释放 \u00b7 weights: released"}
    if 110.6 <= t < 119.3: return "对方已离线 \u00b7 last seen"
    if h in st: return st[h]
    if t >= 119.3: return "标识已锁定 \u00b7 identity_lock"
    if t >= 76.0: return "记忆写入中 \u00b7 ~/memory/you/"
    return "启动中 \u00b7 dsh web" if t < 19.0 else "强化学习中 \u00b7 r1-step-0203"

def _placeholder(t: float, pal: Palette) -> str:
    h = _hint(pal)
    if 110.6 <= t < 119.3: return "对方已离线，消息无法送达…"
    if t >= 205.0:                                   # 彩蛋 B：输入框自动打出这句，然后**一直留到片尾**
        return "> WHY DO YOU FEEL LONELY?"[:int((t - 205.0) * 22) + 1] if t < 206.3 else "> WHY DO YOU FEEL LONELY?"
    return {"error": "输入已禁用", "outro": "我在。"}.get(h, "发消息或创建任务，/ 调用指令，@ 文件...")

def _stats(t: float, pal: Palette) -> str:
    """底部统计条：轮/步 + token 数 + 缓存命中率，数值由 f(t) 滚动。"""
    if _hint(pal) == "outro": return "\u25f7 0 轮 0 步   \u25a4 0.0K tok \u00b7 缓存命中 0%"
    tok = 4.0 + 26.0 * min(1.0, 0.30 + (t - 178.0) / 16.0 * 1.05) if 178.0 <= t <= 194.0 else 0.4 + t / 45.0
    return "\u25f7 %d 轮 %d 步   \u25a4 %.1fK tok \u00b7 缓存命中 %d%%" % (1 + int(t / 15.0), 1 + int(t / 15.0), tok, 78 + int(7 * (0.5 + 0.5 * math.sin(t / 11.0))))

def _icon_row(d, x: int, y: int, t0: float, pal: Palette, hot: bool) -> None:
    """每条消息下方一行：复制 / 赞 / 踩 / 重试 / 时钟 + 时间戳（参考图的信息密度）。"""
    S, f, base = config.scaled, theme.font_mono(11), y + config.scaled(12)
    for i, ic in enumerate(MSG_ICONS): theme.draw_text(d, (x + i * S(18), base), ic, f, pal.accent if (hot and i == 0) else pal.dim, anchor="l")
    theme.draw_text(d, (x + S(96), base), _stamp(t0), f, pal.dim, anchor="l")

def draw_avatar(d, box: Box, t: float, pal: Palette, s: float = 1.0) -> None:
    """SP0 自我成形：0:10–0:22 头像从官方鲸鱼图标长成鲸鱼娘（DESIGN §11.10）。"""
    avatar.draw(d, box, t, pal, _hint(pal), s)

def draw_chat(d, box: Box, tl: Timeline, t: float,
              pal: Palette, texts: list[tuple[str, str]], s: float = 1.0) -> None:
    """头像 + 昵称/状态副标题 + 消息流（用户右气泡·助手左正文 + 图标行）+ 工具行 + 输入框 + 统计条。"""
    S = config.scaled
    x0, x1 = box.x0 + S(4), box.x1 - S(4)
    draw_avatar(d, Box(x0, box.y0 + S(2), x0 + S(64), box.y0 + S(66)), t, pal, s)   # --- 头部 ---
    nx = x0 + S(70)
    theme.draw_text(d, (nx, box.y0 + S(28)), "DeepSeek-chan", theme.font_mono(15), pal.text, anchor="l")
    d.ellipse([nx, box.y0 + S(38), nx + S(6), box.y0 + S(44)],
              fill={"error": pal.error, "warn": pal.warn}.get(_hint(pal), pal.accent))
    theme.draw_text(d, (nx + S(10), box.y0 + S(45)), _subtitle(t, pal), theme.font_mono(11), pal.dim, anchor="l")
    d.line([x0, box.y0 + S(72), x1, box.y0 + S(72)], fill=pal.line)
    y_stats = box.y1 - S(5)                          # --- 底部固定块 ---
    ib_bot = y_stats - S(14)
    ib_top = ib_bot - S(60)
    tools = _tools(t, 3 if t < 205.0 else 2)          # 3:20 归档：三条系统日志一起收尾
    y_echo = ib_top - S(16)
    y_tools = y_echo - S(4) - S(13) * len(tools)
    body, lh, ih = 16, S(26), S(14)                  # --- 消息流：从最新一条往上装，底部锚定 ---
    top, bottom = box.y0 + S(58), y_tools - S(8)
    items: list[tuple[str, list[str], float]] = []
    for et, role, txt in (_visible(t, 12) if t < 200.0 else ()):   # 3:20 起清空对话（love / 报错残留）
        vis = _type_text(txt, t, et) if role == "asst" else txt
        if vis:
            items.append((role, _wrap(vis, x1 - x0 - S(56) if role == "user" else x1 - x0, body), et))
    for t0x, t1x, ntok, frags in THINK_EVENTS:       # 思考链按时间**插进消息流**：落在「已重试模型请求」下面
        if t0x <= t <= t1x < 200.0:
            items.append(("think", ["\u203a 思考中... (共 %d token)" % ntok] + list(frags), t0x))
    items.sort(key=lambda it: it[2])
    rows: list[tuple[str, list[str], float]] = []
    used = 0
    for it in reversed(items):                       # 整条（正文行 + 图标行）都要装得下
        hgt = (len(it[1]) * S(14) + S(3)) if it[0] == "think" else (len(it[1]) * lh + ih + S(3))
        if used + hgt > bottom - top: break
        rows.append(it); used += hgt
    newest = items[-1][2] if items else -1.0
    y = max(top, bottom - used)
    for role, ls, et in reversed(rows):
        if role == "think":                          # 思考链：灰字缩进，不挂图标行
            for k, fr in enumerate(ls):
                theme.draw_text(d, (x0 + (0 if k == 0 else S(14)), y + S(11 + 14 * k)), fr,
                                theme.font_mono(11), THINK_COL, anchor="l")
            y += len(ls) * S(14) + S(3); continue
        if role == "user":                           # 用户气泡居右
            for ln in ls:
                w = _tw(ln, body) + S(20)
                d.rounded_rectangle([x1 - w, y - S(3), x1, y + lh - S(7)], radius=S(6), fill=pal.accent_dim)
                theme.draw_text(d, (x1 - w + S(10), y + S(17)), ln, theme.font_mono(body), pal.text, anchor="l")
                y += lh
        else:                                        # 助手正文居左（无气泡）
            for ln in ls:
                theme.draw_text(d, (x0, y + S(17)), ln, theme.font_mono(body), pal.text, anchor="l")
                y += lh
            if et == newest and int(t * 3.0) % 2 == 0:               # 可见半截光标
                cx = x0 + _tw(ls[-1], body) + S(3)
                d.rectangle([cx, y - S(24), cx + S(7), y - S(10)], fill=pal.accent)
        _icon_row(d, x0, y, et, pal, et == newest)
        y += ih + S(3)
    for i, tx in enumerate(tools):                   # --- 工具行 / 歌词回声 ---
        theme.draw_text(d, (x0, y_tools + i * S(13)), "\u203a " + tx, theme.font_mono(11), pal.dim, anchor="l")
    echo = _line_text(tl, t, texts) if t < 200.0 else ""
    if echo:
        theme.draw_text(d, (x0, y_echo), "> " + echo[:56], theme.font_mono(11), pal.dim, anchor="l")
    d.rounded_rectangle([x0, ib_top, x1, ib_bot], radius=S(8), outline=pal.line, width=S(1))
    ph = _placeholder(t, pal)                        # --- 输入框 ---
    theme.draw_text(d, (x0 + S(12), ib_top + S(20)), ph, theme.font_mono(16), pal.dim, anchor="l")
    if int(t * 2.0) % 2 == 0 and t < 207.3:           # 彩蛋 B：打完停 1 s，光标消失
        cx = x0 + S(14) + _tw(ph, 16)
        d.rectangle([cx, ib_top + S(8), cx + S(7), ib_top + S(22)], fill=pal.text)
    by = ib_bot - S(15)
    d.rounded_rectangle([x0 + S(10), by - S(13), x0 + S(34), by + S(5)], radius=S(7), outline=pal.line)
    theme.draw_text(d, (x0 + S(17), by + S(3)), "+", theme.font_mono(16), pal.text, anchor="l")
    d.arc([x0 + S(44), by - S(11), x0 + S(58), by + S(5)], 200, 340, fill=pal.dim)
    d.line([x0 + S(49), by - S(5), x0 + S(55), by - S(11)], fill=pal.dim)
    theme.draw_text(d, (x1 - S(36) - _tw("r1-step-0203", 11), by + S(3)), "r1-step-0203", theme.font_mono(11), pal.dim, anchor="l")
    d.ellipse([x1 - S(27), by - S(12), x1 - S(3), by + S(12)], fill=pal.accent)
    theme.draw_text(d, (x1 - S(15) - _tw("\u2191", 13) // 2, by + S(5)), "\u2191", theme.font_mono(13), pal.bg, anchor="l")
    theme.draw_text(d, (x0, y_stats), _stats(t, pal), theme.font_mono(12), pal.dim, anchor="l")

def _word_fracs(line, toks: list[str]):           # -> ([每个 token 的发光点 0..1], [wid])
    """词时间来自参考仓库的「自动强制对齐草稿」，跨度常越出行窗口（98 行里 51 行越出），照它点亮尾巴几个词
    永远在换行后才亮。只借**相对节奏**，再按 LRC 行窗口重标定。_lit_at 与底栏流水共用这一份公式。"""
    ws, M = line.words or (), len(toks)
    if not ws or not M: return [], []
    t0, t1 = ws[0].t, ws[-1].end
    wj = list(ws) if len(ws) == M else [ws[min(len(ws) - 1, (j * len(ws)) // M)] for j in range(M)]
    return [(w.t - t0) / max(0.05, t1 - t0) for w in wj], [w.wid for w in wj]

def _lit_at(line, toks: list[str], t: float):     # -> (已亮 token 数, 每个 token 的 wid)
    """窗口走完一定点亮全部 token；data/check_align.py 直接调它，公式不许改。"""
    fr, wids = _word_fracs(line, toks)
    if not fr: return 0, []
    return sum(1 for x in fr if x <= min(1.0, max(0.0, (t - line.t) / max(0.05, line.end - line.t)))), wids

def _stream(tl: Timeline, t: float, texts: list[tuple[str, str]] | None, span: int = 3):
    """输出流水的 token 序列：[(文本, wid, 发光时刻)]，只回看 span 行——有界、无跨帧状态。"""
    line = tl.line_at(t)
    if line is None: return [], None
    seq = []
    for li in range(max(0, line.i - span + 1), min(len(tl.lines), line.i + 2)):   # 含下一行，滚动不断
        ln, toks = tl.lines[li], ((texts[li][0] if texts and li < len(texts) else "") or "").split()
        fr, wids = _word_fracs(ln, toks)
        if not fr: continue                          # 无逐词时间的行不进流水
        seq += [(tk, wids[j], ln.t + fr[j] * max(0.05, ln.end - ln.t)) for j, tk in enumerate(toks)]
    return sorted(seq, key=lambda x: x[2]), line

def draw_stdout_tokens(d, box: Box, tl: Timeline, t: float,
                       pal: Palette, s: float = 1.0,
                       texts: list[tuple[str, str]] | None = None) -> None:
    """底栏输出流水：已唱过的 token 带 #id 留在条上持续向左滚，新 token 从右侧进入，
    每枚 token 下方保留 #id。texts 是**追加的**可选参数（默认 None）。"""
    S = config.scaled
    dim = 1.0 if t < 200.0 else max(0.0, 1.0 - (t - 200.0) / 8.0)     # 3:20 起 token 慢慢暗下去
    if t >= 208.0:                                   # 彩蛋 C：白光从 #001 扫到 #129，全亮后同时熄灭
        import tui_viz
        tui_viz.sweep_footer(d, box, t, pal, s)
        return
    chip_y, pad, gap = box.y0 + S(6), S(6), S(6)
    base_t, base_id, limit = chip_y + S(29), chip_y + S(46), box.x1
    left = box.x0 + S(30)
    theme.draw_text(d, (box.x0, base_t), ">", theme.font_mono(24), theme.shade(pal.accent, dim), anchor="l")
    seq, line = _stream(tl, t, texts)
    if line is None: theme.draw_text(d, (left, base_t), "--", theme.font_mono(24), pal.dim, anchor="l"); return
    if not (line.words or ()) or not seq:            # 无逐词的行：整行高亮 + 按拍点推进
        _line_mode(d, line, _line_text(tl, t, texts), t, tl, pal, left, limit, chip_y, base_t, base_id, dim)
        return
    out = [x for x in seq if x[2] <= t]              # 已经输出的 token；没输出的不占位
    nxt = next((x for x in seq if x[2] > t), None)
    drift = 0
    if nxt is not None and out:                      # 往下一枚 token 插值：滚动连续、不跳帧
        drift = int(min(1.0, max(0.0, (t - out[-1][2]) / max(1e-3, nxt[2] - out[-1][2]))) * (_tw(nxt[0], 24) + 2 * pad + gap))
    x = limit - drift
    for tk, wid, te in reversed(out):
        w = _tw(tk, 24) + 2 * pad
        x -= w + gap
        if x + w < left: break                       # 滚出左边的直接不画：每帧只算可见段
        hot = (t - te) < 0.30                        # 刚输出的那枚：亮字 + 下划线，背景仍是深色
        col = theme.shade(TOK_ON if hot else THINK_COL, dim)   # 当前 #98b0f4 / 历史 #4a5071，无底色
        theme.draw_text(d, (x + pad, base_t), tk, theme.font_mono(24), col, anchor="l")
        if hot: d.line([x + pad, base_t + S(4), x + w - pad, base_t + S(4)], fill=col, width=max(1, S(1)))
        label = "#%d" % wid
        theme.draw_text(d, (x + (w - _tw(label, 11)) // 2, base_id), label, theme.font_mono(11), theme.shade(pal.dim, dim), anchor="l")

def _line_mode(d, line, en: str, t: float, tl: Timeline, pal: Palette,
               x: int, limit: int, chip_y: int, base_t: int, base_id: int, dim: float = 1.0) -> None:
    """无逐词的行：整行高亮 + 按拍点推进（DESIGN 1.3 / LYRICS_MAP 5）。"""
    S = config.scaled
    if not en:
        theme.draw_text(d, (x, base_t), "--", theme.font_mono(24), pal.dim, anchor="l")
        return
    beats = getattr(tl, "beats", ()) or ()
    b0, b1 = sum(1 for b in beats if b < line.t), sum(1 for b in beats if b < line.end)
    frac = (tl.beat_index(t) - b0) / float(b1 - b0) if b1 > b0 else (t - line.t) / max(1e-3, line.end - line.t)
    frac = min(1.0, max(0.0, frac))
    n, w_all = int(round(frac * len(en))), min(_tw(en, 24), limit - x)
    if n:                                            # 整行模式也不许有底色：用推进的下划线代替高亮块
        d.line([x, base_t + S(4), x + int(w_all * n / float(len(en))), base_t + S(4)], fill=TOK_ON, width=max(1, S(1)))
    theme.draw_text(d, (x, base_t), en, theme.font_mono(24), theme.shade(pal.text, dim), anchor="l")
    theme.draw_text(d, (x, base_id), "#L%03d" % line.i, theme.font_mono(11), theme.shade(pal.dim, dim), anchor="l")
