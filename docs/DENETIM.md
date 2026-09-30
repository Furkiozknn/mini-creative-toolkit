# Denetim: mini-creative-toolkit (30 Eylül 2026)

Yenilemeden önce `master` (2.0.0, `fb458f5`) üzerinde, bu makinede (Windows 11 Home, Python 3.14.7 ve 3.12, uv 0.12.5, Git Bash, ffmpeg WinGet'ten) ölçüldü. Ölçülmeyen şey yazılmadı; ölçülemeyenler "ölçülmedi" diye işaretli. Ham çıktılar depo dışında: `kanit/mini-creative-toolkit/{once,sonra}/` (aynı 18 komut, iki sürüme karşı: `olc.py`; kabuksuz başlatıldı, yani cmd.exe/PowerShell gibi joker karakter genişletilmez).

## Temiz ortamda kurulum ve ilk sonuç

| Yol | Süre | Sonuç |
|---|---|---|
| `uvx --from git+https://github.com/Furkiozknn/mini-creative-toolkit mct --version` (boş uv önbelleği) | 22,2 s ve 20,8 s (iki ayrı koşu; 65 paket kurar) | `mct 2.0.0` |
| aynısı, önbellek sıcak | 3,8 s ve 3,3 s | aynı |
| `uv tool install git+https://...` (sıcak önbellek) | 4,8 s | `mct 2.0.0` (PATH uyarısı verir, komut çalışır) |
| `git clone --depth 1` + `uv sync` (boş önbellek) | 12,9 s | `uv run mct --version` 2,7 s |
| `mct <komut>` (kurulu, sıcak) | her çağrı 1,0-1,4 s (Python içe aktarmaları) | |
| `uvx ... mct serve` + `initialize` (stdio) | 7,0 s | 23 araç |

"Tek komutla kur, bir dakikada ilk sonuç" tutuyor: en kötü ölçüm ~22 s. Eski README'de bu komut yoktu (`uv sync` + klonlama vardı, PyPI'da paket yok: `pypi.org/pypi/mini-creative-toolkit/json` 404); `uvx --from git+...` yolu şimdi ilk ekranda.

## Testler

| | Toplanan | Geçti | Başarısız | Atlandı | Süre |
|---|---|---|---|---|---|
| Önce (`master`, Windows) | 327 | 314 | **10** | 3 | 474 s (7 dk 54 sn) |
| Sonra (Windows) | 347 | 342 | 0 | 5 | 45 s |
| Sonra (CI, Linux 3.11/3.12/3.13) | 347 | 347 | 0 | 0 | 49 s (3.12) |
| Sonra (CI, Windows Server, Python 3.12) | 347 | 342 | 0 | 5 | 76 s |

10 başarısızlığın hepsi testlerin Windows varsayımıydı, araç değil:

- **6 test**: alt süreç yalnızca `PATH` ve `HOME` ile başlatılıyordu; Windows'ta `SYSTEMROOT` yoksa `asyncio` Winsock'u yükleyemiyor (`WinError 10106`), sunucu ilk baytı yazmadan ölüyor ve test 90 sn boş bekleyip zaman aşımına düşüyordu (toplam süreyi 8 dakikaya çıkaran bu). Gerçek sunucu tam ortamla 4,1 s'de yanıt veriyor (`scripts/mcp_probe.py`).
- **1 test**: `/etc/hostname` var sayıyordu.
- **3 test**: dosya adı olarak `"`, `|`, `*` deniyordu; Windows'ta bu adlar yok.

