import subprocess, sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, "/home/claude/mini-creative-toolkit/sosyal")
import efektler
W, H, FPS = 1080, 1920, 30
F = "/home/claude/mini-creative-toolkit/sosyal/fonts/"
ALTIN, KOYU, KREM = (201, 169, 97), (15, 11, 11), (231, 220, 192)  # RGB (profile palette)
_fc = {}
def font(ad, b):
    k = (ad, b)
    if k not in _fc: _fc[k] = ImageFont.truetype(F + ad, b)
    return _fc[k]
def ease(u): u = min(max(u, 0.0), 1.0); return u * u * (3 - 2 * u)
def cikis(u): u = min(max(u, 0.0), 1.0); return 1 - (1 - u) ** 3
def yay(t, t0, d=0.2):
    u = (t - t0) / d
    if u < 0: return 0.0
    if u >= 1: return 1.0
    return 1 - (1 - u) ** 3 + 0.22 * np.sin(np.pi * u)
def yaz(d, metin, y, ad, boy, renk, olcek=1.0, kontur=0, kontur_renk=(0, 0, 0), x=None, en=W * 0.9, hiza="orta"):
    if olcek <= 0.02: return
    b = max(8, int(boy * olcek)); f = font(ad, b)
    while d.textlength(metin, font=f) > en and b > 16:
        b -= 3; f = font(ad, b)
    tw = d.textlength(metin, font=f)
    xx = (W - tw) / 2 if x is None else (x if hiza == "sol" else x - tw / 2)
    d.text((xx, y - b * 0.55), metin, font=f, fill=renk, stroke_width=kontur, stroke_fill=kontur_renk)
def kodla(kareler, cikti, n):
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p", cikti], stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(np.ascontiguousarray(kareler(i / FPS)).tobytes())
    enc.stdin.close(); enc.wait()
def sesle(video, muzik, sure, cikti, ekler=(), bas=0.0):
    """Music (+ optional extra wav tracks at -12 dB) -> -14 LUFS."""
    girdi = ["-i", video, "-i", muzik]
    fc = f"[1:a]atrim={bas}:{bas + sure},asetpts=PTS-STARTPTS,afade=t=out:st={sure - 0.7}:d=0.7[m]"
    son = "[m]"
    for j, e in enumerate(ekler):
        girdi += ["-i", e]
        fc += f";[{j + 2}:a]volume=-12dB[e{j}]"
    if ekler:
        fc += ";" + "[m]" + "".join(f"[e{j}]" for j in range(len(ekler))) + f"amix=inputs={len(ekler) + 1}:normalize=0:duration=first[k]"
        son = "[k]"
    fc += f";{son}loudnorm=I=-14:TP=-1:LRA=11[a]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *girdi, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-t", str(sure), cikti], check=True)
