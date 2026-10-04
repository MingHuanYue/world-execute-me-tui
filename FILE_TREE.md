# FILE_TREE.md — 工程结构与接口契约（阶段 1 定稿）

> 本文件是**接口合同**。阶段 2 的多个开发角色按它并行写码，**任何签名的改动都要先改这里**。
> 约束：全部纯 Python（零 Node 依赖），**12 个文件**，**每个文件 ≤ 300 行**，函数签名与下面逐字一致。
> （阶段 1.6：33 个可视化原语**塞不进一个 300 行的文件**，故从 `tui_engine.py` 拆出 `tui_viz.py`。
> 这是对"6–10 个文件"的一次有意破例——**宁可多一个文件，也不要 9 行一个的糊弄函数**。）
> （阶段 1.5 追加：`spectacle.py` —— 宏大场面专用，见 DESIGN.md §11。）

---

## 0. 目录树

```
world-execute-me-tui/
├── build.py                     # ① CLI 入口
├── config.py                    # ② 全部常量与开关
├── theme.py                     # ③ 配色 / 字体 / 绘图原语
├── lyrics.py                    # ④ 时间轴加载与查询（唯一时间真相）
├── scenes.py                    # ⑤ 镜头表与布局求解
├── chat_pages.py                # ⑥ 左栏：聊天窗 + 底栏 token 条
├── tui_engine.py                # ⑦ 注册表 / 分发 / ops + 原语 1–17
├── tui_viz.py                   # ⑪ 原语 18–34（含 AI 历史纵深 27–34）
├── avatar.py                    # ⑫ SP0 自我成形：左栏头像 图标→鲸鱼娘（DESIGN §11.9）
├── spectacle.py                  # ⑩ 宏大场面（L1–L5）：透视/粒子/星系/越界合成
├── composite.py                 # ⑧ 整帧骨架合成
├── render.py                    # ⑨ 帧循环 / 音频时钟 / 编码
├── data/
│   └── timeline.json            # 生成物：只有时间戳与结构，无歌词文本
├── assets/
│   ├── audio/song.mp3           # 留空，主人自备
│   └── lyrics/lyrics.json       # 留空，主人自备（唯一歌词文本来源）
├── docs/                        # DESIGN.md 等设计文档
├── out/                         # film.mp4 / film_master.mp4 / film_4k.mp4
└── _ref/                        # 分析素材，不进交付物
```

---

## 1. 数据流（谁调谁）

```
build.py
  └─ lyrics.Timeline.load(data/timeline.json)      <- 时间真相（无文本）
        └─ render.render_range(tl, t0, t1)
              └─ composite.compose_frame(t, tl)    <- 纯函数 f(t)
                    ├─ scenes.layout_for(t)        -> 该刻的 PanelSpec 列表
                    │     └─ spectacle.override_layout(t, ...)   越界时接管布局（L3–L5）
                    ├─ chat_pages.draw_chat(...)       左栏
                    ├─ chat_pages.draw_stdout(...)     底栏
                    ├─ tui_engine.draw_visual(...)     中栏 26 原语
                    ├─ tui_engine.draw_ops(...)        右栏 ops 滚动
                    ├─ spectacle.compose(...)          宏大场面叠加（粒子/透视/碎裂）
                    └─ theme.*                     框线/字体/配色
        └─ render.encode(...)  ->  ffmpeg rawvideo 管道  ->  out/*.mp4
```

**铁律**：`compose_frame(t, tl)` 必须是 `t` 的纯函数——**不许持有任何跨帧状态**。差分刷新只是渲染层的缓存优化，语义上每一帧都从零算。

---

## 2. 逐文件契约

### ① `build.py` — CLI 入口（≈150 行）

```python
def cmd_check() -> int:
    """自检：音频是否存在且可解码 / timeline.json 是否合法 / 字体是否可用 /
       ffmpeg 是否有 libx264 / out 目录是否可写。任何一项失败返回非 0。"""

def cmd_lyrics() -> int:
    """从 data/timeline.json 反查行数，校验 assets/lyrics/lyrics.json 的行数是否匹配；
       缺失时提示用占位生成（绝不内置真实歌词）。"""

def cmd_frames(t0: float = 0.0, t1: float | None = None) -> int:
    """只出帧不编码，落 out/frames/%06d.png，用于肉眼抽查。"""

def cmd_render(scale: float = 1.0, pixelate: bool = False,
               t0: float = 0.0, t1: float | None = None,
               codec: str = "libx264", jobs: int = 0) -> int:
    """主渲染。scale=1.0 -> out/film.mp4；scale=3.0 -> out/film_4k.mp4。"""

def cmd_all(scale: float, pixelate: bool) -> int:
    """check -> lyrics -> render 串起来跑。"""

def main(argv: list[str] | None = None) -> int:
    """子命令 check|lyrics|frames|render|all；参数 --4k --pixelate --range T0:T1 --codec --jobs。"""
```

