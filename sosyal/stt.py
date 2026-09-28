#!/usr/bin/env python3
"""Offline speech-to-text with approximate word timings (CPU, no Hugging Face).

sherpa-onnx Whisper-small gives text but no word timestamps, so:
  1. Silero VAD splits the audio into speech segments (exact start/end),
  2. each segment is transcribed separately,
  3. the segment's time is shared across its words in proportion to their length.
Good enough for 1-3 word karaoke captions; not frame-exact.

usage: python3 stt.py giris.(mp4|wav) kelimeler.json [--dil tr]
"""
import argparse, json, subprocess, tempfile, os
import numpy as np, soundfile as sf, sherpa_onnx

M = os.environ.get("SOSYAL_MODELLER", os.path.expanduser("~/modeller")) + "/"
WD = M + "sherpa-onnx-whisper-small/"


def wav16k(giris):
    t = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", giris, "-ac", "1", "-ar", "16000", t], check=True)
    a, _ = sf.read(t, dtype="float32")
    os.remove(t)
    return a


def konusma(a, sr=16000):
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = M + "silero_vad.onnx"
    cfg.silero_vad.min_silence_duration = 0.35
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = 20
    cfg.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=120)
    ws = cfg.silero_vad.window_size
    for i in range(0, len(a), ws):
        vad.accept_waveform(a[i:i + ws])
    vad.flush()
    seg = []
    while not vad.empty():
        s = vad.front
        seg.append((s.start / sr, np.array(s.samples, dtype="float32")))
        vad.pop()
    return seg


def cozumle(giris, dil="tr"):
    r = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=WD + "small-encoder.int8.onnx", decoder=WD + "small-decoder.int8.onnx",
        tokens=WD + "small-tokens.txt", language=dil, task="transcribe", num_threads=os.cpu_count() or 4)
    a = wav16k(giris)
    out = []
    for bas, ornek in konusma(a):
        s = r.create_stream(); s.accept_waveform(16000, ornek); r.decode_stream(s)
        kelime = s.result.text.strip().split()
        if not kelime:
            continue
        sure = len(ornek) / 16000
        agirlik = np.array([len(k) + 1 for k in kelime], dtype=float)
        sinir = np.concatenate([[0], np.cumsum(agirlik) / agirlik.sum()]) * sure
        for k, t0, t1 in zip(kelime, sinir[:-1], sinir[1:]):
            out.append(dict(text=k, start=round(bas + t0, 3), end=round(bas + t1, 3)))
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("giris"); p.add_argument("cikti"); p.add_argument("--dil", default="tr")
    x = p.parse_args()
    w = cozumle(x.giris, x.dil)
    json.dump(w, open(x.cikti, "w"), ensure_ascii=False, indent=1)
    print(len(w), "kelime:", " ".join(k["text"] for k in w)[:300])
