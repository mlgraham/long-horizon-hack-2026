#!/usr/bin/env bash
# Mix the narration track into a screen recording of a paced demo run.
#   scripts/mix.sh recording.mov [narration.wav] [offset_seconds] [out.mov]
# offset = seconds between starting the recording and pressing Enter in the demo (about 1).
set -euo pipefail
VIDEO="$1"; AUDIO="${2:-demo/narration.wav}"; OFFSET="${3:-1}"; OUT="${4:-demo-narrated.mov}"
ffmpeg -y -loglevel error -i "$VIDEO" -itsoffset "$OFFSET" -i "$AUDIO" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 160k -shortest "$OUT"
echo "wrote $OUT"
