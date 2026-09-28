#!/usr/bin/env python3
"""Vertical (1080x1920) social video generator, v2.

- 16 templates, rotated globally so consecutive posts never share a layout.
- Each game's own music, rotated per game so a game never repeats a track twice in a row.
- Two output kinds with different safe zones (research: scratchpad/viral-rehber.md, section 3):
    hikaye  Instagram/Facebook story: keep text inside y 250..1580, x 64..1016
    reels   Reels/TikTok/Shorts:      common safe box y 270..1248, x 120..780
  Blurred-background and bordered layouts are skipped for reels, because Instagram
  does not recommend Reels that look framed or blurry (rehber [12]).
- Hook text in the first seconds and a large CTA for the last >=3 s (rehber 1 and 6).
- Audio loudness-normalised to about -14 LUFS / -1 dBTP (rehber 4, unofficial target).

usage: python3 sosyal.py <oyun> [--tur hikaye|reels] [--sablon X] [--muzik yol] [--cikti f.mp4] [--kare]
"""
import argparse, json, os, subprocess
from PIL import ImageFont

def buyuk(m):
    """Turkish-aware upper case: i -> İ, ı -> I (str.upper gets these wrong)."""
    return m.replace("i", "İ").replace("ı", "I").upper()


KOK = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts") + "/"
SURE = 15
OYUN_KOK = os.environ.get("OYUN_KOK", os.path.expanduser("~"))  # game repos (their own music)
KAYNAK = os.environ.get("REEL_KAYNAK", os.path.expanduser("~/reels/out"))  # 16:9 source reels
W, H = 1080, 1920
KUTU = {"hikaye": (64, 250, 1016, 1580), "reels": (120, 270, 780, 1248)}

OYUNLAR = {
    "kanca": dict(ad="Kanca", kanca="Tavana kanca at.", r1="Tavana kanca at, sallan,", r2="doğru anda bırak.",
                  renk="F2B55A", koyu="1A1206", acik="FFF4E0"),
    "yercekimi-cevir": dict(ad="Yerçekimi Çevir", kanca="Zıplama tuşu yok.", r1="Zıplama tuşu yok.",
                            r2="Tek tuş yerçekimini çeviriyor.", renk="7FD6E8", koyu="071A1E", acik="E8FAFD"),
    "derin-kazi": dict(ad="Derin Kazı", kanca="250 metre aşağı in.", r1="Kaz, sat, geliştir.",
                       r2="250 metre aşağıda çekirdek var.", renk="E0875A", koyu="1E0F07", acik="FCEDE4"),
    "tek-tus-kosu": dict(ad="Tek Tuş Koşu", kanca="Tek tuş. Tek şans.", r1="Tek tuş. Her engel",
                         r2="müziğin vuruşunda.", renk="B69CFF", koyu="120B24", acik="F1ECFF"),
}
SABLONLAR = ["sinema", "bolunmus", "poster", "bulanik", "cerceve", "uclu", "tipografik", "bant",
             "zoom", "kare", "gazete", "neon", "cikartma", "plan", "gerisayim", "kinetik"]
REELS_DISI = {"bulanik", "cerceve"}


def f(ad):
    return FD + ad + ".ttf"


def uygun_boy(font, metin, genislik, en_buyuk):
    b = en_buyuk
    while b > 20 and ImageFont.truetype(font, b).getlength(metin) > genislik:
        b -= 2
    return b


def ok_var(font):
    from fontTools.ttLib import TTFont
    return ord("→") in TTFont(font).getBestCmap()


class Sahne:
    """Collects drawtext/drawbox steps; text goes through files to dodge escaping."""

    def __init__(self, td, kutu):
        self.td, self.adim, self.n = td, [], 0
        self.x0, self.y0, self.x1, self.y1 = kutu
        self.gw = self.x1 - self.x0

    def yazi(self, metin, font, boy, renk, x, y, enable=None, ek="", sigdir=True, genislik=None):
        if sigdir:
            boy = uygun_boy(font, metin, genislik or self.gw, boy)
        self.n += 1
        p = os.path.join(self.td, f"{self.n}.txt")
        open(p, "w").write(metin)
        s = f"drawtext=fontfile={font}:textfile={p}:fontsize={boy}:fontcolor={renk}:x={x}:y={y}{ek}"
        if enable:
            s += f":enable='{enable}'"
        self.adim.append(s)
        return boy

    def kutu(self, x, y, w, h, renk, enable=None):
        s = f"drawbox=x={x}:y={y}:w={w}:h={h}:color={renk}:t=fill"
        if enable:
            s += f":enable='{enable}'"
        self.adim.append(s)

    def zincir(self):
        return ",".join(self.adim)


