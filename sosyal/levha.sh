#!/bin/bash
# levha.sh <oyun> <tur> <cikti.jpg> : 16 frames in a 8x2 sheet with the safe box drawn
o=$1; t=$2; out=$3
if [ "$t" = reels ]; then B="x=120:y=270:w=660:h=978"; else B="x=64:y=250:w=952:h=1330"; fi
i=0; args=""; fl=""
for s in sinema bolunmus poster bulanik cerceve uclu tipografik bant zoom kare gazete neon cikartma plan gerisayim kinetik; do
  f=$o-$s-$t.jpg; [ -f "$f" ] || continue
  ffmpeg -y -v error -i $f -vf "drawbox=$B:color=red@0.8:t=4,scale=270:480" /tmp/l_$i.jpg
  args="$args -i /tmp/l_$i.jpg"; fl="$fl[$i]"; i=$((i+1))
done
h=$((i/2))
ffmpeg -y -v error $args -filter_complex "$(for j in $(seq 0 $((h-1))); do printf "[$j]"; done)hstack=$h[a];$(for j in $(seq $h $((i-1))); do printf "[$j]"; done)hstack=$((i-h))[b];[a][b]vstack" $out
