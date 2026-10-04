# REPO_TECH — 三个参考开源实现的架构与算法提炼

> 范围：只提炼设计思路 / 结构 / 算法 / 交互模式 / 视觉语言。**不含**任何受版权保护的画面、音频、歌词原文或素材。
> 文中出现的歌词**只以时间戳、行号、结构角色**引用（例如 "147.660 s 起的 EXECUTION 段"），不引用唱词文本。

## 0. 证据等级约定

| 标记 | 含义 |
|---|---|
| **【确认】** | 已在下载到的源码里读到具体实现，可指到 FILE:LINE 或函数名 |
| **【实测】** | 由本机命令/脚本对仓库内数据文件跑出的真实数字 |
| **【推测】** | 由代码结构反推、但源码中没有直接写明的部分 |

素材获取方式与结果（本机实测）：

| 仓库 | 分支 | 归档字节 | 解包后文件数 | 存放位置 |
|---|---|---|---|---|
| yym8224961/world.execute-me-ascii | main | 3 628 970 | 18 | _ref/repos/yym8224961__world.execute-me-ascii/ |
| KurohaneKaoruko/world-execute-me | main | 10 603 635 | 103 | _ref/repos/KurohaneKaoruko__world-execute-me/ |
| MisakaZentai/world-execute-me-dsh-pv | main | 7 126 958 | 1586 | _ref/repos/MisakaZentai__world-execute-me-dsh-pv/ |

- 下载通道：`https://gh-proxy.com/https://codeload.github.com/<owner>/<repo>/zip/refs/heads/main`（本机 github.com 与 api.github.com 被 hosts 指向 127.0.0.1，codeload 直连亦不可用）。**【实测】**
- 第三个仓库名字注意：实际是 **world-execute-me-dsh-pv（连字符）**，任务清单里的 world.execute-me-dsh-pv（点号）在 codeload / api / jsDelivr 上全是 404。正确名字由 `https://gh-proxy.com/https://api.github.com/users/MisakaZentai/repos` 的返回确定。**【实测】**
- 三个仓库全部拿到源码，**没有"未获取"的仓库**。

---

## 1. 三仓库横向对照

| 维度 | A. world.execute-me-ascii | B. world-execute-me (Rust) | C. world-execute-me-dsh-pv |
|---|---|---|---|
| 语言/依赖 | Python 3 标准库 + Swift 音频助手 | Rust 2024 + crossterm + rodio | Python 3.12 + Pillow/NumPy + Node20/Playwright + ffmpeg |
| 目标形态 | **live 终端播放器**（.pyz 单文件，macOS） | **live 终端播放器** + 逐帧导出 | **离线逐帧出片**（out/film.mp4） |
| 时钟源 | 独立 audio-clock 进程，AVAudioPlayer 拥有时间轴，stdout 送 JSON | rodio get_pos() + 墙钟插值（Clock 混合） | **帧号即时间**：t = n/24，无实时时钟 |
| 帧率 | --fps 默认 24（5..60） | 60（渲染帧率上限） | 24（硬编码 FPS = 24） |
| 画面刷新 | 每帧全量 Canvas.ansi()（行内只切颜色） | **差量刷新**：只输出变化的 cell | Pillow 全帧重画 → 逐帧编码 |
| 场景粒度 | 40+ 个 lyric_* 函数，按 if t<... elif 时间链派发 | 19 个 Seg{start, Box<dyn Scene>}，线性查表 | SHOTS 列表（时间区间 → 函数）+ 转场窗口；v2 再加 Cut 类按 cut 索引接管 |
| 转场 | 一个 16 s 标题接管 + 全程递进故障 | 场景切换处 0.24 s 的 CRT 换台闪断（glitch + 白闪） | **动机化转场**：reflow / zoom / pan / spin / crt，默认 glide |
| 频谱数据 | 离线 spectrum.json：30 fps × 48 段 | 启动时离线 FFT：60 fps × 32 段 + 低/中/高 + 重音点 | 离线 audio_features.json：48.039 fps × 7 段 + loud/kick/flux/cent |
| 歌词数据 | lyrics.json（双语 + end） | lyrics.lrc + lyrics.zh.txt（运行期对齐） | 逐词时间轴 word_timeline.json（**文字不随仓库分发**） |
| 字体 | 代码内 5×5 点阵 + 终端 256 色 | 代码内 3~5 列 × 5 行点阵（bigfont） | Consolas / msyh / **Space Mono、Anton（OFL，随仓库）** + Chromium 界面字体 |
| 色彩 | ANSI 256 色索引（7 档） | **ANSI 真彩** Color::Rgb | RGB 全彩（PIL） |
| 出片管线 | 无（只有 --snapshot 单帧） | .bin 帧序列 → PIL 光栅化 → **ffmpeg rawvideo 管道** | 一帧一 HTML → Playwright 截图 + PIL 引擎 → **ffmpeg rawvideo 管道** → 无损母版 → BT.709 转码 |
| 规模 | scenes.py 3073 行 / player.py 321 行 | Rust ~10.4k 行（13 模块） | Python ~15k 行（75 个 .py） |

---

## 2. 仓库 A：yym8224961/world.execute-me-ascii

### 2.1 架构总览【确认】

```
player.py       主循环 + Canvas/ANSI + 字幕/进度 + 键盘状态机 + Audio 子进程客户端
scenes.py       所有分镜（40+ 函数）+ glitch/phosphor 后处理 + draw_scene 时间派发
AudioClock.swift  独立进程：AVAudioPlayer 拥有时间轴，stdin 收命令、stdout 送位置
config.json     {audio, duration, subtitle_offset}
lyrics.json     129 条双语歌词（time/en/zh/end）
spectrum.json   {fps:30, bands:48, frames:6358}
run.sh / build-audio.sh  编译本机（或 universal）音频助手
tools/build_bundle.py + tools/bundle_main.py + tests/test_bundle.py  zipapp 打包与完整性校验
```

关键设计选择：**播放器自身只依赖 Python 标准库**，把"真正的音频设备访问"隔离在一个 Swift 二进制里（README.md:11）。这样 Python 侧完全不用管解码/缓冲，只要一个随时间单调前进的数字。**【确认】**

### 2.2 ① 音频时钟与同步机制【确认】

**时钟源：音频设备。**

- AudioClock.swift:4 直接写着设计声明：*"The audio device owns the timeline. The terminal consumes currentTime."*
- 该进程在 RunLoop 里以 **1/60 s** 为节拍轮询 player.currentTime，每拍输出一行 JSON：`{"time":%.6f,"duration":%.6f,"playing":%@}`（AudioClock.swift:40-45）。
- 指令通道是 stdin 文本行：play / pause / seek <t> / volume <v> / quit（AudioClock.swift:22-36）。seek 会被 clamp 到 [0, duration-0.01]（第 30 行）。
- 播放失败会回写 `{"error":"Audio output unavailable"}`（第 25 行），Python 侧据此抛错（player.py:247）。

**消费端：一个后台线程 + 一个"最近更新时间"用作看门狗。**

- player.py:208-214 后台线程逐行读 stdout，成功解析就整体替换 self.state 并记 self.last = time.monotonic()。
- 主循环拿的是 state.copy()，**这一帧的所有动画只用这一个时间值**（player.py:246）。
- 看门狗：`if begin-audio.last>2: raise RuntimeError('音频时钟停止更新。')`（player.py:249）。音频引擎意外退出也会被 proc.poll() 抓住（第 248 行）。

**逐帧 vs 逐条消息：这里是"逐帧 + 音频时间采样"，不是事件驱动。**

- 主循环用累加目标时刻做节拍器，避免 sleep 漂移：
  ```
  next_frame += 1/args.fps
  delay = max(0, next_frame - time.monotonic())
  if delay == 0: next_frame = time.monotonic()     # 落后了就重新对齐，不做"追赶补偿"
  ```
  （player.py:266-268）
- 等待键盘用 `select.select([sys.stdin],[],[],delay)`，**睡眠时间就是这一帧的剩余时间**，所以按键响应不会牺牲帧率（第 269 行）。
- 暂停/播放不是本地标志位，而是通过子进程的 pause/play 命令（第 281-282 行），保证 state['playing'] 是设备真实状态。判定"播放到底"也用设备状态而非本地计时（第 251-254 行）。

**字幕/动画的偏移是渲染期加在时间上的，不改时钟：**`e = self.cue(t + offset)`（player.py:140），offset 可在线用 [ / ] 每次 ±0.1 s 调整（第 287-288 行）。

### 2.3 ② 场景状态机【确认】

**没有事件队列，没有状态对象：一条时间 if/elif 链。**

- 五个章节常量：`CHAPTERS = [(0,'01 / CREATION'),(29.709,...),(110.9,...),(125.708,...),(177.246,...)]`（player.py:109-111）；`act = max(x for x in CHAPTERS if x[0] <= t)`（第 141 行）。
- `draw_scene(c,t,top,bt,pulse,e)`（scenes.py:2921）就是分派器：按 t 落入 40+ 个分支，每个分镜拿到 `elapsed = t - lyric_time`（第 2929 行）——**分镜内的动画一律用"本句歌词已经唱了多久"，不是全局时间**，这样 seek 之后状态天然正确。
- 顶层按秒区间切段（0-16 开机、16-29.709 标题、29.709-59.223 主歌…），段内再按歌词行区间二分（例如 第 2959-2961 行的 `lyric_points_dimension`）。
- 中段有一处**刻意复用旧实现**：74.045-85.078 s 用 legacy_organic（scenes.py:1487-1600），并在后处理里也走 legacy_phosphor（scenes.py:3062-3064）——分镜状态机允许"局部回滚到早期版本"，靠时间区间隔离。
- 兜底串场：t>208 显示结束文案（player.py:170-171），不是静默黑屏。

**递进故障是一个"只增不减"的强度函数**，这是最值得抄的一点：

```
def glitch_intensity(t):           # scenes.py:18-28
    if t < 60:    return 0.05
    if t < 110:   return mix(0.05, 0.25, (t-60)/50)
    if t < 110.9: return mix(0.25, 0.6, (t-110)/37)
    anchors = ((110.9,.259),(112.22,.34),(113.1,.43),(114.18,.51),
               (114.92,.59),(115.78,.66),(117.274,.73),(125.708,.81),
               (147.66,.92),(177.246,1.0))
    for (a,low),(b,high) in zip(anchors, anchors[1:]):
        if t < b: return mix(low, high, clamp((t-a)/(b-a)))
    return 1.0
```

注释直说了意图：*"Each departure accumulates damage; later execution never resets it."* 强度只被锚点抬高，永远不回退。apply_glitch（scenes.py:30-99）按强度阈值逐级解锁 5 种效果：行位移 → 颜色污染 → 扫描线干扰 → 块级腐蚀 → 110.9 s 之后的**常驻**数据带与低亮度残影行。

### 2.4 ③ 数据结构（实测 schema）【实测】

config.json（5 行，全文）：
```
{ "audio": "media/song.mp3", "duration": 211.906667, "subtitle_offset": 0.0 }
```

