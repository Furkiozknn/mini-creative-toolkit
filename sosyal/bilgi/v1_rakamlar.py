from ortak import *
MUZ = "/home/claude/derin-kazi/assets/audio/muzik_bazalt.wav"
B = 60 / 161.5; T0 = 0.42
SEG = 4 * B
SAHNE = [  # (number, label, sub)
    (None, None, None),
    (28, "AÇIK KAYNAK DEPO", "hepsi herkese açık"),
    (5247, "GEÇEN TEST", "her sayı, onu basan koşuya bağlı"),
    (1096, "COMMIT", ""),
    (167829, "GERÇEK YER", "Türkiye'nin 81 ilinden"),
    (4, "GODOT OYUNU", "tarayıcıda, ücretsiz"),
    (0, "BAĞIMLILIK", "mcp-vet: yalnız standart kütüphane"),
    (None, None, None),
]
SURE = T0 + SEG * len(SAHNE)
rng = np.random.default_rng(3)
GREN = [rng.integers(0, 18, (H // 4, W // 4), dtype=np.uint8) for _ in range(6)]
def tr(n): return f"{n:,}".replace(",", ".")
def arka(t):
    img = np.zeros((H, W, 3), np.uint8); img[:] = KOYU
    # slow drifting gold grid
    ofs = int(t * 40) % 120
    for y in range(-120 + ofs, H, 120): img[y:y + 1] = (34, 30, 22)
    for x in range(0, W, 120): img[:, x:x + 1] = (34, 30, 22)
    g = cv2.resize(GREN[int(t * 12) % 6], (W, H), interpolation=cv2.INTER_NEAREST)
    return np.clip(img.astype(np.int16) + g[..., None], 0, 255).astype(np.uint8)
def kare(t):
    img = Image.fromarray(arka(t)); d = ImageDraw.Draw(img)
    i = min(int(max(t - T0, 0) / SEG) if t >= T0 else 0, len(SAHNE) - 1)
    t0 = T0 + i * SEG if t >= T0 else 0
    if i == 0:
        yaz(d, "BENİ HİÇ", 760, "Anton-Regular.ttf", 190, KREM, yay(t, 0.05))
        yaz(d, "GÖRMEDİN.", 960, "Anton-Regular.ttf", 190, KREM, yay(t, T0 + B))
        yaz(d, "RAKAMLAR ANLATSIN.", 1160, "Anton-Regular.ttf", 110, ALTIN, yay(t, T0 + 2 * B))
    elif i == len(SAHNE) - 1:
        yaz(d, "FURKİ ÖZKAN", 700, "Anton-Regular.ttf", 170, KREM, yay(t, t0))
        yaz(d, "Yapay zekâ ajanlarının üstünde", 880, "Outfit-Bold.ttf", 52, ALTIN, yay(t, t0 + B))
        yaz(d, "çalıştığı altyapıyı kuruyorum.", 950, "Outfit-Bold.ttf", 52, ALTIN, yay(t, t0 + B))
        yaz(d, "Bazı akşamlar da oyun.", 1060, "Outfit-Bold.ttf", 52, KREM, yay(t, t0 + 2 * B))
        yaz(d, "github.com/Furkiozknn", 1230, "JetBrainsMono-Regular.ttf", 44, (150, 140, 120), yay(t, t0 + 3 * B))
    else:
        n, etiket, alt = SAHNE[i]
        u = cikis((t - t0) / (2 * B))
        deger = int(round(n * u)) if n else 0
        punch = 1 + 0.12 * max(0, 1 - (t - t0 - 2 * B) / 0.15) if t - t0 >= 2 * B else 1
        yaz(d, tr(deger), 740, "Anton-Regular.ttf", 380 if n < 100000 else 260, ALTIN, punch * yay(t, t0, 0.15))
        yaz(d, etiket, 1130, "Anton-Regular.ttf", 110, KREM, yay(t, t0 + B))
        if alt: yaz(d, alt, 1240, "Outfit-Bold.ttf", 50, (170, 160, 140), yay(t, t0 + 2 * B))
        yaz(d, f"{i:02d} / 06", 440, "JetBrainsMono-Regular.ttf", 44, (120, 110, 90), yay(t, t0))
    a = np.asarray(img)
    # white flash on every scene change
    if t >= T0 and (t - t0) < 0.1 and i > 0:
        a = (a + (255 - a.astype(np.float32)) * (1 - (t - t0) / 0.1) * 0.6).astype(np.uint8)
    return a
if __name__ == "__main__":
    if len(sys.argv) > 1:
        for t in map(float, sys.argv[1:]): cv2.imwrite(f"o1_{t:05.2f}.jpg", cv2.cvtColor(kare(t), cv2.COLOR_RGB2BGR))
        sys.exit()
    n = int(SURE * FPS)
    kodla(kare, "v1.mp4", n)
    sesle("v1.mp4", MUZ, n / FPS, "v1a.mp4")
    efektler.sfx_ekle("v1a.mp4", [T0 + k * SEG for k in range(1, 8)], "v1s.mp4", ad="whoosh", en_cok=7)
    efektler.bitir("v1s.mp4", "1-rakamlarla.mp4", dongu=False, renk="0xC9A961")
    print("tamam", n / FPS)
