#!/usr/bin/env python3
"""Edit a person's own video or photo for Reels/TikTok/Shorts/Stories.

Applies the editing rules from scratchpad/viral-rehber.md:
- 9:16 reframe that follows the face (OpenCV), eyes kept near the upper third
- jump cuts: silences and breaths removed (silencedetect)
- a slight punch-in on every other cut as a pattern interrupt
- mild grade (exposure/contrast, skin-safe saturation), light sharpening
- voice chain: high-pass, gentle compression, loudness about -14 LUFS / -1 dBTP
- optional hook title for the first 2.5 s, and optional word-by-word captions
  from a word-timed JSON (e.g. ElevenLabs Scribe output) inside the reels safe box

usage:
  python3 kisi.py video giris.mp4 cikti.mp4 [--kanca "Başlık"] [--kelimeler words.json] [--tur reels|hikaye] [--muzik m.wav]
  python3 kisi.py foto giris.jpg cikti.jpg [--oran 4:5|9:16|1:1] [--baslik "Yazı"]
"""
import argparse, json, os, re, subprocess, tempfile
import cv2
import numpy as np

def buyuk(m):
    """Turkish-aware upper case: i -> İ, ı -> I (str.upper gets these wrong)."""
    return m.replace("i", "İ").replace("ı", "I").upper()


FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts") + "/"
KALIN = FD + "BricolageGrotesque-Bold.ttf"
W, H = 1080, 1920
KUTU = {"hikaye": (64, 250, 1016, 1580), "reels": (120, 270, 780, 1248)}
DERECE = "eq=contrast=1.05:brightness=0.02:saturation=1.04,unsharp=5:5:0.4"


def sure(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)


