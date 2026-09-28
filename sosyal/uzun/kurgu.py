"""Long-form Reel (~2.5 min): who Furki is, told through his real projects.

Timeline is driven by the voice-over: every segment lasts as long as its sentences
(plus a minimum so gameplay can breathe). Captions come from the same sentences, so
they cannot drift from the voice. Chapter cards are HyperFrames renders (hf/*.mp4).
"""
import json, os, subprocess, sys, wave
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, "/home/claude/mini-creative-toolkit/sosyal"); sys.path.insert(0, "/home/claude/mini-creative-toolkit/sosyal/bilgi")
import efektler
from metin import SEG

W, H, FPS = 1080, 1920, 30
F = "/home/claude/mini-creative-toolkit/sosyal/fonts/"
KOYU, ALTIN, KREM = (15, 11, 11), (201, 169, 97), (244, 235, 216)
CAP_Y = 1280
VO = json.load(open("vo.json"))
ONCE, ARA, SONRA = 0.25, 0.28, 0.4
EN_AZ = dict(hook=2.9, k_oyun=2.2, k_web=2.2, k_hari=2.2, k_arac=2.2, tek=9.5, kanca=10.5, yc=9.5,
             derin=9.5, nova=7.5, masal=8.5, ajan=7.5, harita=16, arac=11.5, rakam=10, son=7.5)

# ---------------------------------------------------------------- timeline
plan, t = [], 0.0
for sid, _ in SEG:
    cumle, u = [], t + ONCE
    for p in VO[sid]:
        cumle.append(dict(bas=u, son=u + p["sure"], dosya=p["dosya"], metin=p["metin"]))
        u += p["sure"] + ARA
    sure = max(u - ARA + SONRA - t, EN_AZ.get(sid, 0))
    plan.append(dict(id=sid, bas=t, sure=sure, cumle=cumle))
    t += sure
TOPLAM = t
print("toplam", round(TOPLAM, 1), "sn")

# ---------------------------------------------------------------- helpers
_fc = {}
def font(ad, b):
    if (ad, b) not in _fc: _fc[(ad, b)] = ImageFont.truetype(F + ad, b)
    return _fc[(ad, b)]
def ease(u): u = min(max(u, 0.0), 1.0); return u * u * (3 - 2 * u)
def yay(t, t0, d=0.22):
    u = (t - t0) / d
    if u < 0: return 0.0
    if u >= 1: return 1.0
    return 1 - (1 - u) ** 3 + 0.2 * np.sin(np.pi * u)
def yaz(d, metin, y, ad, boy, renk, olcek=1.0, kontur=0, en=W * 0.9, x=None):
    if olcek <= 0.02: return 0
    b = max(8, int(boy * olcek)); f = font(ad, b)
    while d.textlength(metin, font=f) > en and b > 16: b -= 3; f = font(ad, b)
    tw = d.textlength(metin, font=f)
    xx = (W - tw) / 2 if x is None else x
    d.text((xx, y - b * 0.55), metin, font=f, fill=renk, stroke_width=kontur, stroke_fill=(10, 10, 12))
    return tw

class Klip:
    """Sequential reader with time -> frame mapping, looping and speed."""
    def __init__(self, yol, hiz=1.0, bas=0.0):
        self.yol, self.hiz, self.bas = yol, hiz, bas
        c = cv2.VideoCapture(yol); self.fps = c.get(5) or 30; self.n = int(c.get(7)); c.release()
        self.c, self.i, self.son = None, -1, None
    def kare(self, t):
        hedef = int((self.bas + t * self.hiz) * self.fps) % max(1, self.n - 1)
        if self.c is None or hedef < self.i:
            if self.c: self.c.release()
            self.c = cv2.VideoCapture(self.yol); self.i = -1
        while self.i < hedef:
            ok, k = self.c.read()
            if not ok: break
            self.i += 1; self.son = k
        return cv2.cvtColor(self.son, cv2.COLOR_BGR2RGB)

