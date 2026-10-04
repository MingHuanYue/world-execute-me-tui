# ENV_REPORT — world.execute(me) TUI MV 环境与可行性实测

> 执行者：qa-integrator（task-3）
> 采样时间：2026-10-03 15:53 – 16:05 (Asia/Shanghai)
> 工作区：`<workspace>\world-execute-me-tui`
> 原则：所有数字均为**真实墙钟实测**（`time.perf_counter()` / `Stopwatch`），无估算；外推值一律标注「外推」；未验证项集中在 §11。
> 临时脚本与日志：`_ref/env/`（已清理 2.03 GB 帧中间产物）

---

## 0. 先回答三件事

### ① 这个工程在这台机器上跑得起来吗？—— **跑得起来，而且很宽裕。**

实测已跑通完整链路：**Pillow 绘制帧 → rawvideo 管道 → FFmpeg 7.1 → H.264 + AAC mp4**，
ffprobe 验证输出为 `h264 1280x720 24fps` + `aac 44100Hz 2ch` + `duration=10.000000`。

唯一必须先解决的坑：**本机 GPT-SoVITS 自带的 `ffmpeg.exe` 没有 libx264/libx265，且它的 NVENC 在 596.21 驱动下是坏的**（详见 §4）。
解法已验证：`pip install imageio-ffmpeg`（3.8 s）附带 **FFmpeg 7.1**，libx264 / libx265 / aac / NVENC 全部可用。

两条硬约束：
- **Playwright / 任何 HTML 渲染路线在本沙箱内不可用**（不是下载问题，是 `CreateFile` WinError 5，§8）→ 必须 Pillow 直绘。
- 所有依赖**都有 cp311 win_amd64 预编译 wheel，全程零编译**。

### ② 212 秒 24fps 1280x720 的 MV（5088 帧）大概要渲多久？

| 口径 | 实测吞吐 | 5088 帧 ETA |
|---|---|---|
| 纯编码（帧已在管道，libx264 veryfast crf18） | 432.9 fps | **11.8 s** |
| 纯编码（帧常量走管道，h264_nvenc p4 cq23） | 680.7 fps | **7.5 s** |
| 端到端：Pillow 绘帧 + 管道 + libx264（300 帧样本 147.6 fps） | 147.6 fps | **34.5 s**（外推） |
| 端到端：Pillow 绘帧 + 管道 + h264_nvenc（300 帧样本 189.3 fps） | 189.3 fps | **26.9 s**（外推） |
| 端到端：绘帧 + 落 PNG(level1) + 再编码（300 帧样本 105.9 fps） | 105.9 fps | **48.0 s**（外推） |

> **结论：本轮测试复杂度的渲染器下，720p 全片 ≈ 30–50 秒；即便美术复杂度再翻 10 倍，也还在 5–10 分钟预算内。**
> **编码本身不是瓶颈（< 12 s），真正的成本在 Python 绘帧。**

### ③ 4K 版现实吗？—— **现实。原生 4K 比 ffmpeg 放大慢 4–6 倍，但仍在 5–12 分钟量级。**

| 方案 | 实测吞吐 | 5088 帧 ETA | 画质 |
|---|---|---|---|
| **原生 4K 渲染** + PNG level6（120 帧样本，24 行文字） | 7.5 fps | **679 s ≈ 11.3 min** | 文字锐利 ✅ |
| **原生 4K 渲染** + 管道 + nvenc（120 帧样本） | 15.9 fps | **321 s ≈ 5.4 min** | 文字锐利 ✅ |
| 720p → 4K `scale=3840:2160:flags=lanczos` + libx264 | 56.5 fps | **90 s** | 终端文字发虚 ❌ |
| 720p → 4K lanczos + h264_nvenc | 72.2 fps | **70 s** | 终端文字发虚 ❌ |

> **建议做原生 4K。** 这是**终端文字**风格的 MV —— lanczos 放大把字形边缘糊掉，观感损失明显；
> 而原生代价只是 5–12 分钟（渲染器写成分辨率无关，一套代码出 720p / 4K）。
> 磁盘：4K PNG 序列 1.1–2.2 GB（§6）；**4K rawvideo 绝不能落盘**（120.7 GB）。

---

## 1. 环境基线

