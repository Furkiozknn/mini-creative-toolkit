# Dikey video/foto otomatik kurgu için açık kaynak araçlar (CPU, HF kapalı)

**Yöntem:** Son etkinlik tarihleri `git clone --depth 1` ile alınan son commit'ten (28.09.2026). Sürümler PyPI JSON'dan. Model barındırıcılarına erişim bu konteynerde `curl -r 0-100` ile tek tek denendi. Yıldız sayıları GitHub sayfasından okundu; **≈** işaretliler bellekten tahmin, doğrulanmadı. (GitHub REST API bu oturumda kapalı; `github.com/<repo>/releases/download/...` indirmeleri ise çalışıyor.)

**Erişim testi (bu konteyner):**
- AÇIK: `github.com/.../releases/download/*`, `media.githubusercontent.com` (LFS), PyPI, npm
- KAPALI (000/403): `huggingface.co`, `openaipublic.azureedge.net` (openai-whisper .pt), `alphacephei.com` (Vosk modelleri), `storage.googleapis.com` (MediaPipe Tasks modelleri + Chrome-for-Testing), `download.pytorch.org` (CPU torch indeksi), `cloud.cp.jku.at` (beat_this), `remotion.media`, `playwright.azureedge.net`, `download.blender.org`, `cdn.jsdelivr.net`, `zenodo.org`
- Yerelde hazır Chromium var: `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`

---

