#!/usr/bin/env bash
# Label Studio for the gold set, on a remote host, reached through ssh.
#   scripts/annotate.sh [-p PORT] USER@HOST up      start it (Docker, pinned image)
#   scripts/annotate.sh [-p PORT] USER@HOST tunnel  forward http://127.0.0.1:8090
#   scripts/annotate.sh [-p PORT] USER@HOST backup  copy its data to annotate/data/
#   scripts/annotate.sh [-p PORT] USER@HOST down    stop it; the data stays
# It listens on the host's 127.0.0.1 only, so nothing is exposed; sign up on
# the first visit through the tunnel. The data (SQLite and uploads) lives in
# ~/label-studio on the host: back it up before giving the host back.
set -euo pipefail

IMAGE=heartexlabs/label-studio:1.23.2@sha256:afcc516a22775a39d0d66f4c2ddc95d01be3e3d3862b21fcf4f9de34b4ad4e12
LOCAL_PORT=8090
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
port=22
while getopts p: opt; do
  case "$opt" in
    p) port="$OPTARG" ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [[ $# -ne 2 ]]; then
  echo "usage: $0 [-p PORT] USER@HOST up|tunnel|backup|down" >&2
  exit 2
fi
host="$1"

case "$2" in
  up)
    # The image runs as uid 1001.
    ssh -p "$port" "$host" "mkdir -p ~/label-studio && sudo chown 1001 ~/label-studio \
      && { sudo docker rm -f label-studio >/dev/null 2>&1 || true; } \
      && sudo docker run -d --name label-studio --restart unless-stopped \
        -p 127.0.0.1:${LOCAL_PORT}:8080 -v ~/label-studio:/label-studio/data \
        ${IMAGE} >/dev/null \
      && for i in \$(seq 60); do curl -fs http://127.0.0.1:${LOCAL_PORT}/health >/dev/null && break; sleep 3; done \
      && curl -fsS http://127.0.0.1:${LOCAL_PORT}/health && echo"
    echo "now: $0 -p ${port} ${host} tunnel, then open http://127.0.0.1:${LOCAL_PORT}"
    ;;
  tunnel)
    echo "http://127.0.0.1:${LOCAL_PORT} (Ctrl-C to close)"
    ssh -p "$port" -N -L "${LOCAL_PORT}:127.0.0.1:${LOCAL_PORT}" "$host"
    ;;
  backup)
    mkdir -p "${root}/annotate/data"
    rsync -az --rsync-path="sudo rsync" -e "ssh -p ${port}" "${host}:label-studio/" "${root}/annotate/data/"
    echo "copied to annotate/data/"
    ;;
  down)
    ssh -p "$port" "$host" "sudo docker stop label-studio >/dev/null && echo stopped"
    ;;
  *) echo "up, tunnel, backup or down" >&2; exit 2 ;;
esac