lyrics.json：**顶层是数组**，129 条，每条 `{time, en, zh, end}`。
- 实测：time 起点 0.1，最后 end 210.311；句间 Δt 最小 0.336 / 中位 1.1705 / 最大 16.436；句长最小 0.336 / 中位 1.18 / 最大 4.5。
- 因为每条都带**显式 end**，查询是"二分找最后一条 time ≤ t，再检查 t < end"（player.py:119-122），所以间奏期天然返回 None，不需要额外状态。

spectrum.json：`{"fps":30, "bands":48, "frames":[[48 floats], ...]}`。
- 实测：frames 6358 × 48，全部值落在 [0,1]（已归一化）；第 100 帧前 12 段示例 `[0.681, 0.796, 0.846, 0.821, 0.755, 0.773, 0.893, 0.937, 0.908, 0.735, 0.713, 0.787]`。
- 查表是一行：`a[min(len(a)-1, max(0, int(t*self.spectrum['fps'])))]`（player.py:123-125）。
- 注意 fps=30 而画面 24 fps：**数据帧率与渲染帧率解耦**，渲染时直接按时间取，不做插值（第 150 行 `spec=int(t*30)`）。

双语文稿另存两套便于分发：双语歌词.lrc（每行两条 tag 相同、英中交替）与双语字幕.srt（一条 cue 内英中两行）——都是 lyrics.json 的同源导出物。**【确认】**（双语歌词.lrc:1-8 与 双语字幕.srt:1-10 与 lyrics.json 同时间戳）

### 2.5 ④ 字符画与色彩渲染【确认】

**画布模型**：`Canvas.cells = [[(ch, style), ...]]`（player.py:62-66）。只有两层信息：字符 + 7 档样式。STYLES 是 ANSI **256 色**索引（player.py:12，`38;5;137/215/221/230/203/94/58`），不是真彩。

- **全/半角宽度**：cw(ch) 用 `unicodedata.east_asian_width in ('W','F')` 判 2，组合字符返回 0（player.py:38-40）。put() 在写宽字符时把右半格写成空串 ''，ansi() 遇到空串跳过（player.py:76, player.py:103）——这就是"宽字符占位符"方案。
- **裁切与换行**：crop(s,n) 按显示宽度截断（第 44-50 行）；wrap() 只在纯 ASCII 时按空格断行（第 57 行），中文不拆词。
- **居中按显示宽度**：`center() = (w - width(s))//2`（第 78 行）。
- **行内颜色压缩**：ansi() 只在 `style != last` 时写转义序列（第 102-105 行），并把每行都用 `\x1b[{y+1};1H` 绝对定位（第 101 行）。
- **预留行防抖动**：字幕固定占 2 行 × 2 语言，注释写明 *"Two reserved lines per language prevent changes in caption position."*（player.py:167-169）。
- **点阵大字**：FONT 是 5 行 × 5 列（个别 4 列）的 '0'/'1' 位图（player.py:14-36），`Canvas.big()` 用 '#' 绘制、字距 6 列，超宽时降级为普通居中文本（第 89-97 行）。
- **3D 投影**：point() 用 `p = 3.7/(3.7+z)` 做透视，x/y 各乘 0.34×跨度——**y 用 (bt-top)、x 用 (r-l)，靠屏幕本身的比例吸收格子 2:1**（scenes.py:113-117）。rot() 绕 z 再绕 y（第 107-111 行）。
- **隐式曲线的字符光栅化**：圆周 `x=cx+cos(a)*r, y=cy+sin(a)*r*0.5`（scenes.py:614-615，明确乘 0.5 抵消格子比例）；心形用隐函数采样（lyric_heart，scenes.py:1463 起）。
- **确定性噪声**：hash16(i) 是三段 xorshift-multiply 的整数哈希（scenes.py:9-13），**同参数同帧恒定**——这是故障效果与粒子能"逐帧可复现"的基础。
- **生命游戏**：`life_state(cols,rows,generation)` 用 LIFE_CACHE 缓存整条演化链，按需推进（scenes.py:286-300），避免每帧重算。

### 2.6 ⑤ 导出管线【确认】

**A 仓库没有视频导出。** 全树 grep 无 ffmpeg、无 rawvideo；只有 `--snapshot <t> --plain/--ansi`（player.py:314-316）用来出单帧文本/ANSI。**【确认，属于"能力缺口"而非未获取】**

它真正做的是**单文件分发 + 完整性校验**，这部分设计很值得抄：

- tools/build_bundle.py:11-13 列出要内嵌的 7 个资源（含 audio-clock 与 media/song.mp3）。
- 打包时对每个资源算 sha256 写进 bundle-manifest.json，用 `zipapp.create_archive(..., compressed=True, interpreter='/usr/bin/env python3')` 生成 .pyz（第 21-34 行）。
- 运行时 tools/bundle_main.py:19-30 先校验每个资源的 sha256，再拒绝绝对路径与 ..（第 22-23 行），全部释放到临时目录后 runpy 执行 player.py；退出时临时目录随 TemporaryDirectory 清理。
- tests/test_bundle.py:17-26 断言：内嵌资源与源文件逐字节一致、config.json 里 audio 指向内嵌文件、**.pyz 内不得出现 .mp4/.png/.jpg**；第 43-53 行还构造一个被篡改的包，断言必须报"资源校验失败"。
- macOS 音频助手用 build-audio.sh:8-20 编译两种架构再 lipo 合并（--universal）。

### 2.7 A 仓库可复用点小结

1. 把"音频时钟"做成**外部小进程 + stdin/stdout 文本协议**：宿主语言零音频依赖，且时钟天然由设备拥有。
2. **单条 if t<... 时间链 + 显式 end 的歌词表**：最朴素，但 seek/暂停/跳章节全部自动正确。
3. **强度单调递增的故障函数**：用一个纯函数描述"损伤累积"，后期永不回退，视觉叙事成本极低。
4. **数据帧率 ≠ 渲染帧率**（30 vs 24），查表不插值。
5. .pyz + 资源 sha256 清单 + "拒绝绝对路径/.." + 篡改测试 = 只要 4 个文件就能实现的可分发性与防篡改。

---

## 3. 仓库 B：KurohaneKaoruko/world-execute-me（Rust CLI）

### 3.1 架构总览【确认】

README.md:124-145 给出模块表，与源码一致：

```
main.rs     启动流程 / 主循环 / 离屏渲染（shots、render_video）
audio.rs    rodio 播放 + 自写 radix-2 FFT 离线频谱包络
lyrics.rs   LRC + 中英双语对齐（关键词标注）
view.rs     全局帧状态（频段能量、link 状态、歌词游标）
buf.rs      字符画布：Cell/Canvas/图元，宽字符对位
term.rs     差分刷新终端 + 离屏 HTML/二进制导出
chrome.rs   常驻界面：状态栏/频谱/进度/歌词条/帮助
theme.rs    调色板与关键词高亮
fx.rs       特效库：粒子/故障/字符雨/辉光/心形曲线
fx3d.rs     终端 3D 引擎：透视投影 + Z-Buffer + 兰伯特着色
demo3d.rs   --demo3d 引擎巡演模式
bigfont.rs  5x5 像素大字模
scenes/     19 个场景 + 时间轴
```

渲染流程被 README.md:147-149 一句话概括：每帧 场景.draw(ctx) 画舞台 → 舞台后处理（扫描线/辉光/渐晕/故障）→ 外壳四件套 → 全局调色 → 差分刷新。

### 3.2 ① 音频时钟与同步机制【确认】——本仓库最核心的贡献

**双时钟设计：设备位置做主时钟，墙钟做插值，两者互相校正。**

```
pub struct Clock { base: f32, anchor: Instant, playing: bool }   // audio.rs:400-404
pub fn now(&self) -> f32 { if playing { base + anchor.elapsed() } else { base } }  // :434-440
pub fn sync(&mut self, audio_pos: f32) { self.base = audio_pos; self.anchor = Instant::now(); }  // :430-433
```

```
pub fn time(&mut self) -> f32 {                                  // audio.rs:538-559
    if let Some(p) = &self.player {
        let pos = p.get_pos().as_secs_f32();
        // 播放器位置只在解码块更新时跳变，用墙钟在两次更新间插值，保持丝滑
        if (pos - self.last_pos).abs() > 1e-4 { self.last_pos = pos; self.fallback_clock.sync(pos); }
        let t = self.fallback_clock.now();
        if t > pos + 0.10 { self.fallback_clock.sync(pos); pos } else { t }   // 防止墙钟跑飞
    } else if self.fallback_clock.is_playing() { self.fallback_clock.now() } else { self.fallback_clock.base }
}
```

三点可复用：**(a)** 只在设备位置真的变化时才 sync，避免每帧重置；**(b)** 两次更新之间用墙钟插值得到连续时间；**(c)** 有 `t > pos + 0.10` 的硬护栏，超了就丢弃墙钟结果。

还有一个易踩的坑被显式处理：**闪屏期间先 pause() 播放器，等 start() 才真正开播**，否则"按空格开始"之前音频已经跑了一段，画面永远追不齐（audio.rs:475-477 与 :499-502，CHANGELOG.md:104）。

**谱分析：启动时把整首歌离线解码一遍，按 60 fps 建表，播放期零抖动。**（audio.rs:1-6 的设计声明 + :157-396 实现）

- 常量：FPS=60, BANDS=32, NBIN=1024（audio.rs:14-16）。
- Hann 窗（:200-203）；自写迭代 radix-2 FFT（:89-154）。
- 频段边界：`f = 40 * (f_hi/40)^(k/32)`，`f_hi = min(16000, 0.45*sample_rate)`（:206-213）——**对数分布**；并预计算每个频点属于哪一段（:220-229）避免每帧 32 次比较。
- 三条总线：`(bass_hi, mid_hi) = (edges[6], edges[20])`（:230），即 6/20 段处切分。
- 时间戳取**窗中心**：`t = (total - n*0.5) / sample_rate`（:298），再 `idx = round(t*FPS)` 落到表上。
- 空帧用前值前向填充（:311-323）。
- **归一化用 95 分位而不是峰值**（:330-354），注释：*"避免被单帧尖峰拖垮"*；最后做 gamma `powf(0.7)` 再量化为 u8（:361）。
- **重音检测**：低频局部极大值 `b > 0.72 && b > 前后帧 && 距上次 ≥ 0.18 s`（:371-385），产出 peak_beats。README 说全曲自动标出 700+ 个重音点（README.md:19）。
- 查询是 Spectrum::at() 的 `v[(t*FPS) as usize]`（:53-59），外加 pulse() 取前 6 帧低频均值（:79-85）。

### 3.3 ② 场景状态机【确认】

**Scene trait + 线性时间表 + 查表取下标**，比 A 仓库的 if 链更规整：

```
pub trait Scene { fn name(&self) -> &'static str; fn draw(&mut self, ctx: &mut Ctx); }   // scenes/mod.rs:292-295
pub struct Seg { pub start: f32, pub scene: Box<dyn Scene> }                            // :297-300
pub fn index_at(&self, t: f32) -> usize { /* 最后一个 start <= t */ }                    // :307-317
```

build()（scenes/mod.rs:323-352）用 `add!(时间, Scene::new())` 宏登记 **19 幕**：

