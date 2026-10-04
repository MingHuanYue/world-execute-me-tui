"""render.py — 帧循环 / 音频时钟 / 编码

职责：把 composite.compose_frame 的纯函数帧喂给 ffmpeg rawvideo 管道。
约束：<= 300 行；不落 PNG 序列；ffmpeg 只用 config.ffmpeg_exe()（imageio-ffmpeg 7.1）。
      跨帧状态只允许存在于本文件（CRT 残影的 prev）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterator

from PIL import Image

import config
from composite import compose_frame, finalize_frame, apply_post
from lyrics import Timeline, load_lyric_text
from theme import palette_for


def probe_duration(audio: Path) -> float:
    """用 ffprobe 读音频时长（秒）。失败抛 RuntimeError。"""
    if not Path(audio).exists() or Path(audio).stat().st_size == 0:
        raise RuntimeError("音频不存在或为空: %s" % audio)
    cmd = [config.ffprobe_exe(), "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(audio)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("ffprobe 失败: " + (out.stderr or "")[-300:])
    try:
        return float(out.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("ffprobe 返回值无法解析: %r" % out.stdout) from exc


def frame_count(t0: float, t1: float) -> int:
    return max(0, int(round(t1 * config.FPS)) - int(round(t0 * config.FPS)))


def iter_frames(tl: Timeline, t0: float, t1: float,
                texts: list[tuple[str, str]] | None = None,
                scale: float = 1.0, pixelate: bool = False
                ) -> Iterator[tuple[int, Image.Image]]:
    """产出 (frame_index, image)，frame_index = round(t * FPS)。

    音频时钟原则：帧号是唯一的权威时间，t 由帧号反算，保证任意分段渲染结果一致。
    跨帧的 prev 只用于 apply_post 的残影，不参与几何与布局。
    """
    config.RENDER_SCALE = scale          # 根因：所有坐标都过 config.scaled()，必须在这里设
    i0 = int(round(t0 * config.FPS))
    i1 = int(round(t1 * config.FPS))
    prev: Image.Image | None = None
    for idx in range(i0, i1):
        t = idx / config.FPS
        img = compose_frame(t, tl, texts=texts, scale=scale, pixelate=pixelate)
        img = apply_post(img, t, palette_for(tl.state_at(t)), prev)
        if tl.state_at(t) != "outro":          # 结尾星空段不做残影，避免糊成一团
            prev = img
        yield idx, img


def encode(out_path: Path, tl: Timeline, t0: float, t1: float, audio: Path,
           texts: list[tuple[str, str]] | None = None,
           scale: float = 1.0, pixelate: bool = False,
           codec: str = "libx264", jobs: int = 0) -> None:
    """Pillow -> rawvideo 管道 -> ffmpeg。无损母版用 libx264rgb -qp 0，发布版转 BT.709 yuv420p。"""
    config.RENDER_SCALE = scale          # 同上：4K 时若不同步，画面会缩在左上角 1/9
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    w = int(round(config.WIDTH * scale))
    h = int(round(config.HEIGHT * scale))

    cmd = [config.ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
           "-r", str(config.FPS), "-i", "pipe:0"]
    has_audio = Path(audio).exists() and Path(audio).stat().st_size > 0
    if has_audio:
        # **必须 -ss t0**：否则分段片段的音频从歌曲 0 秒开始（全片 t0=0 时看不出问题）。
        # 放在 -i 之前是 input seek，FFmpeg 7.x 对音频是样本级精确的。
        cmd += ["-ss", "%.6f" % t0, "-i", str(audio)]
    if codec == "libx264rgb":
        cmd += ["-c:v", "libx264rgb", "-preset", "veryfast", "-qp", "0", "-pix_fmt", "rgb24"]
    elif codec == "h264_nvenc":
        cmd += ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-colorspace", "bt709",
                "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-movflags", "+faststart", str(out_path)]

    n = frame_count(t0, t1)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    done = 0
    try:
        for _, img in iter_frames(tl, t0, t1, texts=texts, scale=scale, pixelate=pixelate):
            proc.stdin.write(img.tobytes())
            done += 1
            if done % 48 == 0:
                print("  %d/%d 帧 (%.1f%%)" % (done, n, 100.0 * done / max(n, 1)),
                      file=sys.stderr, flush=True)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg 退出码 %d（输出: %s）" % (rc, out_path))
    print("  写入 %s（%d 帧，%.0fx%.0f）" % (out_path, done, w, h), file=sys.stderr)


def render_range(tl: Timeline, t0: float, t1: float, out_path: Path,
                 audio: Path, **kw) -> None:
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    # 把 t1 夹到**音频总长**：-shortest 下音频比视频短时 ffmpeg 提前退出，
    # 管道 BrokenPipe，尾巴若干帧被丢（206-212 那 6 秒就因此短了 1 帧）。
    if Path(audio).exists():
        try:
            t1 = min(t1, probe_duration(audio))
        except Exception:
            pass
    encode(out_path, tl, t0, t1, audio, texts=texts, **kw)


def dump_frames(tl: Timeline, t0: float, t1: float, out_dir: Path,
                scale: float = 1.0, pixelate: bool = False, step: int = 1) -> int:
    """只出帧不编码，落 out/frames/%06d.png，用于肉眼抽查。"""
    config.RENDER_SCALE = scale
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    n = 0
    for idx, img in iter_frames(tl, t0, t1, texts=texts, scale=scale, pixelate=pixelate):
        if (idx - int(round(t0 * config.FPS))) % step:
            continue
        img.save(out_dir / ("%06d.png" % idx))
        n += 1
    return n
