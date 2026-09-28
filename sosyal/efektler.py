#!/usr/bin/env python3
"""Effects library for short vertical videos and photos (CPU only).

Sources for the choices: scratchpad/viral-rehber.md and scratchpad/teknikler.md.

  altyazi_ass(kelimeler, dosya, stil, tur)  caption styles: hormozi, mrbeast, kutu, pop, sade
  yazi_arkada_foto(foto, yazi, cikti)       big text placed BEHIND the person (rembg mask)
  yazi_arkada_video(video, yazi, cikti)     same, on every frame of a video
  renk_vurgu(foto|video, cikti)             subject in colour, background black & white
  sfx(ad, dosya)                             synthesised whoosh / pop / riser / tik (no samples needed)
  foto_dump(fotolar, muzik, cikti)          photos cut on the music's beats, each with a small push-in
  bitir(video, cikti, ilerleme, dongu)      progress bar + loop ending (last frames fade into the first)
"""
import os, subprocess, tempfile, wave
import cv2, numpy as np

KOK = os.path.dirname(os.path.abspath(__file__))
FONTLAR = os.path.join(KOK, "fonts")
W, H = 1080, 1920
KUTU = {"hikaye": (64, 250, 1016, 1580), "reels": (120, 270, 780, 1248)}


def buyuk(m):
    return m.replace("i", "İ").replace("ı", "I").upper()


# ---------------------------------------------------------------- captions
STILLER = {
    # font, size, primary, outline, outline px, highlight, words per line, upper
    "hormozi": ("Anton", 92, "&H00FFFFFF", "&H00000000", 7, "&H0004C2F7", 2, True),
    "mrbeast": ("Luckiest Guy", 96, "&H00FFFFFF", "&H00000000", 8, "&H0000E1FF", 1, True),
    "kutu":    ("Poppins ExtraBold", 72, "&H00FFFFFF", "&H00000000", 0, "&H00FFFFFF", 3, True),
    "pop":     ("Bangers", 104, "&H00FFFFFF", "&H00202020", 6, "&H0050F0FF", 1, True),
    "sade":    ("Poppins ExtraBold", 64, "&H00FFFFFF", "&H00000000", 0, "&H00FFFFFF", 3, False),
}


