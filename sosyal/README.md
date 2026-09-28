# sosyal: dikey video ve fotoğraf araçları

Reels, TikTok, Shorts ve hikâye için CPU'da çalışan küçük araçlar. Hepsi ffmpeg,
OpenCV ve GitHub release'lerinden inen modellerle çalışır (Hugging Face gerekmez).

| Araç | Ne yapar |
|---|---|
| `sosyal.py` | Oyun/uygulama tanıtımı: 16 şablon sırayla döner, müzik her videoda değişir. `--tur hikaye` veya `reels` (farklı güvenli alanlar). |
| `kisi.py video` | Kişi videosu: yüze göre 9:16 kadraj, sessizlik kesme, her iki kesimde bir hafif yakınlaştırma, renk, ses −14 LUFS, kanca yazısı, kelime kelime altyazı. |
| `kisi.py foto` | Portre: yüze göre 4:5 / 9:16 / 1:1 kırpma, renk, başlık. |
| `kamera.py` | Tek açıdan çekimden sanal çoklu kamera: geniş / orta / yakın plan, yüz takibi, itme-çekme, whip-pan. |
| `stt.py` | Çevrimdışı konuşma tanıma (Whisper-small, Türkçe dahil) ve yaklaşık kelime zamanları. |
| `derinlik.py` | Fotoğraftan 2.5B "3D foto" hareketi (Depth-Anything-V2-Small). |
| `efektler.py` | 5 altyazı stili (hormozi, mrbeast, kutu, pop, sade), yazı kişinin arkasında, renk vurgusu, sentez ses efektleri, müziğin vuruşuna göre foto dizisi, ilerleme çubuğu ve döngülü bitiş. |
| `muzik.py` | Gerçek çalgı sesleriyle (GeneralUser GS soundfont) 7 türde tohumlu arka plan müziği: lofi, synthwave, trap, epik, funk, chiptune, akustik. `--sira` her çağrıda sıradaki türü seçer, aynı tür art arda gelmez. |
| `bilgi/` | Fotoğrafsız, yalnız doğrulanmış bilgiden 3 video şablonu: kinetik rakamlar, terminal hikâyesi, veri haritası. |
| `foto_oyun_montaj.py` | Tek fotoğraf + oyun ekranları: kişi çıkartma olarak, vuruşa göre kesilen 12 sn Reels. |
| `efektler.emoji()` / `GORUNUMLER` | Renkli emoji (Twemoji, CC BY 4.0: paylaşımda "Twemoji" atfı) ve 6 renk görünümü (sıcak film, teal-turuncu, soğuk temiz, vintage, siyah-beyaz, canlı); şablon ve müzik gibi sırayla dönsün. |
| HyperFrames | HTML + GSAP → MP4 (HeyGen, Apache-2.0). Kurulum ve CDN tuzağı: `docs/hyperframes.md`. |
| `bulut/` | Higgsfield sandbox'ında: web oyunundan gerçek oynanış kaydı, faster-whisper ile gerçek kelime zamanlı Türkçe altyazı, edge-tts Türkçe seslendirme. Ayrıntı `bulut/README.md`. |
| `blender_mockup.py` | Videoyu 3D bir telefonun ekranında oynatan Blender sahnesi ve kamera hareketi (yavaş: kare başına ~6 sn CPU). |

Kurulum: `./kurulum.sh` (Blender için `./kurulum.sh --blender`).
Ortam değişkenleri: `SOSYAL_MODELLER` (modeller), `OYUN_KOK` (oyun depoları, müzik için), `REEL_KAYNAK` (16:9 kaynak reel'ler).

Araştırma notları `docs/` altında: `viral-rehber.md` (platform kuralları, güvenli alanlar, kaynaklı),
`teknikler.md` (40 düzenleme tekniği, çok dilli kaynaklar), `github-araclar.md` (açık kaynak araç taraması).

Bilinen sınırlar:
- `stt.py` Türkçe konuşmada henüz gerçek bir kayıtla denenmedi; kelime zamanları segment içinde uzunluğa göre dağıtılıyor, kareye kesin değil. Kesin zaman gerekiyorsa `bulut/altyazi_tr.py`.
- Yüz takibi yalnız örnek bir portreyle denendi.
- Fontlar lisans dosyalarıyla birlikte `fonts/` altında (OFL / Apache 2.0).
