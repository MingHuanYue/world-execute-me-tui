# -*- coding: utf-8 -*-
"""渲染性能剖面：拆出「各原语耗时 / CRT 后期 / 编码等待」。

用法：python data/profile_render.py [--frames 45,65,145,202,205]
"""
import argparse, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config, composite, chat_pages, tui_engine, spectacle   # noqa: E402
from lyrics import Timeline, load_lyric_text                  # noqa: E402
from theme import palette_for                                 # noqa: E402

ACC: dict[str, float] = {}
CALLS: dict[str, int] = {}


def _tick(key: str, dt: float) -> None:
    ACC[key] = ACC.get(key, 0.0) + dt
    CALLS[key] = CALLS.get(key, 0) + 1


def wrap(mod, name: str, label: str | None = None) -> None:
    fn = getattr(mod, name)

    def inner(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            _tick(label or ("%s.%s" % (mod.__name__, name)), time.perf_counter() - t0)
    setattr(mod, name, inner)


def install() -> None:
    # 逐原语：draw_visual 按 spec.viz 记账
    orig_dv = tui_engine.draw_visual

    def dv(d, spec, tl, t, s=1.0):
        t0 = time.perf_counter()
        try:
            return orig_dv(d, spec, tl, t, s)
        finally:
            _tick("viz:" + str(getattr(spec, "viz", "?")), time.perf_counter() - t0)
    tui_engine.draw_visual = dv
    for mod, name in ((chat_pages, "draw_chat"), (chat_pages, "draw_stdout_tokens"),
                      (chat_pages, "draw_avatar"), (composite, "draw_status_bar"),
                      (composite, "draw_copyright"), (tui_engine, "draw_ops"),
                      (spectacle, "compose")):
        wrap(mod, name)


def encode_only(frames, audio: Path, out: Path) -> tuple[float, float]:
    """把已合成好的帧喂管道，只量编码等待。"""
    import render
    cmd = [config.ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (config.WIDTH, config.HEIGHT),
           "-r", str(config.FPS), "-i", "pipe:0", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "18", "-pix_fmt", "yuv420p", str(out)]
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert p.stdin
    for img in frames:
        p.stdin.write(img.tobytes())
    p.stdin.close()
    rc = p.wait()
    dt = time.perf_counter() - t0
    if rc != 0:
        raise RuntimeError("encode rc=%d" % rc)
    return dt, len(frames) / dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="45,65,145,202,205")
    a = ap.parse_args()
    times = [float(x) for x in a.frames.split(",")]

    tl = Timeline.load(config.TIMELINE_PATH)
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    config.RENDER_SCALE = 1.0
    install()

    print("== 单帧剖面（720p）==")
    per_frame = {}
    for t in times:
        ACC.clear(); CALLS.clear()
        t0 = time.perf_counter()
        img = composite.compose_frame(t, tl, texts=texts, scale=1.0)
        compose_dt = time.perf_counter() - t0
        pal = palette_for(tl.state_at(t))
        t1 = time.perf_counter()
        composite.apply_post(img, t, pal, img)
        post_dt = time.perf_counter() - t1
        per_frame[t] = (compose_dt, post_dt, dict(ACC))
        top = sorted(ACC.items(), key=lambda kv: -kv[1])[:6]
        print("\n t=%7.2f  compose %6.1f ms + post %5.1f ms  = %6.1f ms" % (
            t, compose_dt * 1e3, post_dt * 1e3, (compose_dt + post_dt) * 1e3))
        for k, v in top:
            print("      %-34s %6.1f ms  x%d" % (k, v * 1e3, CALLS.get(k, 0)))

    print("\n== 编码等待（帧已在内存，只量管道+libx264）==")
    frames = [composite.compose_frame(t, tl, texts=texts, scale=1.0)
              for t in (45.0, 45.2, 45.4, 45.6, 45.8, 46.0, 46.2, 46.4)]
    dt, fps = encode_only(frames, config.resolve_song(), config.OUT_DIR / "_profile_enc.mp4")
    print("   8 帧编码 %.3f s -> %.1f fps（单帧 %.1f ms）" % (dt, fps, dt / 8 * 1e3))

    print("\n== 全片外推（5085 帧 @720p）==")
    avg = sum(v[0] + v[1] for v in per_frame.values()) / len(per_frame)
    print("   采样帧 compose+post 均值 %.1f ms -> 纯绘帧 %.1f min" % (avg * 1e3, 5085 * avg / 60))
    print("   编码 %.1f fps -> 编码 %.1f min" % (fps, 5085 / fps / 60))
    print("   合计外推 %.1f min" % (5085 * avg / 60 + 5085 / fps / 60))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
