# Kısa dikey video ve foto gönderi teknikleri kataloğu (Eylül 2026)

Kapsam: CPU'da ffmpeg / OpenCV / Python ile uygulanabilecek teknikler. Köşeli parantezdeki numaralar sondaki kaynak listesini gösterir. Oradaki yüzdeler kaynağın kendi iddiasıdır, ben doğrulamadım. Hiçbir kaynağa dayanmayan maddeler **(kaynaksız)** olarak işaretli.

## Genel ritim kuralları (her şablona uygulanır)
- **Kanca ilk 2 saniyede olmalı.** İzleyici 5–6 saniyede kalıp kalmayacağına karar veriyor. Açılışta logo ya da intro olmasın [2]. Japonca kaynaklar da 3–5 saniye diyor (冒頭で心をつかむ) [9][10].
- **Görüntü 2–5 saniyede bir değişmeli (pattern interrupt).** Önerilen süre kaynağa göre değişiyor: 2–3 sn [2], 3–5 sn [1]. Japonca kaynak aynı açının 4 saniyeden uzun sürmemesini söylüyor (同じ画角が4秒以上続かない) [9].
- **İzleyicilerin yaklaşık %80'i sesi kapalı izliyor.** Bu yüzden büyük altyazı zorunlu [2].
- **Ses efekti az kullanılmalı.** Video başına en önemli 3–5 vuruşa konulmalı, her kesmeye koymak ucuz gösterir [4].
- **Altyazıda en fazla 3 renk olmalı.** Vurgu için ya kalın yazı ya renk kullanılmalı, ikisi birden değil (テロップは3色まで) [11].
- **Güvenli alan:** Yazı ekranın üst üçte birinde olmalı. Konuşan kişi varsa üstte, ürün varsa altta durmalı [9]. Instagram'da görselin alt %15'i arayüzün altında kalıyor [7].

## A. Konuşan kişi videoları

1. **Anahtar kelimede ani zoom (punch-in).** Vurgulanan kelimede görüntü 0,3–0,5 sn içinde %110–120'ye yaklaşıyor. 1 saniyeden yavaş zoom etkisini kaybediyor [1].
   - Uygulama: `zoompan` ya da kelime zaman damgasında `crop`+`scale` ile ölçek anahtarlaması yapılır; ease-out için `if(between(t,a,b),...)` kullanılır.
2. **Jump cut (컷편집 / カット).** Her 2–4 kelimede bir kesme yapılır. Her kelimede kesmek izleyiciyi yorar [1]. "えー", "あのー" gibi dolgu sesleri ve boşluklar atılır [11]. Korece kaynaklar bunu temel kesme türü olarak anlatıyor [12].
   - Uygulama: Mevcut sessizlik kesme aracına Whisper'ın dolgu kelimesi zaman damgaları eklenir; `select`/`aselect` ya da `concat` ile birleştirilir.
3. **Sanal kamera açısı değişimi (画角変化).** Geniş, orta ve yakın çekim 5–8 saniyede bir değiştirilir [1][9].
   - Uygulama: Mevcut sanal multicam kırpma; kırpma kutusu yüz takibinden alınır.
4. **Yazı konunun arkasında (text behind subject).** Büyük başlık kişinin arkasında kalır, kişi yazının önünde durur. Katmanlı, derinlikli bir görüntü verdiği için akışta dikkat çekiyor. CapCut ve Premiere'de hazır şablonu var [13][14].
   - Uygulama: Arka plan, sonra yazı, en üstte rembg maskesiyle kesilmiş kişi katmanlanır. Hareketli videoda maske kare kare çıkarılır.
5. **Dondurma + daire vurgusu (定格 + 圈出重点).** Görüntü durur, ilgili yer daire ya da ok ile işaretlenir, 1–2 sn beklenir. Çin'deki 剪映 derslerinin standart bir parçası (kaynaksız, yalnız arama sonuçlarındaki başlıklara dayanıyor).
   - Uygulama: `tpad=stop_mode=clone:stop_duration=1.5` ile kare dondurulur, üzerine `drawbox` konur ya da OpenCV ile `cv2.ellipse` "çizilme" animasyonu yapılır, sonra `overlay`.