| 起始 | 场景 | 起始 | 场景 |
|---|---|---|---|
| 0.000 | open::Boot | 89.223 | organic::Morph |
| 16.000 | open::Title | 101.474 | organic::Trance |
| 29.709 | verse::Geometry | 110.900 | loss::Abandon |
| 44.452 | verse::Electric | 118.333 | loss::Isolation |
| 59.223 | verse::Stimulus | 125.708 | loss::Fragments |
| 64.045 | verse::Trapped | 133.300 | loss::Verdict |
| 74.045 | organic::Organic | 147.660 | exec::Barrage |
| 82.589 | organic::Deity | 162.632 | exec::FinalExec |
| — | — | 177.246 / 191.356 / 205.811 | love::Love / LoveTrapped / Shutdown |

**场景内一律用"相对本幕已过的时间"**：`v.scene_progress = ((v.t-start)/(end-start)).clamp(0,1)`（main.rs:201），`Ctx::new(..., (v.t - start).max(0.0), dt, ...)`（main.rs:206-215）。View::update 里注释写明了理由：*"用绝对时间差而不是累加 dt：既保证离屏渲染能复现，也保证拖动进度条之后动画立刻处于正确状态"*（view.rs:83-88）。

**过渡**：idx > 0 时在切点用 0.24 s 衰减脉冲做 CRT 换台（`fx::pulse(v.t-start, 0.04, 0.20)`），叠 `glitch(0.14*tr)` + 整体向白混合 0.22/0.12（main.rs:222-232）。CHANGELOG.md:27-28 说明这是 v1.2.0 加入的"全局场景开头 CRT 闪断"。

**后处理强度按时间段门控**（main.rs:235-254）：处刑段（147-164 s）辉光 `0.40 + hit*0.25`、故障 `0.30 + hit*0.25`；125-148 s 故障 `0.08 + hit*0.10`；205-207 s 故障固定 0.5；其余 0。**hit 是低频相对 0.15 s 前的增量**（view.rs:77-79：`hit = ((bass - bass_at(t-0.15))*4.0).clamp(0,1)`）——把打击感做成一个可复用的标量。

**"孤独"段落整屏去饱和**是另一条纯时间曲线（main.rs:265-277）：106.8→118 s 升到 0.82，118→127 s 降回 0.27，127→135 s 再升到 0.5。

### 3.4 ③ 数据结构【确认】

Rust 侧没有 JSON：**歌词与频谱都是运行期算出来的**。

- `Lyrics { lines: Vec<Line> }`，`Line { t, en, zh: Option<String>, tokens: Vec<Token>, width, rep }`（lyrics.rs:12-33）。
- **双语对齐不是按序号配对**：中文文件行数与 LRC 不一致，所以用"向前 5 行的窗口 + 归一化精确匹配"（lyrics.rs:121-135），归一化 = trim + 大写 + 双空格合一（第 121 行）。
- **关键词标注在解析期完成**：tokenize() 把一行拆成 token，命中 theme::is_keyword 的 token 带 Kw 枚举（lyrics.rs:58-82）；Line.rep 记录**同文连续重复的序号**，供 EXECUTION ×12 连打使用（第 136-141 行）。
- 查询用二分（Lyrics::current，第 157-175 行）。
- `Spectrum { bands: Vec<[u8;32]>, bass/mid/high/rms: Vec<u8>, peak_beats: Vec<f32> }`（audio.rs:31-39）——u8 量化存储，换取小内存与位精确复现。
- View（view.rs:15-38）是"每帧一次的快照"：频段数组、bass/mid/high/rms/pulse/hit、场景序号/进度、`Link { Linked, Unstable, Lost }`、lyric_idx、lyric_since。**所有场景只读 View，不自己去查音频**。

### 3.5 ④ 字符画与色彩渲染【确认】

**画布**：`Cell { ch: char, fg: Rgb, bg: Rgb }`，`Canvas { w, h, cells: Vec<Cell> }`（buf.rs:64-69, :180-185）。真彩 Rgb + mix/mul/add/lum/desat（:19-61）。

- **宽度**：cw() 手写 East Asian Width 区间表，含 0 宽（组合符、ZWSP、变体选择符）与 2 宽（含 CJK 扩展 B 到 0x3FFFD）（buf.rs:88-114）；sw() 是字符串宽度（:117-119）。
- **宽字符占位**：`SKIP = '\u{0}'`（:72）；put() 在宽字符时把右格写成 SKIP，右格贴边时降级为空格（:270-298）。term 与导出器都显式跳过 SKIP（term.rs:84-86）。
- **画布图元**：Bresenham 直线（:394-421）、中点圆（:424-433，**x 乘 2.0 抵消 2:1 格子**，注释写明）、椭圆、整屏平移 shift（震屏）、按行位移 row_shift（故障）、矩形区域滚动 blit_scroll。
- **辉光（无需模糊）**：glow() 把目标格前景向光色混合，背景加 `fg*a*0.10`（:310-318）；text_glow() 先在左右两侧各铺一层（:359-377）——纯字符网格上的低成本光晕。
- **差分刷新**（term.rs:68-108）：逐格比较 ch/fg/bg，只在变化时输出；MoveTo 仅在光标跳格时发；SetColors 仅在颜色变化时发；最后 `prev.cells.copy_from_slice(&cur.cells)`。
- **离屏导出**：frame_to_html（term.rs:113-168）合并同色同宽连续段成 span；frame_to_bin（:223-238）写 **WEMV** 格式。
- **点阵大字**：bigfont.rs:8-94 收录 3~5 列 × 5 行字形（含小写、大写、符号、数字），draw_reveal（:149-182）支持**小数级逐字揭示**（`d = revealed - idx`，d<1 时在 ghost 与 fg 之间混合并补 glow）；bitmap()（:186-206）把字符串变成布尔位图，供字形溶解变形使用（Morph 场景 F→M / S→M，CHANGELOG.md:16, :81-87）。
- **调色板是语义化的**（theme.rs:2-4）：*冷青=机器/数据、品红=爱、正红=执行/死亡、琥珀=警示、灰蓝=孤独*。Kw 六分类（Math/Machine/Organic/Love/Divine/Negative）各自带 colors()（前景亮色 + 底块色）与 accent()（粒子/光晕主色）（:38-77）。heat() 是青→蓝→品红→琥珀的连续色带（:112-120）。
- **特效库全部纯函数 + 确定性噪声**：hash2(x,y,seed)（fx.rs:52-60）是无状态的坐标哈希；Rng 是 xorshift* 可种子化（:11-48）；pulse/smooth/ease_out/ease_in（:63-90）。粒子系统带 life/max_life/ch/col 与 gravity/drag（:296-372），burst() 生成**椭圆分布初速**（`vx = cos(a)*s*2.0, vy = sin(a)*s`，:357-372）——又一次 2:1 格子补偿。
- **字符集分组**（fx.rs:93-108）：RAIN（含数学符号与日文假名）、GARBAGE（块字符与货币符号）、HALF（`▁▂▃▄▅▆▇█` 八级高度）、BLOCKS、SPARK、SHRED。**用 HALF 做小数高度柱**是频谱/进度条的基础（fx.rs:511-530 bar(), :533-556 spectrum()）。
- **数学可视化**：heart_curve 用隐函数 `(x²+y²−1)³ − x²y²·y = 0` 的**阈值采样**（`|v| < 0.0022`）并再描一条边（`|v| < 0.0009`）加粗；y 乘 0.52（fx.rs:416-450）。sine_with_tangent 的切线斜率直接是解析导数 `-(u*8+phase).cos()*amp*8/w`（:453-488）。asymptote 用 sigmoid 采样 `1/(1+e^-x)`（:491-508）。
- **终端 3D 引擎 fx3d**（v1.1.0 新增，CHANGELOG.md:37-41）——这是最"超规格"的部分：
  - 视向光源常量 `LIGHT = (-0.45, 0.62, -0.65)`（fx3d.rs:21）。
  - 深度/明暗字符阶梯：`DEPTH_RAMP = ['@','◆','●','○','·','.']`、`SHADE_RAMP = ['·','░','▒','▓','█']`（:141-142）。
  - 网格生成器全部是纯函数：fib_sphere（斐波那契球，:146-156）、icosa_mesh、latlong_mesh、box_mesh(sub)、floor_mesh、torus_cloud、knot_cloud(p,q)（(p,q) 环面纽结，p=2,q=3 为三叶结，:289-316）、heart_cloud（隐式心形轮廓绕 y 轴旋转，:319-343）、revolve_cloud(prof, squash, nring)（通用旋转体，茄子/番茄复用，:346-369）、galaxy_cloud（旋涡星系点云，:371-391）、Warp（超时空星流，:586-630）。
  - 相机：`R3 { focal = h*2.0, cam_z = 3.2, near = 0.10, zbuf }`（:432-457）；投影 screens() 里 **y 乘 focal*0.5**（:469-471）。
  - plot() 做 Z-Buffer 测试并写入（:483-495）；cloud() 深度→字符+颜色（:497-517）；surface() **双面兰伯特** `n.norm().dot(LIGHT).abs().powf(0.6)`（gamma 提亮中间调）+ 深度雾（:519-547）；wire() 做**近平面裁剪**并用沿线插值的深度写 Z-Buffer（:549-582）。
  - 所有生成器都是"在 new() 里预计算网格，draw() 里只做旋转+投影"——这正是它能在 --shots 离屏逐帧复现的前提（fx3d.rs:9-10 注释）。

### 3.6 ⑤ 逐帧导出到 mp4 的管线【确认】

**答案：不是"离屏渲染 → PNG → ffmpeg"，而是"离屏渲染 → 自定义二进制 .bin → PIL 光栅化成 RGB 图 → ffmpeg stdin 收 rawvideo"。**

1. Rust 端 `--render-video <dir>`（main.rs:581-628）：固定 160×48 画布，`frames = (dur*60).ceil()`，`DT = 1/60`，从 t=0 **顺序**推进（注释明说"顺序推进本身就是预热"），每帧 term::frame_to_bin(&canvas) 写 f_%05d.bin。
2. **WEMV 格式**（term.rs:223-238）：magic "WEMV" + u32 w + u32 h + 每格 10 字节（fg.r/g/b + bg.r/g/b + u32 codepoint）。仓库里 gallery/v1.0/frames/all_*.bin 就是这格式，**实测** 160×48、每文件 76 812 B（= 12 + 160×48×10 ✓）。
3. Python 端 tools/render_video.py：
   - Rasterizer 为**每个字形只渲染一次 L 模式遮罩**，之后用 `img.paste(tile, pos, mask)` 合成（注释：*"比纯 text 快一个数量级"*，第 26-33 行）；颜色**量化到 5 bit/通道**（`& 0xF8`）让拼贴缓存规模有界（第 96 行）。
   - 输出用管道而非中间文件：`ffmpeg -f rawvideo -pix_fmt rgb24 -s WxH -r 60 -i pipe:0 -i <audio> -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart [-vf scale=1920:1080:flags=lanczos]`（:154-161）。
   - 1080p 是**渲染后再放大**（lanczos），原始字符网格 160 格 × 8.4 px ≈ 1344×768（--noscale 可保留）。