def _t(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _anahtar(grup):
    """The word to highlight: one with a digit, else the longest."""
    for i, w in enumerate(grup):
        if any(ch.isdigit() for ch in w["text"]):
            return i
    return max(range(len(grup)), key=lambda i: len(w_text(grup[i])))


def w_text(w):
    return w["text"].strip(" ,.!?;:")


def altyazi_ass(kelimeler, dosya, stil="hormozi", tur="reels", vurgu_renk=None):
    font, boy, ana, kontur, kpx, vurgu, adet, ust = STILLER[stil]
    vurgu = vurgu_renk or vurgu
    x0, y0, x1, y1 = KUTU[tur]
    y = int(y0 + (y1 - y0) * 0.70)
    kutu_stil = stil == "kutu"
    border = 3 if kutu_stil else 1
    back = "&H0000C8F7" if kutu_stil else "&H80000000"
    sade_golge = 3 if stil == "sade" else 0
    bas = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
           f"Style: A,{font},{boy},{ana},{kontur if not kutu_stil else back},{back},0,{border},{kpx if not kutu_stil else 14},{sade_golge},8,{x0},{1080 - x1},{y}\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    gruplar, g = [], []
    for w in kelimeler:
        g.append(w)
        if len(g) >= adet or w["text"].rstrip().endswith((".", ",", "?", "!")):
            gruplar.append(g); g = []
    if g:
        gruplar.append(g)
    olay = []
    for g in gruplar:
        a = _anahtar(g)
        for i, w in enumerate(g):
            son = g[i + 1]["start"] if i + 1 < len(g) else w["end"]
            parca = []
            for j, x in enumerate(g):
                m = w_text(x) if stil in ("hormozi", "mrbeast", "pop") else x["text"].strip()
                m = buyuk(m) if ust else m
                if stil in ("hormozi",) and j == a:
                    m = "{\\c" + vurgu + "}" + m + "{\\c" + ana + "}"
                elif stil in ("kutu", "sade", "mrbeast", "pop") and j == i:
                    m = "{\\c" + vurgu + "}" + m + "{\\c" + ana + "}" if stil != "kutu" else "{\\c&H00202020}" + m + "{\\c" + ana + "}"
                parca.append(m)
            metin = " ".join(parca)
            if stil in ("pop", "mrbeast"):
                # scale punch-in on every word: 70 % -> 112 % -> 100 % in 160 ms
                metin = "{\\fscx70\\fscy70\\t(0,90,\\fscx112\\fscy112)\\t(90,160,\\fscx100\\fscy100)}" + metin
            olay.append(f"Dialogue: 0,{_t(w['start'])},{_t(son)},A,{metin}")
    open(dosya, "w").write(bas + "\n".join(olay) + "\n")
    return dosya


# ---------------------------------------------------------------- person mask
_oturum = None


def maske(img_bgr):
    """Person alpha mask 0..1 (rembg u2net_human_seg, weights from GitHub releases)."""
    global _oturum
    from rembg import new_session, remove
    from PIL import Image
    if _oturum is None:
        _oturum = new_session("u2net_human_seg")
    rgb = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    m = remove(rgb, session=_oturum, only_mask=True)
    m = np.asarray(m, dtype=np.float32) / 255.0
    return cv2.GaussianBlur(m, (0, 0), 1.2)


def _yazi_katmani(w, h, yazi, font, renk=(255, 255, 255), y_oran=0.18):
    from PIL import Image, ImageDraw, ImageFont
    katman = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(katman)
    satirlar = yazi.split("\n")
    boy = int(h * 0.2)
    while boy > 20:
        f = ImageFont.truetype(font, boy)
        if max(d.textlength(s, font=f) for s in satirlar) <= w * 0.94:
            break
        boy -= 4
    y = int(h * y_oran)
    for s in satirlar:
        tw = d.textlength(s, font=f)
        d.text(((w - tw) / 2, y), s, font=f, fill=(*renk, 255))
        y += int(boy * 0.95)
    return np.asarray(katman)


def _yazi_arkada(img, yazi, font, renk, y_oran, m=None):
    h, w = img.shape[:2]
    m = maske(img) if m is None else m
    k = _yazi_katmani(w, h, yazi, font, renk, y_oran).astype(np.float32)
    a = k[..., 3:4] / 255.0
    yazili = img.astype(np.float32) * (1 - a) + k[..., 2::-1] * a  # RGBA -> BGR
    kisi = m[..., None]
    return (yazili * (1 - kisi) + img.astype(np.float32) * kisi).clip(0, 255).astype(np.uint8)


def yazi_arkada_foto(foto, yazi, cikti, font=None, renk=(255, 255, 255), y_oran=0.12):
    font = font or os.path.join(FONTLAR, "Anton-Regular.ttf")
    img = cv2.imread(foto)
    cv2.imwrite(cikti, _yazi_arkada(img, buyuk(yazi), font, renk, y_oran))
    return cikti


def _kare_isle(giris, cikti, islev):
    c = cv2.VideoCapture(giris)
    w, h, fps = int(c.get(3)), int(c.get(4)), c.get(5) or 30
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                            "-r", str(fps), "-i", "-", "-i", giris, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
                            "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", cikti], stdin=subprocess.PIPE)
    i = 0
    while True:
        ok, k = c.read()
        if not ok:
            break
        enc.stdin.write(islev(k, i / fps).tobytes()); i += 1
    c.release(); enc.stdin.close(); enc.wait()
    return cikti


def yazi_arkada_video(video, yazi, cikti, font=None, renk=(255, 255, 255), y_oran=0.12, her=2):
    """Mask every `her` frames (u2net is ~0.3-0.6 s/frame on CPU) and reuse in between."""
    font = font or os.path.join(FONTLAR, "Anton-Regular.ttf")
    yazi = buyuk(yazi)
    son = {"m": None, "i": -99}

    def f(k, t):
        i = int(round(t * 30))
        if i - son["i"] >= her:
            son["m"], son["i"] = maske(k), i
        return _yazi_arkada(k, yazi, font, renk, y_oran, son["m"])
    return _kare_isle(video, cikti, f)


