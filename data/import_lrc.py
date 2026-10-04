# -*- coding: utf-8 -*-
"""把本地 LRC 按时间戳对齐到 data/timeline.json，写出 assets/lyrics/lyrics.json。

用法：python data/import_lrc.py "<some.lrc>" [--zh "<some.zh.lrc>"]

红线：产物 assets/lyrics/lyrics.json 是**本地文件**，已写进 .gitignore——
      仓库只分发 assets/lyrics/lyrics.example.json（中性占位）。不要把产物提交上去。
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")


def parse_lrc(path: Path) -> dict[float, str]:
    """LRC -> {秒: 文本}。非 [mm:ss.xx] 开头的行（如网易云的 JSON 元数据）跳过。"""
    out: dict[float, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.match(raw.strip())
        if not m:
            continue
        t = int(m.group(1)) * 60 + float(m.group(2))
        txt = m.group(3).strip()
        if txt:
            out[round(t, 3)] = txt
    return out


def load_timeline() -> list[tuple[int, float]]:
    tl = json.loads((ROOT / "data" / "timeline.json").read_text(encoding="utf-8"))
    return [(L["i"], float(L["t"])) for L in tl["lines"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lrc")
    ap.add_argument("--zh", default=None, help="可选的中文翻译 LRC（同格式）")
    ap.add_argument("--out", default=str(ROOT / "assets" / "lyrics" / "lyrics.json"))
    a = ap.parse_args()

    en = parse_lrc(Path(a.lrc))
    zh = parse_lrc(Path(a.zh)) if a.zh else {}
    lines = load_timeline()

    def nearest(src: dict[float, str], t: float, tol: float = 0.30) -> str:
        if not src:
            return ""
        k = min(src, key=lambda x: abs(x - t))
        return src[k] if abs(k - t) <= tol else ""

    rows, hit_en, hit_zh = [], 0, 0
    for i, t in lines:
        e, c = nearest(en, t), nearest(zh, t)
        hit_en += bool(e)
        hit_zh += bool(c)
        rows.append({"i": i, "en": e, "zh": c})

    payload = {
        "_note": "本地导入产物，已 gitignore。仓库只分发 lyrics.example.json。",
        "meta": {"lang": ["en", "zh"], "source": Path(a.lrc).name,
                 "matched": {"lines": len(rows), "en": hit_en, "zh": hit_zh}},
        "lines": rows,
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写入 %s：%d 行，英文命中 %d，中文命中 %d" % (out, len(rows), hit_en, hit_zh))
    missing = [r["i"] for r in rows if not r["en"]]
    if missing:
        print("未命中的行号（前 20）:", missing[:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
