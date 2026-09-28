from ortak import *
import os
MUZ = os.environ.get("MUZ", "/home/claude/yercekimi-cevir/assets/audio/muzik_gergin.wav")
B = 60 / float(os.environ.get("BPM", 143.6)); T0 = float(os.environ.get("T0", 0.67))
P = np.load("noktalar.npy")
LON, LAT, IST = P[:, 0], P[:, 1], P[:, 2] > 0
K = np.cos(np.radians(39.0))
SIRA = np.argsort(LON)                    # reveal west -> east
RANK = np.empty(len(P), np.float32); RANK[SIRA] = np.linspace(0, 1, len(P))
TOPLAM = 167829
T_BAS, T_TAM = 1.9, 7.3                   # sweep
T_ZOOM, T_ZOOM2 = 8.1, 10.1
T_SON = 10.9
SURE = 13.6
TUM = (35.25, 38.97, 19.8 * K * 1.02)      # centre lon, lat, width in "km-ish" x units
IST_V = (28.98, 41.03, 1.25 * K)
def gorunum(t):
    u = ease((t - T_ZOOM) / (T_ZOOM2 - T_ZOOM))
    lon = TUM[0] + (IST_V[0] - TUM[0]) * u; lat = TUM[1] + (IST_V[1] - TUM[1]) * u
    gen = np.exp(np.log(TUM[2]) + (np.log(IST_V[2]) - np.log(TUM[2])) * u)
    return lon, lat, gen
def harita(t):
    lon0, lat0, gen = gorunum(t)
    s = 1040 / gen
    x = (LON - lon0) * K * s + W / 2
    y = -(LAT - lat0) * s + 960
    ilerleme = ease((t - T_BAS) / (T_TAM - T_BAS))
    gor = (RANK <= ilerleme) & (x >= 0) & (x < W) & (y >= 0) & (y < H)
    acc = np.zeros((H, W), np.float32)
    np.add.at(acc, (y[gor].astype(int), x[gor].astype(int)), 1.0)
    # new dots near the sweep front glow brighter
    on = gor & (RANK > ilerleme - 0.03)
    if ilerleme < 1:
        np.add.at(acc, (y[on].astype(int), x[on].astype(int)), 3.0)
    c = np.minimum(acc, 4.0) / 4.0          # cap so dense cities do not blow out
    cekirdek = np.clip(c * 1.6, 0, 1)
    parilti = cv2.GaussianBlur(c, (0, 0), 2.5) * 1.4 + cv2.GaussianBlur(c, (0, 0), 10) * 1.2
    v = np.clip(cekirdek * 0.8 + parilti, 0, 1.3)
    renk = np.array(ALTIN, np.float32) / 255
    img = np.array(KOYU, np.float32) / 255 + v[..., None] * renk * 1.1
    img += np.clip(acc / 12.0 - 0.3, 0, 1)[..., None] * 0.5  # hot cores go white
    return (np.clip(img, 0, 1) * 255).astype(np.uint8), ilerleme
def tr(n): return f"{n:,}".replace(",", ".")
def kare(t):
    a, ilerleme = harita(t)
    img = Image.fromarray(a); d = ImageDraw.Draw(img)
    if t < T_BAS + 0.3:
        g = 1 - ease((t - T_BAS) / 0.3)
        yaz(d, "YAKINIMDA", 820, "Anton-Regular.ttf", 200, KREM, yay(t, 0.05) * g + 0.001)
        yaz(d, "NE VAR?", 1040, "Anton-Regular.ttf", 200, ALTIN, yay(t, T0 + B) * g + 0.001)
    elif t < T_ZOOM:
        yaz(d, tr(int(TOPLAM * ilerleme)), 470, "Anton-Regular.ttf", 190, KREM, yay(t, T_BAS + 0.3))
        yaz(d, "GERÇEK YER", 610, "Anton-Regular.ttf", 80, ALTIN, yay(t, T_BAS + 0.5))
        yaz(d, "81 İL · OpenStreetMap", 1330, "Outfit-Bold.ttf", 54, (190, 180, 160), yay(t, T_TAM - 0.3))
        yaz(d, "tuvalet · su · park · eczane · şarj · wi-fi", 1410, "Outfit-Bold.ttf", 44, (150, 140, 120), yay(t, T_TAM))
    elif t < T_SON:
        yaz(d, "İSTANBUL", 470, "Anton-Regular.ttf", 170, KREM, yay(t, T_ZOOM + 0.8))
        yaz(d, "25.916 yer", 610, "Anton-Regular.ttf", 90, ALTIN, yay(t, T_ZOOM + 1.2))
    else:
        u = ease((t - T_SON) / 0.4)
        a2 = (np.asarray(img).astype(np.float32) * (1 - 0.82 * u)).astype(np.uint8)
        img = Image.fromarray(a2); d = ImageDraw.Draw(img)
        yaz(d, "buradane", 760, "Anton-Regular.ttf", 200, ALTIN, yay(t, T_SON + 0.2))
        yaz(d, "“ücretsiz tuvalet” yaz,", 930, "Outfit-Bold.ttf", 58, KREM, yay(t, T_SON + 0.6))
        yaz(d, "en yakın 19'u gör.", 1005, "Outfit-Bold.ttf", 58, KREM, yay(t, T_SON + 0.6))
        yaz(d, "Yaptım. Açık kaynak.", 1120, "Outfit-Bold.ttf", 50, (190, 180, 160), yay(t, T_SON + 1.1))
        yaz(d, "github.com/Furkiozknn/buradane", 1230, "JetBrainsMono-Regular.ttf", 38, (150, 140, 120), yay(t, T_SON + 1.5))
    return np.asarray(img)
if __name__ == "__main__":
    if len(sys.argv) > 1:
        for t in map(float, sys.argv[1:]): cv2.imwrite(f"o3_{t:05.2f}.jpg", cv2.cvtColor(kare(t), cv2.COLOR_RGB2BGR))
        sys.exit()
    n = int(SURE * FPS)
    kodla(kare, "v3.mp4", n)
    sesle("v3.mp4", MUZ, n / FPS, "v3a.mp4")
    efektler.sfx_ekle("v3a.mp4", [T_BAS, T_ZOOM, T_SON], "v3s.mp4", ad="whoosh", en_cok=3)
    efektler.bitir("v3s.mp4", "3-harita.mp4", dongu=False, renk="0xC9A961")
    print("tamam", n / FPS)
