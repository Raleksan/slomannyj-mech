#!/usr/bin/env bash
# The faster backend for big GPUs: vLLM serving the bf16 safetensors of the
# same model, as root. On an A100 llama.cpp tops out near 120 generated
# tokens/s however many requests run at once; vLLM batches them properly.
#   scripts/deploy.sh -b vllm USER@HOST a100
# Installs vLLM into /opt/vllm, fetches the model into /opt/models/hf with
# aria2c, and writes the vllm-server unit on 127.0.0.1:8080. It stops
# llama-server, which holds the same port and GPU memory, and starts vLLM;
# `systemctl start llama-server` after `systemctl stop vllm-server` goes back.
# Needs about 56 GB of GPU memory for the weights, so A100 80 GB only.
set -euo pipefail

SECONDS=0
HF=huihui-ai/Huihui-Qwen3.8-27B-abliterated
DIR=/opt/models/hf/Huihui-Qwen3.8-27B-abliterated
step() { echo "== $* (${SECONDS}s)"; }

step "vLLM"
if [[ ! -x /opt/vllm/bin/vllm ]]; then
  python3 -m venv /opt/vllm
  /opt/vllm/bin/pip install -q -U pip uv
  /opt/vllm/bin/uv pip install -q --python /opt/vllm/bin/python vllm
fi
/opt/vllm/bin/python -c "import vllm, torch; print('vllm', vllm.__version__, 'torch', torch.__version__)"

step "model ${HF} (bf16)"
mkdir -p "$DIR"
curl -fsSL "https://huggingface.co/api/models/${HF}" \
  | python3 -c "
import json, sys
for s in json.load(sys.stdin)['siblings']:
    name = s['rfilename']
    if name.endswith(('.md', '.gitattributes')) or name.startswith('.'):
        continue
    print(f'https://huggingface.co/${HF}/resolve/main/{name}?download=true')
    print(f'  out={name}')
" >/tmp/vllm-model.txt
aria2c -q -x 16 -s 16 -j 6 -c --file-allocation=none --summary-interval=0 \
  ${HF_TOKEN:+--header="Authorization: Bearer ${HF_TOKEN}"} \
  -d "$DIR" -i /tmp/vllm-model.txt
du -sh "$DIR"

step "vllm-server unit"
# Vision inputs off: the text model alone, without the vision encoder's memory.
cat >/etc/systemd/system/vllm-server.service <<EOF
[Unit]
Description=vLLM bf16 for book-graph
After=network.target
Conflicts=llama-server.service

[Service]
Environment=HF_HUB_OFFLINE=1
ExecStart=/opt/vllm/bin/vllm serve ${DIR} --served-model-name qwen3.8-27b \\
  --host 127.0.0.1 --port 8080 --dtype bfloat16 --max-model-len 32768 \\
  --max-num-seqs 32 --gpu-memory-utilization 0.92 \\
  --limit-mm-per-prompt '{"image":0,"video":0}' --reasoning-parser qwen3
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
if [[ "${START:-1}" == 1 ]]; then
  systemctl stop llama-server || true
  systemctl disable -q llama-server || true
  systemctl enable -q vllm-server
  systemctl restart vllm-server
  step "waiting for vLLM"
  for _ in $(seq 180); do
    curl -fs http://127.0.0.1:8080/health >/dev/null && break
    if ! systemctl is-active -q vllm-server; then
      journalctl -u vllm-server -n 60 --no-pager
      exit 1
    fi
    sleep 5
  done
  curl -fsS http://127.0.0.1:8080/v1/models | head -c 300
  echo
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv
fi
step "done"