6. **Hız rampası (speed ramp / rampa de velocidade).** Sıkıcı kısım hızlanır, doruk anı yavaşlar [1][15].
   - Uygulama: Parçalar `setpts=PTS/k` ile hızlandırılır; akıcı yavaşlatma için `minterpolate` kullanılır (CPU'da yavaş, kısa parçalarda uygun).
7. **LUT / renk kayması.** Konu değiştiğinde kesmeyle birlikte renk tonu da değişir [1].
   - Uygulama: `lut3d=file.cube` ya da `eq=saturation=...:contrast=...` ile parçaya özel renk ayarı.
8. **Beliren metin (pop-up text).** Metin 0,2 sn içinde %0'dan %100'e büyür, 1–2 sn ekranda kalır [1].
   - Uygulama: ASS `\t(0,200,\fscx100\fscy100)`, başlangıç değeri `\fscx0`.
9. **Glitch / RGB ayrışması geçişi.** 3–5 karelik renk kanalı kayması ve yatay bozulma (kaynaksız).
   - Uygulama: `rgbashift=rh=8:bh=-8` + `noise` + kısa `crop` titremesi, `enable='between(t,a,b)'`.
10. **Whip pan / hızlı kaydırma geçişi.** İki çekim, hareket bulanıklığıyla yana kayarak birbirine bağlanır. Whoosh sesiyle birlikte kullanılır [4].
    - Uygulama: `xfade=transition=slideleft:duration=0.2` + `gblur=sigma=20:steps=1` (yalnız yatay bulanıklık için `boxblur` en-boy ayarı).
11. **Maske geçişi (蒙版转场).** Bir nesne ya da kişi ekranı kaplarken sonraki çekim onun silüetinin içinden açılır [16].
    - Uygulama: rembg maskesi büyütülür ve `alphamerge` ile iki çekim birleştirilir. Alternatif olarak `xfade=transition=circleopen`.
12. **Match cut.** Aynı şekil ya da hareket iki farklı sahnede kesintisiz devam eder (kaynaksız).
    - Uygulama: OpenCV ile iki kaynaktan konumu ve boyu benzer kareler (yüz kutusu, histogram) seçilir, tam o karede kesilir.
13. **Bölünmüş ekran tepki (split-screen reaction).** Üstte içerik, altta kişinin yüzü [3].
    - Uygulama: `vstack` ile 1080x960 + 1080x960; alt yarı yüz takipli kırpma.
14. **Ekran görüntüsü üzerine yorum (green-screen commentary).** Arka planda ekran görüntüsü ya da oyun sahnesi, önde kesilmiş kişi [3][6].
    - Uygulama: rembg ile kesilmiş kişi alt köşeye `overlay` edilir, arka plan yavaşça `zoompan` ile yaklaşır.
15. **Çıkartma (sticker) kesim.** Kişi beyaz kenarlıklı bir çıkartma gibi kesilir, zıplayarak girer (kaynaksız).
    - Uygulama: rembg alfası `cv2.dilate` ile büyütülür, bu beyaz kenar olur, ardından hafif gölge eklenir. Giriş animasyonu ölçekle yapılır (overshoot 1.1 → 1.0).
16. **Önce/sonra kaydırıcı.** Dikey bir çizgi soldan sağa kayarak eski ve yeni görüntüyü açar. Keskin kesme, yumuşak geçişten daha iyi çalışıyor [5].
    - Uygulama: `xfade=transition=wiperight` ya da `overlay` + zamana bağlı `crop=w='iw*t/T'`.
17. **"POV:" / bağlam başlığı.** İlk karede tek satırlık, 40 karakterden kısa bir çerçeve cümlesi [7] (40 karakter sınırı carousel kaynağından alındı).
    - Uygulama: `drawtext`, üst üçte birde, 0–3 sn arası.
18. **İlerleme çubuğu.** Ekranın altında ya da üstünde dolan ince bir çubuk; izleyiciye "az kaldı" sinyali verir (kaynaksız).
    - Uygulama: `drawbox=w='iw*t/DUR':h=8:color=yellow@0.9:t=fill`.
19. **Döngülü bitiş (loop ending).** Son kare ilk kareye bağlanır, cümle başa sarınca tamamlanır. Tekrar izlemeleri artırıyor [5][2].
    - Uygulama: Son 0,3 sn ile ilk kare arasında `xfade=fade`; son cümlenin sesi ilk kelimeye bağlanır.

## B. Fotoğraf / carousel gönderileri

20. **2.5B fotoğraf paralaksı.** Mevcut derinlik aracıyla hazırlanır. Kesilen konu ile arka plan farklı hızda kayar (kaynaksız; araç zaten elinde).
21. **Zoom ile açılış (zoom-reveal).** Bir detaydan başlanır, geriye çekilince bütün görüntü ortaya çıkar (kaynaksız).
    - Uygulama: `zoompan=z='max(3-0.02*on,1)'`, önce büyük ölçekte `scale` yapılırsa titreme olmaz.
22. **Photo dump ritmi.** Aynı renk tonuyla işlenmiş fotoğraflar müzik vuruşuna göre art arda gelir. TikTok'ta en fazla 35, Instagram'da en fazla 20 öğe [17].
    - Uygulama: librosa vuruşlarında kesilir, her fotoğrafa aynı LUT uygulanır, `concat` ile birleştirilir.
23. **Vuruşa kesme (卡点 / beat-sync).** Kesme ve fotoğraf değişimi tam vuruş karesine denk gelir [16][6].
    - Uygulama: librosa `beat_track` + `onset_detect`. Kesme vuruştan 1–2 kare önce yapılır (algı gecikmesi; kaynaksız).
24. **Kare kare stop motion.** Seri çekim ya da ardışık fotoğraflar 8–12 fps hızında oynatılır (kaynaksız).
    - Uygulama: `-framerate 10 -i %03d.jpg`, her kareye hafif rastgele kayma ekleyerek "el yapımı" his verilir.
25. **Odak kayması (refocus).** Bulanıklık ön plandan arka plana geçer (kaynaksız).
    - Uygulama: Derinlik haritası eşiği zamanla kaydırılır. Maske eşiğin altında ise `gblur`, üstünde ise net görüntü.
26. **Renk vurgusu (selective color).** Konu renkli kalır, arka plan siyah-beyaz olur (kaynaksız).
    - Uygulama: rembg maskesi + `hue=s=0` arka plan + `overlay`.
27. **Cinemagraph.** Tek bir bölge (su, saç, ekran) hareket eder, geri kalan donuktur (kaynaksız).
    - Uygulama: İlk kare sabit tutulur, elle çizilmiş maske alanında video akar; ileri-geri döngüyle (`reverse` + `concat`) dikiş izi kalmaz.
28. **Carousel yapısı.** 7–10 slayt olmalı, 1–9. slaytlarda kaydırma ipucu bulunmalı, son slaytta çağrı (CTA) olmalı. Boyut 1080x1350 (4:5), önemli içerik ortadaki 1080x1080 alanda kalmalı [7].
    - Uygulama: PIL ile şablon; slaytlar arasında devam eden panorama (kaydırmayı teşvik eder, kaynaksız).

## C. Oyun / uygulama tanıtımı

29. **Önce oyun görüntüsü.** 0. saniyede en çarpıcı oyun anı gösterilir, metin ve müzik üstüne biner. TikTok oyun reklamlarının %27'si bu biçimde [18].
30. **Başarısızlık (fail) kancası.** Oyuncu bariz bir hata yapar, izleyici "ben yapardım" diye düşünür. Oyun reklamlarının %7'si "sahte oynanış + fail" biçiminde [18].
    - Not: Gerçek oynanış kullanılmalı; yanıltıcı reklam riskli [19].
31. **Sen vs yapay zekâ / bot bölünmüş ekran.** Üstte bot, altta insan koşusu (kaynaksız).
    - Uygulama: Mevcut bot iz dosyalarından iki kayıt alınır, `vstack` ile birleştirilir, süre sayaçları eklenir.
32. **Tatmin edici döngü.** Bir mekaniği sonsuz döngüde gösteren kayıt; tekrar izlemeleri artırıyor [5].
33. **Önce/sonra geliştirme ilerlemesi.** Eski ve yeni yapı keskin kesmeyle art arda verilir; en dramatik fark ilk sırada [5].
34. **Hata (bug) videoları.** Komik fizik hataları insani bir yüz gösterdiği için paylaşılıyor [5].
35. **Arayüz vurguları (UI callout).** Ok ya da çerçeve ile özellik gösterilir, dondurma + zoom ile birlikte kullanılır (A5 ve A1'in birleşimi).
36. **"X. gün" serisi.** Numaralı devlog bölümleri, en az haftada 2 paylaşım [5].
37. **Etkileyici kişi formatı (influencer).** Konuşan kişi ile oyun görüntüsü birlikte. Oyun reklamlarının %33'ü bu biçimde [18]. Kamera yoksa B14'teki yorum formatı ya da seslendirme + oyun görüntüsü kullanılabilir.

## D. Altyazı stilleri

| Stil | Görünüm | Font (ücretli → Google Fonts'taki ücretsiz karşılığı) |
|---|---|---|
| Hormozi | TAMAMI BÜYÜK HARF, satırda 3–5 kelime, 1080x1920'de 70–85 px, 5–8 px siyah kontur; tek anahtar kelime sarı `#F7C204` ya da yeşil `#02FB23`, kelime kelime "pop" animasyonu [20] | The Bold Font → **Montserrat Black (900)** ya da **Anton** [20] |
| MrBeast | Kalın, eğlenceli harfler, renkli dolgu, kalın kontur + gölge, hafif eğim (kaynaksız) | Komika Axis → **Luckiest Guy** / **Bangers** (kaynaksız) |
| Karaoke kutusu | Söylenen kelimenin arkasında renkli, yuvarlak köşeli bir kutu [21] | **Montserrat ExtraBold**, **Poppins Bold** |
| Zıplayan pop | Her kelime 0→110→100% ölçekle girer [1] | **Bebas Neue** (enerjik içerik, 75–95 px) [20] |
| Sade | Gölgeli, fade ile giren yazı [20] | **Poppins**, **Roboto** [20] |
| Emoji ekleme | Anahtar kelimenin yanında bağlama uygun emoji. pycaps bağlama göre etiketleme yapabiliyor [22] | Emoji görseli olarak **Noto Color Emoji** PNG'leri kullanılır (libass renkli emoji çizemez; kaynaksız) |

- **Uygulama:** ASS dosyası `\k` / `\kf` karaoke etiketleri ve `\t` dönüşümleriyle yazılır, `ffmpeg -vf subtitles=x.ass:fontsdir=fonts` ile gömülür. Kutu için ya `\3c` + `BorderStyle=3` kullanılır ya da kelime başına ayrı bir `Dialogue` satırı `\p` vektör çizimiyle yazılır.
- **Türkçe:** "İ/ı" harflerini büyük harfe çevirirken `str.upper()` yerine yerele duyarlı bir çevirim kullanılmalı (kaynaksız).

## E. Ses

38. **Kesmede whoosh, yazıda pop/klik, açılıştan önce riser** [4][23]. Japonca kaynak, dikkat çekici bir imza sesinin videoda 3–5 kez kullanılmasını öneriyor (約10秒ごとにチリーン) [9].
    - Uygulama: `adelay` + `amix`. Ses efektleri müziğin 6–10 dB altında tutulmalı, konuşma her zaman en üstte olmalı [11] (dB değeri kaynaksız).
39. **Bas düşüşünde açılış (bass drop reveal).** Riser sürerken ekran kararır ya da donar, düşüş anında en iyi kare açılır (kaynaksız).
    - Uygulama: librosa `onset_strength` en yüksek noktası = düşüş zamanı. Açılış karesi `xfade=fadewhite` ile oraya hizalanır.
40. **Konuşma önceliği.** Müzik ne kadar iyi olursa olsun, konuşma kısık kalırsa izleyici hemen çıkıyor. Kontrol telefon hoparlöründen yapılmalı [11].
    - Uygulama: `sidechaincompress` ile konuşma varken müzik kısılır, `loudnorm=I=-14` (kaynaksız).

## F. GitHub depoları

| Depo | Lisans | GPU | Model / ağ bağımlılığı |
|---|---|---|---|
| [francozanardi/pycaps](https://github.com/francozanardi/pycaps) — CSS ile animasyonlu altyazı, hazır şablonlar, pop/slide/typewriter animasyonları | MIT | Gerekmiyor | Whisper ilk kullanımda indiriliyor (kaynağı belirtilmemiş). Playwright/Chromium isteğe bağlı; tarayıcısız alternatifi `PictexSubtitleRenderer` [22] |
| [unconv/captacity](https://github.com/unconv/captacity) — kelime vurgulu Shorts altyazısı (MoviePy) | MIT | Gerekmiyor | Yerel `openai-whisper` ya da OpenAI API [24] |
| [m1guelpf/auto-subtitle](https://github.com/m1guelpf/auto-subtitle) — ffmpeg + Whisper ile altyazı gömme | MIT | Gerekmiyor | openai-whisper (ağırlıklar HF'den değil, OpenAI CDN'inden iniyor olmalı; kaynaksız) [25] |
| [mutonby/openshorts](https://github.com/mutonby/openshorts) — yüz takipli yeniden çerçeveleme, SPLIT/SCREENCAST düzenleri, altyazı | MIT (`cloud/` dizini hariç) | İsteğe bağlı (NVENC) | faster-whisper (**HF'den indiriyor**), YOLOv8, MediaPipe, Gemini API [26] |
| [RayVentura/ShortGPT](https://github.com/RayVentura/ShortGPT) — otomatik Shorts hattı | MIT [27] | Gerekmiyor | LLM ve TTS API'leri (kaynaksız) |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CPU'da int8 transkripsiyon | MIT | Gerekmiyor | Model varsayılan olarak **HF**'den iniyor, ama yerel bir dizin de verilebilir [28] |
| [hqman/karaoke-caption](https://github.com/hqman/karaoke-caption) — ASS karaoke kelime vurgusu | Lisans görünmüyor | Apple Silicon (MLX) | Yalnız ASS şablonu referansı olarak işe yarar [21] |
| [SamurAIGPT/AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator) — LLM ile öne çıkan anı seçip dikey kırpma | Doğrulanmadı | Gerekmiyor | Whisper + LLM API [29] |

**HF engeli notu:** faster-whisper ve openshorts HF'ye bağlı. Çözüm, CTranslate2 modelini başka bir kaynaktan edinip yerel dizinden yüklemek. Mevcut kelime kelime altyazı hattı çalışıyorsa bu depolardan yalnız **stil/ASS mantığını** almak yeterli.

## Kaynaklar
1. https://edicionvideopro.com/en/editing-for-platforms-video-marketing/pattern-interrupts-tiktok-retention-guide/
2. https://virvid.ai/blog/ai-shorts-increase-retention-watch-time
3. https://github.com/mutonby/openshorts (düzen modları)
4. https://esecut.com/blog/sound-effects-that-boost-engagement
5. https://presskit.gg/field-guides/tiktok-indie-game-marketing
6. https://www.capcut.com/es-es/resource/tiktok-transitions
7. https://www.trymypost.com/blog/instagram-carousel-algorithm-2026-guide
8. https://edicionvideopro.com/pt/edicao-para-plataformas-e-video-marketing/edicao-video-instagram-reels-estilo-ritmo-conversao/
9. https://www.watch.impress.co.jp/docs/pa/impress/1573429.html
10. https://www.ab-net.co.jp/abilivepromotion/news/247/
11. https://www.lemon8-app.com/@takechi0318/7253752630772515333?region=jp
12. https://match.dropshot.io/blog/깔끔한-영상을-만들고-싶다면-필수-컷편집-종류-7가지-8577
13. https://www.capcut.com/template-detail/Text-behind-Subject/7507937836256070973
14. https://www.adobe.com/in/learn/premiere-pro/web/text-behind-subject-object-mask
15. https://www.capcut.com/es-es/resource/how-to-speed-up-tiktok-videos
16. https://www.douyin.com/shipin/7493370497086867495 (剪映蒙版转场) · https://m.bookschina.com/9131712.htm (剪映: 卡点效果/创意转场 başlıkları)
17. https://www.cyberlink.com/blog/trending-topics/5007/photo-dump
18. https://sanlo.io/blog/i-studied-30-mobile-game-ads-on-tiktok-this-is-what-i-learned
19. https://www.z2adigital.com/blog-content/fake-mobile-game-ads
20. https://blitzcutai.com/blog/best-caption-fonts-tiktok
21. https://github.com/hqman/karaoke-caption
22. https://github.com/francozanardi/pycaps
23. https://www.flexclip.com/learn/transition-sound-effects.html
24. https://github.com/unconv/captacity
25. https://github.com/m1guelpf/auto-subtitle
26. https://github.com/mutonby/openshorts
27. https://github.com/RayVentura/ShortGPT/blob/stable/LICENSE
28. https://github.com/SYSTRAN/faster-whisper
29. https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator
