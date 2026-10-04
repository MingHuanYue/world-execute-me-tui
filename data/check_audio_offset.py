# -*- coding: utf-8 -*-
"""片段音轨对齐自检：确认片段的音频取自它对应时刻，而不是从歌曲 0 秒开始。

用法：python data/check_audio_offset.py <clip.mp4> <clip_start_sec> <dur_sec>
"""
import os
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

import config  # noqa: E402


def to_wav(args, dst: str) -> np.ndarray:
    subprocess.run([config.ffmpeg_exe(), "-y", "-v", "error"] + args +
                   ["-ac", "1", "-ar", "8000", dst], check=True)
    with wave.open(dst, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)


def corr(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    if n < 100:
        return 0.0
    a, b = a[:n], b[:n]
    return float(((a - a.mean()) / (a.std() + 1e-9) * (b - b.mean()) / (b.std() + 1e-9)).mean())


def main() -> int:
    clip = sys.argv[1] if len(sys.argv) > 1 else str(config.OUT_DIR / "seg_V_2m40s_2m48s.mp4")
    t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 160.0
    dur = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
    song = str(config.resolve_song())
    tmp = os.path.join(config.OUT_DIR, "_aud")
    os.makedirs(tmp, exist_ok=True)

    a = to_wav(["-ss", "%.6f" % t0, "-t", "%.6f" % dur, "-i", song], os.path.join(tmp, "song_at.wav"))
    b = to_wav(["-i", clip], os.path.join(tmp, "clip.wav"))
    c = to_wav(["-t", "%.6f" % dur, "-i", song], os.path.join(tmp, "song_from0.wav"))

    ca, c0 = corr(a, b), corr(c, b)
    print("片段 %s" % os.path.basename(clip))
    print("  原曲 %.1f-%.1f s 与片段音轨的相关系数 = %+.4f" % (t0, t0 + dur, ca))
    print("  原曲 0 秒起  与片段音轨的相关系数 = %+.4f" % c0)
    print("  判定：%s" % ("片段音频取自对应时刻 —— **对齐**" if ca > c0 and ca > 0.9
                        else "**片段音频仍是从 0 秒开始的**" if c0 > ca else "**两者都不像**"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
