#!/usr/bin/env bash
# Sets up a GPU host for book-graph and copies the repo there.
#   scripts/deploy.sh [-p PORT] [-b llama|vllm] USER@HOST PROFILE
#   scripts/deploy.sh Ubuntu@HOST a6000
#   scripts/deploy.sh -b vllm Ubuntu@HOST a100
# With the llama backend (the default) runs host/install.sh as root with
# host/profiles/PROFILE.env; with vllm, host/vllm.sh instead (A100 80 GB
# only; run the pipeline with -j 24). Then it rsyncs this repo (with books/,
# without work/ and .venv) to ~/book-graph and makes a venv there, so the
# pipeline can run on the host inside tmux. HF_TOKEN, or .hf-token at the
# repo root, goes down the same ssh stdin when present.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
port=22
backend=llama
while getopts p:b: opt; do
  case "$opt" in
    p) port="$OPTARG" ;;
    b) backend="$OPTARG" ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [[ $# -ne 2 || ! -f "${root}/host/profiles/$2.env" ]]; then
  echo "usage: $0 [-p PORT] [-b llama|vllm] USER@HOST PROFILE   (profiles: $(cd "${root}/host/profiles" && ls | sed 's/\.env$//' | xargs))" >&2
  exit 2
fi
host="$1" profile="$2"
case "$backend" in
  llama) scripts=("${root}/host/profiles/${profile}.env" "${root}/host/install.sh") ;;
  vllm) scripts=("${root}/host/vllm.sh") ;;
  *) echo "backend is llama or vllm" >&2; exit 2 ;;
esac

token="${HF_TOKEN:-}"
if [[ -z "$token" && -f "${root}/.hf-token" ]]; then
  token="$(<"${root}/.hf-token")"
fi

rsync -az -e "ssh -p ${port}" --delete --exclude /.venv --exclude /work --exclude /out \
  --exclude __pycache__ --exclude '*.egg-info' "${root}/" "${host}:book-graph/"

{
  [[ -n "$token" ]] && printf 'HF_TOKEN=%q\n' "${token//[[:space:]]/}"
  cat "${scripts[@]}"
} | ssh -p "$port" "$host" "sudo bash -s"

ssh -p "$port" "$host" 'cd book-graph && { [[ -d .venv ]] || python3 -m venv .venv; } \
  && .venv/bin/pip install -q -e ".[llm]" && echo "venv ready: ~/book-graph/.venv"'