### ② `config.py` — 全部常量与开关（≈130 行）

```python
# --- 画布 ---
WIDTH: int = 1280
HEIGHT: int = 720
FPS: int = 24
RENDER_SCALE: float = 1.0            # 1.0 = 720p；3.0 = 原生 4K（3840x2160）
PIXELATE_FOR_TERMINAL: bool = False  # True -> 最近邻放大，复刻原片块状硬边

# --- 路径 ---
ROOT: Path
SONG_PATH: Path          # assets/audio/song.mp3
LYRICS_PATH: Path        # assets/lyrics/lyrics.json
TIMELINE_PATH: Path      # data/timeline.json
OUT_DIR: Path            # out/

# --- 网格（像素级实测，见 DESIGN.md §3）---
STATUS_BAR:   tuple[int, int] = (0, 22)
PANEL_TOP:    int = 38
TITLE_BAR:    tuple[int, int] = (38, 56)
PANEL_BOTTOM: int = 604
STDOUT_BAR:   tuple[int, int] = (616, 680)
COPYRIGHT:    tuple[int, int] = (680, 703)
COPYRIGHT_BASELINE: int = 703      # 文字墨迹实测到 y=702，基线取 703
LEFT_X:    tuple[int, int] = (24, 384)
MID_X:     tuple[int, int] = (404, 1164)   # 默认
MID_X_WIDE: tuple[int, int] = (404, 1180)  # 多面板镜头变体
OPS_X:     tuple[int, int] = (1180, 1256)
GUTTER_LR: int = 20        # 左栏 -> 中栏（384 -> 404）
GUTTER_MID_OPS: int = 16   # 中栏 -> ops（1164 -> 1180）
GUTTER_INNER_V: int = 20   # 中栏内竖直（760 -> 780）
GUTTER_INNER_H: int = 18   # 中栏内水平（382 -> 400）
OUTER_LEFT: int = 24
OUTER_RIGHT: int = 24

# --- 配色 ---
PALETTE_SRC: dict[str, str]    # 源码权威值（参考仓库）
PALETTE_FILM: dict[str, str]   # B站转码后实测值（默认用这套）
STATE_RUNNING, STATE_WARN, STATE_ERROR, STATE_OUTRO: str

# --- 章节表（QA 逐帧目视实测）---
CHAPTERS: list[tuple[str, str, float, float]]   # (code, name, start, end)

# --- 工具 ---
def ffmpeg_exe() -> str:
    """imageio_ffmpeg.get_ffmpeg_exe()。系统 ffmpeg 没有 libx264，禁止使用。"""
def ffprobe_exe() -> str: ...
def scaled(v: int | float) -> int:
    """按 RENDER_SCALE 缩放像素值。全工程所有坐标都必须过这个函数。"""
```

### ③ `theme.py` — 配色 / 字体 / 绘图原语（≈230 行）

