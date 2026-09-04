# PROJECT — mini-creative-toolkit

## Amaç / Goal

Yerelde, CPU üzerinde, deterministik olarak yapılabilecek medya işlerini
(arka plan silme, boyutlandırma, format çevirme, thumbnail, GIF, kırpma,
metadata temizleme, watermark, ses çıkarma, optimizasyon, toplu işlem) bir
MCP sunucusu olarak sunmak.

Temel fikir: **bu işlerin neredeyse hiçbiri bir modele ihtiyaç duymuyor.**
Ücretli bir API'ye hiç ihtiyaç duymuyor. Tek istisna açıkça işaretlenmiş ve
izole edilmiş durumda.

> Do the mechanical work locally. Use AI only when AI is actually necessary.
> Never hide external network calls. Never pretend a hosted model is local.

## Kapsam / Scope

**İçinde:** görüntü işleme (Pillow), süper çözünürlük (FSRCNN, CPU), arka
plan silme (rembg/ONNX, CPU), video ve ses işlemleri (ffmpeg), medya
inceleme (ffprobe), deterministik optimizasyon, toplu işlem, MCP sunucusu ve
aynı motoru kullanan bir CLI.

**Dışında:** bulut platformu, iş kuyruğu, veritabanı, web arayüzü, eklenti
çerçevesi, mikroservis mimarisi, ajan çerçevesi. Bu hâlâ yerel bir MCP
sunucusu; kurulumu basit, açılışı hızlı, bağımlılık grafiği küçük kalmalı.

**Sınırda:** GPU gerektiren Real-ESRGAN upscaling (`upscale_image`) destekli
ama isteğe bağlı — ne binary'si ne modelleri bu repoda, ikisi de indirilmiyor.
Tek hosted araç (`generate_image_free`) korunuyor ama tek bir motorun
arkasında izole.

## Mimari

```
src/mini_creative_toolkit/
  config.py         MCT_* ortam değişkenleri, limitler, izinli kökler
  errors.py         alan hataları (MCP'ye giden mesaj / verbose detay ayrı)
  validation.py     argv'ye ulaşan her değer buradan geçer
  paths.py          güvenilmeyen yol çözümleme + çıktı yöneticisi
  capabilities.py   her aracın gereksinimleri, tek kaynak
  media_info.py     inspect_media'nın motoru
  results.py        yapılandırılmış sonuç biçimi
  log.py            stderr'e, üç seviye, sır sızdırmaz
  engines/          ffmpeg, images (Pillow+OpenCV), background, upscayl, pollinations
  tools/            iş kuralları — MCP ve CLI ikisi de burayı çağırır
  server.py         MCP kaydı ve araç açıklamaları, iş mantığı yok
  cli.py            mct — aynı fonksiyonlar, farklı arayüz
```

Kural: iş mantığının tek bir kopyası var. `server.py` ve `cli.py` ikisi de
`tools/` çağırır; hiçbir kural iki yerde yazılmaz.

## Bağımlılık politikası

Bir bağımlılık sırf kullanışlı olduğu için eklenmez. Her biri için: neden
standart kütüphane yetmiyor, lisansı uyumlu mu, bakımı sürüyor mu, küçük bir
özellik için devasa bir çerçeve mi getiriyor. Gerekçeler `THIRD_PARTY.md`'de.

## Bitti tanımı / Definition of done

1. `uv sync` hatasız kurar.
2. `uv run pytest` tüm testleri geçer.
3. MCP sunucusu stdio üzerinden gerçekten el sıkışır ve araç listesini döner.
4. `mct` CLI çalışır.
5. `uv run toolkit.py` (eski çağrı biçimi) hâlâ çalışır.
6. Repoda hiçbir geliştiriciye özgü sabit yol kalmaz.
7. `shell=True` hiçbir yerde geçmez ve bunu bir test AST üzerinden doğrular.
8. Hosted çağrı tek bir dosyada izole kalır ve bunu bir test doğrular.
9. Testler Pollinations.ai'nin ayakta olmasına bağlı değildir.
