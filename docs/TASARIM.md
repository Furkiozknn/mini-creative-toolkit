# Tasarım: mini-creative-toolkit ilk kullanım ve README yenilemesi (30 Eylül 2026)

## Hedef

Videodan ya da profilden gelen biri ilk dakikada şunu yapabilmeli: aracın ne yaptığını tek cümlede anlamak, tek komutla çalıştırmak (`uvx --from git+... mct inspect photo.jpg`), MCP istemcisine tek satırla bağlamak, ilk sonucu ve yanıtın kendi `execution`/`network` beyanını görmek; ilk komutu yanlış yazarsa doğrusunu ekranda görmek. Çekirdek davranış (23 araç, sonuç sözleşmesi, `--json`, çıkış kodları 0/1/2, güvenlik modeli) değişmedi; sürüm numarası artmadı (2.0.0).

## Önce / sonra

| Konu | Önce | Sonra |
|---|---|---|
| README ilk ekranı | banner, sesli reel GIF'i, altı rozet, elle yazılmış "gerçek çağrı" SVG'si, ikinci GIF; kurulum "Install" bölümünde ve yalnız `uv sync` (klon gerekir) | banner, tek cümlelik tanım (doğru sayılarla), tek komut (`uvx`), tek satır `claude mcp add`, 18 sn gerçek çıktılı terminal demosu, ölçülmüş süre (21 s / 3 s), "ne zaman kullanılır / kullanılmaz" tablosu, sonra rozetler ve eski gövde |
| Demo | kaynağı depoda olmayan `assets/demo.gif`, `docs/reel/*`, elle yazılmış `tool-call.svg` | `scripts/demo-uret.py`: 5 komut gerçekten koşulur, `docs/demo/komutlar.txt` kayıttır, sayfa o kaydı yazma animasyonuyla oynatır; `demo-kayit.js` mp4/gif alır |
| MCP tarafını göstermek | yoktu | `scripts/mcp_probe.py`: stdio'da `initialize`, `tools/list`, 3 gerçek çağrı, görünmez karakter denetimi; demonun son komutu |
| `mct --help` | komut listesi | ilk adımlar (5 çalışan komut), çıktının nereye yazıldığı, çıkış kodları, "yalnız `generate` veriyi dışarı yollar" |
| `mct <komut> --help` | `--width WIDTH` (açıklamasız) | her argümanın açıklaması var (test denetliyor) |
| `capabilities` / `models` / `presets` | tek satırlık JSON yığını | tablo (araç, hazır mı, ağ, ihtiyaç; engeller ayrı satırda); `compare`, `batch` sonuçları bir olgu/satır; `--json` aynı |
| Joker karakter (Windows) | `mct batch nope*.jpg` → yerelleştirilmiş Windows hatası | `mct` kendisi genişletir; eşleşme yoksa `no file matches 'nope*.jpg'`. Yalnızca o ada sahip dosya yoksa genişletir (`shot[1].png` hâlâ bulunur) |
| `batch -o x.jpg` | sessizce yok sayılıyordu | kullanım hatası (çıkış 2) |
| `thumbnail --at 99:00:00` | "reported success but wrote no output" | "clip.mp4 is 8.0 s long, so there is no frame at 99:00:00. Pick a time before 8.0 s." |
| upscale piksel sınırı | "photo.jpg is 11200x8400" (girdi 1600x1200) | "upscaling x7 photo.jpg would produce 11200x8400 ..." |
| `--options` bozuksa | JSON ayrıştırma hatası | + çalışan örnek |
| MCP `serverInfo.version` | boş | paket sürümü |
| `server.json` | şemaya uymuyordu (description 190 > 100 karakter, var olmayan "caption video") | şemaya karşı doğrulanmış |
| "22 araç `network: none`" | 21 doğru + 1 yanlış (`remove_background` `first-run-only`) | README ve `server.json` doğru cümleyi söylüyor |
| "FSRCNN sub-second" | her boyut için | simge 0,04 s, 1600x1200 2x ~3 s |
| Testler | Windows'ta 10 başarısız, 474 s | Windows'ta 342 geçti / 5 atlandı, 45 s; CI'da Windows işi |
| Test sayısı | 327 | 347 (+20) |