| 项目 | 结论 | 证据命令 | 原始输出片段 | 对项目的影响 |
|---|---|---|---|---|
| OS | Windows 10 Pro 19045（Win10 22H2） | `python -c "import platform;print(platform.platform())"` | `Windows-10-10.0.19045-SP0` | 无 |
| CPU | Intel **i5-12490F**，12 逻辑核 | `_ref/env/sysinfo.py` | `"cpu_name": "12th Gen Intel(R) Core(TM) i5-12490F", "cpu_logical": 12` | x264 多线程够用，软编够快 |
| 内存 | 总量 **31.86 GB**，可用 **15.35–15.85 GB**，负载 50–51 % | 同上（`GlobalMemoryStatusEx`） | `"ram_total_gb": 31.86, "ram_avail_gb": 15.85, "mem_load_pct": 50` | 整段预计算/帧缓存都放得下 |
| GPU | **1× NVIDIA GeForce RTX 2080**，驱动 **596.21**，8192 MiB，compute 7.5（Turing） | `nvidia-smi -L` | `GPU 0: NVIDIA GeForce RTX 2080 (UUID: GPU-d1df...)... 0, NVIDIA GeForce RTX 2080, 596.21, 8192 MiB, 7.5` | 支持 NVENC H.264 / HEVC |
| 沙箱事实 | 文件沙箱 `workspace-write`，**enforcement: partial**；WMI/CIM 被拒 | `Get-CimInstance Win32_Processor` | `Get-CimInstance : 拒绝访问 / PermissionDenied (HRESULT 0x80041003)` | 硬件信息改走 `ctypes` / 注册表，别用 WMI |

---

## 2. Python / pip 与网络

| 项目 | 结论 | 证据命令 | 原始输出片段 | 对项目的影响 |
|---|---|---|---|---|
| Python | **3.11.9**（MSC v.1938, 64-bit） | `python -V` | `Python 3.11.9` | cp311 wheel 生态完整 |
| pip | **24.0** | `python -m pip -V` | `pip 24.0 from C:\Users\<user>\...\site-packages\pip (python 3.11)` | 支持 `--dry-run` |
| 默认 PyPI | **可用**，2.78 s | `pip index versions pillow --timeout 60` | `pillow (12.3.0) ... LATEST: 12.3.0` / `ELAPSED_ms=2784` | 不配镜像也能装 |
| 清华镜像 | **可用且更快**，1.29 s | `pip index versions pillow -i https://pypi.tuna.tsinghua.edu.cn/simple` | `ELAPSED_ms=1287` | **推荐**：下载实测 73 MB/s |
| 真实下载 | 12.6 MB / **1.62 s** | `pip download --no-deps -d _ref/env/dl numpy -i <清华> --timeout 60` | `Downloading ... numpy-2.4.6-cp311-cp311-win_amd64.whl (12.6 MB) 73.0 MB/s` / `Successfully downloaded numpy` / `ELAPSED_ms=1623` | 依赖安装几乎不受网络限制 |
| 代理 | 无 | `Get-ChildItem Env: | ? Name -match PROXY` | `HTTP_PROXY= HTTPS_PROXY= ALL_PROXY=` | 直连 |
| pip 缓存 | 已重定向到 D 盘 | `PIP_CACHE_DIR=...\_ref\env\pipcache` + `pip cache dir` | `d:\dsh...\world-execute-me-tui\_ref\env\pipcache` | env 变量覆盖生效，**不写 C 盘** |
| ⚠ pip 全局配置有坏条目 | 存在，被 env 覆盖 | `pip config list` | `global.cache-dir="Z:\pip_cache'"`（结尾多一个引号） | 不显式带 `PIP_CACHE_DIR` 时行为不可预期 → **每条 pip 命令都显式带上** |
| 已装（主 site-packages） | Pillow **12.3.0** / numpy **2.4.4** / soundfile **0.14.0** / cffi 2.1.0 / curl_cffi 0.15.0 | `python -c "import PIL,numpy,soundfile;print(PIL.__version__,numpy.__version__,soundfile.__version__)"` | `Pillow 12.3.0 / numpy 2.4.4 / soundfile 0.14.0` | 主环境开箱即用 |
| soundfile 能力 | 支持 **WAV/FLAC/OGG/MP3** 等 27 种容器 | `soundfile.available_formats()` | `['AIFF','AU',...,'FLAC',...,'MP3',...,'OGG',...,'WAV',...]` / `MP3 supported: True` | 音频读写直接可用，不必装 pydub |
| import 开销 | numpy 172 ms / PIL 162 ms | `python -c "import numpy"` | `import numpy ms=172 / import PIL ms=162` | 一次性成本，可忽略 |

### 可用安装命令（已验证）

```powershell
$PY     = "C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe"
$ROOT   = "<workspace>\world-execute-me-tui"
$MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

# 推荐：D 盘独立 venv，绝不往 C 盘 site-packages 装
& $PY -m venv "$ROOT\.venv"                                  # 实测 8.1 s
$VPY = "$ROOT\.venv\Scripts\python.exe"

# 临时脚本/交付物里必须带的三件套（缓存、超时、镜像）
$env:PIP_CACHE_DIR   = "$ROOT\_ref\env\pipcache"
$env:MPLCONFIGDIR    = "$ROOT\_ref\env\mplconfig"
$env:NUMBA_CACHE_DIR = "$ROOT\_ref\env\numbacache"

& $VPY -m pip install --timeout 60 -i $MIRROR pillow numpy soundfile imageio-ffmpeg
& $VPY -m pip install --timeout 60 -i $MIRROR scipy librosa   # 音频分析才需要
```

