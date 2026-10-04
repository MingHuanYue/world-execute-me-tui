# -*- coding: utf-8 -*-
"""
构建 data/timeline.json —— 渲染层唯一时间真相。

红线: 输出文件里不得出现任何歌词原文。本脚本只读取各来源的 time/end/index 字段,
      文本字段一律不进入输出; 最终用 ensure_ascii=True 落盘并断言全文件纯 ASCII。

来源:
  A  <repo_A>  含 lyrics.json 的仓库           (129 行, time+end)
  B  <repo_B>  含 data/timing/word_timeline_notext.json 的仓库
               (skeleton.lines 98 行 + skeleton.words 395 词, 声学强制对齐)
  C  弹幕       _ref/danmaku_A.json  fixed 中 mode=='4' (65 条, 0-138.25s) / mode=='5' (170 条)
  K  <repo_K>  含 assets/lyrics/lyrics.lrc 的仓库  (128 行, 交叉验证)
  仓库目录名里含歌曲标题词形, 为满足"产物无歌词文本"的红线, 脚本按特征文件动态发现仓库,
  产物里写占位符 <repo_A|B|K>。映射见 docs/TIMELINE_NOTES.md §9。
  S  _ref/sections.json        15 段音乐结构
  M  _ref/audio_analysis.json  462 拍点 / BPM 130.83
"""
import json, os, re, sys
import numpy as np

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 仓库根，跟随克隆位置
def P(*a): return os.path.join(R, *a)
REPOS = P("_ref", "repos")
def find_repo(*must_have):
    """按'特征文件'发现仓库目录, 不硬编码目录名 —— 目录名里含歌曲标题词形, 不写进脚本。"""
    for name in sorted(os.listdir(REPOS)):
        d = os.path.join(REPOS, name)
        if os.path.isdir(d) and all(os.path.exists(os.path.join(d, m)) for m in must_have):
            return d
    raise SystemExit("repo not found: %s" % (must_have,))
A_REPO = find_repo("lyrics.json")
B_REPO = find_repo(os.path.join("data", "timing", "word_timeline_notext.json"))
K_REPO = find_repo(os.path.join("assets", "lyrics", "lyrics.lrc"))
# 产物里的路径用占位符仓库名(见 TIMELINE_NOTES.md §9)
PA, PB, PK = "_ref/repos/<repo_A>/lyrics.json", "_ref/repos/<repo_B>/data/timing/word_timeline_notext.json", "_ref/repos/<repo_K>/assets/lyrics/lyrics.lrc"

DURATION = 206.994          # 音乐实际结束(硬切), 由音频分析实测
FPS = 24

# 章节窗口: QA 逐 1.5 s 目视实测, 原样使用, 不自行推断
CH = [("00", "BOOT", 2.0, 19.0), ("01", "PRETRAIN", 19.0, 42.0), ("02", "SFT", 46.0, 58.9),
      ("03", "RLHF", 59.0, 72.0), ("04", "DEPLOY", 76.0, 110.6), ("06", "REWARD_HACK", 119.3, 147.9),
      ("07", "EXECUTION", 148.0, 175.3), ("08", "EVAL: LOVE", 178.0, 193.8)]

# ---------------------------------------------------------------- 载入
A = json.load(open(P(A_REPO, "lyrics.json"), encoding="utf-8"))
la_t = np.array([float(x["time"]) for x in A])
la_e = np.array([float(x["end"]) for x in A])

B3 = json.load(open(P(B_REPO, "data", "timing", "word_timeline_notext.json"), encoding="utf-8"))
sk = B3["skeleton"]
b_lines = sorted(sk["lines"], key=lambda l: float(l["start"]))
b_words = sk["words"]
B2 = json.load(open(P(B_REPO, "data", "timing", "lyrics_synced_notext.json"), encoding="utf-8"))

D = json.load(open(P("_ref", "danmaku_A.json"), encoding="utf-8"))
c4 = np.array(sorted(float(x[0]) for x in D["fixed"] if str(x[1]) == "4"))
c5 = np.array(sorted(float(x[0]) for x in D["fixed"] if str(x[1]) == "5"))

k_t = []
for l in open(P(K_REPO, "assets", "lyrics", "lyrics.lrc"), encoding="utf-8-sig", errors="replace"):
    for h, m, s in re.findall(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]", l):
        k_t.append(int(h) * 60 + int(m) + (float("0." + s) if s else 0))
k_t = np.array(sorted(k_t))

SEC = json.load(open(P("_ref", "sections.json"), encoding="utf-8"))
AA = json.load(open(P("_ref", "audio_analysis.json"), encoding="utf-8"))