def boyut(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip().split(",")
    return int(o[0]), int(o[1])


def yuz_merkezi(p, ornek=24):
    """Median face centre (x, y) as fractions of the frame; None if no face found."""
    yuzbul = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(p)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    xs, ys = [], []
    for i in np.linspace(0, n - 1, min(ornek, n)).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, kare = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
        f = yuzbul.detectMultiScale(g, 1.1, 5, minSize=(g.shape[1] // 12, g.shape[1] // 12))
        if len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3])
            xs.append((x + w / 2) / g.shape[1]); ys.append((y + h * 0.4) / g.shape[0])
    cap.release()
    return (float(np.median(xs)), float(np.median(ys))) if xs else None


def konusma_parcalari(p, esik="-35dB", en_az=0.35, pay=0.08):
    """Segments that contain sound; silences longer than `en_az` s become cuts."""
    log = subprocess.run(["ffmpeg", "-i", p, "-af", f"silencedetect=noise={esik}:d={en_az}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    bas = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    son = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    toplam, parca, t = sure(p), [], 0.0
    for b, s in zip(bas, son + [None] * (len(bas) - len(son))):
        if b - t > 0.2:
            parca.append((max(0, t - pay), b + pay))
        t = s if s is not None else toplam
    if toplam - t > 0.2:
        parca.append((max(0, t - pay), toplam))
    return parca or [(0, toplam)]


def ass_zaman(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def altyazi_ass(kelimeler, dosya, tur, renk="&H0000D7FF&"):
    """Word-by-word captions, 1-3 words per line, current word highlighted."""
    x0, y0, x1, y1 = KUTU[tur]
    y = int(y0 + (y1 - y0) * 0.72)
    bas = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
           f"Style: A,Bricolage Grotesque,96,&H00FFFFFF&,&H00000000&,&H64000000&,1,1,6,2,8,{x0},{1080 - x1},{y}\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    satir, grup = [], []
    for w in kelimeler:
        grup.append(w)
        if len(grup) == 3 or w["text"].rstrip().endswith((".", ",", "?", "!")):
            satir.append(grup); grup = []
    if grup:
        satir.append(grup)
    olay = []
    for g in satir:
        for i, w in enumerate(g):
            metin = " ".join(("{\\c" + renk + "}" + buyuk(x["text"].strip()) + "{\\c&H00FFFFFF&}") if j == i
                             else buyuk(x["text"].strip()) for j, x in enumerate(g))
            son = g[i + 1]["start"] if i + 1 < len(g) else w["end"]
            olay.append(f"Dialogue: 0,{ass_zaman(w['start'])},{ass_zaman(son)},A,{metin}")
    open(dosya, "w").write(bas + "\n".join(olay) + "\n")


def video(giris, cikti, kanca=None, kelimeler=None, tur="reels", muzik=None):
    gw, gh = boyut(giris)
    yuz = yuz_merkezi(giris)
    # Crop to 9:16 around the face; keep the eye line near the upper third.
    ch = gh
    cw = int(round(ch * 9 / 16 / 2) * 2)
    if cw > gw:
        cw, ch = gw, int(round(gw * 16 / 9 / 2) * 2)
    fx, fy = yuz if yuz else (0.5, 0.35)
    cx = int(min(max(fx * gw - cw / 2, 0), gw - cw))
    cy = int(min(max(fy * gh - ch / 3, 0), gh - ch))
    parca = konusma_parcalari(giris)
    td = tempfile.mkdtemp()
    liste = []
    for i, (a, b) in enumerate(parca):
        z = 1.08 if i % 2 else 1.0  # punch-in on every other cut
        out = os.path.join(td, f"p{i}.mp4")
        vf = (f"crop={cw}:{ch}:{cx}:{cy},scale={int(W * z)}:{int(H * z)},crop={W}:{H},{DERECE},fps=30,format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", giris, "-vf", vf,
                        "-af", "aresample=48000", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac",
                        "-b:a", "192k", out], check=True)
        liste.append(out)
    lst = os.path.join(td, "l.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in liste))
    birlesik = os.path.join(td, "b.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", birlesik], check=True)

    vf = []
    if kelimeler:
        ass = os.path.join(td, "a.ass")
        # Word times refer to the original clip; shift them onto the cut timeline.
        ws, kay, t_yeni = [], [], 0.0
        for a, b in parca:
            kay.append((a, b, t_yeni)); t_yeni += b - a
        for w in json.load(open(kelimeler)):
            for a, b, t in kay:
                if a <= w["start"] < b:
                    ws.append(dict(text=w["text"], start=w["start"] - a + t, end=min(w["end"], b) - a + t)); break
        altyazi_ass(ws, ass, tur)
        vf.append(f"ass={ass}:fontsdir={FD}")
    if kanca:
        kp = os.path.join(td, "k.txt"); open(kp, "w").write(kanca)
        x0, y0, x1, _ = KUTU[tur]
        vf.append(f"drawtext=fontfile={KALIN}:textfile={kp}:fontsize=76:fontcolor=white:borderw=6:bordercolor=black@0.8:"
                  f"x={x0}+({x1 - x0}-tw)/2:y={y0 + 20}:enable='lt(t,2.5)'")
    ses = "highpass=f=80,acompressor=threshold=-18dB:ratio=3:attack=10:release=200"
    son = "loudnorm=I=-14:TP=-1:LRA=11"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", birlesik]
    if muzik:
        # Music ducked well under the voice (rehber 4: about -18..-25 dB).
        cmd += ["-stream_loop", "-1", "-i", muzik]
        fc = (f"[0:v]{','.join(vf) if vf else 'null'}[v];[0:a]{ses}[s];[1:a]volume=-22dB[m];"
              f"[s][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,{son}[a]")
    else:
        fc = f"[0:v]{','.join(vf) if vf else 'null'}[v];[0:a]{ses},{son}[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", cikti]
    subprocess.run(cmd, check=True)
    return dict(yuz=yuz, parca=len(parca), sure=round(sure(cikti), 2), kirpilan=round(sure(giris) - sure(cikti), 2))


def foto(giris, cikti, oran="4:5", baslik=None):
    img = cv2.imread(giris)
    h, w = img.shape[:2]
    ow, oh = {"4:5": (1080, 1350), "9:16": (1080, 1920), "1:1": (1080, 1080)}[oran]
    yuzbul = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    f = yuzbul.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(w // 12, w // 12))
    fx, fy = ((f[0][0] + f[0][2] / 2) / w, (f[0][1] + f[0][3] * 0.4) / h) if len(f) else (0.5, 0.35)
    ch = h; cw = int(ch * ow / oh)
    if cw > w:
        cw, ch = w, int(w * oh / ow)
    cx = int(min(max(fx * w - cw / 2, 0), w - cw)); cy = int(min(max(fy * h - ch / 3, 0), h - ch))
    vf = f"crop={cw}:{ch}:{cx}:{cy},scale={ow}:{oh},{DERECE}"
    if baslik:
        kp = cikti + ".txt"; open(kp, "w").write(baslik)
        vf += (f",drawtext=fontfile={KALIN}:textfile={kp}:fontsize=84:fontcolor=white:borderw=5:bordercolor=black@0.7:"
               f"x=(w-tw)/2:y=h*0.08")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", giris, "-vf", vf, "-q:v", "2", cikti], check=True)
    return dict(yuz=bool(len(f)), boyut=f"{ow}x{oh}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("tip", choices=["video", "foto"])
    p.add_argument("giris"); p.add_argument("cikti")
    p.add_argument("--kanca"); p.add_argument("--kelimeler"); p.add_argument("--muzik")
    p.add_argument("--tur", choices=KUTU, default="reels")
    p.add_argument("--oran", default="4:5"); p.add_argument("--baslik")
    a = p.parse_args()
    if a.tip == "video":
        print(video(a.giris, a.cikti, a.kanca, a.kelimeler, a.tur, a.muzik))
    else:
        print(foto(a.giris, a.cikti, a.oran, a.baslik))