def renk_vurgu(giris, cikti):
    def f(k, t=0):
        m = maske(k)[..., None]
        gri = cv2.cvtColor(cv2.cvtColor(k, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
        return (k * m + gri * (1 - m)).astype(np.uint8)
    if giris.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        cv2.imwrite(cikti, f(cv2.imread(giris))); return cikti
    return _kare_isle(giris, cikti, f)


# ---------------------------------------------------------------- sound effects
def sfx(ad, dosya, sr=48000):
    t = lambda s: np.linspace(0, s, int(sr * s), endpoint=False)
    rng = np.random.default_rng(1)
    if ad == "whoosh":   # band-passed noise sweeping up then down
        x = t(0.45); n = rng.standard_normal(len(x))
        env = np.sin(np.pi * x / 0.45) ** 2
        f = 300 + 2600 * np.sin(np.pi * x / 0.45)
        y = np.convolve(n, np.ones(8) / 8, "same") * env * (0.4 + 0.6 * np.sin(2 * np.pi * np.cumsum(f) / sr) ** 2)
    elif ad == "pop":    # short pitched blip
        x = t(0.12); y = np.sin(2 * np.pi * (900 - 3000 * x) * x) * np.exp(-x * 35)
    elif ad == "riser":  # rising tone + noise, 1.2 s
        x = t(1.2); y = (np.sin(2 * np.pi * (200 + 900 * x ** 2) * x) * 0.6 + rng.standard_normal(len(x)) * 0.15) * (x / 1.2) ** 2
    elif ad == "tik":
        x = t(0.05); y = np.sin(2 * np.pi * 2200 * x) * np.exp(-x * 120)
    else:
        raise ValueError(ad)
    y = (y / (np.abs(y).max() + 1e-9) * 0.8 * 32767).astype(np.int16)
    with wave.open(dosya, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(y.tobytes())
    return dosya


def sfx_ekle(video, anlar, cikti, ad="whoosh", en_cok=5, db=-8):
    """Add an SFX at up to `en_cok` moments (research: only the key 3-5 moments)."""
    td = tempfile.mkdtemp(); s = sfx(ad, os.path.join(td, ad + ".wav"))
    anlar = sorted(anlar)[:en_cok]
    girisler = ["-i", video] + sum([["-i", s] for _ in anlar], [])
    parca = [f"[{i + 1}:a]adelay={int(max(0, a - 0.15) * 1000)}|{int(max(0, a - 0.15) * 1000)},volume={db}dB[s{i}]"
             for i, a in enumerate(anlar)]
    mix = "[0:a]" + "".join(f"[s{i}]" for i in range(len(anlar)))
    fc = ";".join(parca + [f"{mix}amix=inputs={len(anlar) + 1}:duration=first:normalize=0,alimiter=limit=0.9[a]"])
    subprocess.run(["ffmpeg", "-y", "-v", "error", *girisler, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", cikti], check=True)
    return cikti


# ---------------------------------------------------------------- beat-synced photo dump
def vuruslar(muzik):
    import librosa
    y, sr = librosa.load(muzik, sr=22050, mono=True)
    _, b = librosa.beat.beat_track(y=y, sr=sr)
    return librosa.frames_to_time(b, sr=sr).tolist()


def foto_dump(fotolar, muzik, cikti, her_vurus=2, en_fazla=15.0, oran=(1080, 1920)):
    ow, oh = oran
    zaman = [0.0] + [t for t in vuruslar(muzik)[::her_vurus] if 0.3 < t < en_fazla]
    if len(zaman) < 2:
        zaman = list(np.arange(0, en_fazla, 0.8))
    td = tempfile.mkdtemp(); parca = []
    for i, (a, b) in enumerate(zip(zaman, zaman[1:] + [min(en_fazla, zaman[-1] + 0.8)])):
        f = fotolar[i % len(fotolar)]; d = max(0.25, b - a); n = int(d * 30)
        out = os.path.join(td, f"{i}.mp4")
        vf = (f"scale={ow * 2}:{oh * 2}:force_original_aspect_ratio=increase,crop={ow * 2}:{oh * 2},"
              f"zoompan=z='1+0.06*on/{n}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s={ow}x{oh}:fps=30,format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", f, "-vf", vf, "-frames:v", str(n),
                        "-c:v", "libx264", "-crf", "19", out], check=True)
        parca.append(out)
    lst = os.path.join(td, "l.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parca))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", muzik,
                    "-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1",
                    "-c:a", "aac", cikti], check=True)
    return dict(kesim=len(parca))


# ---------------------------------------------------------------- finishing touches
def bitir(video, cikti, ilerleme=True, dongu=True, renk="0xF7C204"):
    """Progress bar along the top edge and a loop ending (last 0.4 s blends into frame 0)."""
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                             capture_output=True, text=True).stdout)
    vf = "[0:v]null[v0]"
    if dongu:
        vf = (f"[0:v]split[a][b];[b]trim=0:0.05,setpts=PTS-STARTPTS,loop=-1:size=2,trim=0:{d},setpts=PTS-STARTPTS[ilk];"
              f"[a][ilk]blend=all_expr='A*(1-clip((T-{d - 0.4})/0.4,0,1))+B*clip((T-{d - 0.4})/0.4,0,1)'[v0]")
    if ilerleme:
        vf += f";color={renk}:1080x10[bar];[v0][bar]overlay=x='-w+w*t/{d}':y=0:shortest=1[v]"
    else:
        vf += ";[v0]null[v]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", cikti], check=True)
    return cikti