def bulanik_dolgu(k, karart=0.45):
    h, w = k.shape[:2]; s = max(W / w, H / h)
    kk = cv2.resize(k, (max(1, int(w * s / 6)), max(1, int(h * s / 6))), interpolation=cv2.INTER_AREA)
    kk = cv2.GaussianBlur(kk, (0, 0), 4)
    kk = cv2.resize(kk, (int(w * s), int(h * s)))
    y0, x0 = (kk.shape[0] - H) // 2, (kk.shape[1] - W) // 2
    return (kk[y0:y0 + H, x0:x0 + W] * karart).astype(np.uint8)

def yapistir(bg, k, x, y, w, h, kenar=6, renk=(255, 255, 255), yuvarlak=0):
    k = cv2.resize(k, (w, h), interpolation=cv2.INTER_AREA if k.shape[1] > w else cv2.INTER_LANCZOS4)
    if kenar:
        bg[max(0, y - kenar):max(0, y + h + kenar), max(0, x - kenar):max(0, x + w + kenar)] = renk
    x1, y1 = max(0, x), max(0, y); x2, y2 = min(W, x + w), min(H, y + h)  # clip to the canvas
    if x2 > x1 and y2 > y1:
        bg[y1:y2, x1:x2] = k[y1 - y:y2 - y, x1 - x:x2 - x]
    return bg

EMO = {}
def emoji(bg, e, x, y, boy):
    if (e, boy) not in EMO: EMO[(e, boy)] = efektler.emoji(e, boy).astype(np.float32)
    a = EMO[(e, boy)]; al = a[..., 3:] / 255
    bg[y:y + boy, x:x + boy] = (bg[y:y + boy, x:x + boy] * (1 - al) + a[..., :3] * al).astype(np.uint8)

def baslik(img, metin, renk, e, t, t0, y=300):
    """Segment title with an emoji, punched in at segment start."""
    pil = Image.fromarray(img); d = ImageDraw.Draw(pil)
    o = yay(t, t0 + 0.05)
    tw = yaz(d, metin, y, "Anton-Regular.ttf", 120, renk, o, kontur=6)
    img = np.asarray(pil).copy()
    if e and o > 0.6:
        b = 96; x = int((W + tw) / 2 + 18)
        if x + b < W: emoji(img, e, x, y - 62, b)
    return img

# ---------------------------------------------------------------- sources
KLIP = dict(tek=Klip("c_tek.mp4", 1.0, 1.0), kanca=Klip("c_kanca.mp4", 1.0), yc=Klip("c_yc.mp4", 1.0),
            derin=Klip("c_derin.mp4", 0.55), nova=Klip("w_nova.mp4", 1.0, 1.0), masal=Klip("w_masal.mp4", 1.0),
            ajan=Klip("w_ajanlar.mp4", 1.0, 0.5), buradane=Klip("gif_buradane.mp4", 0.8),
            mcpvet=Klip("gif_mcpvet.mp4", 0.6, 3.8), refcheck=Klip("gif_refcheck.mp4", 1.0, 1.5))
KART = {k: Klip(f"hf/{k}.mp4") for k in ["hook", "k_oyun", "k_web", "k_hari", "k_arac"]}
OYUN = dict(tek=("TEK TUŞ KOŞU", (255, 214, 10), "🏃"), kanca=("KANCA", (72, 214, 255), "🪝"),
            yc=("YERÇEKİMİ ÇEVİR", (255, 120, 90), "🙃"), derin=("DERİN KAZI", (255, 170, 80), "⛏️"))
WEB = dict(nova=("NOVA DRIFT", (190, 150, 255), "🚀"), masal=("MASAL", (255, 160, 120), "📖"),
           ajan=("TÜRKÇE AJANLAR", (130, 220, 150), "🤖"))