4. 开发期视觉校验用另一条支路：`--shots t1,t2,...` 输出 HTML 与逐帧 .bin（main.rs:632-698），tools/render_frames.py 把 .bin 纵向拼成 PNG，tools/shoot.sh 用 agent-browser 打开 HTML 截图。
5. **离屏必须"预热"**：shots() 从 t-4 s 起按 60 fps 逐帧步进到目标时刻（main.rs:666-680），注释：*"否则离屏单帧看到的是'刚进场景第一帧'的假象"*。render_video 因为是从 0 顺序推进，天然等价于预热。

### 3.7 B 仓库可复用点小结

1. **Clock{base, anchor} + sync(audio_pos) + "跑飞阈值"** 是实时音画同步最省事又稳的写法。
2. **启动时离线算完整首歌的包络 + 播放期 O(1) 查表**，把抖动问题从运行时移到启动时。
3. **95/98 分位归一化**比峰值归一化在实际音乐上稳得多。
4. **View 作为"每帧计算一次的只读快照"**，让所有场景的输入面收敛成一个结构体。
5. **离屏与实时共用同一个 render_frame**，再用"预热步进"补齐依赖 dt 的状态——这是"截图即真相"的关键。
6. **.bin 帧格式（含 codepoint）比 PNG 序列小一个数量级**，且把光栅化留给外部工具（可以在不改 Rust 的情况下换字体/换分辨率）。
7. **字符网格上也能做正经 3D**：2:1 格子补偿 + 每格 Z-Buffer + 双面兰伯特 + 近平面裁剪，成本约 700 行。

---

## 4. 仓库 C：MisakaZentai/world-execute-me-dsh-pv

这是三个里最接近"目标形态"的一个：**左右双画面 + 逐帧纯函数 + 一帧一页截图 + rawvideo 出片**。

### 4.1 架构总览【确认】

README.md:57-71 与 docs/HOW_IT_WORKS.md 给出结构，与源码一致：

- **右边「她所在的世界」**：PIL 手绘的 TUI 风格模型可视化引擎。
  - film/tui_pv_world_execute_20260926/tuikit.py（476 行）：画字、画框、配色、halfblock/字形立绘、后期（辉光/残影/扫描线/渐晕）。
  - full/：第一版镜头（sec_*.py）、镜头表（engine.py + direction.py）、转场（transitions.py）、音乐特征（music.py）、编排（choreo.py）、骨架（rig.py）、舞者（dancer.py）、舞台布局（stage.py）。
  - continuity_full_v2/：第二版，重排全部镜头连续性与转场（s_*.py、scenes_*.py、cuts.py、v2.py、kit.py），含逐字歌词条（words.py）。
- **左边「聊天窗口」**：dsh 网页前端。
  - film/pv_dsh_frontend_20260927/build_frame.py（197 行）：用 dsh 自己的 CSS/类名/SVG 图标拼出**一张静态 HTML**；batch_*.py 按时间批量生成；seg_page.py 生成 seg.html 的逐帧 body。
  - seg_shot.mjs：Playwright 无头 Chromium 把每帧的 HTML 截成 dsh_frames/NNNNN.png，`NNNNN = round(t × 24)`。
  - **没有 dsh 进程、没有服务器、不调用任何模型**（docs/HOW_IT_WORKS.md:14）。
- **合成器**：film/pv_dsh_frontend_20260927/dsh_her.py（371 行）。

### 4.2 ① 音频时钟与逐词同步

**核心哲学（docs/HOW_IT_WORKS.md:3）：** *"每一帧都是歌曲时间 t 的纯函数：24 fps，画布 1280×720。不用视频剪辑软件，也没有手工关键帧。"*

也就是说：**没有实时时钟**。帧号就是时间：`t = n / FPS`，`FPS = 24`（engine.py:32），总帧数 `int(round(END_T * FPS))`，`END_T = 211.0`（engine.py:38, :484-485）。这一点与 A/B 仓库是根本差别——C 把"同步"问题换成了"渲染可复现"问题。

**节拍网格是显式常量并在多处复用**（engine.py:32-36）：

```
FPS = 24
BPM = 130.0
BEAT = 60.0 / BPM
FIRST_BEAT = 0.1587          # 来自 audio/beats.json
SONG_LEN = 211.91
HARD_CUT = 207.58            # 对源 mp3 做 silencedetect -50 dB 的结果
```

派生工具：beat_t(n)、snap8(t)（把任意时刻吸附到 1/8 拍网格）、beat_index(t)、`pulse(t, decay=0.14) = exp(-(t - 最近一拍)/0.14)`、keyframes(t, [(t,v),...]) 线性插值曲线（engine.py:54-77）。**注意到 C 用"显式 BPM 网格"取代了 B 的"谱检测重音点"**：v2.py 里甚至把 BPM 精确到 130.000（kit.py:36 注释："the hi-hat onsets of the whole song fit 130.000"）。

**逐词时间轴 → 逐字出字**（continuity_full_v2/words.py）：

- 数据源是 world_execute_word_timing_20260927/word_timeline.json（构建时由 tools/lyrics.py merge 生成，**文字不随仓库分发**）。
- lines()（words.py:34-62）把每个词映射成字符区间 + onset + 出字时长：
  - 正常词：`td = min(MAX_TYPE=0.25, 词的歌唱时长)`；
  - **带连字符的拖长音**（代码注释举例这种 melisma 写法）：`td = 整个音长`，所以整段拖音是慢慢打出来的（第 52 行）。
- typed(ln, t)（:75-90）返回"此刻已经出了几个字符"和"每个字符出现的时刻"，**字符按词内线性均分 onset→onset+td**；词后的空格与标点**跟随词的最后一个字母同时出现**（第 83-86 行）。
- 换行/淡出策略（:55-62）：下一行开始时本行才消失；若下一行距本行结尾超过 `BREAK = 2.0 s`（间奏），则本行**多停一拍**再淡出一拍。
- 打字机闪烁复用 tuikit.decode 的闪烁字符集，但时钟换成"每个字母自己的出现时刻"（flicker，:96-99，`SETTLE = 0.08`）。

**顶栏换成了歌本身的实时波形**（dsh_wave.py）：

- 预计算 1 ms RMS 存 wave_rms_1ms.npy（:29-45）。**实测**：shape `(211912,)`、float32、归一化到 99.5 分位，即 211.912 s ——与歌曲长度一致。
- 绘制时取"最近 `SPAN = 2.4 s`"，映射成镜像峰值柱（`BAR = 3` px，1 px 柱 + 2 px 间隙），**柱的亮度随新近度上升** `lit = (0.14 + 0.62*age**1.8) * (0.65 + 0.35*v)`（:58-73），最右端一个随当前电平呼吸的圆点。
- 电平映射：`level(rms) = clamp((rms - LO)/(HI - LO))**GAMMA`，`LO=0.05, HI=0.62, GAMMA=1.1`（:25, :48-49）——**显式标定区间**而不是归一化到 0..1，注释给了实际分布（12 ms RMS 跨度约 0.06-0.85，中位 0.26）。

**音频特征表**（full/music.py，供第一版引擎与立绘反应使用）：
- `RATE = 48`（每 0.0208 s 一行），7 个频段 `[(40,120),(120,300),(300,700),(700,1500),(1500,3000),(3000,6000),(6000,10000)]`（music.py:36-37）。
- 用 **ffmpeg 滤波器**做分带而不是自己写 FFT：`highpass=f=lo` 两次 + `lowpass=f=hi` 两次（:71，双重滤波换取更陡的滚降）→ `s16le / -ac 1 / -ar 22050`。
- 派生量（:69-87）：loud（整体 RMS，非对称跟随 0.6/0.15）、bands（0.6/0.18）、`kick = onset(bass)`（0.9/0.2）、`flux = Σ onset(每带)`（0.9/0.25）、cent（300 Hz-6 kHz 段的能量质心，用 `log2(sqrt(lo*hi))` 作对数中心，先取 5%/95% 分位归一化）。
- 基础算子只有三个：_norm(v, q=0.98)（**98 分位归一化**，:51-53）、_follow(v, attack, release)（非对称一阶跟随，:56-61）、`_onset(v) = v - _follow(v,0.08,0.08)` 后非负归一化（:64-66）。
- 结果缓存在 audio_features.json：**实测** keys `['rate','loud','bands','kick','flux','cent']`，rate=48，loud/kick/flux/cent 各 10 180 行，bands 为 7 × 10 180。
  - 10 180 / 48 = 212.08 s；而 kit.fix_clock()（kit.py:43-60）指出**真实行率是 22050/459 = 48.039 行/秒**（一行 459 采样），并按此重设 music.RATE —— 这是一个非常具体的"特征表时间基"陷阱修正，值得照抄其做法（把行率写成由采样率和 hop 推出的表达式，而不是硬编码整数）。

### 4.3 ② 场景状态机与转场

**第一版（full/）：镜头区间表 + 强制无缝 + 转场窗口。**

- `Shot { start, end, fn, chapter, alert, params }`，add(...) 追加，finalize() 做三件事（engine.py:351-374）：
  1. 排序后**断言相邻镜头首尾严格相接**，否则抛 `timeline gap/overlap`；
  2. **断言覆盖 0..END_T**；
  3. 为每个切点向 direction.transition(a,b) 要一个转场规格，并换算成"窗口"：`pre = min(0.7n, 0.6*a长)`、`post = min(0.3n, 0.4*b长)`——**"动作落在切点上：大部分在切点前完成，尾巴在切点后落定"**（:371-373 注释）。
- 切点编号即镜头编号；shot_at(t) 线性查找（:387-391），transition_at(t) 查窗口（:380-384）。
- render_frame（:449-479）优先走转场窗口：先把 A、B 两个 body 各渲染一次，再按 kind 分派到 transitions.apply；**glide 有"降级规则"**——如果任一侧是黑场/无 chrome/raw 模式，就退化成 reflow（:463-469）。
- **布局表 LAYOUT（direction.py:11-101，79 条）**：每条是 `(mode, kind, extra)`，mode ∈ raw/shell/fullbleed/floating/pip/mirror/cinema/tiles/split（stage.py:5-14 有完整语义说明）；kind 是 split（她 + 可视化两栏）或 full（整幅）。extra 携带 shell 命令行，如 `{"cmd": "ls -la ~/memory/you/"}`（direction.py:68）。
- **有"数据驱动的退化序列"**：`YOU_LEFT = ["tiles","floating","split","pip","shell"]`（:104）——同一个 shot_you_left 函数被重复登记多次（sec_chorus2.py:370-372），每次 k+1 就剥掉一层界面，把"你走了"表达成 UI 逐层脱落。
- **EXEC_HIT 表**（:106, :115-118）按 `k % 4` 与 `k==11/>=12` 决定命中的布局与 kind，让 12 连击有节奏变化而不是复制粘贴。
- **转场表 CHOREO（44 条，direction.py:137-220）的写法本身就是文档**：每条前面一行注释说明"为什么这样切"，例如"boot 日志不是结束，而是重排成受保护的启动"→reflow；"推入盾牌：它保护的是权重"→`zoom a=(792,170,1017,494) b="screen"`。**默认是 glide（11 帧），显式 None 表示硬切**（:223-231）。
- check_variety()（:234-240）是一个自检：**相邻镜头布局相同就报错**（处刑连击例外）——把"视觉单调"变成可执行的断言。

