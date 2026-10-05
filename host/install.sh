#!/usr/bin/env bash
# Sets up llama-server with Qwen3.8-27B abliterated on a bare Ubuntu 24.04
# GPU host, as root. scripts/deploy.sh sends a profile (host/profiles/*.env)
# and then this file down one ssh stdin; it does not run alone.
#   CUDA build tools from NVIDIA's apt repo (nvcc, cuBLAS, CCCL), no driver
#   llama.cpp built from source in /opt/llama.cpp, llama-server only
#   the GGUF in /opt/models
#   systemd unit llama-server on 127.0.0.1:8080, waits until it answers
# Every step is skipped when its result is already there.
set -euo pipefail
: "${QUANT:?send a profile first}" "${CTX:?}" "${SLOTS:?}" "${CUDA_ARCH:?}"

SECONDS=0
CUDA=12-9
CUDA_DIR=/usr/local/cuda-12.9
REPO=https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF/resolve/main
MODEL=/opt/models/Huihui-Qwen3.8-27B-abliterated-${QUANT}.gguf
export DEBIAN_FRONTEND=noninteractive

step() { echo "== $* (${SECONDS}s)"; }

step "packages"
if [[ ! -x "${CUDA_DIR}/bin/nvcc" ]]; then
  if ! dpkg -s cuda-keyring >/dev/null 2>&1; then
    curl -fsSL -o /tmp/cuda-keyring.deb \
      https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
    dpkg -i /tmp/cuda-keyring.deb
  fi
  apt-get update -q
  apt-get install -y -q build-essential cmake git aria2 python3-venv tmux \
    "cuda-nvcc-${CUDA}" "cuda-cudart-dev-${CUDA}" "libcublas-dev-${CUDA}" "cuda-cccl-${CUDA}"
fi

step "llama.cpp"
if [[ ! -d /opt/llama.cpp/.git ]]; then
  git clone -q --depth 1 https://github.com/ggml-org/llama.cpp /opt/llama.cpp
fi
if [[ ! -x /opt/llama.cpp/build/bin/llama-server ]]; then
  cmake -S /opt/llama.cpp -B /opt/llama.cpp/build \
    -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON \
    -DCMAKE_CUDA_COMPILER="${CUDA_DIR}/bin/nvcc" \
    -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}" \
    -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF >/dev/null
  cmake --build /opt/llama.cpp/build --target llama-server -j "$(nproc)" 2>&1 | grep -E "error|warning: unused|Built target" || true
fi
/opt/llama.cpp/build/bin/llama-server --version 2>&1 | tail -2

step "model ${QUANT}"
mkdir -p /opt/models
if [[ ! -s "$MODEL" || -e "${MODEL}.aria2" ]]; then
  aria2c -q -x 16 -s 16 -c --file-allocation=none --summary-interval=0 \
    ${HF_TOKEN:+--header="Authorization: Bearer ${HF_TOKEN}"} \
    -d /opt/models -o "$(basename "$MODEL")" "${REPO}/$(basename "$MODEL")?download=true"
fi
ls -la "$MODEL"

step "llama-server unit"
# --jinja so the request's chat_template_kwargs (enable_thinking) reach
# Qwen's template; q8_0 KV cache halves its size at no visible cost.
cat >/etc/systemd/system/llama-server.service <<EOF
[Unit]
Description=llama-server ${QUANT} for book-graph
After=network.target

[Service]
ExecStart=/opt/llama.cpp/build/bin/llama-server -m ${MODEL} --alias qwen3.8-27b \\
  --host 127.0.0.1 --port 8080 -ngl 999 --flash-attn on \\
  -c ${CTX} --parallel ${SLOTS} --cache-type-k q8_0 --cache-type-v q8_0 \\
  --jinja --metrics --slots -b 2048 -ub 512
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable -q llama-server
systemctl restart llama-server

step "waiting for the model to load"
for _ in $(seq 120); do
  if curl -fs http://127.0.0.1:8080/health >/dev/null; then
    break
  fi
  if ! systemctl is-active -q llama-server; then
    journalctl -u llama-server -n 40 --no-pager
    exit 1
  fi
  sleep 5
done
curl -fsS http://127.0.0.1:8080/health
echo
journalctl -u llama-server --no-pager | grep -E "KV self size|kv_cache|n_ctx_seq|CUDA0 (model|KV|compute) buffer|model type|n_layer|general.architecture" | tail -12
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
step "done"