## 1. Sanal çoklu kamera / yüz takipli yeniden kadraj / 9:16 akıllı kırpma
- `openshorts` ([mutonby/openshorts](https://github.com/mutonby/openshorts), 5,3k★, MIT (`cloud/` hariç), 2026) — sahne başına TRACK (MediaPipe + YOLOv8 yüz takibi), SPLIT (iki konuşmacıyı üst üste dizer), blur arka plan; öne çıkan anları LLM seçer (Gemini ya da Ollama). **Kısmen:** Docker ve 8 GB+ RAM ister. Kırpma çekirdeği CPU'da çalışır. YOLO ağırlıkları GitHub'da (erişilebilir). pip `mediapipe` 1.x wheel'inde model yok, modeller googleapis'ten iniyor (kapalı). En iyi fikir kaynağı; tamamını koşturmak ağır.
- `Autocrop-vertical` ([kamilstanuch/Autocrop-vertical](https://github.com/kamilstanuch/Autocrop-vertical), 336★, **lisans dosyası yok**, 2026) — PySceneDetect ile sahnelere böler, YOLOv8n ile kişi bulur, sahne başına ya sıkı kırpar ya letterbox yapar. **Evet:** `yolov8n.pt` `github.com/ultralytics/assets/releases`'ten iniyor (erişim testi 206). Ultralytics AGPL-3.0, torch da gerekiyor (PyPI'daki torch CUDA sürümü, büyük ama CPU'da çalışır). Lisans olmadığı için kodu kopyalama; yaklaşımı örnek al.
- `AI-Youtube-Shorts-Generator` ([SamurAIGPT/…](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator), 4,2k★, MIT, 2026) — `--mode local`: faster-whisper, OpenCV yüz takibi ve hareket yumuşatma. **Kısmen:** kırpma kısmı CPU'da çalışır; faster-whisper modelleri HF'de (kapalı); öne çıkan an seçimi OpenAI/Gemini anahtarı ister.
- `PySceneDetect` ([Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect), ≈4k★, BSD-3, 2026; pip `scenedetect` 0.7.1) — kesme/sahne tespiti, punch-in noktalarının temeli. **Evet:** model gerekmez.
- Kendi "AI multicam" katmanın: `mediapipe==0.10.21` (cp311 wheel). **Doğrulandı:** wheel içinde `face_detection_short_range.tflite`, `face_detection_full_range_sparse.tflite`, `selfie_segmentation*.tflite`, `pose_*.tflite` gömülü (eski `mp.solutions` API'si). 1.0.1 wheel'inde 0 tflite var, o yüzden **0.10.21'e sabitle**. Alternatif: OpenCV YuNet (`media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx`, 206), `cv2.FaceDetectorYN` ile çalışır. Kurgu kısmı (yüz kutusu + ses enerjisi/konuşma → kırpma/zoom anahtar kareleri → ffmpeg `crop`/`zoompan`) elle yazılır.
- Google AutoFlip (mediapipe içinde, C++/Bazel) — **Hayır:** bakımı yok, derlemesi ağır, modelleri googleapis'te.

## 2. Sessizlik kesme / jump cut
- `auto-editor` ([WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor), 5,4k★, Unlicense/public domain, 2026-09) — ses/hareket eşiğiyle sessizliği atar; ffmpeg, Premiere/Resolve/FCP XML çıkarır. **Evet:** Nim ile yazılmış tek dosyalık ikili, `https://github.com/WyattBlue/auto-editor/releases/download/31.6.0/auto-editor-linux-x86_64` (206). PyPI'daki `auto-editor` 29.3.1 yalnızca 5 KB'lık bir sarmalayıcı ve güncel sürümün (31.6.0) gerisinde; GitHub ikilisini kullan.
- `jumpcutter` ([carykh/jumpcutter](https://github.com/carykh/jumpcutter), ≈3k★, MIT, 2021) — ilk örnek; **eski**, yerine auto-editor.
- Yedek plan: ffmpeg `silencedetect` + sherpa-onnx `silero_vad.onnx` (GitHub releases, 206) ile kendi kesme listeni üret. Model gerekmez ya da GitHub'dan iner.

## 3. Kelime zaman damgalı konuşma tanıma (CPU, HF dışı ağırlık)
- `sherpa-onnx` ([k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx), 13,8k★, Apache-2.0, 2026-09; pip 1.13.8, cp311 manylinux wheel) — onnxruntime tabanlı, torch gerektirmez. **Evet, en güçlü seçenek.** Ağırlıklar **GitHub releases `asr-models` etiketinde**, hepsi 206 döndü:
  - `sherpa-onnx-whisper-{tiny,small,medium,turbo}.tar.bz2`: çok dilli Whisper, **Türkçe var**. Kelime düzeyi zaman damgası desteği **doğrulanmadı** (büyük olasılıkla segment düzeyi).
  - `sherpa-onnx-omnilingual-asr-1600-languages-300M-ctc-int8-2025-11-12.tar.bz2`: Meta Omnilingual CTC, 1600 dil (Türkçe dahil olmalı). CTC olduğu için token zaman damgası vermesi beklenir; **bilinmiyor, denenmeli**.
  - `silero_vad.onnx`: VAD.
  - `nemo-parakeet-tdt-0.6b-v3`: 25 Avrupa dili, Türkçe **yok**.
- `vosk-api` ([alphacep/vosk-api](https://github.com/alphacep/vosk-api), 15k★, Apache-2.0, 2026-08; pip `vosk` 0.3.45) — kelime zaman damgası yerleşik, Türkçe model var (`vosk-model-small-tr-0.3`). **Hayır (modeller yüzünden):** modeller yalnızca `alphacephei.com/vosk/models`'te (kapalı), GitHub'da yok. Pip paketi kurulur ama modeli elle yüklemek gerekir.
- `whisper.cpp` ([ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp), 54k★, MIT, 2026-09; pip `pywhispercpp` 1.5.1) — `-ml 1` ile kelime zaman damgası verir, CPU'da hızlı. **Hayır (modeller yüzünden):** ggml modelleri `huggingface.co/ggerganov/whisper.cpp`'de. Dönüştürme betiği openai `.pt` dosyası istiyor, o da kapalı.
- `openai-whisper` ([openai/whisper](https://github.com/openai/whisper), ≈90k★+, MIT, 2026) — `word_timestamps=True` var. **Hayır:** ağırlıklar `openaipublic.azureedge.net`'te (kapalı).
- `faster-whisper` ([SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper), ≈20k★, MIT, 2025-11) ve `whisper-timestamped` (GPLv3) — **Hayır:** CTranslate2 modelleri HF'de; whisper-timestamped openai ağırlığını kullanıyor.
- Yol: sherpa-onnx Whisper small/turbo ile metin, Omnilingual CTC ile hizalama/kelime zamanı. İkisi de denenmeden "çalışıyor" denemez.

## 4. Tek görüntüden derinlik (2.5D paralaks / Ken Burns)
- `Depth-Anything-ONNX` ([fabio-sim/Depth-Anything-ONNX](https://github.com/fabio-sim/Depth-Anything-ONNX), 446★, Apache-2.0, 2024) — Depth Anything V1/V2'nin hazır ONNX dosyaları. **Evet:** `releases/download/v2.0.0/depth_anything_v2_vits.onnx` ve `_dynamic` (206); onnxruntime ile CPU'da çalışır. Not: Depth-Anything-V2 **Small** Apache-2.0; Base/Large CC-BY-NC.
- `MiDaS` ([isl-org/MiDaS](https://github.com/isl-org/MiDaS), 5,4k★, MIT, 2024) — **Evet:** ağırlıklar GitHub releases'te (`v2_1/midas_v21_small_256.pt`, `v3_1/dpt_swin2_tiny_256.pt`, 206; ayrıca `dpt_levit_224`, `dpt_beit_large_512`…). torch gerekir; `midas_v21_small` OpenCV DNN'e de uyarlanabilir.
- `Depth-Anything-V2` ([DepthAnything/Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2), ≈7k★, Apache-2.0 (Small), 2026) — **Hayır doğrudan:** `.pth` dosyaları HF'de. Yukarıdaki ONNX sürümünü kullan.
- `DepthFlow` ([BrokenSource/DepthFlow](https://github.com/BrokenSource/DepthFlow), 1,5k★, **AGPL-3.0**, 2026-08; pip `depthflow` 1.0.1) — GLSL ışın yürütme ile paralaks video, animasyon ön ayarları hazır. **Kısmen:** varsayılan tahminci `transformers.from_pretrained` üzerinden HF'ye gidiyor (kapalı). Ama `scene.input(image=..., depth=...)` dışarıdan derinlik alıyor (ONNX'ten üretilen harita verilebilir). OpenGL 3.3 istiyor: GPU yoksa Mesa llvmpipe/EGL gerekir, **denenmedi**. Pip bağımlılığı olarak torch ve transformers da geliyor (ağır).
- `3d-ken-burns` ([sniklaus/3d-ken-burns](https://github.com/sniklaus/3d-ken-burns), ≈1,5k★, **CC BY-NC-SA**, 2026) ve `3d-photo-inpainting` ([vt-vl-lab](https://github.com/vt-vl-lab/3d-photo-inpainting), ≈7k★, 2021) — **Hayır:** CUDA/cupy gerektiriyor, ticari olmayan lisans, eski.
- Pratik yol: DA-V2-Small ONNX ile derinlik, ardından OpenCV `remap` ile katmanlı kaydırma (ya da ffmpeg `displace`), hepsi CPU'da.

## 5. Arka plan silme / kişi segmentasyonu (CPU)
- `rembg` ([danielgatis/rembg](https://github.com/danielgatis/rembg), 24,6k★, MIT, 2026-09; pip 2.0.85, Python ≥3.11) — **Evet:** kaynak koddaki bütün `.onnx` adresleri `github.com/danielgatis/rembg/releases/download/v0.0.0/` altında. `u2net`, `u2netp`, `u2net_human_seg`, `isnet-general-use`, `silueta`, `BiRefNet-portrait-epoch_150`, `BiRefNet-general-bb_swin_v1_tiny-epoch_232` denendi, hepsi 206. onnxruntime ile CPU'da çalışır. BiRefNet CPU'da yavaştır; tek foto için iyi, video için ağır.
- `RobustVideoMatting` ([PeterL1n/RobustVideoMatting](https://github.com/PeterL1n/RobustVideoMatting), ≈9k★, GPL-3.0, 2023) — zamansal tutarlı video matting. **Evet:** `releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx` (206), CPU'da düşük çözünürlükte kabul edilebilir hızda.
- `mediapipe==0.10.21` selfie segmentation — **Evet:** model wheel'in içinde (doğrulandı). En hızlısı ama kenarları kaba. Yeni Tasks API'si (1.x) modeli googleapis'ten indiriyor, o yol **kapalı**.
- OpenCV DNN / opencv_zoo ([opencv/opencv_zoo](https://github.com/opencv/opencv_zoo), ≈1k★, Apache-2.0, 2026) — `human_segmentation_pphumanseg` ve YuNet, LFS üzerinden `media.githubusercontent.com` ile iniyor. **Evet.**

## 6. Blender otomasyonu (bpy)
- **PyPI `bpy`:** 5.2.2 (15.09.2026) **yalnızca Python 3.13** (5.1.0'dan beri cp313). **Python 3.11 için son sürüm `bpy==5.0.1`** (16.12.2025, cp311, manylinux_2_28_x86_64, wheel ≈356 MB). LTS dalı `4.5.9` da cp311. Kurulu boyut 1 GB civarında olabilir (tahmin). `download.blender.org` kapalı, yani PyPI tek yol.
- Headless render: **Cycles CPU güvenilir.** EEVEE arka plan kipinde OpenGL/EGL ister; GPU yoksa Mesa llvmpipe ile çalışabilir ama **denenmedi**, riskli say. Önerim: Cycles CPU, düşük örnek sayısı (16–32) ve OpenImageDenoise; ya da Workbench motoru.
- Örnek depolar:
  - `blender-cli-rendering` ([yuki-koyama](https://github.com/yuki-koyama/blender-cli-rendering), 827★, GPL-3.0) — komut satırından Cycles render örnekleri (kamera, ışık, malzeme). İyi bir iskelet ama Blender 2.93 hedefli, API farkları olacak.
  - `blenderless` ([oqton/blenderless](https://github.com/oqton/blenderless), pip var, ≈100★, tahmini) — bpy ile headless sahne/render sarmalayıcısı.
  - `blender-python-toolkit` ([AleBrito124356](https://github.com/AleBrito124356/blender-python-toolkit), 2★, MIT) — turntable, kamera yörüngesi, MP4; EEVEE öncelikli, Cycles CPU'ya geri düşüyor. Küçük ama tam bu senaryonun iskeleti.
  - "Telefon ekranına video dokusu" için hazır ve olgun bir açık kaynak depo **bulamadım**. Yazılması kolay: ekran yüzeyine `ShaderNodeTexImage` + `image.source='MOVIE'` + Emission, kamera anahtar kareleri, telefon modeli de bpy ile prosedürel (yuvarlatılmış küp + bevel).

## 7. Programatik motion graphics / şablonlar
- `MoviePy 2` ([Zulko/moviepy](https://github.com/Zulko/moviepy), 14,8k★, MIT, 2026-08; pip 2.2.1) — Python ile kompozit, metin, geçiş. **Evet:** saf CPU, ffmpeg (imageio-ffmpeg) üzerinden. Yavaş ama kurulumu sorunsuz.
- `Remotion` ([remotion-dev/remotion](https://github.com/remotion-dev/remotion), 60,9k★, **özel lisans**: bireylere ücretsiz, belirli büyüklüğün üzerindeki şirketlere ücretli (eşiği LICENSE.md'den doğrula), 2026-09; npm `@remotion/renderer` 4.0.529) — React ile video. **Kısmen, büyük olasılıkla evet:** kendi Chrome Headless Shell'ini `remotion.media`'dan indiriyor (kapalı). Yereldeki `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` `browserExecutable` ile verilebilir, **denenmedi**. CPU render, yazılım GL (SwiftShader).
- `Revideo` ([redotvideo/revideo](https://github.com/redotvideo/revideo), 4,1k★, MIT, 2026-07) — Motion Canvas çatalı, `renderVideo()` ile headless tarayıcıda render. **Kısmen:** puppeteer tarayıcısı Chrome-for-Testing'den iner (kapalı); yerel Chromium'u göstermek gerekir.
- `Motion Canvas` ([motion-canvas/motion-canvas](https://github.com/motion-canvas/motion-canvas), 19k★, MIT, 2026-07) — TS/canvas animasyon, seslendirmeyle senkron. **Kısmen:** varsayılan render editör/tarayıcı UI'ında; headless için Revideo daha uygun.
- `editly` ([mifi/editly](https://github.com/mifi/editly), 5,5k★, MIT, 2025-02) — JSON5 tanımlı klip, geçiş ve başlık, ffmpeg çıktısı. **Kısmen:** `headless-gl` (node-gyp ya da önceden derlenmiş ikili) ve Linux'ta `xvfb` + Mesa gerekir, tarayıcı gerekmez. Kurulumu kırılgan.

## 8. Vuruş (beat) tespiti
- `librosa` ([librosa/librosa](https://github.com/librosa/librosa), ≈8k★, ISC, 2026-09) — `beat_track`, `onset_detect`. **Evet:** Python 3.11'de **`librosa==0.11.0`** (1.0.0 Python ≥3.12 istiyor). Model gerekmez.
- `madmom` ([CPJKU/madmom](https://github.com/CPJKU/madmom), ≈1,6k★, kod BSD, **modeller CC BY-NC-SA**, 2024) — RNN+DBN ile en isabetli klasik beat/downbeat. **Kısmen:** PyPI 0.16.1 (2018) yalnız sdist, Python 3.11 ve NumPy 2 ile derlenmesi büyük olasılıkla kırık; `git+https://github.com/CPJKU/madmom` (modeller git alt modülü, GitHub'da) ile kurulmalı. Ticari olmayan model lisansına dikkat.
- `beat_this` ([CPJKU/beat_this](https://github.com/CPJKU/beat_this), 376★, MIT, 2026-05; pip `beat-this` 1.1.0) — güncel en iyi beat/downbeat tracker, CPU'ya düşebiliyor. **Hayır (modeller yüzünden):** checkpoint'ler `cloud.cp.jku.at`'ta (kapalı); torch da gerektirir.
- `aubio` ([aubio/aubio](https://github.com/aubio/aubio), ≈3,5k★, GPL-3.0, 2026-04) — hafif C, gerçek zamanlı `tempo`/`onset`. **Kısmen:** PyPI 0.4.9 (2019) yalnızca sdist, derleme gerekir ve NumPy 2 ile sorun çıkarabilir.

---

## Önerilen yığın
1. **Kırpma / sanal multicam:** `mediapipe==0.10.21` (gömülü yüz modeli) ya da OpenCV YuNet ile yüz takibi, `scenedetect` ile sahneler, kendi yumuşatmalı kırpma/zoom planın, ffmpeg `crop`/`zoompan`. Autocrop-vertical ve openshorts yalnızca tasarım referansı.
2. **Jump cut:** `auto-editor` GitHub ikilisi (31.6.0); yedek olarak ffmpeg `silencedetect` + silero_vad.
3. **Altyazı / kelime zamanı:** `sherpa-onnx` + GitHub'daki `sherpa-onnx-whisper-small`/`turbo` (Türkçe), kelime zamanı için Omnilingual CTC denemesi. Sonra ffmpeg libass ile kelime kelime vurgulu ASS altyazı.
4. **2.5D foto:** `depth_anything_v2_vits.onnx` (fabio-sim releases) ile onnxruntime, sonra OpenCV katmanlı paralaks. DepthFlow yalnızca OpenGL denemesi başarılı olursa.
5. **Arka plan silme:** `rembg` (u2net_human_seg / BiRefNet-portrait, GitHub'dan). Video için RVM ONNX ya da mediapipe selfie.
6. **3D mockup:** `bpy==5.0.1` (Python 3.11, ≈356 MB wheel) + Cycles CPU, düşük örnek + denoise.
7. **Şablon ve motion:** MoviePy 2 (Python, sorunsuz) ya da ffmpeg filtre grafikleri. Zengin tipografi/animasyon gerekirse yerel Chromium ile Remotion veya Revideo (önce tarayıcı yolunu dene; Remotion lisansını kontrol et).
8. **Vuruş:** `librosa==0.11.0` (kurulumu kolay). Daha isabetli sonuç gerekirse madmom'u git'ten kur (ticari olmayan model lisansı).

**Engelli, elle yükleme gerektiren:** Vosk Türkçe modeli (alphacephei), whisper.cpp ggml ve faster-whisper (HF), openai-whisper .pt (azureedge), beat_this checkpoint (JKU), MediaPipe Tasks modelleri (googleapis). Bu dosyalar kullanıcı tarafından konteynere kopyalanırsa ilgili araçlar da kullanılabilir hale gelir.