def cta(s, o, font, renk_zemin, renk_yazi, y, merkez=True, bas=SURE - 4):
    """Big CTA block, on screen for the last 4 s (rehber: at least 3 s)."""
    en = f"gte(t,{bas})"
    metin = "TARAYICIDA OYNA  →" if ok_var(font) else "TARAYICIDA OYNA"
    w = s.gw
    s.kutu(s.x0, y, w, 120, renk_zemin, en)
    s.yazi(metin, font, 52, renk_yazi, f"{s.x0}+({w}-tw)/2", y + 32, en, genislik=w - 40)
    s.yazi(f"furkiozknn.github.io/{o['slug']}", f("JetBrainsMono-Regular"), 30, renk_zemin,
           f"{s.x0}+({w}-tw)/2" if merkez else s.x0, y + 140, en, genislik=w)


def kanca_yazi(s, o, font, renk, y, bitis=2.5):
    """Hook line alone on screen for the first seconds."""
    s.yazi(o["kanca"], font, 96, renk, f"{s.x0}+({s.gw}-tw)/2", y, f"lt(t,{bitis})")


def sablon_kur(ad, o, s):
    """Returns the base video graph; the Sahne steps are appended after it."""
    c, k, a = "0x" + o["renk"], "0x" + o["koyu"], "0x" + o["acik"]
    x0, y0, x1, y1, gw = s.x0, s.y0, s.x1, s.y1, s.gw
    C = f"{x0}+({gw}-tw)/2"
    B, R = f("BricolageGrotesque-Bold"), f("BricolageGrotesque-Regular")
    MONO = f("JetBrainsMono-Regular")
    AD = buyuk(o["ad"])
    reels = y1 < 1300

    if ad == "sinema":
        g = f"color=black:{W}x{H}[bg];[0:v]scale=1080:608[v];[bg][v]overlay=0:(H-h)/2+80"
        s.yazi("ÜCRETSİZ · TARAYICIDA", MONO, 32, c, x0, y0 + 20)
        s.yazi(AD, B, 130, "white", x0, y0 + 70)
        s.yazi(o["r1"], R, 50, "white@0.9", x0, y0 + 240)
        cta(s, o, B, c, "black", y1 - 180, merkez=False)
        return g
    if ad == "bolunmus":
        g = (f"color={k}:{W}x{H},drawbox=x=0:y=0:w=1080:h=960:color={c}:t=fill[bg];"
             f"[0:v]scale=1000:563[v];[bg][v]overlay=40:{y0 + 150}")
        s.yazi(AD, B, 120, k, x0, y0 - 10)
        s.yazi(o["r1"], R, 52, "white@0.9", x0, 1000)
        s.yazi(o["r2"], R, 52, "white@0.9", x0, 1065)
        cta(s, o, B, "white", k, 1110 if reels else 1400)
        return g
    if ad == "poster":
        g = f"color={c}:{W}x{H}[bg];[0:v]scale=900:506,pad=916:522:8:8:color={k}[v];[bg][v]overlay=82:(H-h)/2+60"
        s.yazi("ÜCRETSİZ · TARAYICIDA", MONO, 34, k, C, y0 + 10)
        s.yazi(AD, B, 170, k, C, y0 + 60)
        if not reels:
            s.yazi(o["r1"], R, 54, k, C, 1330)
        cta(s, o, B, k, c, y1 - 170)
        return g
    if ad == "bulanik":
        g = (f"[0:v]scale=-2:1920,crop=1080:1920,boxblur=30:3,eq=brightness=-0.35:saturation=0.7[bb];"
             f"[0:v]scale=1080:608[fg];[bb][fg]overlay=0:660")
        s.yazi("ÜCRETSİZ · TARAYICIDA", MONO, 30, c, C, y0 + 40)
        s.yazi(o["ad"], B, 104, "white", C, y0 + 100)
        s.yazi(o["r1"], R, 44, "white@0.85", C, y0 + 250)
        s.yazi(o["r2"], R, 44, "white@0.85", C, y0 + 310)
        cta(s, o, B, c, "0x111111", y1 - 190)
        return g
    if ad == "cerceve":
        g = f"color={k}:{W}x{H}[bg];[0:v]scale=880:495,pad=920:535:20:20:color={c}[v];[bg][v]overlay=80:700"
        s.yazi(o["ad"], B, 110, "white", x0, y0 + 150)
        s.yazi("ÜCRETSİZ · TARAYICIDA", MONO, 30, c, x0 + 4, y0 + 300)
        s.yazi(o["r1"], R, 48, "white@0.9", x0, 1290)
        cta(s, o, B, c, k, y1 - 170)
        return g
    if ad == "uclu":
        parca = lambda i, a_, b_: (f"[{i}]trim={a_}:{b_},setpts=PTS-STARTPTS,scale=1080:-2,crop=1080:470,"
                                   f"loop=-1:size=150[{i}2]")
        g = (f"[0:v]split=3[p][q][r];{parca('p',0,5)};{parca('q',5,10)};{parca('r',10,15)};"
             f"color={k}:{W}x{H}[bg];[bg][p2]overlay=0:240[x];[x][q2]overlay=0:730[y];[y][r2]overlay=0:1220,"
             f"drawbox=x=0:y=710:w=1080:h=20:color={c}:t=fill,drawbox=x=0:y=1200:w=1080:h=20:color={c}:t=fill")
        s.yazi(AD, B, 90, "white", C, 130)
        kanca_yazi(s, o, B, c, 560)
        cta(s, o, B, c, k, 1080 if reels else 1440)
        return g
    if ad == "tipografik":
        g = f"color={k}:{W}x{H}[bg];[0:v]scale=1080:608[v];[bg][v]overlay=0:1000"
        for i, (yy, ek) in enumerate([(y0, f":borderw=4:bordercolor={c}"), (y0 + 220, f":borderw=4:bordercolor={c}@0.5")]):
            s.yazi(AD, B, 220, "0x00000000", -40 - i * 100, yy, ek=ek, sigdir=False)
        s.yazi(AD, B, 220, c, -60, y0 + 440, sigdir=False)
        if reels:
            cta(s, o, B, c, k, 1100, merkez=False)
        else:
            s.yazi(o["r1"], R, 48, "white@0.9", x0, 920)
            cta(s, o, B, c, k, 1410, merkez=False)
        return g
    if ad == "bant":
        g = f"color={c}:{W}x{H}[bg];[0:v]scale=1080:608,pad=1080:648:0:20:color={k}[v];[bg][v]overlay=0:640"
        s.yazi("ÜCRETSİZ · TARAYICIDA", MONO, 34, k, x0, y0)
        s.yazi(AD, B, 120, k, x0, y0 + 50)
        s.yazi(o["r1"], R, 50, k, x0, y0 + 210)
        cta(s, o, B, k, c, 1090 if reels else 1340, merkez=False)
        return g
    if ad == "zoom":
        g = (f"color={k}:{W}x{H}[bg];[0:v]scale=1404:790,crop=1080:790[v];[bg][v]overlay=0:(H-h)/2")
        kanca_yazi(s, o, f("Outfit-Bold"), c, y0 + 40)
        s.yazi(AD, f("Outfit-Bold"), 120, "white", C, y0 + 40, "gte(t,2.5)")
        cta(s, o, f("Outfit-Bold"), c, k, 1080 if reels else y1 - 150)
        return g
    if ad == "kare":
        g = f"color={a}:{W}x{H}[bg];[0:v]scale=-2:1080,crop=1080:1080[v];[bg][v]overlay=0:H-h"
        s.yazi(AD, f("BigShoulders-Bold"), 200, k, x0, y0 - 10)
        s.yazi(o["r1"], f("WorkSans-Regular"), 48, k, x0, y0 + 220)
        s.yazi(o["r2"], f("WorkSans-Regular"), 48, k, x0, y0 + 280)
        cta(s, o, f("WorkSans-Bold"), k, a, y0 + 390, merkez=False)
        return g
    if ad == "gazete":
        g = (f"color=0xF4EFE6:{W}x{H},drawbox=x=60:y=230:w=960:h=6:color=0x1A1A1A:t=fill,"
             f"drawbox=x=60:y=242:w=960:h=2:color=0x1A1A1A:t=fill[bg];"
             f"[0:v]scale=960:540,hue=s=0.35[v];[bg][v]overlay=60:{760 if reels else 700}")
        s.yazi("OYUN GAZETESİ · SAYI 1", f("IBMPlexMono-Regular"), 30, "0x1A1A1A", 60, 190, sigdir=False)
        s.yazi(o["ad"], f("Gloock-Regular"), 140, "0x1A1A1A", x0, y0 + 20)
        s.yazi(o["r1"], f("IBMPlexSerif-Italic"), 50, "0x1A1A1A", x0, y0 + 200)
        s.yazi(o["r2"], f("IBMPlexSerif-Italic"), 50, "0x1A1A1A", x0, y0 + 260)
        if reels:
            cta(s, o, f("IBMPlexSerif-Bold"), "0x1A1A1A", "0xF4EFE6", 1320 - 200, merkez=False)
        else:
            s.yazi("Fotoğraf: oyundan bir an", f("IBMPlexMono-Regular"), 26, "0x555555", 60, 1255, sigdir=False)
            cta(s, o, f("IBMPlexSerif-Bold"), "0x1A1A1A", "0xF4EFE6", 1330, merkez=False)
        return g
    if ad == "neon":
        g = f"color=0x07070C:{W}x{H}[bg];[0:v]scale=1080:608,eq=saturation=1.4:contrast=1.1[v];[bg][v]overlay=0:760"
        for bw, al in [(18, 0.15), (10, 0.3), (4, 0.9)]:
            s.yazi(AD, f("Tektur-Medium"), 130, "0x00000000", C, y0 + 60, ek=f":borderw={bw}:bordercolor={c}@{al}")
        s.yazi(AD, f("Tektur-Medium"), 130, "white", C, y0 + 60)
        s.yazi(o["r1"], f("Tektur-Regular"), 46, c, C, y0 + 240)
        cta(s, o, f("Tektur-Medium"), c, "0x07070C", 1110 if reels else y1 - 170)
        return g
    if ad == "cikartma":
        tb = uygun_boy(f("Outfit-Bold"), AD, 640, 110)
        tp = os.path.join(s.td, "cikartma.txt")
        open(tp, "w").write(AD)
        g = (f"color={k}:{W}x{H}[bg];[0:v]scale=1080:608[v];[bg][v]overlay=0:{560 if reels else 640}[b0];"
             f"color={c}:760x200,format=rgba,drawtext=fontfile={f('Outfit-Bold')}:textfile={tp}:fontsize={tb}:"
             f"fontcolor={k}:x=(w-tw)/2:y=(h-th)/2,rotate=-0.07:c=none:ow=rotw(-0.07):oh=roth(-0.07)[st];"
             f"[b0][st]overlay=(W-w)/2-40:{y0 + 30}")
        s.yazi(o["r1"], f("Outfit-Regular"), 50, "white", C, y0 + 310 if reels else 1300)
        cta(s, o, f("Outfit-Bold"), c, k, 1110 if reels else y1 - 170)
        return g
    if ad == "plan":
        g = (f"color=0x0B2A4A:{W}x{H},drawgrid=w=60:h=60:t=1:c=white@0.12,drawgrid=w=300:h=300:t=2:c=white@0.25[bg];"
             f"[0:v]scale=900:506,pad=904:510:2:2:color=white[v];[bg][v]overlay=88:{600 if reels else 720}")
        s.yazi("PLAN NO. 01 — ÖLÇEK 1:1", f("GeistMono-Regular"), 30, "white@0.7", x0, y0)
        s.yazi(AD, f("GeistMono-Bold"), 110, "white", x0, y0 + 50)
        s.yazi(o["r1"], f("GeistMono-Regular"), 38, "white@0.85", x0, y0 + 200)
        if not reels:
            s.yazi(o["r2"], f("GeistMono-Regular"), 38, "white@0.85", x0, y0 + 250)
        cta(s, o, f("GeistMono-Bold"), "white", "0x0B2A4A", 1100 if reels else 1290, merkez=False)
        return g
    if ad == "gerisayim":
        g = f"color={k}:{W}x{H}[bg];[0:v]scale=1080:608[v];[bg][v]overlay=0:(H-h)/2+40:enable='gte(t,1.5)'"
        for i, n in enumerate(["3", "2", "1"]):
            s.yazi(n, f("Boldonse-Regular"), 420, c, "(w-tw)/2", "(h-th)/2-200", f"between(t,{i*0.5},{i*0.5+0.49})", sigdir=False)
        s.yazi(AD, B, 120, "white", C, y0 + 30, "gte(t,1.5)")
        s.yazi(o["r1"], R, 48, "white@0.85", C, y0 + 190, "gte(t,1.5)")
        cta(s, o, B, c, k, 1110 if reels else y1 - 170)
        return g
    if ad == "kinetik":
        g = f"color={k}:{W}x{H}[bg];[0:v]scale=1080:608[v];[bg][v]overlay=0:(H-h)/2+120"
        kelimeler = (o["r1"] + " " + o["r2"]).split()
        for i, kel in enumerate(kelimeler):
            t0 = 0.3 + i * 0.35
            renk = c if i == len(kelimeler) - 1 else "white"
            s.yazi(buyuk(kel), f("InstrumentSans-Bold"), 110, renk, C, y0 + 60, f"between(t,{t0},{t0 + 0.34})")
        son = 0.3 + len(kelimeler) * 0.35
        s.yazi(AD, f("InstrumentSans-Bold"), 110, c, C, y0 + 60, f"gte(t,{son})")
        cta(s, o, f("InstrumentSans-Bold"), c, k, 1110 if reels else y1 - 170)
        return g
    raise SystemExit("bilinmeyen sablon " + ad)