Düzeltme: `tests/helpers.child_env` (SYSTEMROOT'u taşır), sunucu ölürse testin stderr ile hemen düşmesi, POSIX'e özgü adların Windows'ta atlanması, `/etc/hostname` yerine geçici dosya. Hiçbir test gevşetilmedi; 20 test eklendi (bkz. `TASARIM.md`). Kalan 5 atlama: 3 Windows'ta geçersiz dosya adı, 1 satır sonu içeren ad, 1 `mkfifo`.

## README komutları

| Komut | Sonuç |
|---|---|
| `uv sync` | çalıştı (12,9 s, boş önbellek) |
| `sudo apt-get install ffmpeg` / `brew install ffmpeg` | ölçülmedi (bu makine Windows; ffmpeg zaten kurulu) |
| `export UPSCAYL_BIN_PATH=...` (Upscayl) | ölçülmedi: bu makinede Upscayl ve ayrık GPU yok. `mct capabilities` `upscale_image`'i doğru biçimde NO + üç engelle listeliyor |
| `claude mcp add --transport stdio ... -- uv run --project ... toolkit.py` | **çalıştırılmadı** (kullanıcı yapılandırmasını değiştirir). Altındaki süreç, `python toolkit.py`'nin testi (`test_the_legacy_launcher_still_works`) ve stdio el sıkışması ile ölçüldü |
| `mct serve`, `python -m mini_creative_toolkit` | çalıştı (stdio el sıkışması, 23 araç) |
| `mct inspect`, `resize`, `convert` (webp, avif), `optimize` (`--goal web`, `--goal social --preset square`), `strip-metadata`, `watermark`, `thumbnail`, `gif`, `trim`, `compress`, `audio`, `contact-sheet`, `compare`, `capabilities`, `presets`, `models` | hepsi çalıştı, çıkış 0 (sentetik EXIF+GPS'li 1600x1200 JPEG ve 8 sn'lik test videosu) |
| `mct upscale photo.jpg --scale 2` | çalıştı (FSRCNN seçti ve nedenini söyledi); 1600x1200 fotoğraf 2x: ~3 s (model ısınmış), ilk çağrı 9,8 s |
| `mct remove-bg` | **ölçülmedi**: u2net ağırlıkları (176 MB) ilk kullanımda GitHub'dan iner; indirme izni verilmedi |
| `mct generate` | **çağrılmadı**: istemi üçüncü tarafa (Pollinations.ai) gönderir |
| `mct batch photos/*.jpg --operation optimize --options '{"goal":"web"}'` | bash'te çalıştı; **Windows'ta (kabuk genişletmezse) çalışmıyordu**, aşağıda |
| `mct thumbnail clip.mp4 --at 00:00:05` | çalıştı |

Sayılar: "23 tools" → `tools/list` 23 (uyuştu). "Of 23 tools, 22 run entirely on this machine" → `execution: local` 22 (uyuştu). **"22 report `network: none`" tutmuyor**: 21'i `none`, `remove_background` `first-run-only`, `generate_image_free` `required` (`Counter` ile ölçüldü). README başlığı ve `server.json` bu doğrulukla yazıldı; `project-meta.json`'daki `summary`/`key_features`/`social.headline` ve depo `description`'ı hâlâ "22 ... network: none" diyor (çözülmeyenler). "FSRCNN sub-second" yalnızca simge boyutu için doğru: 128x96 4x = 0,04 s, 512 2x = 0,36 s, 1600x1200 2x = 3,3 s (ölçüldü); README ve araç açıklaması düzeltildi. `mct capabilities` "checked nvidia-smi and /sys/class/drm" diyor: Windows'ta yalnızca `nvidia-smi` bakıyor, AMD ayrık GPU görünmez (ölçülmedi, koda göre).

## Hata mesajları ve `--help`

Çıkış kodları hep doğruydu (0/1/2). Sorun sözlerdeydi:

| Girdi | Önce | Sorun |
|---|---|---|
| `mct --help` | komut listesi | örnek yok, çıkış kodları yok, "ilk adım" yok |
| `mct resize --help` | `--width WIDTH` | argümanların çoğunun (`path`, `--width`, `--height`, `--start`, `--crf` ...) açıklaması yok |
| `mct capabilities` | tek satırda 23 araçlık JSON | okunmuyor (tek satır 11.150 karakter (ölçüldü)); `models`, `presets`, `compare`, `batch` sonucu da aynı |
| `mct batch nope*.jpg` (Windows kabuğu) | `paths[0] could not be read: Dosya adı, dizin adı veya birim etiketi sözdizimi hatalı` | cmd.exe/PowerShell `*.jpg`'i genişletmiyor; README'nin `mct batch photos/*.jpg` örneği Windows'ta çalışmıyordu, hata da neden olduğunu söylemiyordu |
| `mct batch ... -o x.jpg` | **sessizce yok sayılıyor** (README "açık output_path reddedilir" diyor) | Hata |
| `mct thumbnail clip.mp4 --at 99:00:00` | `Operation reported success but wrote no output for thumb-....png` | video kaç saniye, söylenmiyor |
| `mct upscale photo.jpg --scale 7` | `photo.jpg is 11200x8400 = 94,080,000 pixels ...` | girdi 1600x1200; mesaj çıktı boyutunu girdiye yüklüyor |
| `--options {bad` | `--options must be a JSON object: Expecting property name...` | örnek yok |
| MCP `initialize` | `serverInfo.version` = `""` | istemcilere ve kayıt defterine sürüm gitmiyor |

Önce/sonra: `kanit/mini-creative-toolkit/once/komutlar.txt`, `sonra/komutlar.txt`.

## MCP: el sıkışma, araç listesi, gerçek çağrılar, mcp-vet

`scripts/mcp_probe.py` sunucuyu stdio'da başlatıp bir istemci gibi konuşur (`initialize`, `tools/list`, 3 gerçek `tools/call`); çıktısı `docs/demo/komutlar.txt` sonunda:

- `initialize` 4,1 s (soğuk Python), protokol `2025-06-18`; 23 araç, 22 yerel + 1 barındırılan (`generate_image_free`).
- Araç açıklamaları (`tools/list`, tam metin `kanit/.../once/tools-list.txt`): en uzunu 743 karakter, **görünmez karakter yok** (Cf/Cc denetimi), modele yönelik gizli talimat yok. Açıklamaların hepsi kendi ihtiyacını (`[execution: local | network: none | requires binary: ffmpeg]`) yazıyor; `generate_image_free` üçüncü tarafa gittiğini büyük harfle söylüyor.
- Gerçek çağrılar: `inspect_media` (JPEG 1600x1200, `has_exif=True`), `strip_metadata` (`removed_exif=True`), yeniden `inspect_media` (`has_exif=False`); üçünde de `execution=local network=none`.
- **mcp-vet** (`mcp-vet audit --offline --path .`, klon `proje-yenileme/mcp-vet`): genel risk **MEDIUM**, çıkış 1, README'nin yazdığıyla aynı (`kanit/.../once/mcp-vet-audit.txt`). Kaynak-kod alanı HIGH görünüyor, çünkü `tests/test_paths_security.py:49` içinde `~root/.ssh/id_rsa` yolu **test verisi** olarak geçiyor; mcp-vet bunu kendisi "outside the shipped server" diye işaretliyor. Gönderilen kaynakta gerçek bulgular: dış süreç başlatma (ffmpeg, belgeli) ve tek gerçek dış ağ çağrısı (`engines/pollinations.py`); "UNEXPLAINED" listesindeki öteki alan adları README/test metinlerindeki bağlantılar. Araç-zehirlenmesi bulgusu yok.
- Ölçülmedi: `remove_background` ve `upscale_image` (yukarıdaki nedenlerle) araç çağrısı olarak, `generate_image_free`.

## awesome-mcp-servers hazırlığı (başvuru yapılmadı)

Hazır olanlar: README ilk ekranda tanım + tek komut + gerçek çıktılı demo; LICENSE (MIT); çalışan stdio sunucusu; araç açıklamaları temiz; CI. Eksik / Furki'nin kararı:

- `server.json` şemaya **uymuyordu** (`description` 190 karakter, üst sınır 100; "caption video" diye var olmayan bir yetenek yazıyordu). Düzeltildi, 2025-12-11 şemasına karşı doğrulandı. Ama `packages[0]` bir PyPI paketi bildiriyor ve **PyPI'da yok**; kayıt defterine göndermek için önce PyPI yayını (Trusted Publishing tanımı `yayinla.yml` başında yazılı) gerekir. Yapılmadı.
- Listeye önerilecek satır (gönderilmedi): `[Furkiozknn/mini-creative-toolkit](https://github.com/Furkiozknn/mini-creative-toolkit) <listenin Python/yerel/platform simgeleri> - 23 local media tools (resize, convert, strip EXIF/GPS, background removal, video trim, GIFs); 22 run on the CPU with no API key, the one hosted tool is labelled.` Listenin simge/kategori kurallarını başvuru anında yeniden kontrol etmek gerekir (bu oturumda okunmadı).
- Afiş (`assets/banner.svg`) hesabın üreticisinden geliyor ve "326 tests" / "22 of 23 never touch the network" diyor; bu depoda elle değiştirilmedi.

## Görseller

- `assets/demo.gif`, `docs/reel/reel.{gif,mp4}` (15 sn'lik "sesli reel"): üreticileri depoda yok, yeniden üretilemedi → README'den ve depodan çıkarıldı (git geçmişinde duruyor). `assets/demo.gif` altyazısı "every removed key is listed" diyordu; gerçek çıktı `removed_other_keys` listeliyor ama GPS anahtarlarını tek tek saymıyor, yalnızca `removed_exif: True`.
- `assets/tool-call.svg` "A real call and a real response" diyordu; içindeki `foto.jpg` 3024x4032 yanıtı elle yazılmış (`has_exif: false`), üreticisi yok → çıkarıldı; yerine `mcp_probe.py`'nin gerçek çıktısı kondu.
- `routing.svg`, `tools-grid.svg`, `limitation.svg`: kavramsal çizimler; sayıları (23 araç, gruplar) `tools/list` ile uyuşuyor, korundu. `limitation.svg`'nin "Intel ekran kartında 7 dakika" ölçümü bu makinede yeniden üretilemedi (Upscayl yok); önceki ölçüm olarak kaldı.

## Günlük "Ekosistem denetimi" (#19, profil deposu)

28 Eylül denetiminin son yorumunda (20 depoda 54 bulgu) `mini-creative-toolkit` geçmiyor; bu depoya ait açık bulgu yok, kapatılacak bir şey yok. Meta-source ayrışması bulguları (varsa) kapatılmadı.

## Çözülmeyenler

- `mct models` ve bilinmeyen `--model` ~9 s sürüyor (rembg/onnxruntime içe aktarımı); `models` listesi rembg'in kendi model adlarını da içerdiği için tembel içe aktarım tasarım değişikliği olurdu, dokunulmadı. Diğer her komut ~1,2 s.
- `project-meta.json`: `summary` "326 tests", `key_features`/`social.headline` "22 ... network: none"; GitHub `description` aynı. `/meta` işi ve meta-source ayrışması Furki'nin kararını bekliyor.
- PyPI yayını yok (yukarıda); `server.json` yayına hazır değil.
- `remove_background`, `upscale_image`, `generate_image_free` araç çağrısı olarak ölçülmedi.