---

## 3. 依赖可装性矩阵（全部 `--target` 装到 D 盘，零编译）

| 包 | 结论 | 耗时（实测） | wheel 大小 | 证据命令 | 对项目的影响 |
|---|---|---|---|---|---|
| **numpy** | ✅ 可装（主环境已装 2.4.4） | 1.6 s（仅下载） | 12.6 MB | §2 | 核心依赖 |
| **Pillow** | ✅ 已装 12.3.0 | — | 7.2 MB | `pip list` | **渲染主力** |
| **soundfile** | ✅ 已装 0.14.0 | — | — | 同上 | 音频 I/O |
| **imageio-ffmpeg** | ✅ 0.6.0 | **3.8 s** | 31.2 MB | `pip install --target _ref/env/t_imageio imageio-ffmpeg` | ★ **附带可用的 FFmpeg 7.1** |
| **scipy** | ✅ 1.17.1 | **27.6 s**（热缓存） | 36.6 MB | `pip install --target _ref/env/t_scipy scipy` | 重采样 / 滤波 |
| **matplotlib** | ✅ 3.11.2 | **23.3 s**（热缓存） | 9.3 MB | 同构 | 可选：调色板 / 波形预览 |
| **moviepy** | ✅ 2.2.1 | **15.5 s**（热缓存） | — | 同上 | 可选：高层合成（自带 imageio-ffmpeg 0.6.0） |
| **librosa** | ✅ 0.11.0 | **53.0 s**（冷装，含全部依赖） | — | `pip install --target _ref/env/t_librosa librosa` | 节拍 / onset 分析 |
| **playwright** | ✅ 包 1.63.0（6.9 s） / ❌ **浏览器不可运行** | 6.9 s | 38.6 MB | 见 §8 | **不要采用** |
| av (PyAV) | ✅ 18.1.0 | 6.2 s | 27.6 MB | `pip install --target _ref/env/t_av av` | 备选后端（未验编码） |
| venv（建在 D 盘） | ✅ 成功 | **8.1 s** | — | `python -m venv _ref/env/t_venv` | 推荐的隔离方式 |

**关键事实：没有任何一个包触发编译。** 全程未见 `Building wheel`；librosa 的 numba 0.68.0 / llvmlite 0.50.0 / scikit-learn 1.9.1 / scipy 1.17.1 全部命中预编译 wheel。

librosa 冷装原始输出：

```
Successfully installed audioread-3.1.0 certifi-2026.7.22 cffi-2.1.1 charset_normalizer-3.5.2
cloudpickle-3.1.2 decorator-5.3.1 idna-3.20 joblib-1.6.0 lazy_loader-0.6 librosa-0.11.0
llvmlite-0.50.0 msgpack-1.2.3 narwhals-2.26.0 numba-0.68.0 numpy-2.4.6 packaging-26.3
platformdirs-4.12.2 pooch-1.9.0 pycparser-3.0 requests-2.34.2 scikit-learn-1.9.1 scipy-1.17.1
soundfile-0.14.0 soxr-1.1.0 threadpoolctl-3.7.0 typing_extensions-4.16.0 urllib3-2.8.0
RESULT=librosa exit=0 ELAPSED_ms=53032
import test: librosa 0.11.0 / numba 0.68.0 / scipy 1.17.1   (1477 ms)
```

### 3.1 主环境 vs 独立 venv —— 建议

主 `site-packages` 在 **C 盘**。按工作区铁律「不往 C 盘丢东西」，**建议建 D 盘 venv**（已验证 8.1 s）。
若不想建 venv，`pip install --target <D盘目录>` + `PYTHONPATH` 也已验证可用（本报告全部测试即用此法）。

副作用提示（已实测，量很小）：`C:\Users\<user>\.matplotlib` 被创建，**0.22 MB**；设 `MPLCONFIGDIR` / `NUMBA_CACHE_DIR` 到 D 盘可避免。

---

## 4. FFmpeg 工具链 —— **本项目最大的坑，务必先读这一节**

### 4.1 三个 ffmpeg 的事实对比

| 二进制 | 版本 | libx264 | libx265 | aac | NVENC | 能编码吗 |
|---|---|---|---|---|---|---|
| `D:\GPT-SoVITS\GPT-SoVITS-v2pro-20250604\runtime\ffmpeg.exe` | n4.3.2-160-gfbb9368226 | ❌ | ❌ | ✅ | ⚠ 存在但**坏** | 只有 mpeg4 / vpx / prores 等 |
| 同目录 `ffprobe.exe` | 2022-04-07 gyan.dev **full_build** | ✅ | ✅ | ✅ | ✅ | ❌ **ffprobe 不能编码** |
| `_ref/env/t_imageio/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe` | **7.1** gyan.dev essentials | ✅ | ✅ | ✅ | ✅ **实测可用** | ✅ **本项目采用** |

