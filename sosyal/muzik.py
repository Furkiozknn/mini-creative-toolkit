#!/usr/bin/env python3
"""Seeded background music in distinct genres, rendered with real instrument samples.

Why: every promo so far used music from our own chiptune generator, so every video
sounded alike. This writes MIDI-style events and renders them through the
GeneralUser GS soundfont (free for music creation, commercial use included; see
fonts/../muzik_lisans.txt) with tinysoundfont, so a lo-fi track gets an electric
piano and brushed drums while an epic track gets strings, brass and timpani.

Each genre fixes tempo range, scale, instruments and drum feel; the seed picks key,
tempo, chord progression, melody and instrument variants. Same seed -> same file.

usage: python3 muzik.py cikti.wav --tur lofi --sure 15 --tohum 7
       python3 muzik.py cikti.wav --sira         (next genre in rotation, state in muzik_durum.json)
"""
import argparse, json, os, subprocess, tempfile
import numpy as np, soundfile as sf

SF2 = os.path.join(os.environ.get("SOSYAL_MODELLER", os.path.expanduser("~/modeller")), "GeneralUser-GS.sf2")
SR = 44100
DURUM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik_durum.json")

MAJ = [0, 2, 4, 5, 7, 9, 11]
MIN = [0, 2, 3, 5, 7, 8, 10]
DOR = [0, 2, 3, 5, 7, 9, 10]
# progressions as scale degrees (0-based)
PROG = {"min": [[0, 5, 2, 6], [0, 3, 4, 0], [0, 6, 5, 6], [5, 3, 0, 4], [0, 3, 6, 2]],
        "maj": [[0, 4, 5, 3], [0, 5, 3, 4], [3, 4, 0, 0], [0, 3, 0, 4], [5, 3, 0, 4]]}

# GM programs: 0 piano, 4 e-piano, 7 clav, 24 nylon, 25 steel, 32 ac bass, 33 finger bass, 36 slap,
# 38/39 synth bass, 48 strings, 52 choir, 61 brass, 47 timpani, 80 square, 81 saw, 89 warm pad,
# 90 polysynth pad, 9 glockenspiel, 10 music box, 11 vibraphone, 46 harp
TURLER = {
    "lofi":      dict(bpm=(70, 84), mod="min", olcek=DOR, akor=[4, 0, 24], bas=[32, 33], melodi=[11, 4, 10],
                      davul="lofi", salinim=0.18, oktav=0),
    "synthwave": dict(bpm=(100, 116), mod="min", olcek=MIN, akor=[89, 90], bas=[38, 39], melodi=[81, 80],
                      davul="dort", salinim=0.0, oktav=0),
    "trap":      dict(bpm=(130, 148), mod="min", olcek=MIN, akor=[89, 48], bas=[39, 38], melodi=[10, 9, 11],
                      davul="trap", salinim=0.0, oktav=1),
    "epik":      dict(bpm=(88, 104), mod="min", olcek=MIN, akor=[48, 52], bas=[48], melodi=[61, 60],
                      davul="epik", salinim=0.0, oktav=0),
    "funk":      dict(bpm=(104, 118), mod="maj", olcek=DOR, akor=[7, 4], bas=[36, 33], melodi=[61, 56],
                      davul="funk", salinim=0.1, oktav=0),
    "chiptune":  dict(bpm=(140, 160), mod="maj", olcek=MAJ, akor=[80], bas=[81], melodi=[80, 81],
                      davul="chip", salinim=0.0, oktav=1),
    "akustik":   dict(bpm=(90, 102), mod="maj", olcek=MAJ, akor=[25, 24], bas=[32], melodi=[0, 46, 11],
                      davul="akustik", salinim=0.08, oktav=0),
}
SIRA = ["synthwave", "lofi", "epik", "funk", "trap", "akustik", "chiptune"]

# GM drum keys
KICK, SNARE, CLAP, HAT, OHAT, RIDE, CRASH, TOM_L, TOM_H, SHAKER, RIM = 36, 38, 39, 42, 46, 51, 49, 45, 50, 70, 37