def durum_oku():
    try:
        return json.load(open(os.path.join(KOK, "durum.json")))
    except Exception:
        return {"sablon": -1, "muzik": {}}


def durum_yaz(d):
    json.dump(d, open(os.path.join(KOK, "durum.json"), "w"), indent=1, ensure_ascii=False)


def muzikler(oyun):
    d = os.path.join(OYUN_KOK, oyun, "assets", "audio")
    out = []
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if n.startswith("muzik") and n.endswith(".wav") and os.path.getsize(p) > 10000:
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                       capture_output=True, text=True).stdout or 0)
            if dur >= 8:  # a 4 s jingle can't carry a 15 s clip
                out.append(p)
    return out


def uret(oyun, tur="hikaye", sablon=None, muzik=None, cikti=None, kare=False, durum_guncelle=True):
    o = dict(OYUNLAR[oyun], slug=oyun)
    d = durum_oku()
    if sablon is None:
        i = d["sablon"]
        while True:
            i = (i + 1) % len(SABLONLAR)
            if not (tur == "reels" and SABLONLAR[i] in REELS_DISI):
                break
        d["sablon"], sablon = i, SABLONLAR[i]
    if muzik is None:
        havuz = muzikler(oyun)
        j = (d["muzik"].get(oyun, -1) + 1) % len(havuz)
        d["muzik"][oyun], muzik = j, havuz[j]
    td = os.path.join(KOK, "t", oyun, sablon, tur)
    os.makedirs(td, exist_ok=True)
    s = Sahne(td, KUTU[tur])
    g = sablon_kur(sablon, o, s)
    vf = g + ("," + s.zincir() if s.adim else "") + ",format=yuv420p[vo]"
    af = (f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{SURE},afade=t=in:d=0.3,afade=t=out:st={SURE-1.2}:d=1.2,"
          f"loudnorm=I=-14:TP=-1:LRA=11,aresample=48000[ao]")
    cikti = cikti or os.path.join(KOK, "cikti", f"{oyun}-{sablon}-{tur}.mp4")
    os.makedirs(os.path.dirname(cikti), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(KAYNAK, oyun, "reel.mp4"), "-i", muzik,
                    "-filter_complex", vf + ";" + af, "-map", "[vo]", "-map", "[ao]", "-t", str(SURE), "-r", "30",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", cikti], check=True)
    if kare:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "12", "-i", cikti, "-frames:v", "1", cikti[:-4] + ".jpg"], check=True)
    if durum_guncelle:
        durum_yaz(d)
    return cikti, sablon, muzik


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("oyun", choices=OYUNLAR)
    p.add_argument("--tur", choices=KUTU, default="hikaye")
    p.add_argument("--sablon", choices=SABLONLAR)
    p.add_argument("--muzik")
    p.add_argument("--cikti")
    p.add_argument("--kare", action="store_true")
    x = p.parse_args()
    print(*uret(x.oyun, x.tur, x.sablon, x.muzik, x.cikti, x.kare), sep="\n")