**证据 1 — 自带 ffmpeg 明确 disable 了 x264/x265：**

```
> & "...\runtime\ffmpeg.exe" -version
ffmpeg version n4.3.2-160-gfbb9368226 Copyright (c) 2000-2021 the FFmpeg developers
configuration: ... --enable-ffnvcodec --enable-cuda-llvm ... --disable-libx264 --disable-libx265
               --disable-libxavs2 --disable-libxvid ...
```

**证据 2 — 同目录 ffprobe 是另一套构建，反而带 x264（但无法编码）：**

```
> & "...\runtime\ffprobe.exe" -version
ffprobe version 2022-04-07-git-607ecc27ed-full_build-www.gyan.dev
configuration: --enable-gpl ... --enable-libx264 --enable-libx265 ... --enable-nvenc ...
> & "...\runtime\ffprobe.exe" -encoders | findstr libx264
V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
```

**证据 3 — 自带 ffmpeg 的 NVENC 在 596.21 驱动下直接报错（0 字节输出，exit=1）：**

```
> & "...\runtime\ffmpeg.exe" -f lavfi -i testsrc2=size=1280x720:rate=24 -frames:v 24 -c:v h264_nvenc -y n1.mp4
[h264_nvenc @ ...] Cannot get the preset configuration: unsupported param (12): Success.
Error initializing output stream 0:0 -- Error while opening encoder ...
exit=1        n1.mp4 = 0 bytes
```

同一条命令加 `-gpu 0` 也一样失败 → 是老 nv-codec-headers 与新驱动不兼容，不是参数问题。

**证据 4 — imageio-ffmpeg 的 7.1 完全可用：**

```
> & "...\ffmpeg-win-x86_64-v7.1.exe" -version
ffmpeg version 7.1-essentials_build-www.gyan.dev
configuration: ... --enable-libx264 --enable-libx265 --enable-nvenc --enable-cuvid ...
> ... -f lavfi -i testsrc2=size=1280x720:rate=24 -frames:v 24 -c:v h264_nvenc -preset p4 -cq 23 -y n3.mp4
Stream #0:0: Video: h264 (Main) (avc1 / 0x31637661), yuv420p(tv, progressive), 1280x720, 24 fps
frame=   24 fps=0.0 q=23.0 Lsize=     582KiB time=00:00:00.87 bitrate=5448.6kbits/s speed=4.09x
exit=0        n3.mp4 = 595943 bytes
```

### 4.2 编码器清单（自带 ffmpeg，188 个编码器中的相关项）

```
V..... h264_amf    V..... h264_mf     V..... h264_nvenc   V..... h264_qsv
V..... hevc_amf    V..... hevc_mf     V..... hevc_nvenc   V..... hevc_qsv
V..... nvenc       V..... nvenc_h264  V..... nvenc_hevc
VF.... png         VF.... prores      VFS... prores_ks    VFS... mjpeg
V..... mpeg4       V..... libvpx      V..... libvpx-vp9    A..... aac
```

注意：`libx264` / `libx265` 在此清单中**完全不存在**。`h264_mf`（MediaFoundation H.264）是另一条潜在路线，但**本轮未测**。

### 4.3 结论

- ❌ **不要用 GPT-SoVITS runtime 的 ffmpeg 做最终编码**（无 H.264 软编、NVENC 坏）。
- ✅ **用 `imageio-ffmpeg` 附带的 FFmpeg 7.1**，程序里这样取路径，不要硬编码：

```python
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()   # -> ...\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe
# 实测: imageio_ffmpeg.get_ffmpeg_version() -> '7.1-essentials_build-www.gyan.dev'
```

- ✅ `ffprobe` 仍可放心用自带的 gyan full_build（只做探测/校验，不需要编码）。

---

## 5. 编码吞吐基准（真实墙钟，FFmpeg 7.1）

复现脚本：`_ref/env/env_bench.py`（结果 JSON：`_ref/env/bench_results.json`）
调用：`python _ref/env/env_bench.py <ffmpeg7.1路径>`

### 5.1 1280x720 / 24fps / 300 帧

| 场景 | 输入 | 编码参数 | 墙钟 | 实测 fps |
|---|---|---|---|---|
| 生成器基线 | lavfi testsrc2 | `rawvideo → null` | 0.161 s | 2239 fps（testsrc2 生成极快） |
| **libx264** | lavfi | `-preset veryfast -crf 18` | **0.607 s** | **494.2 fps** |
| **h264_nvenc** | lavfi | `-preset p4 -rc vbr -cq 23` | 0.759 s | 395.3 fps |
| mpeg4（兜底） | lavfi | `-q:v 3` | 0.225 s | 1333.3 fps |
| **libx264** | rawvideo 文件 | `veryfast -crf 18` | 0.534 s | **561.8 fps** |
| h264_nvenc | rawvideo 文件 | `p4 -cq 23` | 0.659 s | 455.2 fps |