```python
@dataclass(frozen=True)
class Box:
    x0: int; y0: int; x1: int; y1: int
    def inset(self, dx: int, dy: int = 0) -> "Box": ...
    def width(self) -> int: ...
    def height(self) -> int: ...

@dataclass(frozen=True)
class Palette:
    bg: str; line: str; text: str; dim: str; accent: str; accent_dim: str
    warn: str; error: str; ok: str; highlight: str

# 四套状态调色板常量（由 config 原始色值组装）
PALETTE_RUNNING: dict; PALETTE_WARN: dict; PALETTE_ERROR: dict; PALETTE_OUTRO: dict

def palette_for(state: str) -> Palette:
    """state in {running, warn, error, outro}；未知值抛 ValueError。"""

def font_mono(size: int) -> ImageFont.FreeTypeFont: ...
def font_cjk(size: int) -> ImageFont.FreeTypeFont: ...
def font_title(size: int) -> ImageFont.FreeTypeFont: ...

def text_width(text: str, f) -> int: ...
def draw_text(d, xy: tuple[int, int], text: str, f, fill: str,
              scale: float = 1.0, anchor: str = "la") -> None:
    """中英混排：内部按字符区间自动切换 font_mono / font_cjk。"""

def draw_frame_box(d, box: Box, title: str | None, pal: Palette, s: float = 1.0) -> Box:
    """画面板外框 + 左上角标题栏。返回去掉标题栏后的内容区 Box。"""

def draw_bar(d, box: Box, frac: float, color: str, s: float = 1.0) -> None: ...
def draw_grid_bg(d, box: Box, pal: Palette, step: int = 16, s: float = 1.0) -> None: ...

# --- 宏大场面用原语（DESIGN.md §11.5）---
def hash01(i: int, salt: int = 0) -> float:
    """确定性伪随机，纯函数。粒子系统的唯一随机源。"""
def particle_points(d, pts: Sequence[tuple[float, float, float]], pal: Palette, s: float) -> None:
    """pts = (x, y, alpha)。画 1px 点，最快的一条粒子路线。"""
def perspective_grid(d, box: Box, cols: int, rows: int, horizon: float,
                     depth: float, pal: Palette, phase: float, s: float) -> None:
    """逐行缩放 + 行偏移模拟透视；不引入 3D 引擎。"""
def sprite_cache(text: str, sizes: Sequence[int], color: str) -> dict[int, Image.Image]:
    """预渲染字形 sprite（巨字 / token 雨 / love 洪流都靠它）。"""
def paste_sprite(img: Image.Image, sp: Image.Image, xy: tuple[int, int], alpha: float) -> None:
    """带 mask 贴图，比每帧 draw_text 快一个量级。"""
def draw_glow_text(d, xy, text, f, color: str, radius: int = 3) -> None: ...
```

### ④ `lyrics.py` — 时间轴加载与查询（≈180 行）

```python
@dataclass(frozen=True)
class Word:
    t: float; end: float; wid: int

@dataclass(frozen=True)
class Line:
    i: int; t: float; end: float
    section: str; chapter: str; words: tuple[Word, ...]

class Timeline:
    duration: float; fps: int; bpm: float
    beats: tuple[float, ...]
    chapters: tuple[tuple[str, str, float, float], ...]
    sections: tuple[tuple[str, float, float], ...]
    lines: tuple[Line, ...]

    @classmethod
    def load(cls, path: Path) -> "Timeline":
        """读 data/timeline.json。不含任何歌词文本。缺文件抛 FileNotFoundError。"""

    def section_at(self, t: float) -> str: ...
    def chapter_at(self, t: float) -> tuple[str, str]:
        """无章节区段返回 ("--", "")。"""
    def state_at(self, t: float) -> str:
        """映射到配色状态：running / warn / error / outro。"""
    def line_at(self, t: float) -> Line | None: ...
    def line_index_at(self, t: float) -> int: ...
    def active_word_ids(self, t: float) -> list[int]:
        """当前已点亮的 token id 列表（只返回 id，不含文本）。"""
    def beat_index(self, t: float) -> int: ...
    def progress(self, t: float) -> float: ...

def load_lyric_text(path: Path, count: int) -> list[tuple[str, str]]:
    """读 assets/lyrics/lyrics.json -> [(en, zh)]。
       文件缺失或 lines 为空时返回 count 条中性占位——仓库默认零歌词文本。"""
```

### ⑤ `scenes.py` — 镜头表与布局求解（≈260 行）

```python
@dataclass(frozen=True)
class PanelSpec:
    name: str            # 面板标题，如 "attention head 12/16"
    box: Box             # 该面板的绝对矩形（已含标题栏）
    viz: str             # 交给 tui_engine.draw_visual 的原语 id
    params: dict         # 原语参数
    state: str           # running / warn / error / outro

@dataclass(frozen=True)
class Shot:
    t0: float; t1: float
    chapter: str
    panels: tuple[PanelSpec, ...]   # 中栏裂块方案（1~3 块）
    lead: str                       # "left" | "right" | "both"
    cover: bool                     # True 时左栏由聊天窗接管
    transition: str                 # 每条必须有注释说明为什么这样切

SHOTS: tuple[Shot, ...]             # 装载期 finalize() 断言首尾相接且覆盖全片

def finalize(shots: list[Shot]) -> tuple[Shot, ...]:
    """断言 shots[0].t0==0、相邻 t1==t0、最后一段覆盖到 tl.duration；不满足抛 ValueError。"""

def active_shot(t: float) -> Shot: ...
def layout_for(t: float) -> tuple[PanelSpec, ...]:
    """返回该刻中栏的面板列表（含各自 Box）。**这是布局唯一入口**。
       L3–L5 宏大场面时，内部先问 spectacle.override_layout(t, ...)，由它接管（DESIGN.md §11.2）。"""
def lead_at(t: float) -> str: ...
```