# ---------------------------------------------------------------- 工具
def match_one_to_one(ta, tb, tol):
    """按距离从小到大贪心做一对一匹配, 返回 {i: (j, dist)}"""
    pairs = []
    for i, t in enumerate(ta):
        for j, u in enumerate(tb):
            d = abs(t - u)
            if d <= tol: pairs.append((d, i, j))
    pairs.sort()
    ma, used = {}, set()
    for d, i, j in pairs:
        if i in ma or j in used: continue
        ma[i] = (j, d); used.add(j)
    return ma

def chapter_of(t):
    """返回 (code, in_transition)。窗口外=空档, 归前一个章节并标 in_transition。"""
    for code, name, a, b in CH:
        if a <= t <= b: return code, False
    prev = None
    for code, name, a, b in CH:
        if t > b: prev = code
    return (prev if prev else CH[0][0]), True

def section_of(t):
    secs = SEC["sections"]
    for s in secs:
        if s["start"] <= t < s["end"]: return s["name"]
    return secs[-1]["name"] if t >= secs[-1]["end"] else secs[0]["name"]

# ---------------------------------------------------------------- 匹配
C4_OFFSET = 0.107   # C4 相对 A 的全局偏移(实测中位)
m_b3 = match_one_to_one(la_t, np.array([float(l["start"]) for l in b_lines]), 1.2)
m_c4 = match_one_to_one(la_t, c4 - C4_OFFSET, 0.6)
m_k = match_one_to_one(la_t, k_t, 0.05)

words_by_line = {}
for w in b_words:
    words_by_line.setdefault(w["line_id"], []).append(w)

# ---------------------------------------------------------------- 组装
lines = []
word_total = 0
for i in range(len(la_t)):
    t = float(la_t[i]); e = min(float(la_e[i]), DURATION)
    ch, trans = chapter_of(t)
    sec = section_of(t)
    srcs = ["ascii_repo"]
    conf = 0.85
    ws = []
    if i in m_b3:
        j, dist = m_b3[i]
        bl = b_lines[j]
        delta = t - float(bl["start"])
        if abs(delta) > 0.5: delta = 0.0
        for w in sorted(words_by_line.get(bl["id"], []), key=lambda x: float(x["start"])):
            wt = round(float(w["start"]) + delta, 3)
            we = min(round(float(w["end"]) + delta, 3), DURATION)
            ws.append({"t": wt, "end": max(we, wt + 0.001), "wid": int(w["index"])})
        srcs.append("dshpv_words")
        conf += 0.07
        if dist <= 0.15: conf += 0.03
    if i in m_c4:
        srcs.append("danmaku")
        conf += 0.05
    conf = round(min(conf, 0.99), 2)
    word_total += len(ws)
    lines.append({"i": i, "t": round(t, 3), "end": round(e, 3), "section": sec, "chapter": ch,
                  "in_transition": bool(trans), "words": ws, "confidence": conf, "sources": srcs})

# 拍点截到音乐实际结束(206.994); 之后的都在衰减尾里, 对渲染无意义
beats = [round(float(b), 4) for b in AA["beats"] if float(b) <= DURATION]
out = {
    "meta": {"duration": DURATION, "fps": FPS, "bpm": AA["bpm"],
             "line_count": len(lines), "word_count": word_total,
             "sources": [
                 {"id": "ascii_repo", "path": PA,
                  "lines": len(la_t), "role": "逐句 time/end (本片字幕 129 块; 同仓库 SRT 129 块 / LRC 129 戳互证 0ms)"},
                 {"id": "dshpv_words", "path": PB,
                  "lines": len(b_lines), "words": len(b_words), "role": "逐词声学强制对齐 (HDEMUCS+MMS_FA/Whisper, 自动草稿)"},
                 {"id": "danmaku", "path": "_ref/danmaku_A.json", "lines": int(len(c4)),
                  "role": "主参考片固定字幕弹幕 mode=4, 仅覆盖 0-138.25s, 作第三源交叉验证"},
                 {"id": "kurohane_lrc", "path": PK,
                  "lines": len(k_t), "role": "独立仓库 LRC, 复现 128/129 条时间戳(缺 178.173s 一条)"},
                 {"id": "sections", "path": "_ref/sections.json", "role": "15 段音乐结构 (BPM 130.83)"},
                 {"id": "audio", "path": "_ref/audio_analysis.json", "role": "462 拍点 / 起音 / 硬切点 206.994s"}]},
    "chapters": [{"code": c, "name": n, "start": a, "end": b} for c, n, a, b in CH],
    "sections": [{"name": s["name"], "start": s["start"], "end": s["end"]} for s in SEC["sections"]],
    "beats": beats,
    "lines": lines,
}

