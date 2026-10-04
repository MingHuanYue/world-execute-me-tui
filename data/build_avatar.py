# -*- coding: utf-8 -*-
"""SP0「自我成形」资产烘焙 v4 —— **读图处理 + 交叉淡化**（DESIGN.md §11.9）

主人明确否掉了"用手画五官"这条路（64px 画不出来）。这一版**不画任何东西**：
  1. 读两张图（官方鲸鱼图标 / 主人裁好的鲸鱼娘头像），**统一预处理**成同样的分辨率、同样的调色板、同样的扫描线；
  2. 0:10–0:15 官方图标；0:15–0:19 边缘闪烁 + 蓝 -> 青 的色偏；0:19–0:22 Image.blend 交叉淡化；
  3. **淡化后再量化回调色板** —— 这是关键：两张图同调色板，混合后重新量化，就绝不会出现之前那种灰糊。

输出：assets/avatar/morph_sheet.png（12 列 x 8 行 = 96 格，64x64/格）
确定性：hash01 伪随机，无 random；同输入同输出。
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
N = 64                 # = 左栏头像框的设计尺寸（1:1，无重采样）
COLS, ROWS = 12, 8
FRAMES = COLS * ROWS

BG = (0x05, 0x08, 0x13)
GOLD = (0xE8, 0xD7, 0x4B)
CYAN = (0x98, 0xB0, 0xF4)
WHITE = (0xC8, 0xD0, 0xE0)
PAL = (BG, CYAN, WHITE, GOLD)
SRC_ICON = ROOT / "assets" / "avatar" / "src" / "whale_icon.png"
SRC_MAID = ROOT / "assets" / "avatar" / "src" / "whale_maid_head.png"


def hash01(i: int, salt: int = 0) -> float:
    x = (i * 2654435761 ^ salt * 40503) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 3266489917) & 0xFFFFFFFF
    x ^= x >> 16
    return x / 4294967296.0


def ramp(a: float, lo: float, hi: float) -> float:
    if a <= lo:
        return 0.0
    if a >= hi:
        return 1.0
    return (a - lo) / (hi - lo)


def is_bg(c) -> bool:
    """背景判据：高亮 + 近中性。两张图的底都是 (254,254,254)。"""
    return min(c) > 228 and (max(c) - min(c)) < 20


def prep_icon(n: int = N) -> Image.Image:
    """官方图标 -> 单色平涂：完全几何，不带渐变。"""
    src = Image.open(SRC_ICON).convert("RGB").resize((n, n), Image.BOX).load()
    out = Image.new("RGB", (n, n), BG)
    o = out.load()
    for y in range(n):
        for x in range(n):
            if not is_bg(src[x, y]):
                o[x, y] = CYAN
    return out


def prep_maid(n: int = N) -> Image.Image:
    """鲸鱼娘头像 -> 极简剪影：背景 -> 深蓝底，轮廓 -> 青，最亮处（脸/头饰）-> 白。中间阶全压掉。"""
    src = Image.open(SRC_MAID).convert("RGB").resize((n, n), Image.LANCZOS).load()
    out = Image.new("RGB", (n, n), BG)
    o = out.load()
    for y in range(n):
        for x in range(n):
            c = src[x, y]
            if is_bg(c):
                continue
            lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
            if lum > 190:
                o[x, y] = WHITE
            elif lum > 62:
                o[x, y] = CYAN
    return out


def flicker(img: Image.Image, amount: float, fi: int) -> Image.Image:
    """边缘像素闪烁：只翻转"有邻居是背景"的像素，让线条开始抖。"""
    if amount <= 0.01:
        return img
    w, h = img.size
    src = img.load()
    out = img.copy()
    o = out.load()
    for y in range(h):
        for x in range(w):
            if src[x, y] == BG:
                continue
            nb = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            if not any(0 <= nx < w and 0 <= ny < h and src[nx, ny] == BG for nx, ny in nb):
                continue
            if hash01(y * w + x, fi) < amount * 0.5:
                o[x, y] = BG if src[x, y] != BG else CYAN
    return out


def tint_shift(img: Image.Image, u: float) -> Image.Image:
    """蓝 -> 青：u=0 用暗青，u=1 用全亮青。"""
    if u <= 0.0:
        return img
    dim = tuple(int(CYAN[i] * 0.55 + BG[i] * 0.45) for i in range(3))
    src = img.load()
    out = img.copy()
    o = out.load()
    for y in range(img.height):
        for x in range(img.width):
            if src[x, y] != BG:
                c = src[x, y]
                o[x, y] = tuple(int(dim[i] * (1 - u) + c[i] * u) for i in range(3))
    return out


def scanlines(img: Image.Image) -> Image.Image:
    """隔行压暗 —— 与左栏其他头像一致。"""
    p = img.load()
    for y in range(0, img.height, 2):
        for x in range(img.width):
            r, g, b = p[x, y]
            p[x, y] = (int(r * 0.90), int(g * 0.90), int(b * 0.90))
    return img


def build_frame(alpha: float, icon: Image.Image, maid: Image.Image, fi: int) -> Image.Image:
    """α = (t-10)/12。0.42 对应 0:15，0.75 对应 0:19。"""
    base = icon.copy()
    base = tint_shift(base, ramp(alpha, 0.30, 0.62))            # 0:13.6–0:17.4 蓝 -> 青
    base = flicker(base, ramp(alpha, 0.42, 0.60) * (1 - ramp(alpha, 0.66, 0.75)), fi)
    # 0:19–0:22：**方向性扫描擦除**（自上而下）+ 一根白线。
    # 为什么不用 Image.blend：两张图同调色板，CYAN 与 BG 的 50% 混合点离两者几乎等距，
    # 混合后重新量化会得到噪点而不是平滑过渡 —— 见 DESIGN §11.9 的"废弃做法"。
    u = ramp(alpha, 0.75, 1.0)
    if u > 0:
        bp, mp = base.load(), maid.load()
        cut = u * (N + 6) - 3                                   # 含进出场余量，保证扫干净
        for y in range(N):
            for x in range(N):
                if y < cut + 2 * (hash01(x, 3) - 0.5):          # 切边抖动，别像尺子划的
                    bp[x, y] = mp[x, y]
        ly = int(cut)
        if 0 <= ly < N:                                         # 扫过的那根白线
            for x in range(N):
                bp[x, ly] = WHITE
    return scanlines(base)


def main() -> int:
    icon, maid = prep_icon(), prep_maid()
    sheet = Image.new("RGB", (COLS * N, ROWS * N), BG)
    for fi in range(FRAMES):
        alpha = fi / (FRAMES - 1)
        sheet.paste(build_frame(alpha, icon, maid, fi), ((fi % COLS) * N, (fi // COLS) * N))
    out = ROOT / "assets" / "avatar" / "morph_sheet.png"
    sheet.save(out)
    print("写入 %s  %dx%d（%d 帧，%dx%d/帧）" % (out, sheet.width, sheet.height, FRAMES, N, N))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