### ⑥ `chat_pages.py` — 左栏 + 底栏（≈280 行）

```python
def draw_chat(d, box: Box, tl: Timeline, t: float,
              pal: Palette, texts: list[tuple[str, str]], s: float = 1.0) -> None:
    """左栏：头像 + 昵称/状态副标题 + 消息流 + 工具事件行 + 操作图标行 +
       输入框 + 统计行。所有内容随 t 演化。"""

def draw_stdout_tokens(d, box: Box, tl: Timeline, t: float,
                       pal: Palette, s: float = 1.0,
                       texts: list[tuple[str, str]] | None = None) -> None:
    """底栏：提示符 + 当前歌词行切成 token 逐个点亮，每 token 下方标 token id。
       texts 为外部歌词文本（load_lyric_text 的产物）；不传时退化为 id 占位 chip。"""

def draw_avatar(d, box: Box, t: float, pal: Palette, s: float = 1.0) -> None:
    """头像随章节/状态换形态与色相（由 t 与 pal 决定，不要静态贴图）。"""
```

### ⑦ `tui_engine.py` — 注册表 / 分发 / 右栏 ops + 原语 1–17（≤300 行）

```python
VIZ: dict[str, Callable]              # 原语注册表：id -> 函数

def draw_visual(d, spec: PanelSpec, tl: Timeline, t: float, s: float = 1.0) -> None:
    """按 spec.viz 分发。找不到抛 KeyError。"""

OPS_LOGS: dict[str, tuple[tuple[str, str], ...]]
    # 日志表：{"opcodes": (...), "ai_chronicle": (...)}。
    # ai_chronicle 是 1957 PERCEPTRON / 1969 XOR CRITIQUE(WARN) / … 那条 AI 编年史（DESIGN.md 6.1）。

def draw_ops(d, box: Box, tl: Timeline, t: float, pal: Palette,
             s: float = 1.0, params: dict | None = None) -> None:
    """右栏：日志条目持续滚动，当前条目高亮（正常白底 / WARN 黄 / ERROR 红）。
       params={"log": "opcodes"|"ai_chronicle"} 选择日志表；缺省 opcodes。"""

# --- 原语 1-17（结构类：自检 / 曲线 / 矩阵 / 流水线 / 点云 / 表盘 / 波 / 掩码）---
viz_boot_check · viz_loss_curve · viz_pipeline_grid · viz_embedding_matrix
viz_point_cloud · viz_dials · viz_sine_stack · viz_ctx_growth
viz_epoch_bars · viz_recursive_tiles · viz_tsne_avatars · viz_ascii_art
viz_big_number · viz_attn_tri · viz_prob_bars · viz_reward_curve
viz_causal_mask

def register(mod) -> None:
    """把 tui_viz 里的原语登记进 VIZ（import 时调用一次）。"""
```

### ⑧ `composite.py` — 整帧骨架（≈220 行）

```python
def compose_frame(t: float, tl: Timeline,
                  texts: list[tuple[str, str]] | None = None,
                  scale: float | None = None,
                  pixelate: bool = False) -> Image.Image:
    """纯函数 f(t)。固定顺序（不得调换，DESIGN.md §7.3）：
       背景 -> 网格底纹 -> 状态栏 -> 左栏 -> 中栏 panels -> ops -> stdout 条 -> 版权条
       -> spectacle.compose(t)（宏大场面叠加 L1–L5）。
       **后期（残影/扫描线/渐晕）不在这里做** —— 由 composite.apply_post 单独提供、
       render.py 每帧调用（残影需要 prev，跨帧状态只允许存在于 render.py）。
       返回 RGB Image，尺寸 = (WIDTH*scale, HEIGHT*scale)。"""

def draw_status_bar(d, tl: Timeline, t: float, pal: Palette, s: float = 1.0) -> None:
    """片名 + 提示符 + 音频频谱条 + 章节 + 时码 + 状态字。
       6 处 shell 命令插帧也在这里处理（顶栏换成一行命令，UI 不撤销）。"""

def draw_copyright(d, pal: Palette, s: float = 1.0) -> None: ...
def apply_post(img: Image.Image, t: float, pal: Palette,
               prev: Image.Image | None = None) -> Image.Image:
    """残影 / 辉光 / 扫描线 / 渐晕。prev 由 render.py 持有并传入——
       这是整个工程唯一允许的跨帧状态。"""
def finalize_frame(img: Image.Image, pixelate: bool) -> Image.Image:
    """PIXELATE_FOR_TERMINAL=True 时的最近邻放大。"""
```

