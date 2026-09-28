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
echo "hazir: $M"
