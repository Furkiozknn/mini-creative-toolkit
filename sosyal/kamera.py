#!/usr/bin/env python3
"""Virtual multi-camera from a single static shot.

A locked-off video becomes an edit with several "camera angles" by cropping:
geniş (wide) -> orta (medium) -> yakın (close-up) -> ..., each shot with a slow
push-in or pull-out, the frame following the face (MediaPipe, smoothed), the
eye line held near the upper third, and a short whip-blur on some cuts.
Cuts land on speech pauses when there are any, otherwise every 2.5-4 s.
Nothing is generated or invented; every pixel comes from the original shot,
so close-ups are only as sharp as the source resolution allows.

usage: python3 kamera.py giris.mp4 cikti.mp4 [--tur reels|hikaye]
"""
import argparse, os, subprocess, json, random
import cv2, numpy as np

W, H = 1080, 1920
OLCEK = {"genis": 1.0, "orta": 1.4, "yakin": 1.9}
SIRA = ["genis", "orta", "yakin", "orta", "genis", "yakin"]


def bilgi(p):
    c = cv2.VideoCapture(p)
    r = (int(c.get(3)), int(c.get(4)), c.get(5) or 30, int(c.get(7)))
    c.release()
    return r


def yuz_izi(p, n, adim=3):
    """Face centre per frame (fractions), interpolated and smoothed; centre fallback."""
    import mediapipe as mp
    det = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.75)
    c = cv2.VideoCapture(p)
    xs, ys, idx = [], [], []
    i = 0
    while True:
        ok, kare = c.read()
        if not ok:
            break
        if i % adim == 0:
            r = det.process(cv2.cvtColor(kare, cv2.COLOR_BGR2RGB))
            if r.detections:
                b = max(r.detections, key=lambda d: d.score[0]).location_data.relative_bounding_box
                xs.append(b.xmin + b.width / 2); ys.append(b.ymin + b.height * 0.4); idx.append(i)
        i += 1
    c.release()
    # A face must show up in a good share of the sampled frames; stray hits on
    # graphics or patterns would otherwise drag the frame around.
    if len(idx) < 0.3 * (i / adim):
        return np.full(n, 0.5), np.full(n, 0.38), False
    t = np.arange(n)
    fx, fy = np.interp(t, idx, xs), np.interp(t, idx, ys)
    k = np.ones(15) / 15  # ~0.5 s moving average: a camera operator, not a jittery tracker
    fx = np.convolve(np.pad(fx, 7, mode="edge"), k, "valid")
    fy = np.convolve(np.pad(fy, 7, mode="edge"), k, "valid")
    return fx, fy, True


def kesimler(p, fps, n):
    log = subprocess.run(["ffmpeg", "-i", p, "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    import re
    sessiz = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    toplam = n / fps
    noktalar, son = [], 0.0
    rnd = random.Random(7)
    for s in sessiz + [toplam]:
        while s - son > 4.0:  # never hold one angle longer than ~4 s
            son += rnd.uniform(2.5, 3.5); noktalar.append(son)
        if s - son >= 1.5 and s < toplam - 0.8:
            son = s; noktalar.append(s)
    return [int(t * fps) for t in noktalar]


def uret(giris, cikti, tur="reels"):
    gw, gh, fps, n = bilgi(giris)
    fx, fy, yuz_var = yuz_izi(giris, n)
    kes = kesimler(giris, fps, n)
    sinir = [0] + kes + [n]
    plan = []
    for j, (a, b) in enumerate(zip(sinir[:-1], sinir[1:])):
        tip = SIRA[j % len(SIRA)]
        itme = 1 if j % 2 == 0 else -1  # alternate push-in / pull-out
        plan.append((a, b, tip, itme, j > 0 and j % 3 == 0))
    # Largest 9:16 crop the source allows = the "wide" shot.
    bw = min(gw, gh * 9 / 16); bh = bw * 16 / 9
    ses = cikti + ".ses.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", giris, "-vn", "-c:a", "aac", "-b:a", "192k", ses])
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", ses, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
                            "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest",
                            "-movflags", "+faststart", cikti], stdin=subprocess.PIPE)
    c = cv2.VideoCapture(giris)
    for a, b, tip, itme, savur in plan:
        for i in range(a, b):
            ok, kare = c.read()
            if not ok:
                break
            u = (i - a) / max(1, b - a - 1)
            u = u * u * (3 - 2 * u)  # ease in-out
            z = OLCEK[tip] * (1 + 0.06 * (u if itme > 0 else 1 - u))
            cw, ch = bw / z, bh / z
            cx = fx[min(i, n - 1)] * gw - cw / 2
            cy = fy[min(i, n - 1)] * gh - ch / 3  # eyes near the upper third
            cx = min(max(cx, 0), gw - cw); cy = min(max(cy, 0), gh - ch)
            M = np.float32([[W / cw, 0, -cx * W / cw], [0, H / ch, -cy * H / ch]])
            img = cv2.warpAffine(kare, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            if savur and i - a < 4:  # whip-pan blur on the first frames of some cuts
                k = np.zeros((1, 61), np.float32); k[0, :] = 1 / 61
                img = cv2.filter2D(img, -1, k)
            enc.stdin.write(img.tobytes())
    c.release(); enc.stdin.close(); enc.wait(); os.remove(ses)
    return dict(yuz=yuz_var, plan=[(round(a / fps, 2), round(b / fps, 2), t) for a, b, t, _, _ in plan])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("giris"); p.add_argument("cikti"); p.add_argument("--tur", default="reels")
    x = p.parse_args()
    print(json.dumps(uret(x.giris, x.cikti, x.tur), ensure_ascii=False))
