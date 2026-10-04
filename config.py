"""config.py — 全部常量与开关

职责：工程唯一的常量来源，其他 8 个文件都 import 它。
约束：<= 300 行；纯 Python；所有坐标过 config.scaled()。
本文件为阶段 2 的占位骨架——签名已冻结，见 FILE_TREE.md，改动请先改 FILE_TREE.md。
"""
from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

# 工作区级依赖目录：某些沙箱不让写 C:\...\AppData\Roaming\Python，
# pip install --target 到这里，再由下面挂上 sys.path（见 README「依赖装不上怎么办」）。
_VENDOR = Path(__file__).resolve().parent.parent / "_vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

TODO = "TODO(阶段2): 实现"


# ---------- 画布 ----------
WIDTH: int = 1280
HEIGHT: int = 720
FPS: int = 24
RENDER_SCALE: float = 1.0            # 1.0 = 720p；3.0 = 原生 4K(3840x2160)
PIXELATE_FOR_TERMINAL: bool = False  # True -> 最近邻放大，复刻原片块状硬边

# ---------- 路径 ----------
ROOT: Path = Path(__file__).resolve().parent
# 01 PRETRAIN 的 AI 编年史大字（DESIGN §11 致敬段）：每 2-3 秒抽一条，在中栏展示 2 秒。
AI_BIG_CHRONICLE: tuple[tuple[float, float, str, str, str], ...] = (
    (22.0, 24.0, "1957", "PERCEPTRON", ""), (24.4, 26.0, "1969", "XOR CRITIQUE", "warn"),
    (26.0, 28.0, "1986", "BACKPROP", ""), (30.0, 32.0, "2012", "ALEXNET", ""),
    (34.0, 36.0, "2017", "TRANSFORMER", ""), (38.0, 40.0, "2022", "RLHF", ""))

SONG_PATH: Path = ROOT / "assets" / "audio" / "song.mp3"      # 规范位置
# 兼容候选：把自备音轨按任意一种扩展名放进 assets/audio/ 都能被找到。
# 注意扩展名不代表容器——网易云的 .m4a 可能是 AVS3(av3a) 加密轨，ffmpeg 解不了；
# 用 build.py check 或 resolve_song() 后先 probe 一次再渲染。
SONG_CANDIDATES: tuple[Path, ...] = (
    SONG_PATH,
    ROOT / "assets" / "audio" / "song.m4a",
    ROOT / "assets" / "audio" / "song.aac",
    ROOT / "assets" / "audio" / "song.wav",
    ROOT / "assets" / "audio" / "song.flac",
)


@lru_cache(maxsize=8)
def is_decodable(path: Path) -> bool:
    """真跑一次解码——只读元数据会骗人（网易云的 av3a 加密轨元数据完全正常却解不开）。"""
    try:
        r = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(path),
                            "-t", "1", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def resolve_song() -> Path:
    """优先返回第一个**存在且真的能解码**的候选；若都不行，退回首個非空候选（供报错定位）。"""
    existing = []
    for p in SONG_CANDIDATES:
        try:
            if p.exists() and p.stat().st_size > 0:
                existing.append(p)
        except OSError:
            continue
    for p in existing:
        if is_decodable(p):
            return p
    return existing[0] if existing else SONG_PATH
LYRICS_PATH: Path = ROOT / "assets" / "lyrics" / "lyrics.json"
TIMELINE_PATH: Path = ROOT / "data" / "timeline.json"
OUT_DIR: Path = ROOT / "out"

# ---------- 网格（像素级实测，见 DESIGN.md 3 节）----------
STATUS_BAR: tuple[int, int] = (0, 22)
PANEL_TOP: int = 38
TITLE_BAR: tuple[int, int] = (38, 56)
PANEL_BOTTOM: int = 604
STDOUT_BAR: tuple[int, int] = (616, 680)
COPYRIGHT: tuple[int, int] = (680, 703)
COPYRIGHT_BASELINE: int = 703        # 文字墨迹实测到 y=702，基线取 703
LEFT_X: tuple[int, int] = (24, 384)
MID_X: tuple[int, int] = (404, 1164)
MID_X_WIDE: tuple[int, int] = (404, 1180)
OPS_X: tuple[int, int] = (1180, 1256)
GUTTER_LR: int = 20        # 左栏 -> 中栏（384 -> 404）
GUTTER_MID_OPS: int = 16   # 中栏 -> ops（1164 -> 1180）
GUTTER_INNER_V: int = 20   # 中栏内竖直（760 -> 780）
GUTTER_INNER_H: int = 18   # 中栏内水平（382 -> 400）
OUTER_LEFT: int = 24
OUTER_RIGHT: int = 24
TITLE_BAR_H: int = TITLE_BAR[1] - TITLE_BAR[0]

# ---------- 配色 ----------
PALETTE_SRC: dict[str, str] = {
    "bg": "#070b18", "bg2": "#05080f", "panel": "#1f2b52",
    "panel2": "#2a3350", "panel3": "#18233d",
    "accent": "#4d6bfe", "accent2": "#6b8cff", "accent3": "#9fb3ff",
    "error": "#f85149", "ok": "#3fb950", "grey": "#cfd3d6",
}
PALETTE_FILM: dict[str, str] = {
    "bg": "#050813", "line": "#5a5d68", "text": "#c8d0e0", "dim": "#4a5071",
    "bar_from": "#59628e", "bar_to": "#98b0f4",
    "warn": "#e8d74b", "warn_text": "#b1951f",
    "error": "#f4534c", "error_text": "#a63e41",
    "running_text": "#979dad",
}
STATE_RUNNING: str = "running"
STATE_WARN: str = "warn"
STATE_ERROR: str = "error"
STATE_OUTRO: str = "outro"

