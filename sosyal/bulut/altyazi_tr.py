#!/usr/bin/env python3
"""Turkish (or any language) speech -> word timings with faster-whisper.

Real per-word timestamps (unlike ../stt.py, which splits a segment by word
length). Needs the model from Hugging Face, so it runs where HF is reachable
(the Higgsfield sandbox; not our main container). Output JSON matches stt.py:
[{"text", "start", "end"}], so efektler.altyazi_ass() reads it unchanged.

usage: python3 altyazi_tr.py giris.(mp4|mp3|wav) kelimeler.json [--dil tr] [--model small]
"""
import argparse, json
from faster_whisper import WhisperModel

p = argparse.ArgumentParser()
p.add_argument("giris"); p.add_argument("cikti")
p.add_argument("--dil", default="tr"); p.add_argument("--model", default="small")
x = p.parse_args()
m = WhisperModel(x.model, device="cpu", compute_type="int8")
seg, _ = m.transcribe(x.giris, language=x.dil, word_timestamps=True, vad_filter=True)
out = [dict(text=w.word.strip(), start=round(w.start, 3), end=round(w.end, 3)) for s in seg for w in s.words]
json.dump(out, open(x.cikti, "w"), ensure_ascii=False, indent=1)
print(len(out), "kelime:", " ".join(k["text"] for k in out)[:300])