### ⑨ `render.py` — 帧循环 / 音频时钟 / 编码（≈200 行）

```python
def probe_duration(audio: Path) -> float: ...

def iter_frames(tl: Timeline, t0: float, t1: float,
                texts: list[tuple[str, str]] | None = None,
                scale: float = 1.0, pixelate: bool = False
                ) -> Iterator[tuple[int, Image.Image]]:
    """产出 (frame_index, image)。frame_index = round(t * FPS)。无跨帧状态。"""

def encode(out_path: Path, tl: Timeline, t0: float, t1: float, audio: Path,
           texts=None, scale: float = 1.0, pixelate: bool = False,
           codec: str = "libx264", jobs: int = 0) -> None:
    """Pillow -> rawvideo 管道 -> ffmpeg。不要落 PNG 序列。
       无损母版 libx264rgb -qp 0；发布版转 BT.709 yuv420p。"""
```

### ⑩ `spectacle.py` — 宏大场面（≤300 行）

**职责**：L1–L5 的越界合成。它**可以**让画面突破三栏，但**不允许**换字体、换配色、换框线形制（DESIGN.md §11.1）。

```python
@dataclass(frozen=True)
class SetPiece:
    name: str                 # 如 "注意力俯冲"
    sp: str                   # 代号 "SP1".."SP10"
    t0: float; t1: float
    level: int                # 1..5，见 DESIGN.md §11.2
    breaks_layout: bool       # True 时由本模块接管布局
    elements: tuple[str, ...] # 用到的元素（透视网格 / 粒子 / 星系 / token 雨 / 碎裂 ...）
    composer: str             # 查 COMPOSERS

SET_PIECES: tuple[SetPiece, ...]
COMPOSERS: dict[str, Callable]        # composer 名 -> 函数

def finalize(pieces: list[SetPiece], duration: float) -> tuple[SetPiece, ...]:
    """断言：t0/t1 递增不重叠、覆盖 [0, duration]、level 曲线首尾为 0。不满足抛 ValueError。"""

def active(t: float) -> SetPiece | None:
    """当前生效的场面；无则 None。"""

def level_at(t: float) -> int:
    """当前越界级别 0–5（给测试与调试用）。"""

def layout_mode(t: float) -> str:
    """"three_col" | "three_col_open" | "merged" | "single"。"""

def override_layout(t: float, base: Box) -> list[PanelSpec] | None:
    """L3–L5 时返回接管后的面板列表；L0–L2 返回 None（用 scenes 的默认布局）。"""

def ops_box(t: float) -> Box | None:
    """AI 编年史区间（0:19–0:42.5）把 ops 栏加宽到 Box(1000,38,1256,604)；其余返回 None。
       composite._draw_ops 用它替换 config.OPS_X；scenes.layout_for 据此把中栏 x1 收到 ob.x0-16。"""

def keeps_left(t: float) -> bool:
    """SP10 星落消解返回 True —— 左栏必须先画出来，tile 才有内容可散（否则散的是空背景）。
       其余合并场面仍由 composite 跳过左栏。"""

def compose(d, img: Image.Image, tl: Timeline, t: float,
            pal: Palette, s: float = 1.0) -> None:
    """在主骨架画完后叠加场面。**必须是 f(t) 的纯函数**（§11.6）。"""

# --- 10 个场面 composer，统一签名 (d, img, box, tl, t, pal, s) ---
fx_attention_dive · fx_galaxy · fx_token_waterfall · fx_frame_rupture · fx_token_flood
fx_marquee_breakout · fx_execution_surface · fx_reward_straighten · fx_love_torrent · fx_stellar_dissolve

def particle(i: int, t: float, kw: dict) -> tuple[float, float, float]:
    """第 i 个粒子在 t 的 (x, y, alpha)。只依赖 theme.hash01(i, salt)，不读历史。"""
```



