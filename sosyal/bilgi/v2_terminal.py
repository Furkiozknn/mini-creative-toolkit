from ortak import *
import wave
import os
MUZ = os.environ.get("MUZ", "/home/claude/derin-kazi/assets/audio/muzik.wav")
MONO = "JetBrainsMono-Regular.ttf"
YESIL, GRI, BEYAZ = (120, 220, 140), (130, 130, 140), (235, 235, 235)
# (command, output lines) ; commands are typed, outputs appear at once
AKIS = [
    ("whoami", [("furki", BEYAZ), ("yapay zekâ ajanları için altyapı kurar", GRI)]),
    ("ls ~/projeler | wc -l", [("28", ALTIN)]),
    ("mcp-vet ./yeni-mcp-sunucusu", [("31 kural tarandı", GRI), ("her bulgu: dosya:satır", GRI), ("kodu çalıştırmadan", ALTIN)]),
    ("godot-refcheck ./oyun --fix", [("3 kırık referans", (240, 120, 110)), ("3 onarım  ->  temiz", YESIL)]),
    ('buradane "ücretsiz tuvalet"', [("167.829 yer taranıyor...", GRI), ("en yakın 19 sonuç", YESIL)]),
    ("echo $AKSAMLARI", [("oyun motoru.", ALTIN)]),
]
YAZMA = 0.04   # s per typed char
BEKLE = 0.72    # pause after output
X0, Y0, SATIR = 90, 470, 62
# timeline: list of (t_start, kind, text, colour)
olay, t = [], 1.3
for kom, cik in AKIS:
    olay.append((t, "kom", kom, BEYAZ)); t += len(kom) * YAZMA + 0.25
    for s, r in cik:
        olay.append((t, "cik", s, r)); t += 0.12
    t += BEKLE
FINAL = t
SURE = FINAL + 3.0
def pencere(d):
    d.rounded_rectangle((50, 330, W - 50, 1520), 26, fill=(22, 22, 26), outline=(60, 60, 68), width=2)
    for k, r in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((90 + k * 44, 370, 116 + k * 44, 396), fill=r)
    d.text((W / 2 - 90, 366), "furki@ev: ~", font=font(MONO, 30), fill=GRI)
def kare(t):
    img = Image.new("RGB", (W, H), KOYU); d = ImageDraw.Draw(img)
    yaz(d, "BENİ ANLATAN", 150, "Anton-Regular.ttf", 110, KREM, yay(t, 0.05))
    yaz(d, "6 KOMUT", 265, "Anton-Regular.ttf", 110, ALTIN, yay(t, 0.45))
    pencere(d)
    satirlar = []
    for (t0, tur, s, r) in olay:
        if t < t0: break
        if tur == "kom":
            n = min(len(s), int((t - t0) / YAZMA))
            satirlar.append([("$ ", YESIL), (s[:n], r)])
        else:
            satirlar.append([(s, r)])
    satirlar = satirlar[-15:]  # scroll
    f = font(MONO, 40)
    y = Y0; x = X0
    for parca in satirlar:
        x = X0
        for s, r in parca:
            d.text((x, y), s, font=f, fill=r); x += d.textlength(s, font=f)
        y += SATIR
    if satirlar and int(t * 2.5) % 2 == 0 and t < FINAL:  # blinking cursor
        d.rectangle((x + 4, y - SATIR + 6, x + 26, y - 8), fill=BEYAZ)
    if t >= FINAL:
        a = ease((t - FINAL) / 0.4)
        img = Image.blend(img, Image.new("RGB", (W, H), KOYU), 0.9 * a); d = ImageDraw.Draw(img)
        yaz(d, "FURKİ ÖZKAN", 820, "Anton-Regular.ttf", 170, KREM, yay(t, FINAL + 0.2))
        yaz(d, "Her sayı, onu basan koşuya bağlı.", 990, "Outfit-Bold.ttf", 54, ALTIN, yay(t, FINAL + 0.7))
        yaz(d, "github.com/Furkiozknn", 1110, MONO, 44, GRI, yay(t, FINAL + 1.2))
    return np.asarray(img)
def tiklar(dosya):
    """Keyboard clicks for every typed char (synthesised, deterministic)."""
    sr = 48000; n = int(SURE * sr); s = np.zeros(n, np.float32); rng = np.random.default_rng(5)
    for (t0, tur, txt, _) in olay:
        if tur != "kom": continue
        for k in range(len(txt)):
            i = int((t0 + k * YAZMA) * sr); L = 700
            if i + L >= n: break
            env = np.exp(-np.arange(L) / 90.0)
            s[i:i + L] += (rng.normal(0, 1, L) * env * 0.35).astype(np.float32)
    w = wave.open(dosya, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((np.clip(s, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
if __name__ == "__main__":
    if len(sys.argv) > 1:
        for t in map(float, sys.argv[1:]): cv2.imwrite(f"o2_{t:05.2f}.jpg", cv2.cvtColor(kare(t), cv2.COLOR_RGB2BGR))
        sys.exit()
    n = int(SURE * FPS)
    kodla(kare, "v2.mp4", n); tiklar("tik.wav")
    sesle("v2.mp4", MUZ, n / FPS, "v2a.mp4", ekler=["tik.wav"])
    efektler.bitir("v2a.mp4", "2-terminal.mp4", dongu=False, renk="0x78DC8C")
    print("tamam", n / FPS)