# ---------- 内容常量 ----------
FLOOD_TOKEN: str = "me"          # #21 词元洪水重复的 token（DESIGN.md 6 第 21 条）

# ---------- 宏大场面开关（DESIGN.md 11.8）----------
SPECTACLE_ENABLED: bool = True
FX_QUALITY: str = "full"                 # full | half | off（降级按 DESIGN.md 11.7(4) 的优先级）
FX_PARTICLE_ROUTE: str = "point"         # "point"(A，默认) | "sprite"(C)；"rgba" 会被直接拒绝
FX_PARTICLE_BUDGET: int = 2000           # 视觉密度旋钮，不是性能旋钮（实测砍它只省 4%）
FX_SPRITE_CACHE: bool = True             # 字形 sprite 缓存（token 雨提速 5.9x）
FX_TINT_MODE: str = "blend"              # "blend"（等价且快 2x）| "alpha"
FX_TILE_GRID: tuple[int, int] = (8, 20)  # 左栏碎裂的 tile 网格
FX_TILE_GRID_4K: tuple[int, int] = (12, 7)  # 4K 降级档
FX_LAYOUT_BREAK: bool = True             # False 时所有场面被限制在 L2 以内

# ---------- 章节表（QA 逐帧目视实测；05 故意缺席）----------
CHAPTERS: list[tuple[str, str, float, float]] = [
    ("00", "BOOT",        2.0,   19.0),
    ("01", "PRETRAIN",   19.0,   42.0),
    ("02", "SFT",        46.0,   58.9),
    ("03", "RLHF",       59.0,   72.0),
    ("04", "DEPLOY",     76.0,  110.6),
    ("06", "REWARD_HACK",119.3, 147.9),
    ("07", "EXECUTION",  148.0, 175.3),
    ("08", "EVAL: LOVE", 178.0, 193.8),
]


# ---------- 工具 ----------
# ffmpeg 解析顺序（DESIGN.md §8.3 硬约束 1：系统 PATH 那个没有 libx264，禁止使用）
#   1) 环境变量 DSH_FFMPEG / DSH_FFPROBE —— CI 与多机复现用
#   2) imageio-ffmpeg 包（官方推荐路径，随包附 FFmpeg 7.1：libx264/x265/aac/NVENC 全有）
#   3) 工程内已解包的 imageio-ffmpeg 二进制（_ref/ 下的开发副本，不进交付物）
#   4) 报错，并给出可执行的修复命令（绝不静默回落到系统 ffmpeg）
_FFMPEG_HINT = (
    "找不到带 libx264 的 ffmpeg。系统 PATH 里的那个没有 libx264 且有问题的 NVENC，禁止使用。\n"
    "修复：pip install imageio-ffmpeg   （约 3.8 s，随包附 FFmpeg 7.1）\n"
    "   或设置环境变量 DSH_FFMPEG 指向一个 --enable-libx264 的 ffmpeg 可执行文件。"
)
_FFPROBE_HINT = (
    "找不到 ffprobe。ffprobe 只用于探测/校验，不参与编码。\n"
    "修复：设置环境变量 DSH_FFPROBE，或把 ffprobe 放到 ffmpeg 同目录。"
)


def _first_file(*cands: object) -> str | None:
    for c in cands:
        if c and os.path.isfile(str(c)):
            return str(c)
    return None


def ffmpeg_exe() -> str:
    """返回带 libx264 的 ffmpeg 路径。系统 PATH 里的 ffmpeg 没有 libx264，禁止使用。"""
    got = _first_file(os.environ.get("DSH_FFMPEG"))
    if got:
        return got
    try:
        import imageio_ffmpeg  # type: ignore
        got = _first_file(imageio_ffmpeg.get_ffmpeg_exe())
        if got:
            return got
    except Exception:
        pass
    local = sorted(ROOT.glob("_ref/**/imageio_ffmpeg/binaries/ffmpeg-*.exe"))
    got = _first_file(*(str(p) for p in local))
    if got:
        return got
    raise RuntimeError(_FFMPEG_HINT)


def ffprobe_exe() -> str:
    """返回 ffprobe 路径（仅探测/校验用）。"""
    got = _first_file(os.environ.get("DSH_FFPROBE"))
    if got:
        return got
    got = _first_file(*[p for p in (
        r"D:\GPT-SoVITS\GPT-SoVITS-v2pro-20250604\runtime\ffprobe.exe",  # 本机实测可用
        r"C:\ffmpeg\bin\ffprobe.exe", r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
    )])
    if got:
        return got
    try:
        beside = os.path.join(os.path.dirname(ffmpeg_exe()), "ffprobe.exe")
        got = _first_file(beside, beside[:-4])
        if got:
            return got
    except RuntimeError:
        pass
    raise RuntimeError(_FFPROBE_HINT)


def scaled(v: int | float) -> int:
    """按 RENDER_SCALE 缩放像素值。全工程所有坐标都必须过这里。

    读的是模块全局 RENDER_SCALE（不是默认参数快照），所以运行时改 config.RENDER_SCALE
    会立刻生效——build.py 的 720p / 4K 两条路线共用同一套代码。
    """
    return int(round(v * RENDER_SCALE))
