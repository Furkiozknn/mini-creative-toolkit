#!/bin/bash
# One-time setup on a fresh Linux box (CPU only). Models come from GitHub releases,
# not Hugging Face, so this works where huggingface.co is blocked.
set -e
M=${SOSYAL_MODELLER:-$HOME/modeller}; mkdir -p "$M" "$HOME/.u2net"
pip install --break-system-packages -q "mediapipe==0.10.21" onnxruntime sherpa-onnx "rembg[cpu]" "librosa==0.11.0" soundfile
# Optional, ~360 MB, only for blender_mockup.py (Python 3.11 needs 5.0.1):
[ "$1" = "--blender" ] && pip install --break-system-packages -q "bpy==5.0.1"
R=https://github.com
curl -sSfL -o "$M/depth_vits.onnx" $R/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/depth_anything_v2_vits.onnx
curl -sSfL -o "$M/silero_vad.onnx" $R/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx
curl -sSfL $R/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-small.tar.bz2 | tar xj -C "$M"
curl -sSfL -o "$HOME/.u2net/u2net_human_seg.onnx" $R/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx
# Scene cuts, audio FX, jump cuts, emoji rasterising (all measured working here, 28.09.2026)
pip install --break-system-packages -q "scenedetect[opencv-headless]==0.6.7" "pedalboard==0.9.25" "auto-editor==29.3.1" cairosvg
# Real-instrument music (muzik.py): tinysoundfont wheel without its optional pyaudio dep,
# GeneralUser GS soundfont (v2.0.3, free for music creation incl. commercial, ~32 MB).
pip install --break-system-packages -q --no-deps "tinysoundfont==0.3.7"
curl -sSfL -o "$M/GeneralUser-GS.sf2" https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2
# HyperFrames (HTML + GSAP -> MP4, Apache-2.0). Renders with the local headless shell; GSAP is
# vendored because headless Chrome here cannot reach jsDelivr. See docs/hyperframes.md.
if [ "$1" = "--hyperframes" ] || [ "$2" = "--hyperframes" ]; then
  mkdir -p "$HOME/hf" && (cd "$HOME/hf" && npm init -y >/dev/null && npm i --no-audit --no-fund "hyperframes@0.8.85" "gsap@3.14.2")
fi
echo "hazir: $M"
