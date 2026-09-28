# Single photo -> 12 s beat-synced reel: punch-in hook, person cut out as a sticker over
# framed game screenshots (4 beats each), fast montage, 2x2 grid + CTA. No AI video.
# Inputs: duzen.jpg (graded 1080x1920 photo) in the working dir; paths below.
# usage: python3 foto_oyun_montaj.py            (render)
#        python3 foto_oyun_montaj.py 1.4 5.0    (preview frames at given seconds)
import sys, subprocess, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, "/home/claude/mini-creative-toolkit/sosyal")
import efektler
from efektler import buyuk
W, H, FPS = 1080, 1920, 30
F = "/home/claude/mini-creative-toolkit/sosyal/fonts/"
H_ = "/home/claude/"
MUZ = H_ + "yercekimi-cevir/assets/audio/muzik_hizli.wav"
B = 0.4  # beat (150 bpm)
T0 = 0.44  # first beat
def vurus(n): return T0 + n * B

# ---------------------------------------------------------------- assets
foto = cv2.imread("duzen.jpg")
m = efektler.maske(foto)
m = np.where(m > 0.5, 1.0, m * 0.6).astype(np.float32)
m = cv2.GaussianBlur(m, (0, 0), 1.0)
# sticker outline
kalin = cv2.dilate((m > 0.4).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29)))
kalin = cv2.GaussianBlur(kalin.astype(np.float32), (0, 0), 1.5)
golge = cv2.GaussianBlur(kalin, (0, 0), 25)

OYUNLAR = [("KANCA", H_ + "kanca/yayin/ekran_2.png", (72, 214, 255)),
           ("YERÇEKİMİ ÇEVİR", H_ + "yercekimi-cevir/yayin/ekran/02-oynanis.png", (255, 120, 90)),
           ("DERİN KAZI", H_ + "derin-kazi/yayin/ekran-2.png", (80, 190, 255)),
           ("TEK TUŞ KOŞU", H_ + "tek-tus-kosu/yayin/ekran-2.png", (255, 220, 60))]
ARKA = []
HAM = []
for ad, p, renk in OYUNLAR:
    a = cv2.imread(p)
    HAM.append(a)
    s = H / a.shape[0]
    ARKA.append(cv2.resize(a, (int(a.shape[1] * s), H), interpolation=cv2.INTER_NEAREST))

def dolgu(img, w, h, u=0.5):
    """Fill-crop img to w x h, panning horizontally by u in 0..1."""
    s = max(w / img.shape[1], h / img.shape[0])
    r = cv2.resize(img, (int(img.shape[1] * s + 1), int(img.shape[0] * s + 1)), interpolation=cv2.INTER_NEAREST)
    x = int((r.shape[1] - w) * u); y = (r.shape[0] - h) // 2
    return r[y:y + h, x:x + w]

def yazi(img, metin, y, boy, renk=(255, 255, 255), font="Anton-Regular.ttf", kontur=10, olcek=1.0):
    if olcek <= 0.01: return img
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    b = int(boy * olcek)
    f = ImageFont.truetype(F + font, b)
    while d.textlength(metin, font=f) > W * 0.92 and b > 20:
        b -= 4; f = ImageFont.truetype(F + font, b)
    tw = d.textlength(metin, font=f)
    d.text(((W - tw) / 2, y - b / 2), metin, font=f, fill=renk, stroke_width=kontur, stroke_fill=(15, 15, 20))
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)

def kisi_yerlestir(bg, olcek, dy=0):
    """Composite the person (with white outline + shadow) scaled around bottom centre."""
    ow, oh = int(W * olcek), int(H * olcek)
    k = cv2.resize(foto, (ow, oh), interpolation=cv2.INTER_AREA)
    mm = cv2.resize(m, (ow, oh)); kk = cv2.resize(kalin, (ow, oh)); gg = cv2.resize(golge, (ow, oh))
    x0 = (W - ow) // 2; y0 = H - oh + dy
    out = bg.astype(np.float32)
    ys, ye = max(0, y0), min(H, y0 + oh); ky = ys - y0
    sl = (slice(ys, ye), slice(x0, x0 + ow)); ks = slice(ky, ky + ye - ys)
    g = gg[ks][..., None] * 0.55
    out[sl] = out[sl] * (1 - g)
    kb = kk[ks][..., None]
    out[sl] = out[sl] * (1 - kb) + 255 * kb
    a = mm[ks][..., None]
    out[sl] = out[sl] * (1 - a) + k[ks] * a
    return out.clip(0, 255).astype(np.uint8)

