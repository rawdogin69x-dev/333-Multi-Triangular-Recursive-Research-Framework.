# Assumptions (defaults until the owner overrides them)

Each default is chosen so that it is safe and easy to reverse. Change any of them by editing this
file and the config it points to.

| # | Question | Default | Why this default | Where it lives |
| --- | --- | --- | --- | --- |
| A1 | First research charter | **Decided (D8):** the system's own epistemology | Phase 1 output feeds Phases 2–5 directly, and you can judge its quality yourself | `config/charters.example.yaml` |
| A2 | Cloud API budget | **$0: cloud disabled** until a cap is set | Nothing unattended can spend money by default | router config (Phase 3) |
| A3 | Subscriptions vs API keys | Unattended loop uses API keys only; subscription CLIs only in supervised sessions | Consumer plans are not meant for 24/7 automation and reset in rolling windows | Phase 3 |
| A4 | CPU | Assume **no AVX-512** | Holds for most Intel desktop chips; AMD Zen 4/5 is a bonus | embedder choice |
| A5 | Shared PC | Assume yes: the daemon yields the GPU on demand | Safer than assuming exclusive use | scheduler (Phase 3) |
| A6 | OS layout | WSL2 Ubuntu; DB on the WSL ext4 disk, never under `/mnt/c` | SQLite locking over the Windows mount is unreliable | `docs/SETUP.md` |
| A7 | Reading surface | Obsidian vault export first, web dashboard later | Free graph view, works offline | Phase 5 |
| A8 | Esoteric scope | **Decided (D4, D6):** ATTRIBUTED for teachings, PHENOMENOLOGICAL for experience reports; sources allowed from Phase 2 | Lets the gate be calibrated on ordinary claims first | `docs/ARCHITECTURE.md` |
| A9 | Topic for "mass" | First two taxonomy levels | Stable, unlike embedding clusters that shift as data grows | `gravity.topic_depth` |
| A10 | Lineage | Root domain for now; **D9** moves to origin-of-percept matching | Simple; weak for syndicated content (see SELF_CRITIQUE) | `store.root_domain` |
| A11 | Gravity constants | τ0 0.60, γ 0.03, k 2→4 | Cold start works; dense topics get stricter; recalibrate in Phase 2 | `config/akashic.example.yaml` |
| A12 | Privacy | This repo holds only framework code and docs. Data, configs, fixtures and the DB are git-ignored | The repo is public | `.gitignore` |
