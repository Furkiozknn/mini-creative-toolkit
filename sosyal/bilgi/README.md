# bilgi: fotoğrafsız, yalnız bilgiden video

Görüntü yok, kişi yok; video yalnız doğrulanmış bilgiden kodla çizilir.

| Şablon | Ne | Müzik (her biri farklı) |
|---|---|---|
| `v1_rakamlar.py` | Kinetik tipografi: sayılar vuruşa göre sayar ve oturur (28 depo, 5.247 test, 1.096 commit, 167.829 yer, 4 oyun, 0 bağımlılık). | Derin Kazı `muzik_bazalt` 161 bpm |
| `v2_terminal.py` | Terminal hikâyesi: 6 komut yazılır, çıktılar gelir; klavye tıkı sentezlenir. | Derin Kazı `muzik` 108 bpm |
| `v3_harita.py` | buradane'nin 167.829 gerçek OSM noktası batıdan doğuya yanar, İstanbul'a yaklaşır. | Yerçekimi Çevir `muzik_gergin` 144 bpm |

Sayılar profil README'sinden (her biri bir test koşusuna bağlı); değiştiklerinde şablondaki listeyi güncelle.
`v3_harita.py` önce `noktalar.npy` ister (buradane `frontend/data/places.*.json` → lon, lat, İstanbul bayrağı).
Önizleme: `python3 v1_rakamlar.py 1.5 3.2` → `o1_*.jpg`; argümansız çalıştırma videoyu üretir.