PX, PY, PW, PH = 0, 380, 1080, 608
def bulanik(i):
    b = cv2.GaussianBlur(dolgu(HAM[i], W // 8, H // 8), (0, 0), 3)
    return (cv2.resize(b, (W, H)) * 0.45).astype(np.uint8)
def panel(bg, i, t0, t, x=PX, y=PY, w=PW, h=PH, kenar=6):
    """Sharp 16:9 game screenshot as a framed panel; slow push-in, pop + shake on the cut."""
    z = 1.0 + 0.08 * ease((t - t0) / 1.6)
    pop = 1 + 0.07 * max(0, 1 - (t - t0) / 0.15)
    a = HAM[i]
    cw, ch = int(a.shape[1] / z), int(a.shape[0] / z)
    cx, cy = (a.shape[1] - cw) // 2, (a.shape[0] - ch) // 2
    ww, hh = int(w * pop), int(h * pop)
    p = cv2.resize(a[cy:cy + ch, cx:cx + cw], (ww - 2 * kenar, hh - 2 * kenar), interpolation=cv2.INTER_NEAREST)
    p = cv2.copyMakeBorder(p, kenar, kenar, kenar, kenar, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    sx = int(14 * max(0, 1 - (t - t0) / 0.25) * np.sin(t * 90))
    x0, y0 = x + (w - ww) // 2 + sx, y + (h - hh) // 2
    x1, y1 = max(0, x0), max(0, y0); x2, y2 = min(W, x0 + ww), min(H, y0 + hh)
    out = bg.copy()
    out[y1:y2, x1:x2] = p[y1 - y0:y2 - y0, x1 - x0:x2 - x0]
    return out

def ease(u): u = min(max(u, 0), 1); return u * u * (3 - 2 * u)
def yay(t, t0, d=0.18):
    """Punch: 0 before t0, overshoots to ~1.1 then settles at 1."""
    u = (t - t0) / d
    if u < 0: return 0.0
    if u > 1: return 1.0
    return 1 - (1 - u) ** 3 + 0.25 * np.sin(np.pi * u)

KESIM = [vurus(2)] + [vurus(2 + 4 * i) for i in range(1, 4)]  # 1.24, 2.84, 4.44, 6.04
HIZLI = vurus(18)   # 7.64 fast montage, one beat each
IZGARA = vurus(22)  # 9.24 2x2 grid
SON = 12.4

def kare(t):
    # ---------------- intro: full photo punch-in, hook text
    if t < KESIM[0]:
        z = 1.0 + 0.35 * (1 - ease(t / 0.5))
        k = cv2.resize(foto, (int(W * z), int(H * z)))
        y = (k.shape[0] - H) // 2; x = (k.shape[1] - W) // 2
        img = k[y:y + H, x:x + W].copy()
        img = yazi(img, "4 OYUN YAPTIM", 330, 150, olcek=yay(t, 0.05))
        img = yazi(img, "TEK BAŞIMA.", 500, 130, (255, 214, 10), olcek=yay(t, vurus(1)))
        return img
    # ---------------- each game gets 4 beats
    if t < HIZLI:
        i = max(j for j in range(4) if KESIM[j] <= t)
        t0 = KESIM[i]; u = (t - t0) / (4 * B)
        bg = panel(bulanik(i), i, t0, t)
        if i == 0:  # reveal: person shrinks from full frame to sticker size
            e = ease((t - t0) / 0.3); ol = 1.0 - 0.38 * e; dy = int(110 * e)
        else:
            ol = 0.62 * (1 + 0.05 * max(0, 1 - (t - t0) / 0.2)); dy = 110
        img = kisi_yerlestir(bg, ol, dy + int(6 * np.sin(t * 3)))
        ad, _, renk = OYUNLAR[i]
        img = yazi(img, buyuk(ad), 290, 130, tuple(renk), olcek=yay(t, t0 + 0.03))
        fl = max(0, 1 - (t - t0) / 0.12)
        return (img + (255 - img.astype(np.float32)) * fl * 0.8).astype(np.uint8)
    # ---------------- fast montage
    if t < IZGARA:
        n = int((t - HIZLI) / B) % 4; t0 = HIZLI + int((t - HIZLI) / B) * B
        bg = panel(bulanik(n), n, t0, t)
        img = kisi_yerlestir(bg, 0.62 * (1 + 0.05 * max(0, 1 - (t - t0) / 0.15)), 110)
        img = yazi(img, "HEPSİ ÜCRETSİZ", 290, 130, (255, 214, 10), olcek=yay(t, HIZLI))
        fl = max(0, 1 - (t - t0) / 0.08)
        return (img + (255 - img.astype(np.float32)) * fl * 0.5).astype(np.uint8)
    # ---------------- 2x2 grid + CTA
    g = bulanik(0)
    for j in range(4):
        r, c = divmod(j, 2)
        g = panel(g, j, IZGARA + j * B / 2, t, 8 + c * 536, PY + r * 306, 528, 298, 4) if t >= IZGARA + j * B / 2 else g
    img = kisi_yerlestir(g, 0.62, 110)
    img = yazi(img, "TARAYICIDA OYNA", 215, 100, olcek=yay(t, IZGARA))
    img = yazi(img, "LİNK PROFİLDE", 320, 80, (255, 214, 10), olcek=yay(t, IZGARA + 2 * B))
    return img

if __name__ == "__main__":
    if len(sys.argv) > 1:  # preview frames
        for t in map(float, sys.argv[1:]):
            cv2.imwrite(f"on_{t:.2f}.jpg", kare(t))
        sys.exit()
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", "v.mp4"], stdin=subprocess.PIPE)
    for i in range(int(SON * FPS)):
        enc.stdin.write(kare(i / FPS).tobytes())
    enc.stdin.close(); enc.wait()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "v.mp4", "-i", MUZ, "-filter_complex",
                    f"[1:a]atrim=0:{SON},afade=t=out:st={SON - 0.6}:d=0.6,loudnorm=I=-14:TP=-1:LRA=11[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", "va.mp4"], check=True)
    efektler.sfx_ekle("va.mp4", KESIM + [HIZLI, IZGARA], "vs.mp4", ad="whoosh", en_cok=6)
    efektler.bitir("vs.mp4", "oyunlarim-reel.mp4", dongu=False)
    print("tamam")