import importlib.util
_s = importlib.util.spec_from_file_location("harita", "/home/claude/mini-creative-toolkit/sosyal/bilgi/v3_harita.py")
os.environ.setdefault("MUZ", "x")
HARITA = importlib.util.module_from_spec(_s); _s.loader.exec_module(HARITA)

def harita_kare(ilerleme, zoom):
    H_ = HARITA
    lon0 = H_.TUM[0] + (H_.IST_V[0] - H_.TUM[0]) * zoom; lat0 = H_.TUM[1] + (H_.IST_V[1] - H_.TUM[1]) * zoom
    gen = np.exp(np.log(H_.TUM[2]) + (np.log(H_.IST_V[2]) - np.log(H_.TUM[2])) * zoom)
    s = 1040 / gen
    x = (H_.LON - lon0) * H_.K * s + W / 2; y = -(H_.LAT - lat0) * s + 820
    g = (H_.RANK <= ilerleme) & (x >= 0) & (x < W) & (y >= 0) & (y < H)
    acc = np.zeros((H, W), np.float32)
    np.add.at(acc, (y[g].astype(int), x[g].astype(int)), 1.0)
    c = np.minimum(acc, 4.0) / 4.0
    v = np.clip(np.clip(c * 1.6, 0, 1) * 0.8 + cv2.GaussianBlur(c, (0, 0), 2.5) * 1.4 + cv2.GaussianBlur(c, (0, 0), 10) * 1.2, 0, 1.3)
    img = np.array(KOYU, np.float32) / 255 + v[..., None] * np.array(ALTIN, np.float32) / 255 * 1.1
    img += np.clip(acc / 12.0 - 0.3, 0, 1)[..., None] * 0.5
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)

def tr(n): return f"{n:,}".replace(",", ".")

# ---------------------------------------------------------------- segment renderers
def r_kart(s, tt):
    k = KART[s["id"]].kare(min(tt, KART[s["id"]].n / 30 - 0.05))
    if s["id"] == "hook":  # fast gameplay montage glows behind the kinetic text
        srcs = ["tek", "kanca", "yc", "derin", "nova"]
        m = KLIP[srcs[int(tt / 0.35) % 5]].kare(tt)
        m = bulanik_dolgu(m, 0.55) if m.shape[0] < m.shape[1] else cv2.resize(m, (W, H))
        k = np.maximum(k, (m * 0.42).astype(np.uint8))
    return k

def r_kimim(s, tt):
    img = np.zeros((H, W, 3), np.uint8); img[:] = KOYU
    pil = Image.fromarray(img); d = ImageDraw.Draw(pil)
    d.rounded_rectangle((60, 300, W - 60, 1200), 26, fill=(22, 22, 26), outline=(60, 60, 68), width=2)
    for i, r in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((100 + i * 44, 340, 126 + i * 44, 366), fill=r)
    d.text((W / 2 - 80, 336), "furki@ev: ~", font=font("JetBrainsMono-Regular.ttf", 30), fill=(130, 130, 140))
    satirlar = [("whoami", "furki"), ("cat gunduz.txt", "yapay zekâ ajanları için altyapı"),
                ("cat aksam.txt", "oyun motoru: Godot"), ("ls ~/projeler | wc -l", "28")]
    f = font("JetBrainsMono-Regular.ttf", 44); y = 440
    for i, (kom, cik) in enumerate(satirlar):
        c = s["cumle"][min(i, len(s["cumle"]) - 1)]; t0 = c["bas"] - s["bas"]
        if tt < t0: break
        n = min(len(kom), int((tt - t0) / 0.045))
        d.text((110, y), "$ ", font=f, fill=(120, 220, 140)); d.text((160, y), kom[:n], font=f, fill=(235, 235, 235))
        y += 66
        if n == len(kom):
            d.text((110, y), cik, font=f, fill=ALTIN if i != 0 else (235, 235, 235)); y += 84
    return np.asarray(pil)

