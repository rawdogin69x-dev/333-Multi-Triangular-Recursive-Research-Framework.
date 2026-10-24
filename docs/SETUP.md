# Setup (Windows + WSL2, NVIDIA GPU)

1. **WSL2 Ubuntu.** In an admin PowerShell: `wsl --install -d Ubuntu-24.04`, reboot, create your Linux user.
   Keep the project and `data/` inside the Linux home (e.g. `~/akashic`), **not** under `/mnt/c`.
2. **GPU in WSL.** Install the current NVIDIA Windows driver only (no Linux driver inside WSL).
   Check with `nvidia-smi` inside Ubuntu.
3. **Build tools.** `sudo apt install -y build-essential cmake git` and the CUDA toolkit for WSL from NVIDIA's site.
4. **llama.cpp with CUDA.**
   ```bash
   git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
   cmake -B build -DGGML_CUDA=ON && cmake --build build -j --config Release
   ```
   Example day-model server (14B, fully on a 12 GB card, 16K context, q8 KV cache):
   ```bash
   ./build/bin/llama-server -m models/<model>-Q4_K_M.gguf -ngl 99 -c 16384 -fa on \
     -ctk q8_0 -ctv q8_0 --host 127.0.0.1 --port 8080
   ```
   MoE with experts kept in system RAM (flag names change between releases; check `--help`):
   ```bash
   ./build/bin/llama-server -m models/<moe>-Q4_K_M.gguf -ngl 99 --n-cpu-moe 99 -c 16384 -fa on --port 8081
   ```
5. **Python.** `curl -LsSf https://astral.sh/uv/install.sh | sh`, then in the repo:
   ```bash
   uv venv && uv pip install -e ".[dev]"
   .venv/bin/pytest -q
   cp config/akashic.example.yaml config/akashic.yaml
   cp config/charters.example.yaml config/charters.yaml
   .venv/bin/akashic init
   .venv/bin/akashic charters --load config/charters.yaml
   ```
6. **Benchmark.** Put 20–30 `.txt` pages in `bench/fixtures/`, start a model server, then
   `.venv/bin/python bench/bench_models.py --model <name>`. Repeat per candidate model and compare
   `quote_anchor_rate`, `json_valid_rate` and `median_tok_per_s`.
