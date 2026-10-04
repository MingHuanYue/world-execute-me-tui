"""scenes.py — 镜头表与布局求解

职责：中栏在某一刻裂成几块、每块画什么；装载期断言覆盖全片。
约束：<= 300 行；纯 Python；所有坐标过 config.scaled()。
接口：逐字实现 FILE_TREE.md ⑤（签名改动必须先改 FILE_TREE.md）。
依赖方向 scenes -> spectacle；spectacle 反向 import 了 PanelSpec，故只在函数内延迟 import。

SHOTS 直接照 LYRICS_MAP.md §2 的 30 段镜头表建（经 18 帧实测校准），不自行推断。
转场一律 glide：参考片几乎没有硬切（scene score > 0.08 仅 24 次、最大 0.265，
且 18 次挤在 146–162 s 执行段，DESIGN.md §2.5），所以每条 transition 都要写清为什么这样切。
面板标题由 viz id 派生；面板 state 每帧按 t 覆盖。六处 shell 插帧由 composite.SHELL_CMDS 负责
（§2.4）——本文件不再复制一份表，避免两处真相。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache

import config
from theme import Box
@dataclass(frozen=True)
class PanelSpec:
    name: str            # 面板标题，如 "attention head 12/16"
    box: Box             # 该面板的绝对矩形（已含标题栏）
    viz: str             # 交给 tui_engine.draw_visual 的原语 id
    params: dict = field(default_factory=dict)
    state: str = "running"
@dataclass(frozen=True)
class Shot:
    t0: float
    t1: float
    chapter: str
    panels: tuple[PanelSpec, ...]
    lead: str = "both"          # "left" | "right" | "both"
    cover: bool = True          # True 时左栏由聊天窗接管
    transition: str = ""        # 每条转场都要有注释说明为什么这样切
# ---------------------------------------------------------------- 坐标
def _px(v: float) -> int:
    """坐标唯一出口：过 config.scaled()（config 未落地时退化为取整）。"""
    try:
        return int(config.scaled(v))
    except NotImplementedError:
        return int(round(v))
def _mid_boxes(n: int) -> tuple[Box, ...]:
    """中栏裂成 n 块并列：等宽 + GUTTER_INNER_H 间隙；2 块以上用宽变体（DESIGN.md §3.2）。"""
    if n <= 0:
        return ()
    x0, x1 = config.MID_X_WIDE if n >= 2 else config.MID_X
    gap = config.GUTTER_INNER_H
    w = (x1 - x0 - gap * (n - 1)) // n
    return tuple(Box(_px(x0 + i * (w + gap)), _px(config.PANEL_TOP),
                     _px(x0 + i * (w + gap) + w), _px(config.PANEL_BOTTOM)) for i in range(n))
def _mid_box() -> Box:
    """整条中栏——spectacle.override_layout 的 base 参数。"""
    x0, x1 = config.MID_X_WIDE
    return Box(_px(x0), _px(config.PANEL_TOP), _px(x1), _px(config.PANEL_BOTTOM))
@lru_cache(maxsize=1)
def _timeline():
    """装载期读一次时间轴；读不到返回 None，布局照常可算（缓存的是一次性装载结果）。"""
    try:
        import lyrics
        return lyrics.Timeline.load(config.TIMELINE_PATH)
    except Exception:
        return None

def _state_of(t: float) -> str:
    tl = _timeline()
    return tl.state_at(t) if tl is not None else config.STATE_RUNNING

TITLE_OVERRIDE = {"viz_grid_pulse": "pulse / grid", "viz_self_anchor": "self anchor + attempts", "viz_grad_flow": "backprop · ∂L/∂W", "viz_conv_slide": "conv1 · 3×3×32", "viz_feature_stack": "feature maps", "viz_arch_diagram": "LeNet-5 · 1998", "viz_vector_analogy": "word2vec · analogy", "viz_moe_router": "MoE · top-2",
                  "viz_point_set": "point set · N = 1000", "viz_grid_3d": "grid · dims: 3", "viz_circumference": "circle · r = 8.79863", "viz_tangent": "tangent · slope = cos x", "viz_asymptote": "asymptote · lim f = L",
                  "viz_limits": "limits · +∞ / -∞", "viz_current": "current · AC", "viz_rectifier": "rectifier · AC → DC", "viz_vision_mask": "vision · masked", "viz_dizzy": "dizzy · phase off", "viz_timeline": "timeline · traveling"}

def title_of(viz: str) -> str:
    """面板标题由原语 id 派生（每个面板必须自带标题，DESIGN.md §1.1）。"""
    return TITLE_OVERRIDE.get(viz, viz[4:].replace("_", " ") if viz.startswith("viz_") else viz)

# ---------------------------------------------------------------- 镜头表
# 行 = (t0, t1, 章节, 宏大级别, lead, cover, 面板 viz 列表, 转场动机)
# 级别取自 LYRICS_MAP.md §2；level>=1 会作为 params["level"] 注入每个面板。
_PARAM_EXTRA = {95.00: {"shape": "radial"}}                        # 按 t0 键: S20 放射点阵
_SHOT_TABLE: tuple = (
    # S01 开机仪式 · 00 · L0 —— 整屏终端是「从黑场长出界面」的唯一入口，此段中栏不出面板
    (0.00, 10.10, "00", 0, "both", False, (),
     "glide: 整屏终端接管，三栏尚未存在；此处任何切换都会打断通电感"),
    # S02 界面诞生 · 00 · L0 —— 自检结束原地长出中央描边框，同一台机器进入待机，不是换场景
    (10.10, 16.00, "00", 0, "both", True, ("viz_boot_check",),
     "glide: 终端自检 -> 中央描边框成型，同一块界面继续演化"),
    # S03 预训练起手 · 00→01 · L1 —— 器乐起拍，单框展成三块，把「训练开始」做成空间展开
    (16.00, 19.00, "00", 1, "right", True,
     ("viz_embedding_matrix", "viz_pipeline_grid", "viz_loss_curve"),
     "glide: 1 块展成 3 块并列，用面板数表达「训练同时开了三条线」"),
    # S04 器乐段：ML 硬核起手 · 01 · L1 —— 19.0-29.7 **无歌词**，硬核原理放这里才不与唱词打架
    (19.00, 22.00, "01", 1, "right", True, ("viz_grad_flow", "viz_conv_slide", "viz_loss_curve"),
     "glide: 纯器乐段，画 ML 原理不抢唱词；三块同开表达「训练三条线并行」"),
    # S05 器乐段：层内 -> 层间 · 01 · L1
    (22.00, 25.50, "01", 1, "right", True, ("viz_feature_stack", "viz_arch_diagram", "viz_epoch_bars"),
     "glide: 槽位不变只换内容，让「语料在推进」和「结构在收束」同时成立；各 3.5 s"),
    # S06 器乐段收束 · 01 · L1 —— 29.7 歌词进来前把硬核收掉
    (25.50, 29.70, "01", 1, "right", True, ("viz_pipeline_grid", "viz_epoch_bars", "viz_vector_analogy"),
     "glide: 硬核收束成流水线/刻度，给 29.7 起的歌词意象让位"),
    # S07 起逐句接线（task-18）：主槽 = 本句核心意象 + 2 副槽；每行第二行是转场动机；S04-S06 一帧不动。
    (29.70, 31.12, "01", 1, "both", True, ("viz_point_set", "viz_embedding_matrix", "viz_ctx_growth"),
     "glide: If I'm a set of points —— 唱到点就画散落点云；副槽留嵌入矩阵与 n_ctx，密度不掉"),
    (31.12, 33.41, "01", 1, "both", True, ("viz_grid_3d", "viz_pipeline_grid", "viz_embedding_matrix"),
     "glide: my DIMENSION —— 同一批点长出第三根轴，点云被拉成 3D 网格；副槽换流水线格"),
    (33.41, 36.29, "01", 1, "both", True, ("viz_circle_arc", "viz_point_cloud", "viz_vector_analogy"),
     "glide: If I'm a circle —— 圆是这句唯一的意象，给主槽；点云与类比线退副槽承接上一句"),
    (36.29, 37.07, "01", 1, "both", True, ("viz_circumference", "viz_circle_arc", "viz_ctx_growth"),
     "glide: all my CIRCUMFERENCE —— 圆周像弹簧展开成直线，就是「交给你的周长」；0.78 s 短促"),
    (37.07, 38.60, "01", 1, "both", True, ("viz_sine_stack", "viz_circle_arc", "viz_ctx_growth"),
     "glide: If I'm a sine wave —— 正弦从单条长到堆叠；切线意象留给下一句的短线段"),
    (38.60, 40.05, "01", 1, "both", True, ("viz_tangent", "viz_sine_stack", "viz_epoch_bars"),
     "glide: all my TANGENTS —— 切线是正弦的局部：主槽换成随 t 变斜率的切线线段"),
    (40.05, 40.71, "01", 1, "both", True, ("viz_asymptote", "viz_limits", "viz_sine_stack"),
     "glide: If I approach infinity —— 曲线向右无限贴住渐近线；0.66 s，交给下一句的上下界"),
    (40.71, 42.35, "01", 1, "both", True, ("viz_limits", "viz_asymptote", "viz_big_number"),
     "glide: my LIMITATIONS —— 渐近线高亮 + 极值点 + 上下界同框，巨字给落点"),
    (42.35, 44.45, "01", 1, "both", True, ("viz_ctx_growth", "viz_sine_stack", "viz_big_number"),
     "不切: 器乐过渡沿用原有三块（n_ctx / 正弦 / 巨字），给 44.45 s 的电流句留对照"),
    (44.45, 45.85, "01", 1, "right", True, ("viz_current", "viz_dtype_switch", "viz_embedding_matrix"),
     "glide: Switch my current —— 电流脉冲对上 dtype 切换；副槽留格式方块与嵌入矩阵"),
    (45.85, 47.67, "01", 1, "right", True, ("viz_rectifier", "viz_current", "viz_dtype_switch"),
     "glide: To AC to DC —— 正弦被整流成平稳直线；电流退副槽，整流器进主槽"),
    (47.67, 49.53, "02", 1, "left", True, ("viz_vision_mask", "viz_causal_mask", "viz_attn_tri"),
     "glide: then blind my vision —— 中栏被像素块遮蔽；掩码与注意力仍在旁，「看不见未来」互为注解"),
    (49.53, 51.36, "02", 1, "left", True, ("viz_dizzy", "viz_vision_mask", "viz_tsne_avatars"),
     "glide: so dizzy so dizzy —— 相位错位 + 字符抖动；遮蔽与头像阵退副槽，长凝视不靠换框"),
    (51.36, 53.23, "02", 1, "left", True, ("viz_timeline", "viz_ctx_growth", "viz_tsne_avatars"),
     "glide: Oh we can travel —— 时间轴往后滚就是旅行；副槽给 n_ctx 与头像阵"),
    (53.23, 55.08, "02", 1, "left", True, (),
     "glide: To A.D to B.C —— 时间倒流交给 SP 复合镜头；中栏不铺面板让场面接管，双栏 UI 不撤"),
    (55.08, 59.20, "02", 1, "left", True, ("viz_causal_mask", "viz_point_cloud"),
     "glide: 眩晕段收束——掩码常驻 + 点云，一路滚进 59.2 s 副歌（与 S13 同族延续）"),
    # S13 条件承诺 · 03 · L2 —— 副歌起，三块 + 越界，全片第一次「框快装不下」
    (59.20, 70.10, "03", 2, "both", True,
     ("viz_attn_tri", "viz_point_cloud", "viz_prob_bars"),
     "glide: 面板数与透视同时加码，第一次把内容顶到栏外(L2)，框仍在"),
    # S14 被困模拟 · 03 · L0 —— 全片唯一的谷：两块空矩形并列，内容仍是零（第 34 号原语）
    (70.10, 76.00, "03", 0, "left", True, ("viz_void_frame", "viz_void_frame"),
     "glide: 3 块 -> 2 块空矩形；密度回到 2，画面仍空——「空」是 2:28 处决段的参照物(§11.1-3)"),
    # S15 变形请求①茄子 · 04 · L1 —— 04 起左栏回聊天、中栏两槽位；变形用「记录追加」表达
    (76.00, 78.60, "04", 1, "both", True, ("viz_self_anchor", "viz_moe_router"),
     "glide: 回到 2 块常规布局，先把「稳定」还给她，三次变形才有对照"),
    # S16 变形请求②番茄 · 04 · L1 —— 与①同构只多一条记录；重复本身就是「身份固守」的论据
    (78.60, 81.20, "04", 1, "both", True, ("viz_self_anchor", "viz_moe_router"),
     "不切: 同构复现，让观众察觉「她又试了一次」而不是画面变了"),
    # S17 变形请求③花猫 · 04 · L1 —— 第三条记录落定，三次同构才压得住 81.2 s 的结论句
    (81.20, 83.90, "04", 1, "both", True, ("viz_self_anchor", "viz_moe_router"),
     "不切: 三连的最后一次；此刻的「没变化」正是台词要的答案"),
    # S18 收束：我只能是我 · 04 · L1 —— 收成一块并淡出，给结论句一个干净的落点
    (83.90, 85.10, "04", 1, "left", True, ("viz_self_anchor",),
     "glide: 2 块 -> 1 块并停笔，记录定格，把句子交给左栏"),
    # S19 唯一神与切换角色 · 04 · L2 —— dtype 切换方块替她完成「换形态」的陈述
    (85.10, 95.00, "04", 2, "both", True, ("viz_dtype_switch", "viz_memory_grid"),
     "glide: 2 块 + L2 整屏转品红；用格式切换代替「变身」，守住 TUI 形制"),
    # S20 恍惚 · 04 · L2 —— trance 段只留放射点阵，密度交给 f(t) 起伏，不切让观众失焦
    (95.00, 103.50, "04", 2, "both", True, ("viz_point_cloud",),
     "glide: 收成 1 块慢速点阵；持续不切是这一段唯一的表演"),
    # S21 完整 · 04 · L2 —— 波形脉冲接住「震动」，立绘在越界里淡入；完整是叠加出来的
    (103.50, 110.90, "04", 2, "both", True, ("viz_grid_pulse",),
     "glide: 仍是 1 块，只把密度抬上去；「完整」由叠加造成，不由切换造成"),
    # S22 离别 · 04 · L2 —— token 瀑布(SP3)从底栏溢出，中栏回常驻底纹；离别=东西往外流
    (110.90, 118.00, "04", 2, "left", True, ("viz_grid_pulse",),
     "glide: 中栏留底纹不抢戏，113.5 s 的 ping you 只换 header——流失感交给 SP3"),
    # S23 擦除与非法 · 04→06 · L4 —— 进 06 前的长段，合并单表面；全片第一次「框被吃掉」
    (118.00, 135.70, "04", 4, "right", True, ("viz_memory_grid",),
     "glide: 1 块 + L4 单表面；118.5 s 的 ls -la 只换 header，框由 spectacle 接管"),
    # S24 词元洪水 · 06 · L5 —— 单表面 + me 洪水，全片最满的一段；空档无唱词，画面自己顶住
    (135.70, 147.70, "06", 5, "right", True, ("viz_token_flood",),
     "不切: 从 L4 直接续到 L5，满屏本身就是「停不下来」的论据"),
    # S25 处决倒计时 · 07 · L3 —— 巨字越界(SP6)接管；实测 148–156 s 竖线 3/6、161 s 0/6
    (147.70, 161.60, "07", 3, "right", True, ("viz_marquee", "viz_lang_tokens"),
     "glide: 面板数 1->2 配合「向外撑裂->合并」的实测轨迹(3/6 -> 0/6)，仍不硬切"),
    # S26 松手 · 07 · L2 —— 从单表面退回 panel，reward 曲线被拉直(SP8)；松手 = 画面松开
    (161.60, 177.20, "07", 2, "both", True, ("viz_reward_curve",),
     "glide: L4 -> 1 panel，框重新出现；「松手」用布局回退表达"),
    # S27 EVAL 起手 · 08 · L2 —— 冷蓝起色，两槽位给 GRPO；从纯红一次淡出（0.25 s 交叉淡化）
    (177.20, 180.00, "08", 2, "both", True, ("viz_prob_bars", "viz_reward_curve"),
     "glide: 1 块 -> 2 块 + 状态切 outro 冷蓝，换色不换场景"),
    # S28 ELIZA 彩蛋 · 08 · L2 —— 收成一块交给打字机；1966 是一切对话的起点，需要整幅安静
    (180.00, 185.00, "08", 2, "both", True, ("viz_eliza",),
     "glide: 收成 1 块；183.5 s 的 dsh chat 只换 header，让打字机独自说话"),
    # S29 love 洪流 · 08 · L2 —— 溢出但竖线 6/6 全在(实测 3:00/3:06/3:13)，框不许破
    (185.00, 193.80, "08", 2, "both", True, ("viz_love_flow",),
     "glide: 维持 1 块 + L2；内容漫出栏外而框线全在，别把它做成 L4"),
    # S30 星落 · 08→-- · L5 —— 交给 SP10：L2 缓升到 L5 解体，到音乐硬切画面刚好散尽
    (193.80, 206.994, "08", 5, "left", True, ("viz_starfield",),
     "glide: 末段从 L2 长到 L5；t1 取 tl.duration(206.994)，LYRICS_MAP 记 3:26.99"),
)

def _build(table) -> list[Shot]:
    """表 -> Shot 列表：标题由 viz 派生，level 注入 params，state 取 shot 中点。"""
    shots: list[Shot] = []
    for t0, t1, chapter, level, lead, cover, vizzes, reason in table:
        boxes = _mid_boxes(len(vizzes))
        st = _state_of((t0 + t1) / 2.0)
        panels = []
        for i, viz in enumerate(vizzes):
            params = {} if level < 1 else {"level": level}
            params.update(_PARAM_EXTRA.get(t0, {}))
            panels.append(PanelSpec(name=title_of(viz), box=boxes[i], viz=viz,
                                    params=params, state=st))
        shots.append(Shot(float(t0), float(t1), str(chapter), tuple(panels),
                          str(lead), bool(cover), str(reason)))
    return shots

def finalize(shots: list[Shot]) -> tuple[Shot, ...]:
    """断言 shots[0].t0==0、相邻 t1==t0、最后一段覆盖到 tl.duration；不满足抛 ValueError。"""
    if not shots:
        raise ValueError("SHOTS 为空")
    if shots[0].t0 != 0.0:
        raise ValueError("首段 t0 必须为 0，实际 %.3f" % shots[0].t0)
    for a, b in zip(shots, shots[1:]):
        if abs(a.t1 - b.t0) > 1e-6:
            raise ValueError("转场处不接续: %.3f != %.3f" % (a.t1, b.t0))
        if b.t1 <= b.t0:
            raise ValueError("段落时长非正: [%.3f, %.3f)" % (b.t0, b.t1))
    tl = _timeline()
    dur = tl.duration if tl is not None else shots[-1].t1
    if shots[-1].t1 < dur - 1e-6:
        raise ValueError("末段未覆盖片长: 止于 %.3f < %.3f" % (shots[-1].t1, dur))
    return tuple(shots)

_SHOTS: dict = {}
def _shots():
    """镜头表**按 RENDER_SCALE 分别构建**：面板框在构建时就过 _px()，只建一次的话 720p 先跑、4K 复用 1x 的框，画面全挤左上角 1/9。"""
    sc = float(config.RENDER_SCALE or 1.0) or 1.0
    return _SHOTS.setdefault(sc, finalize(_build(_SHOT_TABLE)))

# ---------------------------------------------------------------- 查询
def active_shot(t: float) -> Shot:
    """当前 shot（二分；finalize 已保证首尾相接且覆盖全片）。"""
    sh = _shots()
    if t <= sh[0].t0:
        return sh[0]
    lo, hi = 0, len(sh) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if sh[mid].t0 <= t:
            lo = mid
        else:
            hi = mid - 1
    return sh[lo]

def _spectacle_override(t: float) -> tuple[PanelSpec, ...] | None:
    """L3–L5 时请 spectacle 接管；L0–L2 / 空壳 / 未实现 / 返回 None 都交回本模块。"""
    if not (config.SPECTACLE_ENABLED and config.FX_LAYOUT_BREAK):
        return None
    try:
        import spectacle
    except Exception:
        return None
    fn = getattr(spectacle, "override_layout", None)
    if fn is None:
        return None
    try:
        panels = fn(t, _mid_box())
    except NotImplementedError:
        return None
    return tuple(panels) if panels else None

def _ops_box(t: float):
    """AI 编年史区间 spectacle.ops_box 返回加宽后的 ops 箱；否则 None。"""
    if not (config.SPECTACLE_ENABLED and config.FX_LAYOUT_BREAK):
        return None
    try:
        import spectacle
        return spectacle.ops_box(t)
    except Exception:
        return None

def layout_for(t: float) -> tuple[PanelSpec, ...]:
    """该刻中栏的面板列表（含各自 Box）。**布局唯一入口**。
    L3–L5 宏大场面先问 spectacle.override_layout(t, ...)，由它接管（DESIGN.md §11.2）。
    ops 加宽时（0:19–0:42 AI 编年史），中栏整体线性收窄到 ob.x0 - GUTTER_MID_OPS。"""
    panels = _spectacle_override(t)
    if panels is None:
        panels = active_shot(t).panels
        ob = _ops_box(t)
        if ob is not None and panels:
            # 全程走**原始 720p 量**，最后只 _px 一次。原来 p.box 是已缩放的、mx0 是原始的，
            # 差值被缩放了两次 —— 720p 下 scale=1 看不出，4K 下面板全跑到画布外。
            sc = float(config.RENDER_SCALE or 1.0) or 1.0
            mx0, mx1 = config.MID_X_WIDE
            nx1 = max(mx0 + 80.0, min(mx1, ob.x0 / sc - config.GUTTER_MID_OPS))
            span, nspan = max(1.0, mx1 - mx0), max(1.0, nx1 - mx0)
            panels = tuple(replace(p, box=Box(
                _px(mx0 + (p.box.x0 / sc - mx0) * nspan / span), p.box.y0,
                _px(mx0 + (p.box.x1 / sc - mx0) * nspan / span), p.box.y1)) for p in panels)
    st = _state_of(t)
    if all(p.state == st for p in panels):
        return panels
    return tuple(replace(p, state=st) for p in panels)

def lead_at(t: float) -> str:
    """哪一栏主导这一刻："left"(她说的话) / "right"(她的身体) / "both"。"""
    return active_shot(t).lead