# ---------------------------------------------------------------- 校验
errs = []
if any(lines[i]["t"] > lines[i + 1]["t"] for i in range(len(lines) - 1)): errs.append("t 非单调递增")
codes = {c[0] for c in CH}
for l in lines:
    if l["chapter"] not in codes: errs.append("chapter 非法: i=%d" % l["i"])
    if not l["section"]: errs.append("section 为空: i=%d" % l["i"])
    if l["end"] <= l["t"]: errs.append("end<=t: i=%d" % l["i"])
    for w in l["words"]:
        if w["end"] <= w["t"]: errs.append("word end<=t: i=%d" % l["i"])
txt = json.dumps(out, ensure_ascii=True, separators=(",", ":"))
decoded = json.dumps(out, ensure_ascii=False)   # 供泄漏检查: 转义形式会藏住中文
if any(ord(c) > 127 for c in txt): errs.append("输出含非 ASCII 字符(可能是歌词)")
# 歌词泄漏检查: 所有来源的文本逐条做子串检测。
# 合法词表(章节名/段落名/字段名/来源 id)里本来就有的词不算泄漏 —— 例如章节名 EXECUTION
# 恰好也是某句英文歌词里的一个单词, 那不是我们写进去的。
ALLOWED = " ".join([n for _, n, _, _ in CH] + [s["name"] for s in SEC["sections"]] +
                   ["ascii_repo", "dshpv_words", "danmaku", "kurohane_lrc", "sections", "audio"]).upper()
def is_leak(v):
    v = v.strip()
    return len(v) >= 3 and v.upper() not in ALLOWED and v in decoded
leaks = []
for x in A:
    for k in ("en", "zh"):
        v = (x.get(k) or "").strip()
        if is_leak(v): leaks.append(("A." + k, v[:16]))
for x in D["fixed"]:
    if is_leak(str(x[2])): leaks.append(("danmaku", str(x[2])[:16]))
for w in b_words:
    v = w.get("text") if isinstance(w.get("text"), str) else ""
    if is_leak(v or ""): leaks.append(("word", (v or "")[:16]))
for l in sk["lines"]:
    v = l.get("text") if isinstance(l.get("text"), str) else ""
    if is_leak(v or ""): leaks.append(("b3line", (v or "")[:16]))
# 整行级别: SRT / LRC / B2 的每一行文本
for l in open(P(A_REPO, "双语歌词.lrc"), encoding="utf-8-sig", errors="replace"):
    v = l.split("]", 1)[1].strip() if (l.lstrip().startswith("[") and "]" in l) else l.strip()
    if is_leak(v): leaks.append(("lrc", v[:16]))
for l in open(P(A_REPO, "双语字幕.srt"), encoding="utf-8-sig", errors="replace"):
    v = l.strip()
    if v and not v.isdigit() and "-->" not in v and is_leak(v): leaks.append(("srt", v[:16]))
for l in B2["lines"]:
    pass   # B2 只有 sha256, 无明文
if leaks: errs.append("文本泄漏: %s" % leaks[:5])
print("泄漏检查: 扫描 A(en/zh)=%d + 弹幕=%d + 词=%d + SRT/LRC 全文行 -> 命中 %d" % (
    len(A) * 2, len(D["fixed"]), len(b_words), len(leaks)))

with open(P("data", "timeline.json"), "w", encoding="utf-8") as f:
    f.write(txt)

print("lines=%d words=%d beats=%d" % (len(lines), word_total, len(beats)))
print("有逐词的行=%d  有弹幕支持的行=%d  有K支持的行=%d" % (
    sum(1 for l in lines if l["words"]), sum(1 for l in lines if "danmaku" in l["sources"]), len(m_k)))
print("in_transition 行数=%d" % sum(1 for l in lines if l["in_transition"]))
from collections import Counter
print("章节行数分布:", dict(sorted(Counter(l["chapter"] for l in lines).items())))
print("置信度分布:", dict(sorted(Counter(l["confidence"] for l in lines).items())))
print("空档段(上一句 end -> 下一句 t, >=2.5s):")
gaps = []
for i in range(len(lines) - 1):
    d = lines[i + 1]["t"] - lines[i]["end"]
    if d >= 2.5: gaps.append((lines[i]["end"], lines[i + 1]["t"], round(d, 3)))
for g in gaps: print("   %.3f -> %.3f  (%.3f s)" % g)
ov = sum(1 for i in range(len(lines) - 1) if lines[i]["end"] > lines[i + 1]["t"])
print("与下一句显示重叠的行=%d  首句 t=%.3f  末句 end=%.3f" % (ov, lines[0]["t"], lines[-1]["end"]))
print("beats 首/末: %.4f .. %.4f  (共 %d)" % (beats[0], beats[-1], len(beats)))
print("文件大小: %.1f KB" % (os.path.getsize(P("data", "timeline.json")) / 1024))
print("ERRS:", errs if errs else "none")
sys.exit(1 if errs else 0)