### ⑪ `tui_viz.py` — 原语 18–33（≤300 行）

与 ⑦ 同一套签名，由 `tui_engine.VIZ` 注册（自带 `register()` 由 `tui_engine` import 时调用）。

```python
# --- 18-26（表现类：格式切换 / 残影 / 格子 / 洪水 / 巨字 / 词元 / 洪流 / 星空 / 脉冲）---
viz_dtype_switch · viz_ocr_ghost · viz_memory_grid · viz_token_flood
viz_marquee · viz_lang_tokens · viz_love_flow · viz_starfield · viz_grid_pulse

# --- 27-33（AI 历史纵深，DESIGN.md 6.1）---
viz_conv_slide      # 27 CNN 3x3 滑窗 + 6 个卷积核响应条（输入为 8x8 像素块拼的 "ME"）
viz_feature_stack   # 28 三层特征图 32x32 -> 16x16 -> 8x8，亮度 1.0 / 0.62 / 0.38
viz_grad_flow       # 29 反向传播：前向蓝 + 反向红，权重更新时节点闪白
viz_arch_diagram    # 30 LeNet-5 七层结构图 + params/flops/year 滚动
viz_vector_analogy  # 31 Word2Vec：点云 + king-man+woman=queen 三连线 + 终点高亮
viz_moe_router      # 32 MoE：8 专家 + router -> top-2 + 专家负载百分比
viz_eliza           # 33 ELIZA 对话回放：打字机逐行 + 光标闪烁 + 年份刻度
viz_void_frame      # 34 空框：Bridge 的"谷"——只画一个空矩形 + 一行小标题，其余什么都不画

# 内容数据（不是常量，别放 config）
RI_GALLERY: ...     # 8x8 像素块字形表（至少 "ME"）
LENET5_LAYERS: ...  # [(name, w, h, depth), ...] 七层
AI_CHRONICLE: ...   # 见 tui_engine.OPS_LOGS["ai_chronicle"]
ELIZA_SCRIPT: ...   # 三行对话 + 打字机时间表
```

---

## 3. 并行开发分工建议（阶段 2）

| 角色 | 负责文件 | 依赖 |
|---|---|---|
| 开发 A | `config.py` + `theme.py` | 无（最先冻结） |
| 开发 B | `lyrics.py` + `scenes.py` | A 的常量名 |
| 开发 C | `chat_pages.py` + `composite.py` | A + B |
| 开发 D | `tui_engine.py`（注册表 / 分发 / ops + 原语 1–17） | A |
| 开发 F | `tui_viz.py`（原语 18–33，其中 27–33 是 AI 历史纵深） | A |
| 开发 E | `spectacle.py`（10 个场面，可按 SP1–SP5 / SP6–SP10 再拆两组） | A 的常量名 + DESIGN.md §11 |
| 集成 | `render.py` + `build.py` | 全部 |

**写码前先冻结 `config.py` 与 `theme.py` 的签名**——其余七个文件都依赖它们。

---

## 4. 硬约束（写码时必须守住）

1. **每文件 ≤ 300 行**；`build.py check` 里加一条行数断言。
2. **纯 Python**：不许 import playwright / node / selenium。
3. **ffmpeg 只用** `config.ffmpeg_exe()`（imageio-ffmpeg 7.1）；**禁止**调用系统 PATH 里的 ffmpeg。
4. **所有坐标都过** `config.scaled()`，保证分辨率无关。
5. **不落 PNG 序列**：走 rawvideo 管道。
6. `compose_frame` 保持纯函数；差分刷新只能出现在 `render.py` 的缓存层。
7. **仓库内零歌词文本**：`assets/lyrics/lyrics.json` 默认空，`lyrics.load_lyric_text` 会补中性占位。
8. **宏大场面必须无状态**：粒子位置一律 `f(i, t)` + 确定性哈希（`theme.hash01`），**禁止累积状态**（DESIGN.md §11.6）。
9. **单帧只允许启用一个场面**：`build.py check` 里加断言；`config.FX_QUALITY` 支持 `full|half|off` 降级。
