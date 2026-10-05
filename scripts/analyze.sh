#!/usr/bin/env bash
# Runs the pipeline on the GPU host in a tmux session named bookgraph, so it
# survives a dropped ssh connection. Copy the repo there first with
# scripts/deploy.sh.
#   scripts/analyze.sh [-p PORT] [-j JOBS] USER@HOST books/FILE.fb2.zip [EXTRACT ARGS...]
#   scripts/analyze.sh -j 24 Ubuntu@154.54.100.124 books/slomannyj_mech-b302190.fb2.zip
#   scripts/analyze.sh Ubuntu@154.54.100.124 books/slomannyj_mech-b302190.fb2.zip -c 1-3
# parse, chunk and calibrate run when their output is missing; extract
# always runs and skips chunks it has already done. Then resolve, thread,
# summarize and render, unless extract got arguments (a partial run such as
# -c 1-3 stops after extract). JOBS is how many requests each model stage
# sends at once: 8 for llama-server on the a100 profile, 4 on a6000, 24 for
# vLLM. The log goes to ~/book-graph/work/BOOK/run.log on the host; watch
# with scripts/status.sh.
set -euo pipefail

port=22
jobs=8
while getopts p:j: opt; do
  case "$opt" in
    p) port="$OPTARG" ;;
    j) jobs="$OPTARG" ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [[ $# -lt 2 ]]; then
  echo "usage: $0 [-p PORT] [-j JOBS] USER@HOST books/FILE.fb2.zip [EXTRACT ARGS...]" >&2
  exit 2
fi
host="$1" file="$2"
shift 2
[[ "$jobs" =~ ^[0-9]+$ ]] || { echo "-j takes a number" >&2; exit 2; }
book="$(basename "$file")"
book="${book%.zip}"
book="${book%.fb2}"
book="$(sed -E 's/-b[0-9]+$//' <<<"$book")"

extra=""
for arg in "$@"; do
  extra+=" $(printf '%q' "$arg")"
done
bg=".venv/bin/python -m bookgraph"
w="work/${book}"
rest=""
if [[ $# -eq 0 ]]; then
  rest="${bg} resolve ${book} -j ${jobs} && ${bg} thread ${book} -j ${jobs} \
    && ${bg} summarize ${book} -j ${jobs} && ${bg} render ${book}"
fi
script="set -o pipefail; cd ~/book-graph && mkdir -p ${w} && {
  [[ -f ${w}/chapters.json ]] || ${bg} parse $(printf '%q' "$file")
  [[ -f ${w}/calibration.json ]] || { ${bg} chunk ${book} && ${bg} calibrate ${book}; }
  ${bg} stats ${book}
  ${bg} extract ${book} -j ${jobs}${extra} ${rest:+&& ${rest}}
} 2>&1 | tee -a ${w}/run.log; echo; echo 'finished, press Enter'; read"

ssh -p "$port" "$host" "tmux has-session -t bookgraph 2>/dev/null && { echo 'a bookgraph session is already running' >&2; exit 1; }
  tmux new-session -d -s bookgraph bash -c $(printf '%q' "$script") && echo 'started in tmux session bookgraph'"
