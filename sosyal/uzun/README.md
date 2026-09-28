# uzun: 2,5 dakikalık Reels (kişisel tanıtım)

İlk uzun Reels'in üretim hattı (28.09.2026). Seslendirme zamanı yönetiyor: her bölüm
cümleleri kadar sürer, altyazı aynı cümlelerden gelir, kayma olmaz.

| Adım | Dosya | Ne |
|---|---|---|
| 1 | `metin.py` | Bölümler ve cümleler (ekran metni, gerekirse ayrı okunuş) |
| 2 | `vo.py` | Türkçe seslendirme: sherpa-onnx + Piper `tr_TR-fettah-medium` (GitHub releases, veri seti CC0). Sentez ses. |
| 3 | `hf_kartlar.py` | Bölüm kartları ve açılış: HyperFrames + GSAP |
| 4 | `web_kayit.py` | Web projelerini Playwright ile dikey kaydeder (yerel http sunucu) |
| 5 | oyun kaydı | Godot `--write-movie` + xvfb, oyunların kendi botlarıyla (aşağıda) |
| 6 | `kurgu.py` | Kurgu: kartlar, oyun panelleri + ikinci kamera, web telefon çerçevesi, veri haritası, araç demoları, rakamlar, kapanış; müzik yan zincirle kısılır, −14 LUFS |

Godot oynanış kaydı (ekran kartı yok, llvmpipe ile çalışıyor):
```bash
xvfb-run -a -s "-screen 0 1280x720x24" godot --path <oyun> --rendering-driver opengl3 \
  --resolution 1280x720 --fixed-fps 60 --write-movie /tmp/x.avi --scene res://tools/rota.tscn -- --tani 5
```
Kanca `rota.tscn --tani N` ve Yerçekimi Çevir `bot.tscn -- 1 N - insan` dosya yazmaz. Tek Tuş Koşu için
`oyun.tscn`'u `bot_modu = true` ile açan geçici bir SceneTree betiği; depoya eklenmedi.
`--import` bazı depolarda `.import` dosyası üretebiliyor; kayıttan sonra `git status` temiz olmalı.

Seslendirme kontrolü: her cümle `stt.py` ile geri yazıya çevrildi. "Klod Kod" ve araç adları okunmadığı için cümleler adsız kuruldu, adlar ekranda.