def davul(stil, bar, adim, rng, son_bar):
    """16th-step drum hits for one bar: list of (step, key, velocity)."""
    h = []
    if stil == "lofi":
        for s in (0, 7, 10):
            h.append((s, KICK, 100))
        for s in (4, 12):
            h.append((s, SNARE, 80))
        for s in range(0, 16, 2):
            h.append((s, HAT, 45 + (s % 4 == 0) * 15))
    elif stil == "dort":
        for s in (0, 4, 8, 12):
            h.append((s, KICK, 110))
        for s in (4, 12):
            h.append((s, SNARE, 100)); h.append((s, CLAP, 70))
        for s in range(2, 16, 4):
            h.append((s, OHAT, 60))
    elif stil == "trap":  # half-time: snare on 3, rolling hats
        for s in (0, 3, 10) if bar % 2 == 0 else (0, 6, 11):
            h.append((s, KICK, 110))
        h.append((8, CLAP, 105)); h.append((8, SNARE, 80))
        for s in range(16):
            if s % 2 == 0 or (rng.random() < 0.35):
                h.append((s, HAT, 55 + int(rng.integers(0, 30))))
    elif stil == "epik":
        h.append((0, KICK, 115)); h.append((8, KICK, 100))
        for s in (4, 12):
            h.append((s, TOM_L, 95))
        if bar % 2 == 1:
            for s in (12, 13, 14, 15):
                h.append((s, TOM_H, 70 + s * 2))
    elif stil == "funk":
        for s in (0, 3, 6, 10):
            h.append((s, KICK, 105))
        for s in (4, 12):
            h.append((s, SNARE, 105))
        h.append((15, SNARE, 45))
        for s in range(16):
            h.append((s, HAT, 70 if s % 2 == 0 else 45))
    elif stil == "chip":
        for s in (0, 8):
            h.append((s, KICK, 110))
        for s in (4, 12):
            h.append((s, SNARE, 100))
        for s in range(0, 16, 2):
            h.append((s, HAT, 60))
    elif stil == "akustik":
        for s in (0, 8):
            h.append((s, KICK, 90))
        for s in (4, 12):
            h.append((s, CLAP, 85))
        for s in range(16):
            h.append((s, SHAKER, 40 + (s % 2 == 0) * 20))
    if bar == 0:
        h.append((0, CRASH, 90))
    if son_bar:  # fill into the loop point
        h = [x for x in h if x[0] < 12] + [(s, SNARE, 70 + (s - 12) * 10) for s in (12, 13, 14, 15)]
    return h