## CLI akışı

```
kur            uvx --from git+https://github.com/Furkiozknn/mini-creative-toolkit mct ...     (ya da uv tool install git+...)
bak            mct inspect photo.jpg              ne olduğu, EXIF var mı; dosyaya dokunmaz
işle           mct strip-metadata photo.jpg       yeni dosya yazar, neyin gittiğini listeler
               mct optimize photo.jpg --goal web  her ödünleşme raporlanır
ne çalışır     mct capabilities                   araç araç: hazır mı, neden değil
MCP            claude mcp add ... -- uvx --from git+... mct serve
istemci gibi   python scripts/mcp_probe.py photo.jpg
yanlış komut   mct: <ne oldu>  → çıkış 1 (işlem) ya da 2 (kullanım)
```

## Kararlar ve sınırlar

- **Görsel dil (video sisteminden alınanlar).** README görselleri ve demo FRK-OS kimliğinde:

  | Ne | Nereden | Nerede |
  |---|---|---|
  | zemin `#0e0d0b`, panel `#14120e`, yazı `#f1ece2`, vurgu `#ffc21a` | `sosyal/uret/tema.mjs` `klasik.akis` | terminal sahnesi zemini, panel, metin, `$` istemi ve sol çizgi |
  | `#ff4d6d` (mercan), `#19d3e6` (camgöbeği) | `tema.mjs` klasik vurgular | yalnız boyama: `has_exif: True` mercan, `False` ve `network: none` camgöbeği, `removed_exif: True` sarı. Metin değişmez |
  | `doku: "izgara"` | `tema.mjs` | gövdede soluk sabit ızgara (`rgba(241,236,226,.045)`, 48 px) |
  | JetBrains Mono | `tema.mjs` `F.jb` | tüm terminal metni; SIL OFL 1.1, `assets/yazi/` (mcp-vet deposundaki kopya, yerel dosya; indirme yok) |
  | `terminal: "koyu"` sahnesi, 30 ms/harf, satır satır çıktı | `tema.mjs` `tercih.terminal`, `sahne.js` | `scripts/demo-uret.py` sayfası |

  Bilerek alınmayanlar: League Gothic başlık (README'nin görsel başlığı yok), geçişler (çıktının kendisi okunmalı). `prefers-reduced-motion`'da imleç yanıp sönmesi kapalı.
- Kontrast (panel `#14120e` üstünde, WCAG göreli parlaklıktan hesaplandı): krem 15,9:1, sönük metin `#b6ae9d` 8,5:1, sarı 11,6:1, mercan 5,8:1, turuncu 7,2:1, camgöbeği 10,2:1; hepsi ≥ 4,5:1.
- **Banner değişmedi.** `assets/banner.svg` hesabın üreticisinden geliyor ("326 tests", "22 of 23 never touch the network"); bu depoda elle değiştirmek üreticinin bir sonraki çıktısında silinir.
- Demo, sentetik bir fotoğrafla çalışır (EXIF + GPS etiketli, `make_photo()`); kimsenin fotoğrafı ve konumu ekranda yok. `komutlar.txt` başında yazılı.
- Dikey 1080x1920 kayıt (`demo-dikey.mp4`) depoya girmedi (`.gitignore` `*.mp4` zaten engelliyor); günlük video hattı için `sosyal/medya/projeler/mini-creative-toolkit/terminal.mp4` (17,7 sn, H.264 yuv420p, +faststart, sessiz) ve aynı dizinde `komutlar.txt`.
- CI: `windows` işi eklendi (`windows-latest`, choco ile ffmpeg, tam paket). Sürüm, etiket, PyPI, dizin/awesome-list başvurusu, Pages ve GitHub description/homepage **yapılmadı** (onay kapısı).
