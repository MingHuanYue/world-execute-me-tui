"""build.py — CLI 入口

职责：一键出片。子命令 check / lyrics / frames / render / all。
约束：<= 300 行；ffmpeg 一律走 config.ffmpeg_exe()。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import config


def _ok(msg: str) -> None:
    print("  [OK]   " + msg)


def _bad(msg: str) -> None:
    print("  [FAIL] " + msg)


def cmd_check() -> int:
    """音频 / 时间轴 / 字体 / ffmpeg 编码器 / out 可写 —— 任一失败返回非 0。"""
    bad = 0
    print("== 环境自检 ==")

    # 1) 音频（存在 + 非空 + **真的能解码**——网易云的 m4a 可能是加密轨，只查大小会漏）
    song = config.resolve_song()
    if song.exists() and song.stat().st_size > 0:
        try:
            from render import probe_duration
            d = probe_duration(song)
            if config.is_decodable(song):
                _ok("音频 %.3f s -> %s（解码实测通过）" % (d, song.name))
            else:
                _bad("音频 %s 元数据可读（%.3f s）但解不开——加密轨特征" % (song.name, d))
                _bad("提示：网易云的 m4a 常是 AVS3(av3a) 加密轨；换 mp3/aac/flac/wav 放 assets/audio/ 即可自动发现")
                bad += 1
        except Exception as exc:
            _bad("音频无法解码（%s）: %s" % (song.name, str(exc).splitlines()[0][:120]))
            _bad("提示：网易云下载的 m4a 可能是 AVS3(av3a) 加密轨，FFmpeg 无解码器；请换一份 mp3/aac/flac/wav")
            bad += 1
    else:
        _bad("音频缺失或为空: %s（把自备音轨放进 assets/audio/）" % config.SONG_PATH)
        bad += 1

    # 2) 时间轴
    try:
        import json
        tl = json.loads(config.TIMELINE_PATH.read_text(encoding="utf-8"))
        n = len(tl["lines"])
        _ok("时间轴 %d 行 / %d 拍 / %d 段 / %d 章（%.3f s）" % (
            n, len(tl.get("beats", [])), len(tl.get("sections", [])),
            len(tl.get("chapters", [])), tl["meta"]["duration"]))
        if any(("一" <= ch <= "鿿") for ch in config.TIMELINE_PATH.read_text(encoding="utf-8")):
            _bad("时间轴里出现了中文 —— 歌词文本不该在这里")
            bad += 1
    except Exception as exc:
        _bad("时间轴不可用: %s" % exc)
        bad += 1

    # 3) 字体
    try:
        from theme import font_mono, font_cjk, font_title
        font_mono(12); font_cjk(16); font_title(72)
        _ok("字体可用（mono / cjk / title）")
    except Exception as exc:
        _bad("字体不可用: %s" % exc)
        bad += 1

    # 4) ffmpeg 编码器
    try:
        exe = config.ffmpeg_exe()
        out = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True)
        have = [c for c in ("libx264", "libx264rgb", "aac", "h264_nvenc") if c in out.stdout]
        if "libx264" in have:
            _ok("ffmpeg %s，可用编码器: %s" % (Path(exe).name, ", ".join(have)))
        else:
            _bad("ffmpeg 没有 libx264 —— 别用系统那个")
            bad += 1
    except Exception as exc:
        _bad("ffmpeg 不可用: %s" % exc)
        bad += 1

    # 5) 代码规模与单一场面断言
    try:
        import spectacle
        over = []
        for p in sorted(Path(config.ROOT).glob("*.py")):
            k = len(p.read_text(encoding="utf-8").splitlines())
            if k > 300:
                over.append("%s=%d" % (p.name, k))
        if over:
            _bad("超过 300 行的文件: " + ", ".join(over))
            bad += 1
        else:
            _ok("所有模块 <= 300 行")
        _n = len(getattr(spectacle, "SET_PIECES", ()))
        _named = len({p.sp for p in getattr(spectacle, "SET_PIECES", ()) if getattr(p, "sp", "")})
        _ok("宏大场面登记 %d 条（其中命名场面 %d 个，DESIGN.md 11.4）" % (_n, _named))
    except Exception as exc:
        print("  [WARN] 代码规模检查跳过: %s" % exc)

    # 6) SP0 头像资产
    sheet = config.ROOT / "assets" / "avatar" / "morph_sheet.png"
    if sheet.exists() and sheet.stat().st_size > 0:
        _ok("SP0 头像 sprite sheet 就位（%s）" % sheet.name)
    else:
        _bad("缺 assets/avatar/morph_sheet.png —— 跑 python data/build_avatar.py 生成")
        bad += 1

    # 7) out 可写
    try:
        config.OUT_DIR.mkdir(parents=True, exist_ok=True)
        probe = config.OUT_DIR / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        _ok("输出目录可写: %s" % config.OUT_DIR)
    except Exception as exc:
        _bad("输出目录不可写: %s" % exc)
        bad += 1

    print("== 自检结果: %s ==" % ("通过" if bad == 0 else "%d 项失败" % bad))
    return 0 if bad == 0 else 1


def cmd_lyrics() -> int:
    """校验 assets/lyrics/lyrics.json 行数与 data/timeline.json 是否匹配。"""
    from lyrics import Timeline, load_lyric_text
    tl = Timeline.load(config.TIMELINE_PATH)
    texts = load_lyric_text(config.LYRICS_PATH, len(tl.lines))
    if len(texts) != len(tl.lines):
        _bad("歌词行数 %d != 时间轴行数 %d" % (len(texts), len(tl.lines)))
        return 1
    real = sum(1 for a, b in texts if a or b)
    if real == 0:
        print("  [WARN] lyrics.json 为空 —— 使用中性占位，管线可跑通，但成片没有歌词文本")
    _ok("歌词 %d 行（其中 %d 行有真实文本）" % (len(texts), real))
    return 0


def cmd_frames(t0: float = 0.0, t1: float | None = None, step: int = 24) -> int:
    from lyrics import Timeline
    from render import dump_frames
    tl = Timeline.load(config.TIMELINE_PATH)
    t1 = tl.duration if t1 is None else t1
    n = dump_frames(tl, t0, t1, config.OUT_DIR / "frames", step=step)
    _ok("导出 %d 张抽查帧 -> %s" % (n, config.OUT_DIR / "frames"))
    return 0


def cmd_render(scale: float = 1.0, pixelate: bool = False,
               t0: float = 0.0, t1: float | None = None,
               codec: str = "libx264", jobs: int = 0, master: bool = False) -> int:
    from lyrics import Timeline
    from render import probe_duration, render_range
    tl = Timeline.load(config.TIMELINE_PATH)
    song = config.resolve_song()
    if t1 is None:                       # 默认渲到**音频结尾**（含那 4.9 s 衰减尾）
        t1 = tl.duration
        try:
            t1 = max(t1, probe_duration(song))
        except Exception:
            pass
    tag = "_4k" if scale >= 3.0 else ""
    name = "film_master.mp4" if master else ("film%s.mp4" % tag)
    out = config.OUT_DIR / name
    config.RENDER_SCALE = scale
    print("渲染 %.3f s -> %.3f s（%d 帧，scale=%.1f，pixelate=%s）" % (
        t0, t1, int(round((t1 - t0) * config.FPS)), scale, pixelate))
    render_range(tl, t0, t1, out, song, scale=scale,
                 pixelate=pixelate, codec=("libx264rgb" if master else codec))
    _ok("完成: %s" % out)
    return 0


def cmd_all(scale: float, pixelate: bool, with4k: bool) -> int:
    rc = cmd_check()
    if rc:
        return rc
    rc = cmd_lyrics()
    if rc:
        return rc
    rc = cmd_render(scale=scale, pixelate=pixelate)
    if rc:
        return rc
    if with4k:
        rc = cmd_render(scale=3.0, pixelate=pixelate)
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="build.py", description="world.execute(me); 双栏 TUI MV 出片")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="环境自检")
    sub.add_parser("lyrics", help="校验歌词与时间轴对齐")
    f = sub.add_parser("frames", help="只导出抽查帧")
    f.add_argument("--range", default="0:0"); f.add_argument("--step", type=int, default=24)
    r = sub.add_parser("render", help="渲染成片")
    r.add_argument("--4k", dest="four_k", action="store_true")
    r.add_argument("--pixelate", action="store_true")
    r.add_argument("--range", default="0:0")
    r.add_argument("--codec", default="libx264")
    r.add_argument("--master", action="store_true", help="无损母版 libx264rgb -qp 0")
    a = sub.add_parser("all", help="check + lyrics + render")
    a.add_argument("--4k", dest="four_k", action="store_true")
    a.add_argument("--pixelate", action="store_true")
    return p


def _range(s: str) -> tuple[float, float | None]:
    if not s or s == "0:0":
        return 0.0, None
    a, b = s.split(":")
    return float(a), float(b)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "lyrics":
        return cmd_lyrics()
    if args.cmd == "frames":
        t0, t1 = _range(args.range)
        return cmd_frames(t0, t1, args.step)
    if args.cmd == "render":
        t0, t1 = _range(args.range)
        return cmd_render(scale=(3.0 if args.four_k else 1.0), pixelate=args.pixelate,
                          t0=t0, t1=t1, codec=args.codec, master=args.master)
    if args.cmd == "all":
        return cmd_all(3.0 if args.four_k else 1.0, args.pixelate, args.four_k)
    return 2


if __name__ == "__main__":
    sys.exit(main())