**转场实现（transitions.py）各自的数学**：

| kind | 做法 | 代码 |
|---|---|---|
| reflow | 两侧图各自降采样到 7 px 格，取亮度 > 38 的点；用 **Hilbert 曲线索引**排序，使邻近格在序列里也邻近；最多 1500 个粒子沿**带弯曲的弧线**从 A 的点飞向 B 的同序号点，颜色线性插值并提亮 `min(255, v*1.5+30)`；A 在 q<0.35 内淡出，B 在 q>0.62 后淡入 | transitions.py:28-92 |
| pane_dissolve | 每格一个随机阈值，`thr < q` 的格切到 B；`abs(thr-q) < 0.08` 的格画成解码乱码块（"正在翻转的格子"） | :95-112 |
| zoom | _warp 用**等比缩放** `s = sqrt((dw/sw)*(dh/sh))`、中心对齐，把 A 的矩形映射到 B 的矩形，两帧各 warp 到同一中间矩形再在 p=0.3..0.75 混合；s > 1.8 时用 NEAREST 保持像素感 | :117-132 |
| pan | 两场景在空间上相邻：向右平移时 A 左移、B 从右侧进入；**再把 p 与 p-0.012 两帧混合 0.3 制造运动模糊** | :135-143 |
| spin | 旋转 220°，中间缩到 1-0.38 | :146-160 |
| crt | 前半段 A 高度压扁成一条线，后半段 B 从线展开，中线画一条白线 | :163-175 |

**glide（默认转场）是"布局本身在动"**（stage.py:397-445）：取 A、B 两个 mode 的 geometry() 元素表，同名元素（me / viz）做矩形线性插值，只在一侧存在的元素向中心塌缩（_collapse）；元素内容按类型换形——me 用 pane_dissolve，viz 用 reflow(n=900)；chrome 单独渲染成透明层后按 e 交叉淡化（chrome_overlay，:378-383）。

**第二版（continuity_full_v2/）：Cut 类按切点索引接管。**

- 模块自述（cuts.py:1-6）：*"A cut owns a window around its time T. Inside it, the outgoing scene keeps running past its end and the incoming one starts on time; the cut decides which objects cross (drawn as ink on the carrier layer), how the rest of the old drawing gives way (per-cell glyph switch from a seed, never a band wipe), and whether she reacts."*
- `Cut.pre, post = 0.3, 0.5`；`active(t) = T-pre <= t < T+post`；old(t) 允许**旧镜头跑过自己的 end**，new(t) 用 `max(t, T)` 保证新镜头按计划开始（cuts.py:63-82）。
- **"carrier"（载体）机制**：跨切点的物体**以"墨"重画，而不是搬运已完成帧的截图**。`kit.ink(img, t, rect)` 用 `|当前帧 - stage.background(t)|` 求出笔画 alpha（:280-289）——因为背景是已知的纯函数（点阵网格），这一步是精确可逆的。
- **逐格切换而不是整条擦除**：`kit.reveal(old,new,t,delay,region,cell=(8,16),dur=0.09,density=0.4)` 对区域内每个格子算自己的切换时刻（`delay(cx,cy)` 由 radial / inward / sweep 生成），未到时刻用旧帧、到了用新帧，**正在切换的格子画一个解码字形**（:348-395）。三个 delay 生成器：radial（从种子点环形扩散）、inward（**离种子越远越先走，种子最后走**——"画面被吸进一个点"）、sweep（沿方向投影的线性扫过）（:398-414）。
- **v2.py 的分段插件协议**（v2.py:7-20 文档）：每个 section 模块可导出 STUB / REPLACE / SPLIT / FULL_ART / SHELL / CUTS / HIDE_HER / OVERLAY / OWN / setup(v1)。CUTS 的键是**v1 的镜头索引**（"audit numbering"），所以新转场能精确挂在既有切点上而不改动 v1 时间表（:97）。
- **v2 的逐帧分层顺序被固定并写进文档**（kit.py:3-9）：① 场景自身（无她）→ ② carriers（跨切点的墨）→ ③ 她（同一个字符串舞者，同一个 pane）→ ④ chrome + 歌词带（**每帧只画一次，永不参与变换**）→ ⑤ CRT 后期。
- **"她"被抽成一个统一渲染器**：kit.me_stub 替换各场景模块里的 me_pane，场景只声明"她此刻是什么表情/什么 title/softmax"，实际渲染由 `kit.her_layer(t, call)` 负责（kit.py:85-132）。这就是"同一个她在所有场景里都不换脸"的实现方式——**把角色从场景里解耦**，是这套代码最值得学的一处架构决策。
- **`her_anchor(t, part)` 用已渲染立绘的 alpha 通道测出"头/胸/伸出的手"的屏幕坐标**（v2.py:228-246），供"从她身上飞出/飞入"的载体使用——不依赖美术给锚点，靠图像本身测量。
- 附加的细粒度控制：slide_at(t)（全宽镜头前 0.3 s 把她的 pane 向左滑出，之后 0.35 s 滑回）、retract_at(t)（shell 模式时 header 上移 + ticker 右移并变暗，歌词带永不动）、_Draw 代理（把"贯穿她的那一条音高扫描线"暂存起来，在她剪影内绘制）（v2.py:142-166, kit.py:150-166）。

### 4.4 ③ 数据结构（实测 schema）

| 文件 | schema | 实测 |
|---|---|---|
| data/song.json | `{title, sha256, duration_s, codec, sample_rate, channels, bit_rate, note}` | duration 211.913；mp3 44100 Hz 2ch 320 kbps；sha256 前缀 79c4e53663c7… **【实测】** |
| data/timing/lyrics_synced_notext.json | `{about, target, sha256, format{encoding,newline,final_newline}, lines[{tag, pre, post, len, sha256}]}` | 102 条计时行；首 tag 00:00.03，末 tag 206.3 s；**只有每行文字的长度与 sha256，没有文字** **【实测】** |
| data/timing/word_timeline_notext.json | 顶层 `{about,target,sha256,format,patches,lines,skeleton}`；skeleton = `{schema_version:1,title,status,audio,audio_sha256,time_unit:"seconds",time_origin:"decoded supplied MP3 at t=0",duration:211.886,global_offset:0,method,timing_note,lines[98],words[395]}` | 每条 line`{id,text,source_lrc_start,start,end,display_end,words}`；每个 word`{index,line_id,word_index,text,start,end,review_flags,candidate_spread_ms,candidates[4]}` **【实测】** |
| data/h3_takes.json | `{about, fps:24, caches[{folder, read_by, takes{<take>:{frames, rgba:[[first,last],…]}}}]}` | 用于校验"舞者缓存帧数/索引是否齐全" **【实测】** |
| full/audio_features.json | `{rate:48, loud[10180], bands[7][10180], kick[10180], flux[10180], cent[10180]}` | 全部为 0..1 浮点 **【实测】** |
| 运行时 cursor.json | `{x,y,w,h,n}` —— .cur 光标的 bounding rect | 由截图脚本实测 DOM 得到 **【确认】** |
| pv_dsh_frontend…/disclosure_map.json | dsh 前端混淆类名到语义名的映射（root/row/leading/title/chevronHover/iconIdle） | 用于让页面脚本不直接写哈希类名 **【确认】** |

**skeleton.method / status / review_flags 是这份数据最有价值的部分** **【实测】**：

- `status = "AUTOMATIC_DRAFT_REQUIRES_LISTENING_REVIEW"`。
- `method = "HDEMUCS vocals; MMS_FA and Whisper medium.en forced alignment; bounded LRC search; median of model families"`。
- `timing_note = "These are acoustic alignment estimates, not frame-accurate human-verified onsets. End is approximate; use start for reveal."` —— **明确写了"end 不可靠，出字只用 start"**，并且下游 words.py 确实只用 start 驱动揭示（words.py:75-90）。
- 每个词的 candidates 保留 4 种方法的原始结果：mms_line / whisper_line / mms_block / mms_initial（各 395/395/393/393 条），candidate_spread_ms 记录族间分歧，**实测** min 0 / median 87 / max 1797 ms。
- review_flags 直方图（**实测**）：onset_disagreement_gt_200ms 118、single_model_family 46、lyric_text_review 7、multilingual_counting 6、short_word 2、monotonicity_repair 2。
- patches（1 条）用**可审计的操作**修正词序：`{"op":"reorder_words","order":[0,2,1,3],"why":"…"}`；tools/lyrics.py:153-164 只认识 reorder_words 与 replace_words 两种 op，其它直接报错退出。

**这套"存时间与哈希、不存文本"的方案是可分发性与可复现性的结合**，是 C 仓库最值得抄的数据设计。

### 4.5 ④ 字符画与色彩渲染

**tuikit.py —— 字符/终端美学的唯一来源。**

- **配色是语义化的三套调色板**（tuikit.py:27-48），由 `TUI_PALETTE` 选择：amber（琥珀荧光 + 异常绿）、deepsea（冷白钢铁 + 日志黄）、phosphor（绿荧光 + 黄）。语义名固定为 BG / UI(AMBER) / ERR(RED) / ANOM / ME_LO / ME_MID / ME_HI / ME_TEXT，其中 `ME_MID = DS_BLUE = (77,107,254)` 就是 DeepSeek 品牌蓝 #4D6BFE（:26）。
- **`mix(c, level, base=BG)` 是所有颜色的唯一入口**（:63-65）；`amb(level)` 额外乘一个全局 `UI_GAIN[0]`（:68-73）——UI_GAIN 由引擎按时间曲线设置（engine.py:91-94）：*"系统色是'你'。你离开时它被抽干，而且再也回不来。"* 0-110.4 s = 1.0 → 116.5 s 掉到 0.42 → 176.9-179.5 s 回升到 0.85 → 206 s 再降到 0.45。
- **打字机 + 乱码闪烁**：`decode(s, age, rng, rate=45, settle=0.12, corrupt=0)`（:105-120）——第 i 个字符在 `age - i/rate < settle` 期间随机替换成 `SCR = "!<>-_\\/[]{}=+*^?#%$&@01|~:;"` 里的字符；corrupt 让任意字符按概率持续乱码。**"每个字符只有它刚出现的 0.12 s 在闪烁"**，非常廉价但观感极好。
- **假 BPE 分词**：tokenize() 按正则切词与标点，**长度 > 7 的词再对半切**（:123-132）；`token_id(tok) = crc32(tok.lower()) % 100000`（:135-136）。歌词条上每个 token 下方标出这个 id —— 用 20 行代码做出"这是 token 流"的观感。
- **half-block 立绘**：halfblock_lum 把立绘缩到"每 px×px 一格"，亮度量化成 8 级（`(0.16 + 0.84*v/255)*(levels-1)`），alpha 二值化阈值 100（:179-190）；halfblock 用 NEAREST 放大并把 grid_mask（每 px 列画一条黑线、每 2px 行画一条 70/255 的线）乘进 alpha（:155-164, :193-202）——**这就是"半块字符"的实现：不是真的用 ▀▄，而是用单元格网格把位图切碎**。
- **字形立绘（glyph art）**（:239-304）：立绘缩到 cols×rows 后，用两个 3×3 卷积核求 x/y 梯度（:247-248），
  - 梯度模 > 1.1 的格子 → **按梯度方向选方向笔画**：角度落到 4 个 45° 分箱，输出 `| \ - /`（:262-265）；
  - 其余格子 → 用 `GLYPH_RAMP = " .:-=+*#%@"` 的密度字符（:267）。
  - 这个"边界定向 + 内部密度"的两段法，让 ASCII 人像的轮廓远比纯密度 ramp 清楚。glyph_sprite 还支持 scramble（换乱码）与 reveal（随机隐藏比例）做"重组/解体"（:273-304）。
- **横幅大字**（:310-328）：用 Anton 字体在 220 px 渲染 → 裁到 bbox → **下采样到 rows×rows*cell_aspect 的位图** → 阈值 110 二值化 → NEAREST 放大 + grid_mask。即"用真字体做点阵大字"的通用做法。
- **终端边框**：box()（:333-348）画矩形 + 四个角的**加长角标**（每角两条 7px 粗线）+ 带 spinner（`|/-\`）的标题贴片（标题处先用 BG 色盖一条底再写字）。
- **后期 post()（:468-476）只有四步，20 行**：
  ```
  if prev is not None: img = ImageChops.lighter(img, prev.point(lambda v: int(v*trail)))   # 残影
  glow = img.filter(ImageFilter.GaussianBlur(4)); img = ImageChops.add(img, glow.point(lambda v: int(v*bloom)))
  img.alpha_composite(scanlines())        # 每 3 行一条 alpha=55 的黑线
  img.alpha_composite(vignette(lift))     # 64×36 的 L 图双线性放大
  ```
  默认 trail=0.42, bloom=0.35。scanlines() 与 vignette() 都是 lru_cache 的静态图（:441-447, :453-465），所以每帧只是两次 alpha_composite——**"预渲染滤镜贴图"比每帧算快得多**。渐晕有 LYRIC_LIFT 开关，避免压暗底部歌词带（:450, :454-462）。
- **dsh_gpu.py（可选）把后期搬上 GPU**：分离式高斯（核半径 12，sigma 4，对应 PIL GaussianBlur(4)）、`torch.maximum(x, floor(p*trail))` 复现残影、扫描线用 `x[:, 0::3, :] *= 200/255`。注释给了收益：CPU 后期约占一帧 40 %（PIL 的 1280×720 高斯模糊单独约 30 ms）（dsh_gpu.py:2-4）。`dsh_gpu.py check <t>` 会打印 CPU/GPU 同一帧的 mean/p99/max 差（:85-97）——**给优化留了可测量的验收口**。

**video_ascii_v1/convert.py —— "视频 → 字符视频"的完整工程实现**（227 行，是 ④ 和 ⑤ 的交叉点）：

- 预设 `PRESETS = {'readable': (6,12,11), 'dense': (6,10,10)}`，即 (格宽, 格高, 字号)（:12）；`RAMP = ' .,:;irsXA253hMHGS#9B&@'`（20 级，:14）。
- **背景不是去掉的整块，而是"边缘连通的 flood fill"**（:61-99）：先按颜色容差（默认 20）判定"候选背景格"，再从**四条边界**做 BFS，只把与边界连通的候选取掉——注释：*"Only border-connected background is removed. Interior dark cloth survives."* 另有独立的 --white-pockets 通道处理"封闭的纯白口袋"，且要求 `max(rgb)-min(rgb) <= 5` 以保护偏白布料（:93-99）。
- **方向笔画 + 密度字符**（与 tuikit 同思路，但用中央差分）：`dx = lum[right]-lum[left]`, `dy = lum[down]-lum[up]`；`strong = |dx|+|dy| > 76`；边角分成 4 档（`|dx| > 1.7|dy|` → `|`，反之 → `_`，同号 → `/`，异号 → `\`）（:100-110）。
- **时间一致性（抖动抑制）**：`hysteresis = 3`——上一帧不是空格、当前候选与上一帧不同、且亮度差 ≤ 3、每通道差 ≤ 8，**且该格当前和上一帧都不是边**，就保留旧字符（:112-118）。注释强调：*"No averaging, spatial history or trails. Moving/strong edges never hold."* 即**只在阈值附近抑制闪烁，绝不引入拖尾**。
- **颜色量化**：`min(248, max(82, round((v*0.83+39)/16)*16))`（:121）——先把暗部抬到 82 再 16 级量化，保证字符在所有视频上都可读。
- **管道与自检**（:147-166, :200-214）：ffmpeg 解码成 rawvideo rgb24 走管道，同时喂给"彩色"和"单色诊断"两个编码器；结束后对每个输出做 ffprobe 与整片解码复检，并**断言**：时长误差 ≤ 1 帧、编码/解码帧数差 ≤ 1、帧率一致、尺寸一致、音轨有无一致、输出 sha256 记录进 manifest.json；还有 VFR 检测与 source_pts_quantization_max_seconds 报告（:143, :210）。
- 另外生成 comparison.png（源帧 vs 字符帧对照）与 index.html 复核页（:195-198, :220-223）。

### 4.6 ⑤ 出片管线（最详细的一条）

**总思路：左右两条完全不同的渲染路径，在 dsh_her.py 里按帧合并。**

**Step 1｜左画面 = 一帧一张 HTML + Playwright 截图**（build.py:35-38, :103-106）

- 9 个页面组按顺序跑：batch_a1, a2, a3, b, c, seg_page, e, g, f（build.py:35）。每组脚本先写出 <组>_frames.json，每条形如 `{n: 帧号, t: 秒, body: "<div…>…</div>", sheets: [启用的样式表 id], measure: bool}`（batch_a1.py:186-188）。
- 页面组的时间范围（**实测** grep）：a1 5–16、a2 16–29.28、a3 29.28–44、b 44–73.54、c 73.54–103、seg 103–125、e 125–147.5、f 147.5–177、g 177–212。合计约 4966 帧，与 README.md:55 自述的 **4968 张窗口截图**一致。
- seg_shot.mjs 每帧只做三件事（:19-42）：viewport 固定 **354×537**；page.evaluate 注入 body HTML（用 app.dataset.body 缓存，避免重复 innerHTML）、按 sheets 开关 link、**遍历 `document.getAnimations()` 把所有 CSS 动画 pause() 并设 `currentTime = (t*1000) % duration`**；然后 page.screenshot 输出 dsh_frames/%05d.png（%05d 就是 `n = round(t*24)`）。
  - **"动画时间 = 歌曲时间"这一招是整条管线可复现的关键**：CSS 动画不再由真实时钟驱动，因此同一帧永远得到同一像素。**【确认，注释在 seg_shot.mjs:2】**
  - `measure: true` 的帧追加测量 .cur 光标的 getBoundingClientRect() 并写入 cursor.json（:43-50）——**排版数据由浏览器实测回收，而不是靠代码猜**。
- 页面本身是"用真前端的 CSS 拼静态 HTML"：seg.html 按 id 挂载 7 张样式表（s-vendor/s-index/s-components/s-palette/s-bare/s-code/s-pv），其中 s-palette 只是覆盖一组 CSS 变量（:5）就完成换肤；build_frame.py 用 icons.py:svg() + dsh 的类名拼出思考行/工具调用/用户气泡/回复/操作栏/输入框/统计 pill 等组件（build_frame.py:21-129）。**没有 dsh 进程、没有网络请求。**

**Step 2｜右画面 = PIL 逐帧（详见 4.2-4.5）**

**Step 3｜合成 = 运行期 monkeypatch（dsh_her.py:128-293）**

这是全仓库最"非常规"但很实用的设计：**不改动 v2 引擎的源文件，而是在内存里替换若干函数**，把"她"的窗格换成那一帧的 dsh 截图。

- `kit.her_layer(t, call, box_level)` 被整体替换（:161-193）：
  - 不在 COVER 内 → 调原函数；
  - 在 `GONE=115.42` 到 `BACK=121.77` 之间 → **只画一个闪烁的实心方块（光标）**，颜色就是品牌蓝 (77,107,254)（:164-172）——"界面被拆到只剩一个光标"；
  - 否则取 dsh_frame(t)（`n = round(t*24)`）按 pane 内缩 `INNER=(3,9,3,3)` 缩放粘贴，再按 levels(t)[0] 设整体 alpha，并用 tk.box 画 pane 边框、标题改成 "dsh web"（:173-191）。
- **推拉镜头为什么还能作用在截图上**：因为 v2 的镜头编排作用在 her_layer 返回的那一层上，替换只改变了"层里画什么"，没改变层的几何契约（dsh_her.py:3-6 的说明）。**【确认】**
- 其他被替换的入口（:128-293）：tk.box（改 pane 标题）、kit.scan_mix（COVER 内不做上下重绘扫描过渡）、v2.her_anchor（DEPLOY 段锚点改成头像方块 `AVATAR_C=(69,105)`）、**所有模块 globals 里的 me_pane**（:263-265，用 `_dsh` 标记幂等）、s_chorus1.C26.figure（"从她身上流出的行"改用窗口的行）、以及 v2.OVERLAY / s_deploy.OVERLAY 里的道具叠加（DEPLOY 段道具改挂到头像上）。
- **tk.vignette 被整体关掉**（:146-149）：因为 dsh 窗口 + 歌词已经足够聚焦。注意它是**运行期把 tk.vignette 换成一个返回全透明图的 lambda**，而不是改 post() —— 因为 post() 在调用时才查这个名字。**【确认，注释写明】**
- **LEAD 表决定"这一刻谁是主角"**（:35-37, :99-113）：另一侧亮度降到 `SUPPORT = 0.42`，切换处用 0.25 s 的 ease 交叉淡化；左侧只通过 her layer 的 alpha 降（所以标题/边框不受影响）。
- **finish(im, t)** 是帧级最终修饰入口（:296-310）：登记在 FINISH 列表里的组补丁可以整体接管某段；默认只做"把 RIGHT 区域按 levels(t)[1] 与黑混合"。
- 组补丁（dsh_patch_<g>.py，g ∈ fix, r1, e, f, g, mem, d）统一暴露 `install(D, v2)`，由主模块按顺序导入并调用（:288-291）——**这就是"几百个镜头由多批人/多轮审片分别改动"的协作机制：每组一个补丁文件，互不覆盖主模块。**

**Step 4｜编码与合并（dsh_her.py:313-352）**

```
python dsh_her.py render 0 211.9 film_master.mp4 8
  → ProcessPoolExecutor(8)，把 [n0,n1) 平分成 16 段（parts = workers*2）
  → 每个 worker：ffmpeg -f rawvideo -pix_fmt rgb24 -s 1280x720 -r 24 -i pipe:0 -an <codec> seg_kk.mp4
       master:      -c:v libx264rgb -qp 0 -pix_fmt rgb24   (无损 RGB 母版)
       交付/代理:    -c:v libx264 -crf 17 -pix_fmt yuv420p
  → ffmpeg -f concat -safe 0 -i list.txt -ss t0 -t dur -i song.mp3 -map 0:v -map 1:a -c:v copy -c:a aac 192k