### 5.2 3840x2160 / 24fps / 120 帧

| 场景 | 输入 | 墙钟 | 实测 fps |
|---|---|---|---|
| libx264 `veryfast -crf 18` | lavfi | 2.098 s | 57.2 fps |
| h264_nvenc `p4 -cq 23` | lavfi | 1.993 s | 60.2 fps |
| libx264 | rawvideo | 2.047 s | 58.6 fps |
| h264_nvenc | rawvideo | 1.950 s | 61.5 fps |

> 4K 下 **x264 与 nvenc 几乎打平（57–62 fps）** —— 此时瓶颈是内存带宽 / 帧拷贝而非编码算法。
> 4K 想真正提速必须减少 CPU 侧拷贝（如让 GPU 直接吃帧），**本轮未验证**。

### 5.3 端到端管道（Pillow 绘帧 → 管道 → 编码）

复现脚本：`_ref/env/png_bench.py`（结果：`_ref/env/png_bench_results.json`）

| 场景 | 墙钟（300 帧） | fps | 5088 帧 ETA（外推） |
|---|---|---|---|
| 绘帧 + 存 PNG（compress_level=1） | 2.833 s | 105.9 | 48.0 s |
| PNG 序列 → libx264（`-framerate 24 -i %06d.png`） | 1.954 s | 153.5 | 33.1 s |
| PNG 序列 → h264_nvenc | 0.756 s | 397.1 | 12.8 s |
| **绘帧 → 管道 → libx264** | 2.033 s | **147.6** | **34.5 s** |
| **绘帧 → 管道 → h264_nvenc** | 1.585 s | **189.3** | **26.9 s** |
| 管道写入上限（帧恒定，5088 帧）libx264 | 11.753 s | 432.9 | 11.8 s |
| 管道写入上限（帧恒定，5088 帧）h264_nvenc | 7.474 s | **680.7** | **7.5 s** |

**解读：** 恒定帧的管道上限 432.9 / 680.7 fps 与「绘帧 + 编码」147.6 / 189.3 fps 的差距，就是 **Python 绘帧时间**（约 3.8 ms/帧 ≈ 263 fps 纯绘制）。
→ **优化重点永远在绘帧代码，不在编码器。**

### 5.4 完整链路正确性验证（ffprobe）

复现脚本：`_ref/env/e2e_test.py`

```
=== 4) END-TO-END: pillow frames -> stdin pipe + wav -> h264/aac mp4 ===
exit=0 wall_s=2.47 fps=97.3 err=          # 240 帧 1280x720 + 10s 音频
mp4 size: 347679
=== 5) ffprobe the result ===
"streams": [
  { "index": 0, "codec_name": "h264", "codec_type": "video", "width": 1280, "height": 720,
    "r_frame_rate": "24/1", "duration": "10.000000" },
  { "index": 1, "codec_name": "aac", "codec_type": "audio", "sample_rate": 44100, "channels": 2,
    "duration": "10.000000" } ],
"format": { "format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "10.000000", "size": "347679" }
```

（该 97.3 fps 低于 147.6 fps，因为每帧额外画了帧号文字，且同时喂音频。）

**推荐编码配方（已实测产出 ffprobe 可解析文件）：**

```python
cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
       "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "24", "-i", "pipe:0",
       "-i", audio_wav,
       "-frames:v", str(N), "-pix_fmt", "yuv420p",           # yuv420p 必须有，否则部分播放器不认
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
       "-c:a", "aac", "-b:a", "192k", "-shortest", out_mp4]
# 追求速度时把 -c:v 换成 h264_nvenc -preset p4 -rc vbr -cq 23（约快 28%）
```

---

## 6. 内存 / 磁盘 / PNG 落盘评估

| 项目 | 结论 | 证据 | 对项目的影响 |
|---|---|---|---|
| 内存 | 31.86 GB 总量 / **15.85 GB 可用** / 50% 负载 | `_ref/env/sysinfo.py` | 允许预计算整段时间轴与缓存 |
| C 盘 | 199.3 GB 总 / **49.4 GB 可用** | `shutil.disk_usage('C:/')` | 紧张，**不要往这写** |
| D 盘（项目盘） | 1562.5 GB 总 / **283.5 GB 可用** | `shutil.disk_usage('D:/')` | 充裕 |
| Z 盘 | 5589 GB 总 / 2650.5 GB 可用 | 同 | 溢出备份可用 |
| 本轮中间产物清理 | 释放 **2026.5 MB**（raw yuv + png 序列 + 测试 mp4） | `Remove-Item` 前后统计 | 已按铁律清理 |

