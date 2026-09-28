# bulut: Higgsfield sandbox'ında çalışan araçlar

Ana ortamımızdan erişilemeyen şeyler (github.io'daki web oyunları, Hugging Face
modelleri, Microsoft'un Türkçe sesleri) Higgsfield sandbox'ında açık. Bu klasör
oraya kopyalanıp çalıştırılır. Sandbox çağrı bitince ~10 sn sonra silinir:
her iş tek komut zincirinde yapılır, çıktı `media_upload` + `curl PUT` +
`media_confirm` ile dışarı alınır.

| Araç | Ne yapar | Ölçülen (28 Eylül 2026) |
|---|---|---|
| `oyun_kayit.js` | Web oyununu başsız Chromium'da açar, menüyü geçer, tuşlara basarak gerçek oynanış kaydeder (1280×720 webm). | Kanca: menü + 1. bölüm oynanışı kaydedildi, 25 sn, WebGL SwiftShader'da çalıştı. |
| `altyazi_tr.py` | faster-whisper ile gerçek kelime zamanları (Türkçe dahil). | Türkçe sentez sesle 17/17 kelime doğru, model indirme dahil 12 sn. Gerçek insan sesiyle henüz denenmedi. |
| `edge-tts` (pip) | Türkçe seslendirme: `tr-TR-AhmetNeural`, `tr-TR-EmelNeural`. | `edge-tts --voice tr-TR-AhmetNeural --text "..." --write-media ses.mp3` çalıştı. |

Örnek zincir (sandbox içinde):

```bash
pip install -q edge-tts
NODE_PATH=$(npm root -g) node oyun_kayit.js https://furkiozknn.github.io/kanca/ 15 Space:700
edge-tts --voice tr-TR-AhmetNeural --text "Kanca ile sallan" --write-media ses.mp3
python3 altyazi_tr.py ses.mp3 kelimeler.json
ffmpeg -i vid/*.webm -i ses.mp3 ... cikti.mp4 && curl -f -X PUT --upload-file cikti.mp4 '<upload_url>'
```

Sınırlar: sandbox sonucu (cloudfront) ana ortamımıza indirilemiyor; sonuç
Higgsfield'da kalır, oradan Buffer'a ya da doğrudan paylaşıma gider.