def olustur(tur, sure, tohum):
    rng = np.random.default_rng(tohum)
    g = TURLER[tur]
    bpm = int(rng.integers(g["bpm"][0], g["bpm"][1] + 1))
    ton = int(rng.integers(0, 12))  # key
    olc = g["olcek"]
    prog = PROG[g["mod"]][int(rng.integers(0, len(PROG[g["mod"]])))]
    adim = 60 / bpm / 4  # 16th note
    bar_s = adim * 16
    barlar = max(4, int(round(sure / bar_s)))
    barlar += (-barlar) % 4  # whole progressions so it loops
    olay = []  # (t, kind, chan, key, vel)

    def nota(t, ch, k, v, d):
        olay.append((t, 1, ch, k, v)); olay.append((t + d, 0, ch, k, 0))

    def derece(d, oktav=0):
        return 48 + ton + olc[d % 7] + 12 * (d // 7 + oktav)

    # melody motif: 8 steps over 2 bars, repeated with variation
    motif = []
    d = int(rng.integers(0, 5))
    for i in range(8):
        d += int(rng.choice([-2, -1, 0, 1, 1, 2, 3]))
        d = max(-2, min(9, d))
        motif.append((i * 4 + int(rng.choice([0, 0, 2])), d, int(rng.choice([2, 3, 4, 6]))))
    for b in range(barlar):
        t0 = b * bar_s
        kok = prog[b % 4]
        # swing: delay every off-beat 16th
        def zaman(s):
            return t0 + s * adim + (g["salinim"] * adim if s % 2 == 1 else 0)
        # chords
        if g["davul"] in ("funk", "chip"):
            for s in (0, 3, 6, 10, 14):
                for k in (0, 2, 4):
                    nota(zaman(s), 0, derece(kok + k, 1), 70, adim * 1.5)
        elif g["davul"] == "akustik":
            for s in range(0, 16, 2):
                for j, k in enumerate((0, 2, 4, 7)):
                    nota(zaman(s) + j * 0.012, 0, derece(kok + k, 1), 62 if s % 4 else 78, adim * 2)
        else:
            for k in (0, 2, 4, 6 if tur == "lofi" else 4):
                nota(t0, 0, derece(kok + k, 1), 62, bar_s * 0.98)
        # bass
        if g["davul"] == "trap":
            nota(t0, 1, derece(kok, -1), 115, bar_s * 0.6)
            nota(zaman(10), 1, derece(kok, -1), 105, adim * 5)
        elif g["davul"] == "dort":
            for s in range(0, 16, 2):
                nota(zaman(s), 1, derece(kok, -1 + (s % 4 == 2)), 95, adim * 1.6)
        elif g["davul"] == "funk":
            for s, o in ((0, -1), (3, 0), (6, -1), (7, -1), (10, 0), (12, -1)):
                nota(zaman(s), 1, derece(kok, o), 100, adim * 1.2)
        else:
            for s in (0, 6, 8, 14) if tur == "lofi" else (0, 8):
                nota(zaman(s), 1, derece(kok, -1), 95, adim * 5)
        # melody from bar 1 (bar 0 is the intro), motif every 2 bars, varied on repeats
        if b >= 1:
            yarim = (b % 2) * 32
            for s, dd, uz in motif:
                if yarim <= s < yarim + 16 and not (b % 4 == 3 and s % 2 == 1):
                    oy = dd + (1 if (b // 2) % 2 and s == motif[-1][0] else 0)
                    nota(zaman(s - yarim), 2, derece(oy, 1 + g["oktav"]), 88, adim * uz)
        for s, k, v in davul(g["davul"], b, adim, rng, b == barlar - 1):
            nota(zaman(s), 9, k, v, adim)
    toplam = barlar * bar_s
    return olay, toplam, dict(tur=tur, bpm=bpm, ton=ton, barlar=barlar, sure=round(toplam, 2),
                              calgi=None, tohum=tohum), rng


def cal(olay, toplam, tur, rng):
    import tinysoundfont as tsf
    g = TURLER[tur]
    s = tsf.Synth(gain=-6, samplerate=SR)
    sid = s.sfload(SF2)
    calgi = dict(akor=int(rng.choice(g["akor"])), bas=int(rng.choice(g["bas"])), melodi=int(rng.choice(g["melodi"])))
    s.program_select(0, sid, 0, calgi["akor"])
    s.program_select(1, sid, 0, calgi["bas"])
    s.program_select(2, sid, 0, calgi["melodi"])
    s.program_select(9, sid, 128, 0, True)
    olay = sorted(olay, key=lambda e: (e[0], e[1]))
    parca, t = [], 0.0
    kuyruk = 1.5
    for (te, tip, ch, k, v) in olay + [(toplam + kuyruk, 0, 0, 0, 0)]:
        n = int(round((te - t) * SR))
        if n > 0:
            parca.append(np.frombuffer(s.generate(n), dtype=np.float32).reshape(-1, 2).copy()); t += n / SR
        if tip == 1:
            s.noteon(ch, k, v)
        elif k:
            s.noteoff(ch, k)
    ses = np.concatenate(parca)
    # fold the release tail back onto the start so the loop is seamless
    L = int(toplam * SR)
    govde, kalan = ses[:L].copy(), ses[L:]
    govde[:len(kalan)] += kalan[:L]
    return govde, calgi


def uret(cikti, tur=None, sure=15.0, tohum=None):
    if tur is None:  # rotation: never the same genre twice in a row
        d = json.load(open(DURUM)) if os.path.exists(DURUM) else {"i": -1, "tohum": 0}
        d["i"] = (d["i"] + 1) % len(SIRA); d["tohum"] += 1
        json.dump(d, open(DURUM, "w"))
        tur, tohum = SIRA[d["i"]], d["tohum"] if tohum is None else tohum
    tohum = 1 if tohum is None else tohum
    olay, toplam, bilgi, rng = olustur(tur, sure, tohum)
    ses, calgi = cal(olay, toplam, tur, rng)
    bilgi["calgi"] = calgi
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, ses, SR)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp.name, "-af",
                    "acompressor=threshold=-18dB:ratio=3:attack=10:release=120,loudnorm=I=-14:TP=-1:LRA=9",
                    "-ar", "48000", cikti], check=True)
    os.remove(tmp.name)
    return bilgi


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cikti")
    p.add_argument("--tur", choices=list(TURLER)); p.add_argument("--sure", type=float, default=15)
    p.add_argument("--tohum", type=int); p.add_argument("--sira", action="store_true")
    x = p.parse_args()
    print(json.dumps(uret(x.cikti, None if x.sira else (x.tur or "synthwave"), x.sure, x.tohum), ensure_ascii=False))