### 6.1 逐帧 PNG 落盘空间需求（实测，含 warm-up）

| 分辨率 | 内容 | level=1 | level=6 | level=9 |
|---|---|---|---|---|
| 1280x720 | 简约 TUI（20 行文字） | 116.0 KB / 10.1 ms | **89.2 KB / 13.3 ms** | 88.5 KB / 64.6 ms |
| 1280x720 | 噪声/特效密集 | 246.2 KB / 15.9 ms | 161.0 KB / 19.3 ms | 168.9 KB / 69.0 ms |
| 1920x1080 | 简约 TUI | 157.5 KB | 102.6 KB | 101.6 KB |
| 3840x2160 | 简约 TUI | 435.0 KB | 224.9 KB | 219.5 KB |

（「KB / ms」= 单帧体积 / 单帧保存耗时）

**5088 帧总空间（外推）：**

| 方案 | 单帧 | 5088 帧合计 | 备注 |
|---|---|---|---|
| 720p PNG（level 6，简约） | ~89 KB | **≈ 0.43 GB** | 安全 |
| 720p PNG（level 6，特效密集） | ~161 KB | **≈ 0.78 GB** | 安全 |
| 720p PNG 最坏（level 1 噪声） | ~246 KB | **≈ 1.2 GB** | 仍安全 |
| 1080p PNG（level 6） | ~103 KB | ≈ 0.50 GB | 安全 |
| 4K PNG（level 6） | ~225 KB | **≈ 1.1 GB** | 安全（实测样本 414 KB/帧 → 2.0 GB） |
| 720p **raw** yuv420p | 1.35 MB | ≈ 6.7 GB | 不划算 |
| 720p **raw** rgb24 | 2.64 MB | **≈ 13.4 GB** | 落盘不划算 |
| 4K **raw** rgb24 | 23.73 MB | **≈ 120.7 GB** | ❌ **绝对不要落盘** |

**建议：**
- 720p 首选 **rawvideo 管道（不落盘）**：省 13 GB，且比存 PNG 快（13.3 ms 保存 vs 管道写入 ~1.5 ms）。
- 需要断点续渲 / 复用帧时用 PNG 序列，选 `compress_level=6`（体积/速度平衡最好；level=9 只小约 1% 却慢 5 倍，**别用 9**）。
- 4K 一律管道；如需落盘，预算 **1.1–2.2 GB**。

---

## 7. 字体（TUI 外观的关键资源）

| 字体 | 等宽 | ASCII 框线 `┌─┐│└┘` | 方块 `█░▓` | 箭头 `↑↓▶◀` | **CJK `世界永远`** |
|---|---|---|---|---|---|
| **Consolas** | ✅ MONO | ✅ | ✅ | ✅ | ❌ **缺字** |
| **Cascadia Mono** | ✅ MONO | ✅ | ✅ | ✅ | ❌ **缺字** |
| Courier New | ✅ MONO | ✅ | ✅ | ✅ | ❌ 缺字 |
| Lucida Console | ✅ MONO | ✅ | ✅ | ✅ | ❌ 缺字 |
| **SimSun（宋体）** | ✅ MONO | ✅ | ✅ | ✅ | ✅ **真字形** |
| **SimHei（黑体）** | ✅ MONO | ✅ | ✅ | ✅ | ✅ **真字形** |
| **MS YaHei（微软雅黑）** | ❌ 比例字体 | ✅ | ✅ | ✅ | ✅ 真字形 |

证据：`python _ref/env/font_and_png.py`（用私用区 U+E123 / U+FFFF 的 `.notdef` 做对照，避免 Pillow 对缺字返回非空 bbox 的假阳性）

```
Consolas        世 = MISSING(205px)   ─= REAL(54px)   █= REAL(666px)   →= REAL(82px)
Cascadia Mono   世 = MISSING(218px)   ─= REAL(92px)   █= REAL(741px)   →= REAL(127px)
Lucida Console  世 = MISSING(78px)    ─= REAL(40px)   █= REAL(640px)   →= REAL(56px)
SimSun          世 = REAL(252px)      ─= REAL(96px)   █= REAL(900px)   →= REAL(108px)
MS YaHei        世 = REAL(403px)      ─= REAL(69px)   █= REAL(782px)   →= REAL(122px)
SimHei          世 = REAL(392px)      ─= REAL(96px)   █= REAL(930px)   →= REAL(188px)
```

**影响与建议：**
- 纯英文/代码 TUI：**Consolas**（`C:\Windows\Fonts\consola.ttf`）或 **Cascadia Mono**，等宽 + 框线完美。
- 只要出现一个汉字：**必须换 SimHei / SimSun**，或对 CJK 字符单独走 YaHei（Pillow **不做字形回退**，混排需手动分段绘制）。
- 「命令提示符」的复古感更接近 SimSun；Consolas 更干净 —— 这是美术选择，不是环境限制。

