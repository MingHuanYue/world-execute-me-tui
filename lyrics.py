"""lyrics.py — 时间轴加载与查询（唯一时间真相）

职责：读 data/timeline.json；仓库内零歌词文本，文本从外部 lyrics.json 按行号拼。
约束：<= 300 行；纯 Python。
接口：逐字实现 FILE_TREE.md ④（签名改动必须先改 FILE_TREE.md）。

设计要点
- Timeline 只持有时间与结构（行号 / 起止 / 段落 / 章节 / 逐词 id），**不含任何歌词文本**。
- 查询全部走二分：每帧 composite 会打好几次，O(log n) 比 O(n) 稳。
- 「05 缺席」那种状态栏整条空白的时段**不在 state_at 里表达**（它只能返回四个配色状态），
  信号是 chapter_at(t) == ("--", "")（DESIGN.md §2.3 / §2.4）。
"""
from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import config

# 配色状态区间（DESIGN.md §2.3 状态机：全片只换三次色 蓝→黄→红→冷蓝）。
# 区间按起点降序排列，state_at 取第一个命中项。没命中 = running。
STATE_SPANS: tuple[tuple[float, float | None, str], ...] = (
    (178.0, None, config.STATE_OUTRO),      # 178 s 之后：冷蓝 + 星白
    (132.0, 178.0, config.STATE_ERROR),     # Final Chorus + 07 EXECUTION：纯红
    (119.3, 132.0, config.STATE_WARN),      # 奖励黑客前段：黄
    (59.0, 76.0, config.STATE_WARN),        # 03 RLHF 蓝→黄 + Bridge 谷
)

# 外部歌词文件缺失时的中性占位（仓库默认零歌词文本）。
PLACEHOLDER_EN = "line %03d"


@dataclass(frozen=True)
class Word:
    t: float
    end: float
    wid: int


@dataclass(frozen=True)
class Line:
    i: int
    t: float
    end: float
    section: str
    chapter: str
    words: tuple[Word, ...]


class Timeline:
    """data/timeline.json 的内存形态。不可变，可安全跨帧共享。"""

    __slots__ = ("duration", "fps", "bpm", "beats", "chapters", "sections", "lines",
                 "_sec_t", "_line_t")

    duration: float
    fps: int
    bpm: float
    beats: tuple[float, ...]
    chapters: tuple[tuple[str, str, float, float], ...]
    sections: tuple[tuple[str, float, float], ...]
    lines: tuple[Line, ...]

    def __init__(self, duration: float, fps: int, bpm: float,
                 beats: tuple[float, ...],
                 chapters: tuple[tuple[str, str, float, float], ...],
                 sections: tuple[tuple[str, float, float], ...],
                 lines: tuple[Line, ...]) -> None:
        self.duration = float(duration)
        self.fps = int(fps)
        self.bpm = float(bpm)
        self.beats = beats
        self.chapters = chapters
        self.sections = sections
        self.lines = lines
        self._sec_t = tuple(s[1] for s in sections)
        self._line_t = tuple(ln.t for ln in lines)

    # ---------------------------------------------------------------- 装载
    @classmethod
    def load(cls, path: Path) -> "Timeline":
        """读 data/timeline.json。缺文件抛 FileNotFoundError。"""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(str(p))
        with p.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        meta = raw.get("meta") or {}
        beats = tuple(sorted(float(b) for b in (raw.get("beats") or ())))
        chapters = tuple(
            (str(c["code"]), str(c["name"]), float(c["start"]), float(c["end"]))
            for c in (raw.get("chapters") or ()))
        sections = tuple(
            (str(s["name"]), float(s["start"]), float(s["end"]))
            for s in (raw.get("sections") or ()))
        lines = []
        for item in (raw.get("lines") or ()):
            words = tuple(Word(float(w["t"]), float(w["end"]), int(w["wid"]))
                          for w in (item.get("words") or ()))
            lines.append(Line(int(item["i"]), float(item["t"]), float(item["end"]),
                              str(item.get("section") or ""),
                              str(item.get("chapter") or ""), words))
        lines.sort(key=lambda ln: ln.t)
        return cls(float(meta.get("duration") or 0.0), int(meta.get("fps") or config.FPS),
                   float(meta.get("bpm") or 0.0), beats, chapters, sections, tuple(lines))

    # ---------------------------------------------------------------- 查询
    def section_at(self, t: float) -> str:
        """音乐结构段名（15 段）。片头片尾落到首/末段。"""
        for name, a, b in self.sections:
            if a <= t < b:
                return name
        if not self.sections:
            return ""
        return self.sections[0][0] if t < self.sections[0][1] else self.sections[-1][0]

    def chapter_at(self, t: float) -> tuple[str, str]:
        """(code, name)。无章节区段（含 05 缺席的 110.6–119.3）返回 ("--", "")。"""
        for code, name, a, b in self.chapters:
            if a <= t < b:
                return (code, name)
        return ("--", "")

    def state_at(self, t: float) -> str:
        """映射到配色状态：running / warn / error / outro。"""
        for a, b, st in STATE_SPANS:
            if t >= a and (b is None or t < b):
                return st
        return config.STATE_RUNNING

    def line_at(self, t: float) -> Line | None:
        """当前正在显示的那一句；落在句间空档时返回 None。"""
        k = self._containing_index(t)
        return self.lines[k] if k >= 0 else None

    def line_index_at(self, t: float) -> int:
        """给底栏 token 条用的行号：句间空档时**保留上一句**（拖进度条也不会空屏）。"""
        n = len(self.lines)
        if n == 0:
            return -1
        k = bisect_right(self._line_t, t) - 1
        return 0 if k < 0 else (n - 1 if k >= n else k)

    def active_word_ids(self, t: float) -> list[int]:
        """当前已点亮的 token id 列表（只返回 id，不含文本）。"""
        k = self.line_index_at(t)
        if k < 0:
            return []
        return [w.wid for w in self.lines[k].words if w.t <= t]

    def beat_index(self, t: float) -> int:
        """最后一个已到的拍号；无拍点返回 -1。"""
        if not self.beats:
            return -1
        k = bisect_right(self.beats, t) - 1
        return 0 if k < 0 else (len(self.beats) - 1 if k >= len(self.beats) else k)

    def progress(self, t: float) -> float:
        if self.duration <= 0.0:
            return 0.0
        return 0.0 if t <= 0.0 else (1.0 if t >= self.duration else t / self.duration)

    # ---------------------------------------------------------------- 内部
    def _containing_index(self, t: float) -> int:
        k = bisect_right(self._line_t, t) - 1
        if k < 0 or k >= len(self.lines):
            return -1
        return k if t < self.lines[k].end else -1


def load_lyric_text(path: Path, count: int) -> list[tuple[str, str]]:
    """读 assets/lyrics/lyrics.json -> [(en, zh)]。
    文件缺失或 lines 为空时返回 count 条中性占位——仓库默认零歌词文本。"""
    items: list = []
    try:
        with Path(path).open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            items = list(raw.get("lines") or [])
        elif isinstance(raw, list):
            items = list(raw)
    except (OSError, ValueError):
        items = []
    out: list[tuple[str, str]] = []
    for item in items[:max(0, count)]:
        if isinstance(item, dict):
            out.append((str(item.get("en") or ""), str(item.get("zh") or "")))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append((str(item[0]), str(item[1])))
        else:
            out.append(("", ""))
    while len(out) < count:                      # 不足的用中性占位补齐
        out.append((PLACEHOLDER_EN % len(out), ""))
    return out[:count]
