#!/usr/bin/env bash
# Label Studio for the gold set, here or on a remote host reached through ssh.
#   scripts/annotate.sh local up|down              here, with Docker or Podman;
#                                                  the data is annotate/data/
#   scripts/annotate.sh local projects [BOOK] PACKET...
#                                                  a project per packet, e.g.
#                                                  place, or place-repeat
#   scripts/annotate.sh [-p PORT] USER@HOST up      start it (Docker, pinned image)
#   scripts/annotate.sh [-p PORT] USER@HOST tunnel  forward http://127.0.0.1:8090
#   scripts/annotate.sh [-p PORT] USER@HOST backup  copy its data to annotate/data/
#   scripts/annotate.sh [-p PORT] USER@HOST down    stop it; the data stays
# It listens on the host's 127.0.0.1 only, so nothing is exposed; sign up on
# the first visit through the tunnel. The data (SQLite and uploads) lives in
# ~/label-studio on the host: back it up before giving the host back. A
# backup lands in annotate/data/, where the local one reads it, so moving from
# a host to here is backup, down, then local up.
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
if [[ $# -lt 2 || ( $# -gt 2 && "$1" != local ) ]]; then
  echo "usage: $0 [-p PORT] USER@HOST up|tunnel|backup|down, or $0 local up|down|projects ..." >&2
  exit 2
fi
host="$1"

if [[ "$host" == local ]]; then
  data="${root}/annotate/data"
  if command -v docker >/dev/null; then
    engine=docker
    # The image runs as uid 1001; run it as you instead, so the files stay yours.
    owner=(--user "$(id -u):$(id -g)")
  elif command -v podman >/dev/null; then
    engine=podman
    # Rootless: your files appear as uid 1001, the image's user, inside.
    # and the shell's proxy settings stay out: it needs no network.
    owner=(--userns "keep-id:uid=1001,gid=1001" --http-proxy=false)
  else
    echo "needs docker or podman" >&2
    exit 1
  fi
  case "$2" in
    up)
      mkdir -p "$data"
      "$engine" rm -f label-studio >/dev/null 2>&1 || true
      "$engine" run -d --name label-studio "${owner[@]}" \
        -p "127.0.0.1:${LOCAL_PORT}:8080" -v "${data}:/label-studio/data:z" \
        "docker.io/${IMAGE}" >/dev/null
      for _ in $(seq 60); do
        curl -fs "http://127.0.0.1:${LOCAL_PORT}/health" >/dev/null && break
        sleep 3
      done
      curl -fsS "http://127.0.0.1:${LOCAL_PORT}/health" && echo
      echo "open http://127.0.0.1:${LOCAL_PORT}; stop with: $0 local down"
      ;;
    down)
      "$engine" stop label-studio >/dev/null && "$engine" rm label-studio >/dev/null && echo stopped
      ;;
    projects)
      # Usage here is: local projects [BOOK] PACKET...; the book defaults to
      # the only one in gold/.
      shift 2
      book="$(ls "${root}/gold" | head -1)"
      if [[ $# -gt 0 && -d "${root}/gold/$1" ]]; then book="$1"; shift; fi
      [[ $# -gt 0 ]] || { echo "which packets? e.g. place or place-repeat" >&2; exit 2; }
      tmp="$(mktemp -d)"
      cp "${root}"/annotate/configs/*.xml "${root}/annotate/projects.py" "$tmp/"
      for packet in "$@"; do
        cp "${root}/gold/${book}/packets/${packet}.json" "$tmp/"
      done
      "$engine" exec label-studio rm -rf /tmp/packets
      "$engine" cp "$tmp" label-studio:/tmp/packets
      rm -rf "$tmp"
      "$engine" exec label-studio python3 /tmp/packets/projects.py /tmp/packets "$@" 2>/dev/null \
        | grep -E "^[a-z-]+: |^expected"
      ;;
    *) echo "local takes up, down or projects" >&2; exit 2 ;;
  esac
  exit 0
fi

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
