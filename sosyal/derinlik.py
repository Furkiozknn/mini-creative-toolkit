#!/usr/bin/env python3
"""Turn a still photo into a 2.5D "3D photo" clip (parallax camera move).

Depth comes from Depth-Anything-V2-Small (ONNX, from its GitHub release, runs on CPU).
Near pixels move more than far ones as a virtual camera dollies/orbits, so a flat
picture gains depth. Edges reuse mirrored pixels, and a 12 % margin keeps them off screen.

usage: python3 derinlik.py foto.jpg cikti.mp4 [--hareket dolly|yorunge|yukselis] [--sure 6] [--oran 9:16|4:5]
"""
import argparse, os, subprocess
import cv2, numpy as np, onnxruntime as ort

MODEL = os.path.join(os.environ.get("SOSYAL_MODELLER", os.path.expanduser("~/modeller")), "depth_vits.onnx")


def derinlik(img):
    s = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
    x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (518, 518), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    d = s.run(None, {s.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    d = cv2.resize(d, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_CUBIC)
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)  # 1 = near
    return cv2.GaussianBlur(d, (0, 0), 3)


def kirp(img, ow, oh):
    h, w = img.shape[:2]
    s = max(ow / w, oh / h) * 1.12  # 12 % margin so edges never show during the move
    img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_CUBIC)
    h, w = img.shape[:2]
    y, x = (h - int(oh * 1.12)) // 2, (w - int(ow * 1.12)) // 2
    return img[y:y + int(oh * 1.12), x:x + int(ow * 1.12)]


def uret(foto, cikti, hareket="dolly", sure=6.0, oran="9:16", fps=30):
    ow, oh = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080)}[oran]
    img = kirp(cv2.imread(foto), ow, oh)
    d = derinlik(img)
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ow}x{oh}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", cikti], stdin=subprocess.PIPE)
    n = int(sure * fps)
    for i in range(n):
        u = i / (n - 1); e = u * u * (3 - 2 * u)
        if hareket == "dolly":        # push towards the subject: near things grow faster
            z = 1 + 0.10 * e * (0.4 + d)
            mx, my = cx + (xx - cx) / z, cy + (yy - cy) / z
        elif hareket == "yorunge":    # sideways orbit: near things slide more
            a = np.sin(e * np.pi - np.pi / 2)
            mx, my = xx + a * 0.035 * w * (d - 0.5), yy
        else:                          # "yukselis": crane up
            mx, my = xx, yy - (e - 0.5) * 0.04 * h * (d - 0.4)
        kare = cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        ox, oy = (w - ow) // 2, (h - oh) // 2
        enc.stdin.write(np.ascontiguousarray(kare[oy:oy + oh, ox:ox + ow]).tobytes())
    enc.stdin.close(); enc.wait()
    cv2.imwrite(cikti[:-4] + "-derinlik.jpg", (d * 255).astype(np.uint8))
    return cikti


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("foto"); p.add_argument("cikti")
    p.add_argument("--hareket", default="dolly", choices=["dolly", "yorunge", "yukselis"])
    p.add_argument("--sure", type=float, default=6.0); p.add_argument("--oran", default="9:16")
    x = p.parse_args()
    print(uret(x.foto, x.cikti, x.hareket, x.sure, x.oran))