```

- 然后 build.py:118-131 从**无损母版**统一转交付版，并使用 BT.709 全链路标记：
  `-vf scale=out_color_matrix=bt709:out_range=tv,format=yuv420p -c:v libx264 -crf 16 -preset slow -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv -c:a aac -b:a 320k -movflags +faststart`
- 结尾提示音用 filter_complex 混入：`adelay=207873|207873`，`amix=inputs=2:duration=first:normalize=0`（build.py:34, :118-120）。
- **4K 是"像素级 3 倍放大"**：`scale=3840:2160:flags=neighbor` + libx265（:126-130）——因为画面本来就是字符像素画，无需插值。

**Step 5｜v1 的并行出片（对照）**：engine.py:507-542 的 render_video 只在**镜头边界**切分区间（`cuts = {n0,n1} ∪ {镜头起点}`），注释写明原因：*"split at shot boundaries so the phosphor trail never crosses a segment"* —— **并行渲染必须避开依赖上一帧状态的后处理**。v2.py:335-354 则用 `--worker k a b seg` 起独立子进程，每段一个 ffmpeg，再 concat，并顺带用 ffmpeg drawtext 生成 v1/v2 左右对照片。

**Step 6｜开发期校验工具链**

- `--stills t1,t2,…`：单帧 PNG（dsh_her.py:355-364；注意它先渲染 round(t*24)-1 这一帧，因为 CUR[0] 会影响 pane 标题的逻辑）。
- full/build.py --stills / v2 --stills：批量静帧。
- 转场审视：v2.py:368-383 对每个切点用 ffmpeg `fps=12,scale=384:216,tile=5x3` 生成**一张 15 格的切点接触表（strips）**，并写出 cuts_<tag>.json 记录切点编号/时间/类名/文档字符串。
- CPU/GPU 后期一致性：dsh_gpu.py check <t>。

### 4.7 C 仓库可复用点小结

1. **"帧号 = 时间"**：整条管线不需要实时时钟，同步问题退化成"索引对齐"；代价是要一条"逐词时间轴"来驱动出字。
2. **一份数据两种存法**：时间轴存时间+哈希+字符跨度，文字由本地 LRC 在构建时合并，并在写盘前用 sha256 校验"重建出的字节与原文件完全一致"。这是**既不分发版权内容、又能保证复现**的完整解。
3. **渲染期 monkeypatch 做合成**：不 fork 引擎，用"替换函数 + 幂等标记 + 独立补丁文件"来让几十个镜头由多批改动共存。
4. **CSS 动画钉到歌曲时间**再截图，是让网页 UI 逐帧可复现的最短路径。
5. **后期用预渲染滤镜贴图 + 逐帧"与上一帧取亮"**（`ImageChops.lighter(img, prev*0.42)`）：一个 20 行的后处理就得到 CRT 残影 + 荧光溢出。
6. **并行出片必须在"不依赖上一帧状态"的边界上切分**（镜头边界 / 段边界）。
7. **无损母版 + 统一转码**：所有交付版本（720p / 4K / 不同码率）都从同一份 libx264rgb -qp 0 母版派生，避免多次有损编码叠加。

---

## 5. 五个关注点的横向结论

### ① 音频时钟与消息/帧同步

| 问法 | A | B | C |
|---|---|---|---|
| 时钟源 | 独立进程里的 AVAudioPlayer.currentTime | rodio Player::get_pos() + 墙钟插值 | 无时钟，帧号 = round(t*24) |
| 差分刷新 | 每帧全量重画（差分只到"颜色序列"粒度） | **逐格差分**（term.rs:68-108） | 每帧全量 Pillow 图，逐帧编码 |
| 逐帧 vs 逐条 | 逐帧（24 fps）+ 设备时间采样 | 逐帧（60 fps）+ 查询帧表 | 逐帧（24 fps）+ 逐词出字 |
| 防漂移手段 | next_frame += 1/fps 累加目标 + 落后重置 | Clock.sync + t > pos+0.10 护栏 | 不需要（离线） |
| 抖动来源 | 音频设备自身 | 解码块更新的跳变（用墙钟填） | 无 |

**取用建议**：做"终端 live 播放"抄 B 的 Clock；做"纯渲染出片"抄 C 的"帧号即时间 + 离线特征表"；A 的子进程时钟协议适合宿主语言没有音频绑定的场合。

### ② 场景状态机

- A：单一 if/elif 时间链 + 章节常量（最省事，但 3073 行挤在一个文件里）。
- B：Scene trait + Seg.start 线性查表 + 场景内相对时钟（最规整）。
- C：Shot 区间表 + finalize() 强制无缝隙 + **转场表（44 条带动机注释）** + v2 的 Cut 类按切点索引接管窗口（表达力最强）。
- **共同点**：三者都**不用事件队列**，场景切换是"时间的纯函数"，因此 seek/跳转/离屏渲染都不需要额外状态机。

### ③ 数据结构

- 三者的歌词表都带**显式结束时间或"下一行开始时间"**（A 用 end，C 用 display_end / show_until / fade_until 三级）。
- 频谱数据三者都选择**离线预计算 + 时间索引查表**，且都用**高分位归一化**（B 95 分位；C 98 / 99.5 分位）。
- C 多一层**逐词时间轴 + 每词多方法候选 + 评审标记**，是"自动对齐产物如何工程化"的范本。

### ④ 字符画与色彩

- **格子 2:1** 这条约束在三个仓库里都出现，且处理方式一致：y 乘 0.5（或 x 乘 2）。A：scenes.py:614-615；B：buf.rs:424-433、fx3d.rs:469-471、fx.rs:357-372；C：tuikit.py 的 grid_mask 与 cell 宽高比隐含。
- **色彩层级**：A 只用 ANSI 256 色 7 档；B 用真彩但给字符分级（HALF / SHADE_RAMP）；C 用真彩 + 语义调色板 + UI_GAIN 全局曲线。
- **字形来源**：A/B 手写点阵（5×5）覆盖标题与关键词；C 用真字体（Anton/Space Mono）降采样成点阵，视觉上更"现代"。
- **抖动字符集**：三者的乱码字符集都在 20~40 个字符量级，且都偏向"块字符 + 数学符号 + 假名"的混合（fx.rs:93-108、tuikit.py:59、scenes.py:72）。

### ⑤ 逐帧导出到 mp4

| | A | B | C |
|---|---|---|---|
| 中间格式 | 无 | .bin（WEMV，10 B/格） | 左：PNG（Playwright）；右：进程内 PIL 图 |
| 到 ffmpeg | 无 | Python 光栅化 → rawvideo 管道 | 直接 img.tobytes() → rawvideo 管道 |
| 音视频合并 | 无 | `-i pipe:0 -i audio` 一步 | concat 分段 → -map 0:v -map 1:a → 再统一转 BT.709 |
| 帧率 | — | 60（-r 60） | 24 |
| 无损 | — | crf18（有损） | **libx264rgb -qp 0 母版**（无损） |

**结论：三个里没有一个走"PNG 序列 → ffmpeg"的常规路线**（C 的左侧 PNG 是浏览器截图，不是渲染器输出）。B 与 C 都用 **stdin 管道喂 rawvideo**，这是逐帧渲染的标准做法：省掉磁盘 I/O 与二次解码。

---

## 6. 10 条可直接落地的设计规则

> 每条一句话 + 代码依据。适用于"用字符/TUI 风格做一支同步音乐视频"这类项目。

1. **时钟只认音频设备的位置，墙钟只用于两次设备更新之间的插值，并且必须有一条"墙钟跑飞就重新对齐"的护栏。**
   依据：KurohaneKaoruko__world-execute-me/src/audio.rs:538-559（Audio::time，`if t > pos + 0.10 { sync(pos); pos }`）；yym8224961__world.execute-me-ascii/AudioClock.swift:40-45（设备拥有时间轴，60 Hz 输出 JSON）。

2. **整首歌的频谱/能量包络在启动时离线算一遍并按帧号建表，播放期只做一次数组索引，绝不在运行时做 FFT。**
   依据：src/audio.rs:157-396（analyze）+ :53-77（Spectrum::at，`v[(t*FPS) as usize]`）；player.py:123-125（`int(t*30)` 查表）；MisakaZentai__…/full/music.py:105-111（`at(t)`）。

3. **归一化用 95~99.5 分位而不是峰值，否则单帧尖峰会压掉整首歌的动态。**
   依据：src/audio.rs:330-354（排序取 95 分位作参考，注释"避免被单帧尖峰拖垮"）；full/music.py:51-53（`_norm(v, q=0.98)`）；film/pv_dsh_frontend_20260927/dsh_wave.py:42（`np.percentile(p, 99.5)`）。

4. **场景/镜头用"时间区间表"，并在装载阶段就断言"首尾相接 + 覆盖全片"，让时间轴的错误在启动时立刻炸掉而不是在成片里留一帧黑。**
   依据：full/engine.py:351-362（add/finalize 抛 `timeline gap/overlap` 与覆盖断言）；continuity_full_v2/kit.py:63-74（patch_code 替换字节码前先 `assert a in src`）；src/scenes/mod.rs:307-320（index_at / marks）。

5. **场景内部只依赖"进入本幕后的已过时间"（lt = t - start），不要用累加的 dt 去构建状态；需要逐帧积分的东西（粒子、出字）单独隔离在特效层。**
   依据：full/engine.py:99-121（`Ctx.lt` / `Ctx.u = lt/dur`）；src/view.rs:85-88（注释："用绝对时间差而不是累加 dt：既保证离屏渲染能复现，也保证拖动进度条之后动画立刻处于正确状态"）。

6. **转场必须是"有动机"的：默认让布局本身滑走重组，只有叙事上真的需要硬切时才硬切，并为每个特例写一行理由注释。**
   依据：full/direction.py:131-231（44 条 CHOREO，每条带一行注释；默认 glide，None 表示硬切）；full/transitions.py:1-11（docstring 逐条解释 reflow/pane_dissolve/zoom/pan/spin/crt 各自"跨过了什么"）。

7. **终端字符格约 2:1，所有几何计算都要在 y 方向乘 0.5（或 x 方向乘 2）才是正圆/正多边形；写代码时把这个系数注释出来。**
   依据：src/buf.rs:424-433（circle，注释"字符格子非正方，x 方向按 0.5 压缩"，实现为 `x = cx + cos*rad*2`）；src/fx3d.rs:469-471（screens() 里 `cy - focal*0.5*p.y/d`）；scenes.py:614-615（`y = cy + sin(angle)*radius*0.5`）。

8. **如果目标是"在真终端里 live 播放"，必须做逐格差分刷新，并用一个"占位符字符"标记宽字符的右半格以免重复输出。**
   依据：src/term.rs:68-108（present()：逐格比 ch/fg/bg，只在变化时 MoveTo/SetColors/Print，末尾 `prev.cells.copy_from_slice`）；src/buf.rs:70-74（`SKIP = '\u{0}'`）+ :279-293（宽字符写两格）。

9. **逐帧导出 mp4 走"渲染器 → rawvideo RGB24 → ffmpeg stdin 管道"，并且离屏渲染必须调用与实时完全相同的渲染函数、必要时先用"预热步进"把依赖状态推到目标时刻。**
   依据：full/engine.py:488-504（_render_segment，`-f rawvideo -pix_fmt rgb24 -s WxH -r 24 -i -`）；tools/render_video.py:154-161（同款管道，外加 `scale=1920:1080:flags=lanczos`）；src/main.rs:666-680（shots() 从 t-4s 按 60 fps 预热，注释"否则离屏单帧看到的是'刚进场景第一帧'的假象"）；dsh_her.py:313-331（libx264rgb -qp 0 无损母版）。

10. **把"不可验证的输入"挡在门外：对素材与中间产物做哈希校验，并且要求"重建出的文件字节级 sha256 必须与原文件一致，否则什么都不写"。**
    依据：tools/lyrics.py:222-231（重建 LRC 与 word timeline 后比对 sha256，不一致就 sys.exit 且不落盘）；tools/build_bundle.py:23-33 + tests/test_bundle.py:43-53（manifest sha256 + 篡改必须被拒绝）；video_ascii_v1/convert.py:200-209（对每个输出做整片解码复检 + 时长/帧数/帧率/尺寸断言）。

---

## 7. 证据索引（按关注点）

### ① 同步与时钟
- yym8224961__world.execute-me-ascii/AudioClock.swift:4（"The audio device owns the timeline"）、:22-36（命令）、:40-45（60 Hz JSON）
- …/player.py:197-220（Audio 客户端 + 看门狗 self.last）、:246-254（状态消费与结束判定）、:266-269（帧节拍器 + select 等待）
- KurohaneKaoruko__world-execute-me/src/audio.rs:400-441（Clock）、:538-559（time() 插值 + 护栏）、:468-490（闪屏期间挂起播放器）
- MisakaZentai__world-execute-me-dsh-pv/film/tui_pv_world_execute_20260926/full/engine.py:32-38（FPS/BPM/FIRST_BEAT/HARD_CUT）、:54-77（beat_t/snap8/pulse/keyframes）
- …/continuity_full_v2/words.py:75-99（逐字 onset 与闪烁）、:55-62（换行/淡出规则）
- …/film/pv_dsh_frontend_20260927/dsh_wave.py:29-49（1 ms RMS 表）、:52-78（波形绘制）

### ② 场景状态机与转场
- …/scenes.py:2921-3058（A 的分派链）、:18-28（强度函数）、:106-126（3D 投影）
- KurohaneKaoruko__world-execute-me/src/scenes/mod.rs:292-352（trait/Seg/Timeline/19 幕表）
- …/src/main.rs:181-278（render_frame 后处理与时段门控）、:450-533（主循环）
- …/full/engine.py:338-391（Shot/add/finalize/CUTS/shot_at）、:449-479（转场分派）
- …/full/direction.py:11-101（79 条 LAYOUT）、:104-123（YOU_LEFT / EXEC_HIT）、:137-231（44 条 CHOREO + 默认 glide）、:234-240（check_variety）
- …/full/transitions.py:28-92（Hilbert reflow）、:95-112（pane_dissolve）、:117-132（zoom）、:135-143（pan+motion blur）、:163-175（crt）
- …/full/stage.py:36-38（背景视差）、:224-254（geometry 九种模式）、:302-375（chrome/compose）、:397-445（glide）
- …/continuity_full_v2/kit.py:3-9（五层顺序）、:63-74（patch_code）、:85-132（me_stub/her_layer）、:280-289（ink）、:348-414（reveal + 三个 delay 生成器）
- …/continuity_full_v2/cuts.py:53-82（Frame / Cut 基类）、:28-50（body）
- …/continuity_full_v2/v2.py:7-20（分组件协议）、:97（CUTS 按 v1 索引）、:142-166（retract/slide）、:228-246（her_anchor 用 alpha 通道测锚点）、:258-294（逐帧分层）

### ③ 数据结构
- yym8224961__world.execute-me-ascii/config.json（全文）、lyrics.json（129 条）、spectrum.json（30 fps × 48 段）
- KurohaneKaoruko__world-execute-me/src/audio.rs:31-39（Spectrum）、:53-85（查询）
- …/src/lyrics.rs:12-33（Token/Line/Lyrics）、:58-82（关键词 tokenize）、:121-153（向前 5 行双语对齐 + rep）
- …/src/view.rs:15-96（每帧快照）
- MisakaZentai__…/data/song.json、data/timing/lyrics_synced_notext.json、data/timing/word_timeline_notext.json、data/h3_takes.json、full/audio_features.json（schema 见 §4.4）
- …/tools/lyrics.py:99-118（LRC 解析与变体归一化）、:121-150（SequenceMatcher 对齐）、:153-164（patch op）、:173-235（重建 + sha256 校验）

### ④ 字符画与色彩
- …/player.py:12（256 色）、:14-36（5×5 点阵）、:38-60（宽度/裁切/换行）、:62-107（Canvas + 行内颜色压缩）、:89-97（big）
- …/scenes.py:9-13（hash16）、:30-99（5 级故障）、:2796-2918（标题接管）、:3060-3073（phosphor）
- KurohaneKaoruko__…/src/buf.rs:88-119（宽度）、:263-268（去饱和）、:270-298（宽字符占位）、:310-318（glow）、:394-433（线/圆）、:484-509（blit_scroll）
- …/src/theme.rs:2-4（色彩语义）、:38-77（Kw 六分类）、:112-120（heat）
- …/src/fx.rs:52-60（hash2）、:80-90（pulse）、:112-183（scanlines/vignette/bloom）、:186-215（glitch）、:218-287（Rain）、:296-372（Particles）、:416-508（心形/正弦切线/渐近线）、:511-556（bar/spectrum）
- …/src/fx3d.rs:141-142（字符阶梯）、:146-391（网格生成器）、:432-582（投影/Z-Buffer/兰伯特/裁剪）
- …/src/bigfont.rs:8-94（字形表）、:149-182（draw_reveal）、:186-206（bitmap）
- …/src/term.rs:113-168（HTML 导出）、:223-238（WEMV）
- MisakaZentai__…/tuikit.py:27-48（三套调色板）、:63-86（mix/amb）、:105-120（decode）、:123-136（tokenize/token_id）、:155-202（halfblock + grid_mask）、:239-304（glyph art 两段法）、:310-328（banner）、:333-348（box）、:441-476（scanlines/vignette/post）
- …/full/music.py:125-167（react 立绘反应）
- …/film/pv_dsh_frontend_20260927/dsh_gpu.py:24-62（GPU 后期三件套）
- …/film/tui_pv_world_execute_20260926/video_ascii_v1/convert.py:47-131（背景 flood fill + 方向笔画 + hysteresis + 颜色量化）

### ⑤ 出片管线
- KurohaneKaoruko__…/src/main.rs:581-628（--render-video）、:632-698（--shots + 预热）
- …/tools/render_frames.py:17-85（WEMV → PNG 拼图）、tools/render_video.py:26-99（遮罩缓存光栅化器）、:132-185（ffmpeg 管道合成）、tools/dump_txt.py（纯文本排版核对）、tools/shoot.sh（HTML 截图）
- MisakaZentai__…/build.py:35-38（页面组顺序）、:103-106（pages 步骤）、:109-131（母版 + BT.709 转码 + 4K neighbor）
- …/film/pv_dsh_frontend_20260927/seg_shot.mjs:19-50（Playwright 逐帧截图 + 动画钉时间 + DOM 测量）
- …/film/pv_dsh_frontend_20260927/batch_a1.py:184-189（frames.json 结构）
- …/film/pv_dsh_frontend_20260927/dsh_her.py:121-125（帧号→PNG）、:128-293（monkeypatch 合成）、:313-352（分段并行 + concat + 混音）
- …/film/tui_pv_world_execute_20260926/full/engine.py:488-542（分段并行 + 镜头边界切分）
- …/film/tui_pv_world_execute_20260926/continuity_full_v2/v2.py:311-383（worker 子进程 + v1/v2 对照 + 切点 contact sheet）

---

## 8. 明确区分：确认 / 推测 / 未验证

### 已确认（有源码与行号）

- 上述全部函数级结论；三仓库的 schema 数字均为本机脚本实测。
- B 仓库 tools/render_video.py 的第一步是 rawvideo 管道（**不是** PNG 序列）：render_video.py:154-158。
- C 仓库左侧窗口在出片时**没有 dsh 进程、没有服务器**：docs/HOW_IT_WORKS.md:14，且全树无 HTTP 客户端调用模型（只有 build_frame.py 生成静态 HTML）。
- A 仓库**没有视频导出能力**：全树无 ffmpeg/rawvideo 引用，只有 --snapshot。

### 推测（结构合理但源码未明说）

- **【推测】** A 仓库的正式 MV 视频（B 站那支）是在外部录屏或另有一份未开源的导出脚本；仓库内只留了播放器与单帧快照。理由是 tests/test_bundle.py:26 明确断言打包产物里不得出现 .mp4/.png/.jpg。
- **【推测】** B 仓库 gallery/v1.0/frames/all_*.bin（49 个）是用 --shots 对一组关键时间点导出的存档，而非 --render-video 的产物——因为文件命名 all_%02d.bin 与 --out 的 stem 派生规则一致（main.rs:686-696），而 --render-video 产出的是 f_%05d.bin（main.rs:603）。
- **【推测】** C 仓库 data/timing/word_timeline_notext.json 里 candidates 的四种方法与 README 的音频分析工具链（Demucs 分人声 + MMS_FA CTC + Whisper stable-ts）一一对应，但源码中**没有**生成这份数据的脚本（只有消费它的 tools/lyrics.py merge），因此生成流程本身未获取。
- **【推测】** C 仓库 full/（第一版）与 continuity_full_v2/（第二版）是同一支片子的两代引擎，最终成片用的是 v2 + dsh_her 合成；docs/HOW_IT_WORKS.md:8-10 与 dsh_her.py:25（import pv_full）都指向 v2。

### 未获取 / 拿不到

- **C 仓库的歌曲音频与歌词原文**：仓库明确不分发（README.md:43-47, input/README.md）。因此**无法在本机完整复现出片**（build.py all 会先在 check 步骤报缺 input/song.mp3）。本任务只做源码与数据结构的提炼，不需要音频。
- **C 仓库的舞者帧**（pv_cache/、continuity_full_v2/cache/h3_full_v1/）：因第三方 MMD 授权问题不分发，构建时由 tools/placeholder_h3.py 生成替身。仓库里的 data/h3_takes.json 只有"清单"，没有帧。
- **C 仓库的 final 镜头精确数量**：full/sec_*.py 的固定注册点为 80 个，另有两组按歌词行数变化（USER_LEFT 的重复次数、EXECUTION 的 12 连击）。用仓库内 lyrics_synced_notext.json 实测：110–116 s 区间 6 行、147–158.5 s 区间 12 行。因仓库不含唱词文本，无法逐条核对前缀过滤条件，故**不能给出精确的 final 镜头数**；docs/HOW_IT_WORKS.md:11 自述为「全部 96 个镜头」。
- **B 仓库的 ffmpeg/agent-browser 外部依赖**：tools/shoot.sh 依赖 agent-browser，本机未安装，因此没有复跑；但 render_frames.py 的 WEMV 解析已用 gallery/v1.0/frames/all_00.bin 实测确认（magic 与尺寸正确）。
- **三仓库的成片画面均未下载**（只有 _ref/ 里两支 B 站参考视频，与本任务无关），所有视觉结论都来自源码与仓库自带数据，未做逐帧视觉比对。
