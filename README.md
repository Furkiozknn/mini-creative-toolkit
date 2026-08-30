![mini-creative-toolkit](assets/banner.svg)

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-8effc2?style=flat-square" alt="license: MIT">
  <img src="https://img.shields.io/badge/python-3.11%2B-ffd76d?style=flat-square" alt="python 3.11+">
  <img src="https://img.shields.io/badge/protocol-MCP-ff9f5a?style=flat-square" alt="MCP protocol">
  <img src="https://img.shields.io/badge/tests-passing-8effc2?style=flat-square" alt="tests: passing">
  <img src="https://img.shields.io/badge/GPU%20required-no-ffd76d?style=flat-square" alt="no GPU required">
  <img src="https://img.shields.io/badge/API%20keys-0-ff9f5a?style=flat-square" alt="0 API keys">
</p>

<p align="center"><b>Local, CPU-only image/video utilities exposed as an MCP (Model Context Protocol) server.</b><br>No API keys, no GPU, no paid dependency — everything runs on-device, except the one tool that's honest about being a hosted call.</p>

---

## İçindekiler / Table of contents

- [Neden var — the pitch](#-neden-var--the-pitch)
- [The toolbox](#-the-toolbox)
- [Routing philosophy](#-routing-philosophy)
- [Known limitation — dürüstlük testi](#-known-limitation--dürüstlük-testi)
- [Setup](#️-setup)
- [Running the tests](#-running-the-tests)
- [Registering as an MCP server](#-registering-as-an-mcp-server)
- [Project layout](#-project-layout)
- [License](#-license)

---

## 🎯 Neden var — the pitch

GitHub'da onlarca "ücretsiz AI creative studio" reposu var — açıp bakınca hepsi aynı hikâye: kayıt ol, bir API key yapıştır, kredi kartı iste, sonra "ücretsiz" katmanın 10 isteklik olduğunu öğren. `fal-ai-alternative`, `kling-ai-wrapper`, `stable-diffusion-free-*` — hepsi ince bir arayüz, arkasında ücretli bir servis.

Bu repo tam tersi bir iddiada bulunuyor: **arka planı silmek, boyutlandırmak, formatı çevirmek, bir klipten GIF çıkarmak — bunların hiçbiri bir modele ihtiyaç duymuyor, bırakın başkasının ücretli modeline ihtiyaç duymayı.** Bu iş yerelde, CPU'da, anında biter.

| İddia edilen | Gerçek durum |
|---|---|
| "Ücretsiz AI studio" | Genelde ücretli API'ye ince bir kapı |
| Bu repo | 7 araç tamamen yerel (rembg/Pillow/ffmpeg) + 1 araç gerçekten ücretsiz hosted (Pollinations.ai) |
| API key gerekiyor mu? | Hayır — hiçbir araç için |
| Kredi kartı / hesap? | Hayır |
| Üretici (generative) model çağrısı? | Sadece `generate_image_free`, ve o da ücretsiz |

Deterministik işler yerelde kalır; tek üretici (generative) araç ücretsiz hosted bir API'ye gider ve **hiçbir zaman ücretli bir API'ye gitmez**. Bu, aşağıdaki [routing philosophy](#-routing-philosophy) bölümünde diyagramla anlatılıyor.

---

## 🧰 The toolbox

![tool grid](assets/tools-grid.svg)

| Tool | Engine | Does | Where it runs |
|---|---|---|---|
| ✨ `generate_image_free` | [Pollinations.ai](https://pollinations.ai) | Text → image, genuinely free, no signup or API key | hosted (free) |
| 🖼️ `remove_background` | `rembg` (ONNX) | Cuts out the subject → transparent PNG | local, CPU |
| 📐 `resize_image` | Pillow | High-quality Lanczos resize/fit | local, CPU |
| 🔄 `convert_format` | Pillow | PNG ⇄ JPG ⇄ WebP, flattens alpha for JPEG | local, CPU |
| 🎬 `video_thumbnail` | ffmpeg | Grabs a single frame from a video | local, CPU |
| 🎞️ `video_to_gif` | ffmpeg | Clip → optimized GIF (two-pass palette) | local, CPU |
| ✂️ `video_trim` | ffmpeg | Fast lossless cut, re-encode fallback if needed | local, CPU |
| 🔍 `upscale_image` | Real-ESRGAN via Vulkan (Upscayl's bundled binary) | Upscales an image | local, **GPU-bound** — see [limitation](#-known-limitation--dürüstlük-testi) |

Every tool takes a file path in, returns a file path out (`output/` inside the repo, timestamped). No hidden state, no queue, no polling.

---

## 🧭 Routing philosophy

![routing philosophy](assets/routing.svg)

Bu projenin gerçek fikri burada: bir dosya geldiğinde, **ne kadarının gerçekten bir modele ihtiyacı var?** Cevap: neredeyse hiçbiri.

- **7 araç** — `remove_background`, `resize_image`, `convert_format`, `video_thumbnail`, `video_to_gif`, `video_trim`, `upscale_image` — bu makinede, CPU üzerinde, deterministik olarak çalışır. `rembg`, `Pillow`, `ffmpeg` — network gerektirmez (upscale_image'in Vulkan binary'si de yerel çalışır, sadece GPU'ya ihtiyaç duyar).
- **1 araç** — `generate_image_free` — gerçekten üretici (generative) olduğu için tek başına hosted bir API'ye, Pollinations.ai'ye gider. Ücretsiz, key'siz, kayıtsız.
- **Hiçbir araç** ücretli bir API'ye gitmez. Bu bir tasarım kararı, bir eksiklik değil — bkz. [Neden var](#-neden-var--the-pitch).

Bu repo, ağır işi ([nvidia-nim-mcp](../cosmos-video)'nin ücretsiz katmanlı hosted modellerine) bırakan geniş bir kurulumun deterministik/mekanik tarafı olarak tasarlandı: üretim orada, temizlik/dönüştürme burada.

---

## ⚠️ Known limitation — dürüstlük testi

![known limitation](assets/limitation.svg)

`upscale_image` **gerçek ve doğru çalışıyor** — Real-ESRGAN modelini Vulkan üzerinden, Upscayl'in bundled binary ve modellerini yeniden kullanarak çağırıyor. Ama bu makinede test edildi ve dürüstçe raporlanıyor:

> Intel UHD (entegre, ayrı/discrete GPU yok) üzerinde tek bir küçük ikon **7+ dakikada, %32 ilerlemede** bile bitmedi.

Vulkan tabanlı upscaling'in etkileşimli olarak kullanılabilir olması için gerçekten ayrı bir GPU gerekiyor. Entegre grafikte:

- **Pratik seçenek**: `generate_image_free` kullan (hosted, saniyeler içinde).
- **Ya da**: bekle — araç doğru sonucu üretiyor, sadece yavaş.

Bu sınır kasıtlı olarak gizlenmiyor veya yumuşatılmıyor: `toolkit.py` içindeki `upscale_image` docstring'i bunu birebir söylüyor, `PROJECT.md` bunu kapsam dışı bırakıyor, ve bu README onu ilk sayfada tutuyor. Şeffaflık burada bug değil, özellik.

---

## ⚙️ Setup

```bash
uv sync
```

Bu, `rembg`, `Pillow`, `httpx`, `mcp[cli]` gibi tüm bağımlılıkları kurar. `ffmpeg`/`ffprobe` sistemde kurulu olmalı (PATH'te). `upscale_image` için ayrıca Upscayl'in bundled binary/modellerine ihtiyaç var (repo içinde `toolkit.py`'de yolu tanımlı).

## ✅ Running the tests

Her araç, gerçek üretilmiş fixture'lara karşı uçtan uca test edilir — mock yok, gerçek görsel/video dosyaları üretilip işlenir:

```bash
uv run pytest
```

`test_toolkit.py` şunları doğrular: aspect-ratio korumalı/korumasız resize, boyut validasyonu, eksik dosya hataları, JPEG için alfa düzleştirme, `remove_background`'ın gerçekten RGBA ürettiği, video thumbnail/GIF/trim'in beklenen çıktı ve süreleri, ve GIF üretiminin ara palet dosyasını temizlediği.

## 🔌 Registering as an MCP server

```bash
claude mcp add --transport stdio mini-creative-toolkit -- uv run --project /path/to/this/repo toolkit.py
```

Proje veya kullanıcı scope'unda kaydedilebilir. Kayıttan sonra 8 araç da (`generate_image_free`, `remove_background`, `resize_image`, `convert_format`, `video_thumbnail`, `video_to_gif`, `video_trim`, `upscale_image`) doğrudan çağrılabilir hale gelir.

## 📁 Project layout

```
mini-creative-toolkit/
├── toolkit.py          # MCP server + all 8 tools
├── test_toolkit.py      # end-to-end tests, real fixtures, no mocks
├── PROJECT.md            # scope, stack, definition of done
├── assets/
│   ├── banner.svg         # hero banner
│   ├── routing.svg        # local-vs-hosted routing diagram
│   ├── tools-grid.svg     # 8-tool icon grid
│   └── limitation.svg     # upscale_image honesty panel
└── output/                # generated files land here (timestamped)
```

## 📄 License

MIT