def r_oyun(s, tt):
    ad, renk, e = OYUN[s["id"]]
    k = KLIP[s["id"]].kare(tt)
    bg = bulanik_dolgu(k, 0.5)
    z = 1 + 0.06 * ease(tt / s["sure"])          # slow push-in inside the panel
    h, w = k.shape[:2]; cw, ch = int(w / z), int(h / z)
    k = k[(h - ch) // 2:(h - ch) // 2 + ch, (w - cw) // 2:(w - cw) // 2 + cw]
    pop = 1 + 0.05 * max(0, 1 - tt / 0.18)
    pw, ph = int(1040 * pop), int(585 * pop)
    img = yapistir(bg, k, (W - pw) // 2, 430 + (585 - ph) // 2, pw, ph)
    # second view: a close crop of the same frame, like a second camera
    zk = cv2.resize(KLIP[s["id"]].son, (1280, 720))
    zk = cv2.cvtColor(zk[180:560, 200:880], cv2.COLOR_BGR2RGB)
    img = yapistir(img, zk, 640, 900, 380, 212, kenar=5, renk=renk)
    return baslik(img, ad, renk, e, tt, 0)

def r_web(s, tt):
    ad, renk, e = WEB[s["id"]]
    k = KLIP[s["id"]].kare(tt)
    bg = bulanik_dolgu(k, 0.4)
    pw, ph = 500, 889
    img = yapistir(bg, k, (W - pw) // 2, 410, pw, ph, kenar=8, renk=(240, 240, 240))
    return baslik(img, ad, renk, e, tt, 0)

def r_harita(s, tt):
    c = s["cumle"]; t1 = c[1]["bas"] - s["bas"]; t2 = c[2]["bas"] - s["bas"]
    if tt < t2:
        ilerleme = ease(tt / (t1 - 0.2)); zoom = ease((tt - t1) / 1.6)
        img = harita_kare(ilerleme, zoom)
        pil = Image.fromarray(img); d = ImageDraw.Draw(pil)
        if zoom < 0.5:
            yaz(d, tr(int(167829 * ilerleme)), 330, "Anton-Regular.ttf", 170, KREM, yay(tt, 0.1), kontur=4)
            yaz(d, "GERÇEK YER · 81 İL", 470, "Anton-Regular.ttf", 70, ALTIN, yay(tt, 0.4))
        else:
            yaz(d, "İSTANBUL · 25.916 YER", 350, "Anton-Regular.ttf", 100, KREM, yay(tt, t1 + 0.6), kontur=4)
        img = np.asarray(pil).copy()
        emoji(img, "🗺️", 60, 1060, 110)
        return img
    k = KLIP["buradane"].kare(tt - t2)
    bg = bulanik_dolgu(k, 0.4)
    img = yapistir(bg, k, 40, 520, 1000, 640)
    return baslik(img, "BURADANE", ALTIN, "🚻", tt, t2)

def r_arac(s, tt):
    t1 = s["cumle"][1]["bas"] - s["bas"]
    t2 = s["cumle"][2]["bas"] - s["bas"] - 0.2
    if tt >= t2:  # repo-vet has no demo capture: a checklist that fills in as it is read
        img = np.zeros((H, W, 3), np.uint8); img[:] = (18, 18, 22)
        pil = Image.fromarray(img); d = ImageDraw.Draw(pil)
        yaz(d, "repo-vet", 330, "JetBrainsMono-Regular.ttf", 90, (155, 227, 138), yay(tt, t2 + 0.05))
        d.rounded_rectangle((70, 470, W - 70, 1180), 22, fill=(26, 26, 32), outline=(60, 60, 68), width=2)
        f = font("JetBrainsMono-Regular.ttf", 46)
        d.text((110, 510), "$ repo-vet Furkiozknn/kanca", font=f, fill=(235, 235, 235))
        for i, m in enumerate(["kurulum komutu", "rozetler", "bağlantılar", "sürüm zinciri"]):
            if tt > t2 + 0.6 + i * 0.55:
                d.text((110, 620 + i * 120), "ok  " + m, font=font("JetBrainsMono-Regular.ttf", 56), fill=(155, 227, 138))
        img = np.asarray(pil).copy(); emoji(img, "🛠️", W // 2 - 48, 170, 96)
        return img
    ad, kl, t0 = ("mcp-vet", "mcpvet", 0) if tt < t1 - 0.2 else ("godot-refcheck", "refcheck", t1 - 0.2)
    k = KLIP[kl].kare(tt - t0)
    img = np.zeros((H, W, 3), np.uint8); img[:] = (18, 18, 22)
    w = 1000; h = int(k.shape[0] * w / k.shape[1])
    img = yapistir(img, k, 40, 1230 - h - 20, w, h, kenar=4, renk=(60, 60, 68))
    pil = Image.fromarray(img); d = ImageDraw.Draw(pil)
    yaz(d, ad, 330, "JetBrainsMono-Regular.ttf", 90, (155, 227, 138), yay(tt, t0 + 0.05))
    img = np.asarray(pil).copy(); emoji(img, "🛠️", W // 2 - 48, 170, 96)
    return img

def r_rakam(s, tt):
    img = np.zeros((H, W, 3), np.uint8); img[:] = KOYU
    pil = Image.fromarray(img); d = ImageDraw.Draw(pil)
    c0 = s["cumle"][0]; L = c0["son"] - c0["bas"]; b0 = c0["bas"] - s["bas"]
    sira = [(28, "AÇIK KAYNAK PROJE", b0 + 0.15 * L), (5247, "TEST", b0 + 0.45 * L), (1096, "COMMIT", b0 + 0.78 * L)]
    y = 420
    for n, et, t0 in sira:
        if tt < t0: break
        u = 1 - (1 - min(1, (tt - t0) / 0.7)) ** 3
        yaz(d, tr(int(n * u)), y, "Anton-Regular.ttf", 200, ALTIN, yay(tt, t0, 0.15))
        yaz(d, et, y + 150, "Anton-Regular.ttf", 64, KREM, yay(tt, t0 + 0.2))
        y += 290
    if tt >= s["cumle"][1]["bas"] - s["bas"]:
        yaz(d, "her sayı, onu basan koşuya bağlı", 1250, "Outfit-Bold.ttf", 48, (190, 180, 160), 1.0)
    return np.asarray(pil)

SON_KARE = {}
def r_son(s, tt):
    if not SON_KARE:
        for i, kk in enumerate(["tek", "kanca", "yc", "derin"]):
            SON_KARE[i] = KLIP[kk].kare(2.5)
    img = np.zeros((H, W, 3), np.uint8)
    for i in range(4):
        r, c = divmod(i, 2)
        k = cv2.resize(SON_KARE[i], (540, 304))
        img[r * 304 + 180:(r + 1) * 304 + 180, c * 540:(c + 1) * 540] = k
    img = (img * 0.35).astype(np.uint8)
    pil = Image.fromarray(img); d = ImageDraw.Draw(pil)
    yaz(d, "HEPSİ AÇIK KAYNAK", 820, "Anton-Regular.ttf", 120, KREM, yay(tt, 0.1), kontur=5)
    yaz(d, "HEPSİ ÜCRETSİZ", 950, "Anton-Regular.ttf", 120, ALTIN, yay(tt, 0.6), kontur=5)
    c1 = s["cumle"][1]["bas"] - s["bas"]
    yaz(d, "LİNK PROFİLDE", 1080, "Anton-Regular.ttf", 90, KREM, yay(tt, c1))
    img = np.asarray(pil).copy()
    if tt > c1 + 0.2: emoji(img, "👇", W // 2 - 55, 1135, 110)
    return img

R = dict(hook=r_kart, k_oyun=r_kart, k_web=r_kart, k_hari=r_kart, k_arac=r_kart, kimim=r_kimim,
         tek=r_oyun, kanca=r_oyun, yc=r_oyun, derin=r_oyun, nova=r_web, masal=r_web, ajan=r_web,
         harita=r_harita, arac=r_arac, rakam=r_rakam, son=r_son)

def kare(t):
    for s in plan:
        if s["bas"] <= t < s["bas"] + s["sure"]:
            img = R[s["id"]](s, t - s["bas"])
            if s["id"] not in ("hook",) and t - s["bas"] < 0.08:  # flash on every cut
                img = (img + (255 - img.astype(np.float32)) * 0.45).astype(np.uint8)
            return img
    return np.zeros((H, W, 3), np.uint8)

# ---------------------------------------------------------------- audio + captions
def ses_ve_altyazi():
    sr = 22050
    vo = np.zeros(int((TOPLAM + 1) * sr), np.float32)
    kelimeler = []
    for s in plan:
        for c in s["cumle"]:
            import soundfile as sf
            y, _ = sf.read(c["dosya"], dtype="float32")
            i = int(c["bas"] * sr); vo[i:i + len(y)] += y[:len(vo) - i]
            ks = c["metin"].split(); ag = np.array([len(k) + 1 for k in ks], float)
            sin = np.concatenate([[0], np.cumsum(ag) / ag.sum()]) * (c["son"] - c["bas"])
            for k, a, b in zip(ks, sin[:-1], sin[1:]):
                kelimeler.append(dict(text=k, start=round(c["bas"] + a, 3), end=round(c["bas"] + b, 3)))
    import soundfile as sf
    sf.write("vo_tam.wav", vo, sr)
    efektler.altyazi_ass(kelimeler, "altyazi.ass", stil="kutu", tur="reels", y=CAP_Y, olcek=1.45)
    json.dump(kelimeler, open("kelimeler.json", "w"), ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for t in map(float, sys.argv[1:]):
            cv2.imwrite(f"on_{t:06.2f}.jpg", cv2.cvtColor(kare(t), cv2.COLOR_RGB2BGR))
        sys.exit()
    json.dump([{k: v for k, v in s.items() if k != "cumle"} for s in plan], open("plan.json", "w"), indent=1)
    ses_ve_altyazi()
    n = int(TOPLAM * FPS)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "g.mp4"],
                           stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(np.ascontiguousarray(kare(i / FPS)).tobytes())
        if i % 300 == 0: print("kare", i, "/", n, flush=True)
    enc.stdin.close(); enc.wait()
    # mix: music ducked under the voice (sidechain), voice cleaned, then -14 LUFS
    fc = (f"[1:a]aresample=48000,highpass=f=80,acompressor=threshold=-20dB:ratio=3,volume=1.6,asplit=2[v][vk];"
          f"[2:a]atrim=0:{TOPLAM},volume=0.55,afade=t=out:st={TOPLAM - 1.5}:d=1.5[m];"
          f"[m][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[md];"
          f"[md][v]amix=inputs=2:normalize=0:duration=longest,atrim=0:{TOPLAM},loudnorm=I=-14:TP=-1:LRA=11[a];"
          f"[0:v]ass=altyazi.ass:fontsdir={F}[vv]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "g.mp4", "-i", "vo_tam.wav", "-i", "muzik.wav", "-filter_complex", fc,
                    "-map", "[vv]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-t", str(TOPLAM), "ga.mp4"], check=True)
    kartlar = [s["bas"] for s in plan if s["id"].startswith("k_")]
    efektler.sfx_ekle("ga.mp4", kartlar, "gs.mp4", ad="whoosh", en_cok=8, db=-12)
    efektler.bitir("gs.mp4", "furki-reel-uzun.mp4", dongu=False, renk="0xC9A961")
    print("tamam", round(TOPLAM, 1))
