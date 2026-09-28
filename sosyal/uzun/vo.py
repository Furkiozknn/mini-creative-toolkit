import json, sherpa_onnx, soundfile as sf, numpy as np
from metin import SEG
d = "/home/claude/modeller/vits-piper-tr_TR-fettah-medium/"
tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
    vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=d + "tr_TR-fettah-medium.onnx", tokens=d + "tokens.txt", data_dir=d + "espeak-ng-data"),
    num_threads=4)))
bilgi = {}
for sid, satirlar in SEG:
    parca = []
    for i, (cap, soz) in enumerate(satirlar):
        a = tts.generate(soz or cap, sid=0, speed=0.97)
        y = np.asarray(a.samples, np.float32)
        # trim silence at both ends, keep 60 ms
        idx = np.where(np.abs(y) > 0.01)[0]
        y = y[max(0, idx[0] - 1300): idx[-1] + 1300]
        f = f"vo/{sid}_{i}.wav"; sf.write(f, y, a.sample_rate)
        parca.append(dict(dosya=f, sure=len(y) / a.sample_rate, metin=cap))
    bilgi[sid] = parca
json.dump(bilgi, open("vo.json", "w"), ensure_ascii=False, indent=1)
top = sum(p["sure"] for v in bilgi.values() for p in v)
print("toplam konusma", round(top, 1), "sn")
for k, v in bilgi.items(): print(k, [round(p["sure"], 2) for p in v])
