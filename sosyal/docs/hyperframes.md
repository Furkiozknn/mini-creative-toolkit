# HyperFrames bu ortamda nasıl çalışır

HeyGen'in açık kaynak (Apache-2.0) aracı: HTML + CSS + GSAP animasyonu → deterministik MP4.
Motion graphics, kinetik tipografi, kelime altyazısı, veri grafiği şablonları hazır (`npx hyperframes catalog`).

Ölçülen (28 Eylül 2026, bu konteyner, CPU): `warm-grain` örneği 1080×1920, 10 sn → **22,4 sn** render.

```bash
export DO_NOT_TRACK=1 HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1
export HYPERFRAMES_BROWSER_PATH=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell
cd ~/hf && npx hyperframes init proje --example warm-grain --resolution portrait --non-interactive
# GSAP CDN'den yüklenemiyor: yerel kopyaya çevir
cd proje && for f in $(grep -rl "cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js" . --include=*.html); do
  cp ../node_modules/gsap/dist/gsap.min.js "$(dirname $f)/"; sed -i 's#https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js#gsap.min.js#' $f; done
npx hyperframes render -o cikti.mp4
```

Tuzaklar:
- CDN'e bağlı her kütüphane aynı hatayı verir (`sub_timeline_script_failure`); yerel kopya şart.
- `whisper-cpp`, Kokoro TTS ve MusicGen isteğe bağlı; burada kurulu değil. Altyazı için `bulut/altyazi_tr.py` ya da `stt.py`, müzik için `muzik.py`.
- Telemetri varsayılan açık; yukarıdaki iki değişken kapatır.
- Kullanıcının bilgisayarında (Claude Code) eklenti olarak da kurulu: `hyperframes@hyperframes` 0.8.85.