---

## 8. Playwright —— **不可用**（结论明确）

| 步骤 | 结论 | 证据命令 | 原始输出 |
|---|---|---|---|
| pip 安装 | ✅ 1.63.0，6.9 s | `pip install --target _ref/env/t_playwright playwright` | `Successfully installed greenlet-3.5.6 playwright-1.63.0 pyee-13.0.1 typing-extensions-4.16.0` |
| 版本 | ✅ | `python -m playwright --version` | `Version 1.63.0` |
| dry-run 解析地址 | ✅ | `python -m playwright install --dry-run chromium` | `Chrome for Testing 153.0.8010.12 (playwright chromium v1243)` / `Download url: https://cdn.playwright.dev/builds/cft/153.0.8010.12/win64/chrome-win64.zip` |
| **`playwright install chromium`** | ❌ **失败** | 同上（去掉 --dry-run） | 见下方代码块 |
| **能否 launch 浏览器** | ❌ **失败（决定性）** | `python _ref/env/pw_launch_test.py`（用本机已装 msedge.exe） | 见下方代码块 |
| 官方 CDN 速度 | ❌ 不可用 | `_ref/env/probe_pw.py`（Range 4 MiB） | `HTTP 206 ... Content-Range: bytes 0-4194303/205123748` / `got_bytes 4194304 in_s 136.222 MBps 0.03`（另一次直接 `WinError 10054 远程主机强迫关闭了一个现有的连接`） |
| prss.microsoft.com 回退 | ❌ | `_ref/env/probe_mirrors.py` | `FAILED HTTPError: HTTP Error 400: Bad Request` |
| **npmmirror 镜像** | ✅ **11.5–21.9 MB/s** | 同上 | `npmmirror      status=206 bytes=8388608 s=0.70 MBps=11.49` / `npmmirror-alt  status=206 bytes=8388608 s=0.37 MBps=21.89` |

```
> python -m playwright install chromium
Downloading Chrome for Testing 153.0.8010.12 (playwright chromium v1243) from https://cdn.playwright.dev/...
Failed to install browsers
Error: Failed to download Chrome for Testing ..., caused by
Error: spawn EPERM
    at ChildProcess.spawn (node:internal/child_process:458:11)
    at downloadBrowserWithProgressBarOutOfProcess (...coreBundle.js:32417:28)
install exit=1 ELAPSED_ms=326
```

### 8.1 决定性证据：连启动都不行

```
> python _ref/env/pw_launch_test.py          # 不下载任何浏览器，直接用本机 msedge.exe
browser candidates found: ['C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe']
RESULT: FAIL mode=headless exe=...msedge.exe
  PermissionError: [WinError 5] 拒绝访问。
RESULT: FAIL mode=headed   exe=...msedge.exe
  PermissionError: [WinError 5] 拒绝访问。

Traceback (most recent call last):
  File "...\playwright\_impl\_transport.py", line 120, in connect
    self._proc = await asyncio.create_subprocess_exec(
  File "...\asyncio\windows_utils.py", line 136, in __init__
    stdin_rh, stdin_wh = pipe(overlapped=(False, True), duplex=True)
  File "...\asyncio\windows_utils.py", line 63, in pipe
    h2 = _winapi.CreateFile(
PermissionError: [WinError 5] 拒绝访问。
```

**根因：** 失败发生在**启动 Playwright 自己的 driver 进程**时，甚至还没轮到浏览器 —— asyncio 在 Windows 上为子进程创建 **overlapped（= 命名管道）双向管道**，而本沙箱禁止命名管道，于是 `CreateFile` 直接 WinError 5。
这与「下载 195 MB 浏览器」**无关**，换任何镜像都救不了。
（注意：普通 `subprocess.Popen(stdin=PIPE, stdout=PIPE)` 创建的是匿名管道，**实测可用** —— §5.4 的端到端管道就是这么跑的。区别在 overlapped / 命名管道。）

### 8.2 结论

- ❌ **Playwright / Chromium / 任何 HTML-CSS 渲染路线，在本沙箱内不可用。** 不要写进方案。
- ✅ **替代方案：Pillow 直绘。** 已验证可行且**足够快**（720p 全片 30–50 s，见 §5.3）。
- ℹ️ 这是**环境性**限制，不是工程性的：若最终脚本在 DSH 沙箱**之外**运行，Playwright 大概率能跑（浏览器仍需从 `cdn.npmmirror.com` 镜像下载）。但**交付物必须在本环境可复现**，故按不可用处理。
- 📁 已安装的 `_ref/env/t_playwright`（109 MB）可随时删除。

---

## 9. 推荐工具链配方（可直接照抄）

