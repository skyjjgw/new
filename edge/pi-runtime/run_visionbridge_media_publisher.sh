#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${VISIONBRIDGE_MEDIA_ENV_FILE:-/etc/visionbridge/media-publisher.env}"
if [[ ! -r "$ENV_FILE" ]]; then
  echo "missing media publisher environment: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${VISIONBRIDGE_DEVICE_ID:?VISIONBRIDGE_DEVICE_ID is required}"
: "${VISIONBRIDGE_MEDIA_PUBLISH_SECRET:?VISIONBRIDGE_MEDIA_PUBLISH_SECRET is required}"

SAFE_DEVICE_ID="$(printf '%s' "$VISIONBRIDGE_DEVICE_ID" | sed -E 's/[^a-zA-Z0-9_-]+/-/g; s/^-+|-+$//g')"
if [[ -z "$SAFE_DEVICE_ID" ]]; then
  echo "invalid device id" >&2
  exit 1
fi

INPUT_URL="${VISIONBRIDGE_PREVIEW_URL:-http://127.0.0.1:8090/stream.raw}"
INPUT_FORMAT="${VISIONBRIDGE_MEDIA_INPUT_FORMAT:-rawvideo}"
RTSP_HOST="${VISIONBRIDGE_MEDIA_RTSP_HOST:-127.0.0.1}"
RTSP_PORT="${VISIONBRIDGE_MEDIA_RTSP_PORT:-18554}"
FPS="${VISIONBRIDGE_MEDIA_FPS:-15}"
WIDTH="${VISIONBRIDGE_MEDIA_WIDTH:-320}"
HEIGHT="${VISIONBRIDGE_MEDIA_HEIGHT:-240}"
BITRATE="${VISIONBRIDGE_MEDIA_BITRATE:-450k}"

ENCODER="${VISIONBRIDGE_MEDIA_ENCODER:-libx264}"

OUTPUT_URL="rtsp://${VISIONBRIDGE_DEVICE_ID}:${VISIONBRIDGE_MEDIA_PUBLISH_SECRET}@${RTSP_HOST}:${RTSP_PORT}/devices/${SAFE_DEVICE_ID}"

if [[ "$INPUT_FORMAT" == "rawvideo" ]]; then
  INPUT_ARGS=(
    -fflags nobuffer+discardcorrupt -flags low_delay -use_wallclock_as_timestamps 1
    -f rawvideo -pixel_format bgr24 -video_size "${WIDTH}x${HEIGHT}" -framerate "$FPS" -i "$INPUT_URL"
  )
  VIDEO_FILTER="format=yuv420p"
else
  INPUT_ARGS=(
    -fflags nobuffer+discardcorrupt -flags low_delay -analyzeduration 0 -probesize 64k -use_wallclock_as_timestamps 1
    -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2 -f mpjpeg -i "$INPUT_URL"
  )
  VIDEO_FILTER="fps=${FPS},scale=${WIDTH}:${HEIGHT}:flags=fast_bilinear,format=yuv420p"
fi

if [[ "$ENCODER" == "h264_v4l2m2m" ]]; then
  # bcm2835-codec on the legacy Raspberry Pi kernel returns encoded packets
  # without PTS. Encode to Annex-B first, then remux at an explicit input rate
  # so RTSP/WebRTC cannot accumulate a 30-fps-vs-15-fps timestamp drift.
  ffmpeg -hide_banner -loglevel warning -nostdin \
    "${INPUT_ARGS[@]}" -an -vf "$VIDEO_FILTER" \
    -c:v h264_v4l2m2m -b:v "$BITRATE" -bf 0 \
    -force_key_frames "expr:gte(t,n_forced*1)" \
    -flush_packets 1 -f h264 pipe:1 | \
  ffmpeg -hide_banner -loglevel warning -nostdin \
    -fflags genpts+nobuffer -flags low_delay -use_wallclock_as_timestamps 1 -r "$FPS" -f h264 -i pipe:0 \
    -an -c:v copy -rtsp_transport tcp -muxdelay 0 -muxpreload 0 -flush_packets 1 -f rtsp "$OUTPUT_URL"
  exit ${PIPESTATUS[1]}
fi

exec ffmpeg -hide_banner -loglevel warning -nostdin \
  "${INPUT_ARGS[@]}" -an -vf "$VIDEO_FILTER" \
  -r "$FPS" -vsync cfr \
  -c:v libx264 -preset ultrafast -tune zerolatency -profile:v baseline -level 3.0 \
  -b:v "$BITRATE" -maxrate "$BITRATE" -bufsize "$BITRATE" -g "$FPS" -keyint_min "$FPS" -bf 0 \
  -rtsp_transport tcp -muxdelay 0 -muxpreload 0 -flush_packets 1 -f rtsp "$OUTPUT_URL"
