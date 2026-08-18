# SelectiSafe

An automated hit-generation pipeline for structure-based drug discovery,
built around five open-source models run as SLURM jobs on the Northeastern
Explorer HPC cluster, orchestrated by a small multi-agent Python system with
a Streamlit dashboard.

Given a target protein and a reference ligand (to define the binding
pocket), the pipeline:

1. **Generates** novel candidate ligands into the pocket ([FlowR](https://github.com/jule-c/flowr_root))
2. **Docks** each candidate against the target ([DiffDock](https://github.com/gcorso/DiffDock))
3. **Rescores** the best pose with a CNN-based binding estimate ([GNINA](https://github.com/gnina/gnina))
4. **Checks retrosynthetic accessibility** -- can it actually be made? ([AiZynthFinder](https://github.com/MolecularAI/aizynthfinder))
5. **Predicts ADMET properties** -- absorption, distribution, metabolism,
   excretion, toxicity ([ADMET-AI](https://github.com/swansonk14/admet_ai))

...then, optionally, asks a local LLM (via Ollama) to summarize the results,
grounded in facts computed directly from the pipeline's own output rather
than free-form generation.

The worked example throughout this repo is **EGFR bound to osimertinib**
(PDB [4ZAU](https://www.rcsb.org/structure/4ZAU)) -- see `selectisafe/4ZAU/`
and the caveats documented in its own generation/docking write-ups, which
this project treats as load-bearing: a docking method that fails its own
self-docking control on a given target is flagged as such, not silently
trusted.

## Repository layout

Two directories, mirroring their layout on the Explorer cluster
(`/scratch/g.murugan/Pfizer/`) so every `../selectisafe/...` reference in
`sif-agents`'s own docs and code resolves correctly here too:

- **[`sif-agents/`](sif-agents/)** -- the multi-agent pipeline itself:
  - `agents/` -- one Python module per model above, each wrapping exactly one
    Apptainer container and submitting its own `sbatch --wait` SLURM job
  - `run_pipeline.py` -- runs all five agents in sequence
  - `streamlit.py` + `pages/` -- the dashboard: launch/monitor runs, a
    **Results Gallery** (funnel chart, 2D/3D structure viewer), and a
    **Browse Files** page over the raw output
  - `llm/` -- the Ollama-backed analysis step (`report_agent.py`), grounded
    in deterministic facts computed by `report_signals.py`
  - `docs/architecture.md` -- component diagram and full run sequence
  - `prompts/` -- what's verified against each model's own upstream source
    vs. what's still an assumption, per model
  - Also packaged as an Open OnDemand Batch Connect app
    (`manifest.yml`, `form.yml`, `submit.yml.erb`, `template/`)

  Start with **[`sif-agents/README.md`](sif-agents/README.md)** for setup,
  cluster-specific configuration (Slurm account/partition, walltime), and the
  full list of real issues found and fixed by actually running each stage.

- **[`selectisafe/`](selectisafe/)** -- the source scripts, docs, and
  target-prep code this pipeline builds on:
  - `scripts/` -- the original SLURM job scripts for FlowR and DiffDock
  - `docs/`
  - `4ZAU/` -- EGFR/osimertinib target preparation (protein/ligand prep,
    pocket definition)

## Quick start

```bash
cd sif-agents
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run streamlit.py
```

See `sif-agents/README.md` for running it as an Open OnDemand app instead of
locally, and for the Slurm account/partition/walltime settings you'll likely
need to adjust for your own cluster account.

## Not included

See `.gitignore`:

- The `.sif` container images and model checkpoints these scripts run
  against -- multi-GB binaries that live on scratch, not in version control.
- `sif-agents/.venv/` and `.aizynthfinder_numpy_fix/` -- rebuildable from
  `sif-agents/requirements.txt` (the latter is a runtime NumPy-downgrade
  workaround for a broken dependency inside the third-party AiZynthFinder
  container image; see `sif-agents/prompts/aizynthfinder.md`).
- `sif-agents/runs/` -- generated run output, not source.
