# SelectiSafe

Two directories, mirroring their layout on the Explorer cluster
(`/scratch/g.murugan/Pfizer/`) so every `../selectisafe/...` reference in
`sif-agents`'s own docs and code resolves correctly here too:

- **`sif-agents/`** -- the multi-agent drug-discovery pipeline: one agent per
  container (FlowR, DiffDock, GNINA, AiZynthFinder, ADMET-AI), a Streamlit
  dashboard with a Results Gallery and file browser, and an Ollama-backed
  analysis step. Start with `sif-agents/README.md`.
- **`selectisafe/`** -- the source scripts, docs, and target-prep code this
  pipeline builds on: `scripts/` (the original SLURM job scripts for FlowR/
  DiffDock), `docs/`, and `4ZAU/` (EGFR/osimertinib target preparation).

Not included (see `.gitignore`): the `.sif` container images and model
checkpoints these scripts run against (multi-GB binaries that live on
scratch, not in version control), `sif-agents/.venv/` and
`.aizynthfinder_numpy_fix/` (rebuildable from `sif-agents/requirements.txt`),
and `sif-agents/runs/` (generated run output, not source).
