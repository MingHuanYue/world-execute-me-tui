#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键构建：检查环境 -> 建虚拟环境 -> 装依赖 -> 自检 -> 渲染成片。

用法:
    python oneclick.py              # 出 720p 成片
    python oneclick.py --4k         # 另出原生 3840x2160
    python oneclick.py --check      # 只做环境自检，不渲染
    python oneclick.py --no-install # 跳过依赖安装
"""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 中文提示在中文 Windows 控制台默认走 GBK，会崩或乱码。强制 UTF-8。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
VENV = ROOT / ".venv"
REQ = ROOT / "requirements.txt"
AUDIO = ROOT / "assets" / "audio" / "song.mp3"
LYRICS = ROOT / "assets" / "lyrics" / "lyrics.json"
MIN_PY = (3, 9)
TOTAL = 5


def say(msg=""):
    print(msg, flush=True)


def bar():
    say("-" * 64)


def step(n, title):
    say()
    bar()
    say("  [%d/%d] %s" % (n, TOTAL, title))
    bar()


def die(msg, hint=None, code=1):
    say()
    say("  [X] " + msg)
    if hint:
        say("      " + hint)
    sys.exit(code)


def in_venv():
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv():
    if in_venv():
        return
    if not VENV.is_dir():
        say("  创建虚拟环境 .venv（只此一次）...")
        try:
            venv.EnvBuilder(with_pip=True).create(str(VENV))
        except Exception as e:
            die("虚拟环境创建失败：" + str(e),
                "可以直接用系统 Python 跑：pip install -r requirements.txt")
    py = venv_python()
    if not py.exists():
        die("虚拟环境里找不到 python", str(py))
    say("  切换到虚拟环境重新执行 ...")
    os.execv(str(py), [str(py), str(Path(__file__).resolve())] + sys.argv[1:] + ["--_reentry"])


def pip_env():
    """给 pip 一个**仓库本地**的缓存目录。

    为什么要显式指定：全局 pip 配置里的 cache-dir 可能是坏的
    （指向不存在的盘、或值里带引号），pip 会在那儿卡死而不是报错。
    环境变量优先级高于配置文件，所以这一句能绕开绝大多数的坏配置。
    """
    env = dict(os.environ)
    env["PIP_CACHE_DIR"] = str(ROOT / ".pip-cache")
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def pip_run(args, what):
    cmd = [sys.executable, "-m", "pip", "install", "--no-input"] + args
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), env=pip_env(), timeout=900)
    except subprocess.TimeoutExpired:
        die("安装超时（15 分钟）：" + what,
            "手动试一次：pip install --no-cache-dir -r requirements.txt")
    return r.returncode


def install_deps():
    say("  安装依赖（Pillow / numpy / imageio-ffmpeg，首次约 1-2 分钟）...")
    if pip_run(["-r", str(REQ)], "requirements.txt") != 0:
        die("依赖安装失败",
            "手动试一次：" + NL +
            "        pip install --no-cache-dir -r requirements.txt" + NL +
            "      国内网络慢可加镜像：" + NL +
            "        pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple")
    say("  依赖就绪")


def check_assets():
    if not AUDIO.exists():
        say()
        say("  [!] 缺少音频文件：assets/audio/song.mp3")
        say("      本仓库不分发任何音乐，需要你自备音频。")
        say("      文件名必须是 song.mp3，放进 assets/audio/ 目录。")
        say("      （用你自己有权使用的音频；本工程为非商业同人示例。）")
        sys.exit(2)
    say("  音频就位：%.1f MB" % (AUDIO.stat().st_size / 1048576))
    if not LYRICS.exists():
        say("  [i] 没有歌词文件 —— 照样能出片，底栏会显示中性占位。")
        say("      想要真歌词：见 data/import_lrc.py")
    else:
        say("  歌词就位")


def run_build(args, label):
    say("  " + label + " ...")
    cmd = [sys.executable, str(ROOT / "build.py")] + args
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(cmd, cwd=str(ROOT), env=env)
    if r.returncode != 0:
        die("构建失败（退出码 %d）" % r.returncode)


def main():
    ap = argparse.ArgumentParser(description="world.execute(me); TUI MV 一键构建")
    ap.add_argument("--4k", action="store_true", help="另出原生 3840x2160")
    ap.add_argument("--check", action="store_true", help="只做自检，不渲染")
    ap.add_argument("--no-install", action="store_true", help="跳过依赖安装")
    ap.add_argument("--_reentry", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if not args._reentry:
        say()
        bar()
        say("  world.execute(me); · 双栏 TUI 音乐 MV · 一键构建")
        say("  每一帧都是时间 t 的纯函数：frame = f(t)，24 fps")
        bar()

    step(1, "Python 版本")
    v = sys.version_info
    if (v.major, v.minor) < MIN_PY:
        die("需要 Python %d.%d 或更高，当前 %d.%d" % (MIN_PY + v[:2]),
            "下载：https://www.python.org/downloads/")
    say("  Python %d.%d.%d  OK" % v[:3])

    step(2, "虚拟环境")
    ensure_venv()
    say("  使用 " + sys.executable)

    step(3, "依赖")
    if args.no_install:
        say("  已跳过（--no-install）")
    else:
        install_deps()

    step(4, "素材检查")
    check_assets()

    step(5, "构建")
    run_build(["check"], "环境自检（音频 / 时间轴 / 字体 / ffmpeg / 行数）")
    if args.check:
        say()
        say("  只做自检，未渲染。")
        return 0
    run_build(["all"] + (["--4k"] if args.__dict__["4k"] else []), "渲染成片")

    say()
    bar()
    say("  完成")
    bar()
    out = ROOT / "out"
    for name in ("film.mp4", "film_4k.mp4"):
        p = out / name
        if p.exists():
            say("  %-14s %6.1f MB" % (name, p.stat().st_size / 1048576))
    say("  目录：" + str(out))
    say()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say()
        say("  已中断。")
        sys.exit(130)