```powershell
# ---- 0. 环境 ----
$PY     = "C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe"
$ROOT   = "<workspace>\world-execute-me-tui"
$MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
$env:PIP_CACHE_DIR   = "$ROOT\_ref\env\pipcache"
$env:MPLCONFIGDIR    = "$ROOT\_ref\env\mplconfig"
$env:NUMBA_CACHE_DIR = "$ROOT\_ref\env\numbacache"

# ---- 1. D 盘 venv（实测 8.1 s）----
& $PY -m venv "$ROOT\.venv"
$VPY = "$ROOT\.venv\Scripts\python.exe"

# ---- 2. 依赖（全部有 wheel，零编译）----
& $VPY -m pip install --timeout 60 -i $MIRROR pillow numpy soundfile imageio-ffmpeg
& $VPY -m pip install --timeout 60 -i $MIRROR scipy librosa      # 仅音频分析需要

# ---- 3. 关键：ffmpeg 路径不要硬编码，用 imageio-ffmpeg 取 ----
#    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()   # FFmpeg 7.1，带 libx264/libx265/aac/nvenc
```

**必须遵守的三条：**
1. **ffmpeg 用 imageio-ffmpeg 的 7.1**；GPT-SoVITS runtime 那个既没有 libx264，NVENC 也是坏的。
2. **帧走 rawvideo 管道**（`-f rawvideo -pix_fmt rgb24 -i pipe:0`），不要落盘 PNG —— 省 13 GB、快约 3 倍。
3. **渲染用 Pillow 直绘**，分辨率无关（一个 scale 因子同时出 720p / 4K）；不要碰 Playwright。

---

## 10. 交付物与复现清单

| 文件 | 用途 |
|---|---|
| `_ref/env/sysinfo.py` | 硬件 / 磁盘探测（绕开被禁的 WMI） |
| `_ref/env/env_bench.py` → `bench_results.json` | 纯编码吞吐基准 |
| `_ref/env/png_bench.py` → `png_bench_results.json` | PNG 落盘 vs 管道端到端基准 |
| `_ref/env/e2e_test.py` → `e2e_result.json` | 完整音频+视频链路 + ffprobe 校验 |
| `_ref/env/font_and_png.py` | 字体字形 / 等宽核查 + PNG 体积扫描 |
| `_ref/env/final_checks.py` | 4K 原生渲染样本 |
| `_ref/env/moviepy_test.py` | moviepy 2.2.1 冒烟 |
| `_ref/env/probe_pw.py / probe_mirrors.py / pw_launch_test.py` | Playwright 下载与启动证据 |
| `_ref/env/encoders.txt` | 自带 ffmpeg 全量编码器清单 |
| `_ref/env/pip_*.log` | 各包安装原始日志 |
| `_ref/env/t_*` | 各包安装快照（可删，约 0.7–0.9 GB） |

---

## 11. 未验证 / 不确定项（显式声明，勿当结论）

1. **4K 编码瓶颈归属未定位。** 测到 x264 与 nvenc 在 4K 下都是 57–62 fps，怀疑瓶颈在 CPU 侧帧拷贝 / 内存带宽，但**未用 profiler 证实**。
2. **`h264_mf`（MediaFoundation）未测。** 自带 ffmpeg 里有这个编码器，是理论上无需第三方依赖的 H.264 路线，但属老构建，风险同 NVENC。
3. **PyAV（av 18.1.0）只验证了可安装（6.2 s），未验编码。** 是 imageio-ffmpeg 之外的另一条后端，本轮未深入。
4. **`librosa` 的音频分析精度未评估**（只验证装得上、导得进）。节拍 / onset 实际效果属第三阶段交叉验证。
5. **多 GPU 描述不一致：** 注册表列出两个 RTX 2080 适配器键，`nvidia-smi -L` 只报 **1 张**（8192 MiB）。以 nvidia-smi 为准；注册表那条疑为驱动残留 / SLI 配置，**未查证**，不影响本项目。
6. **原生 4K 的 11.3 min 基于「1 帧 24 行文字」样本**；真实美术复杂度若高 3 倍，线性外推约 30 min 量级（**外推，未实测**）。
7. **未测任何播放器兼容性**（ffprobe 校验通过 ≠ 播放器能播）；`-pix_fmt yuv420p` 是通行做法，但未实机播放确认。
8. **Playwright 在沙箱外是否可用未验证**（仅按机制推断）。
9. 主环境 `numpy 2.4.4` 与各 `--target` 目录里的 `numpy 2.4.6` 版本不同 —— 用 venv 可避免混用；本轮测试均在隔离 `--target` 下进行，不影响结论。
10. **`scipy`/`matplotlib`/`moviepy` 的耗时是「热缓存」值**（wheel 已在本地 pip 缓存中）；冷装需额外下载 36.6 / 9.3 / ~7.0 MB，按实测 73 MB/s 约 +0.5 s，影响可忽略。`librosa` 的 53.0 s 是**冷装**值。
