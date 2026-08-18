# sif-agents

Standalone multi-agent pipeline: one agent per container in
`../selectisafe/builds/`. No Celery/Redis/FastAPI — each agent submits one
SLURM job via `apptainer exec` and blocks on `sbatch --wait`, so the whole
pipeline is a single sequential Python script.

| Agent | Container | Job type | Source repo |
|---|---|---|---|
| `agents/generation_agent.py` | `flowr-v1.0.sif` | GPU | [jule-c/flowr_root](https://github.com/jule-c/flowr_root) |
| `agents/docking_agent.py` | `diffdock-v1.0.sif` | GPU | [gcorso/DiffDock](https://github.com/gcorso/DiffDock) |
| `agents/gnina_agent.py` | `gnina.sif` | GPU | [gnina/gnina](https://github.com/gnina/gnina) |
| `agents/retrosynthesis_agent.py` | `aizynthfinder.sif` | CPU | [MolecularAI/aizynthfinder](https://github.com/MolecularAI/aizynthfinder) |
| `agents/admet_agent.py` | `admet-ai.sif` | CPU | [swansonk14/admet_ai](https://github.com/swansonk14/admet_ai) |

Each agent's command was checked against its upstream repo, not just guessed from the
container — see `prompts/<tool>.md` for what was verified, what's still open, and a
standalone smoke-test command for that container alone. Short version:

- **FlowR, DiffDock**: commands copied from scripts that already run successfully on
  this cluster (`../selectisafe/scripts/submit_flowr_inference.sh`,
  `run_diffdock_inference.sh`); repo READMEs cross-checked and consistent.
- **GNINA**: rescores DiffDock's best pose per molecule (`--minimize`, a documented
  mode for scoring poses already placed in a binding site) rather than running a
  second independent blind-docking search. Score tag names (`CNNscore`/`CNNaffinity`/
  `minimizedAffinity`) are inferred from `--pose_sort_order`'s help text, not observed
  directly in an actual output file — see `prompts/gnina.md`.
- **AiZynthFinder**: `--smiles`/`--config`/`--output` and the output file's JSON
  structure are confirmed by reading `aizynthcli.py` and `aizynthfinder.py` directly
  from the repo. The one open item is the exact `config.yml` path inside this specific
  image — see `prompts/aizynthfinder.md`.
- **ADMET-AI**: `--data_path`/`--smiles_column`/`--save_path` is the exact example
  command from the repo's README. The one open item is whether the output CSV
  preserves the `complex_name` column — see `prompts/admet_ai.md`.

`agents/chem_utils.py` is a small helper, not a 5th agent — it reuses
admet-ai.sif's bundled RDKit to convert FlowR's 3D SDF output into SMILES,
since FlowR tags molecules with predicted affinity (pic50/pki/...) but never
writes a SMILES string, and both aizynthfinder and admet-ai need one.

## Before the first real run

- `config.CPU_PARTITION` is set to `"short"` as a placeholder — confirm the real
  partition name with `sinfo` and update `config.py`.
- **Slurm account/partition is generic by default, not tied to one person's
  allocation.** The original `../selectisafe` scripts hardcoded
  `--account=a.barabasi` and `--partition=gpu`, which fails outright
  (`Invalid account or account/partition combination specified`) for anyone
  not on that account. `config.py` now defaults to **no `--account`** (Slurm
  falls back to the submitting user's own default association) and
  `--partition=gpu-interactive` with an unqualified `--gres=gpu:N` — the
  partition used for real GPU work by multiple general-access OOD apps on
  this cluster (`tensorboard`, `rstudio`). Override with
  `SIF_AGENTS_SLURM_ACCOUNT`, `SIF_AGENTS_GPU_PARTITION`, `SIF_AGENTS_GPU_TYPE`
  (e.g. `a100`), or `SIF_AGENTS_CPU_PARTITION` if you *do* have access to a
  faster/dedicated allocation.
- **Walltime requests are deliberately conservative and centralized.**
  `config.GPU_WALLTIME` (default `01:00:00`) and `config.CPU_WALLTIME`
  (default `00:30:00`) are used by every agent instead of each hardcoding its
  own request. This isn't a measured safe value — it's a guess picked after
  two real submissions were rejected with `Requested time limit is invalid`
  at 4-4.5h on both `gpu` and `gpu-interactive`, and this environment has no
  `sinfo`/`sacctmgr` access to look up the real per-partition `MaxTime`. If a
  stage instead gets **killed for running out of time** (a different, clearer
  failure than the submission-time rejection above — check that stage's
  `.err` file), raise `SIF_AGENTS_GPU_WALLTIME`/`SIF_AGENTS_CPU_WALLTIME`
  rather than guessing a new fixed value into the code.
- **Every `apptainer exec` now binds `/scratch` and `/projects` explicitly**
  (`config.APPTAINER_BIND`). The original selectisafe scripts passed no `-B` at
  all and relied on the node's default `apptainer.conf` bind paths -- that held
  on the `gpu` partition, but a real run on `gpu-interactive` got
  `FileNotFoundError` for `.../data/models/flowr_root_v2.2.ckpt` *inside the
  container* despite the file existing at that exact path on the host,
  consistent with `gpu-interactive` nodes having a more restrictive default.
  **Deliberately not `/home`**: a first attempt at this fix also bound
  `/home:/home` and broke DiffDock a different way -- `diffdock-v1.0.sif`
  bakes its own `HOME=/home/appuser` with DiffDock's Python interpreter at
  `/home/appuser/micromamba/...` (confirmed from the image's own OCI labels),
  so binding the host's `/home` over it hid the image's `/home/appuser`
  entirely (`FATAL: stat .../bin/python: no such file or directory`).
  Override with `SIF_AGENTS_APPTAINER_BIND` if your paths differ.

Everything else needed to run has been checked against the tools' own source
(see `prompts/`).

## Run

```
cd /scratch/g.murugan/Pfizer/sif-agents
python run_pipeline.py \
    --pdb ../selectisafe/4ZAU/4ZAU_protein.pdb \
    --ligand ../selectisafe/4ZAU/4ZAU_ligand.sdf \
    --run-id 4zau_test \
    --n-molecules 10
```

Output lands in `runs/<run-id>/`:
- `generation/samples_<pdb stem>.sdf` — FlowR's raw batch
- `ligands/*.sdf` — one molecule per file (also DiffDock's ligand input)
- `docking/<complex_name>/rank1_confidence*.sdf` — DiffDock poses
- `gnina/<complex_name>.sdf.gz` — GNINA's rescored/minimized best pose
- `smiles.csv` — `complex_name,smiles`
- `retro_output.json.gz` — AiZynthFinder routes
- `admet_predictions.csv` — ADMET-AI properties
- `final_report.json` — everything joined by `complex_name`

Each stage's sbatch script and log live under `runs/<run-id>/jobs/` and
`runs/<run-id>/logs/`; a failed stage names its own log file when it raises.

## Reference

`prompts/{flowr,diffdock,gnina,aizynthfinder,admet_ai}.md` — one file per model: what's
verified against the upstream repo, what's still open, and a copy-pasteable
standalone command to smoke-test that one container by itself before trusting
it inside the full pipeline.

## Dashboard (Streamlit) + Ollama analysis

`streamlit.py` is a dashboard on top of the pipeline: launch a run, watch its log,
browse `final_report.json`, and ask a local Ollama model to summarize it. Structured
the same way as **`../auxilium-analyze`**, whose "Analyze with Auxilium" feature this
directly borrows the design of:

- **Fact pipeline, not a chatbot.** `llm/report_signals.py` computes grounded facts
  from `final_report.json` first (best docking confidence, unsolved retrosynthesis
  routes, missing data) — mirrors `auxilium-analyze/analyze/signals.py`. The model
  (`llm/report_agent.py`) explains and ranks against those facts; it doesn't discover
  them, and the prompt says not to contradict them.
- **Same Ollama runtime.** `llm/ollama_client.py` reuses the shared
  `/projects/rc/projects/Auxilium` install (native binary preferred, apptainer
  fallback), the same proxy bypass (Ollama's on localhost; compute nodes inject an
  HTTP proxy), and the same `/api/tags` readiness poll instead of a blind sleep.
  Default model is `mistral` (the one already pulled there); override with `OLLAMA_MODEL`.
  Deliberate difference: Ollama starts **lazily**, on first "Analyze with Ollama"
  click, not upfront in `template/script.sh.erb` — auxilium-analyze's job exists only
  to analyze, so it always needs Ollama immediately; this is a long-lived dashboard
  where analysis is one optional action among several.
- **Every analysis writes a trace.** `runs/<run_id>/llm_runs/<UTC>-<pid>/{trace.json,
  prompt.json, response.txt, feedback.json}` — same per-run, never-overwritten layout
  and the same reason: without the exact prompt, a bad answer can't be attributed to a
  bad model vs. a bad prompt vs. a fact `report_signals.py` missed. The dashboard's
  👍/👎 buttons write `feedback.json` next to the run they judge.
- **Files are the message bus.** `launch_run()` starts the pipeline as a detached
  background process (`start_new_session=True`) and writes `status.txt`/`pipeline.pid`;
  the dashboard only ever learns a run's state by reading those files back, so it
  survives a page reload — same reasoning as `auxilium-analyze/docs/architecture.md` §2
  ("Scratch is the message bus").

**A real bug found and fixed while building this:** the file is named `streamlit.py`
(as asked), which is exactly the name of the `streamlit` package itself — the moment
its own directory lands on `sys.path` (which Streamlit's launcher does, to support
local imports), `import streamlit as st` would resolve to *this file* instead of the
installed package, confirmed by actually reproducing it (see git history / ask if you
want the repro). Fixed at the top of `streamlit.py` by stripping the script's own
directory from `sys.path` before importing `streamlit`, then restoring it afterward
for this project's own `llm.*` imports. Verified end-to-end: both a bare `python
streamlit.py` and an actual `streamlit run streamlit.py` correctly load the installed
package and execute the app's UI logic.

### Navigation

`streamlit.py` is now a thin router: it defines the nav menu with
`st.navigation`/`st.Page` and hands off to whichever page is selected --
**"Run Pipeline"** (`pages/run_pipeline.py`, the launch/monitor/Ollama-analysis
dashboard, formerly the whole of `streamlit.py`), **"Results Gallery"**
(`pages/results_gallery.py`, curated/parsed view), and **"Browse Files"**
(`pages/browse_files.py`, the raw files on disk).

This was originally built the other way -- letting Streamlit auto-discover
`pages/` as a second page -- but that auto-discovery re-scans the directory
via a filesystem watcher, and a page added to an already-running session
never showed up: `/scratch` is a network filesystem, and Streamlit's watcher
relies on OS-level file-change events that don't reliably fire there. Calling
`st.navigation` explicitly reads the page list fresh on every script run
instead of depending on watch events at all, and doesn't have this failure
mode. (A real, if less serious, consequence either way: **a code change to
this app requires ending and relaunching the OOD session**, not just editing
files -- the running `streamlit run` process doesn't restart itself.)

### Results Gallery page

`pages/results_gallery.py` -- the second item in the nav menu above. Two data
sources, picked at the top of the page:

- **This project's own pipeline runs** (`runs/<run_id>/final_report.json`) --
  full docking/GNINA/retrosynthesis/ADMET data.
- **A reference example**: a colleague's real, fully-documented FlowR/DiffDock
  run on EGFR (PDB 4ZAU, osimertinib) in `../selectisafe/Nithish/`, with an
  actual two-tier filtering funnel (pIC50 then docking confidence) already
  worked out in its own `filtering_report.txt`. Retrosynthesis/ADMET were
  never run for it, so the page shows those as `—` rather than inventing
  them, and its own docking README's caveat (self-docking control failed,
  3.36 Å RMSD -- likely because osimertinib binds covalently and DiffDock
  can't model that) is surfaced directly in the page, not buried.

Shows: a funnel chart (pIC50 tier -> docking tier -> combined pass, adjustable
thresholds, status colors from the project's dataviz reference palette --
`#0ca30c` good / `#d03b3b` critical, never used for anything but pass/fail
state), a sortable/filterable molecule gallery with **2D structure images**
(RDKit, straight from SMILES), and an on-demand **3D pose viewer** (py3Dmol,
rendered from a real docked-pose SDF when one exists, the plain generated 3D
structure otherwise -- one at a time, not all 50 at once, since embedding
that many py3Dmol viewers eagerly is what actually got slow when tried).

### Browse Files page

`pages/browse_files.py` -- the third nav item. Results Gallery shows a
*derived* view (parsed CSVs, computed pass/fail); this page is the plain file
tree underneath it, for looking at exactly what's on disk. Pick a root (any
completed pipeline run, or the `Nithish` reference example), filter by
filename, pick a file, and get a type-appropriate preview: `.md` rendered as
markdown, `.csv` as a table, `.json`/`.json.gz` pretty-printed, `.sdf`/`.mol`
as both a 2D depiction (RDKit, 2D coordinates freshly computed -- an SDF's own
coordinates are 3D, so drawing them directly projects flat and wrong) and a 3D
py3Dmol view, `.pdb` as a 3D cartoon (confirmed working on the reference
example's own 4ZAU target protein, not just small-molecule SDFs), plain text
types as a code block. Deliberately not a free-text arbitrary-path field --
scoped to the roots people actually asked to browse.

`rdkit` and `py3Dmol` were added to `requirements.txt` and installed directly
into the existing pre-built `.venv` (not left to the first-launch install path
-- see the walltime section above for why that path is deliberately avoided).

### Running it

**Locally / manually** (any node with `apptainer` + `sbatch`, e.g. for testing the UI):

```bash
cd /scratch/g.murugan/Pfizer/sif-agents
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run streamlit.py
```

**As an Open OnDemand Batch Connect app** (mirrors `../auxilium-analyze`'s "this repo
*is* the deployed app" convention — no separate deploy step):

```bash
ln -s /scratch/g.murugan/Pfizer/sif-agents ~/ondemand/dev/sif-agents
```

Then launch it from **`/pun/sys/dashboard/batch_connect/sessions`** → *SIF Agents
Pipeline* under *App Development*. `manifest.yml`/`form.yml`/`submit.yml.erb`/
`template/` follow the "basic" Batch Connect template contract used by the real
apps in `explorer-ood-apps` (`find_port`, `wait_until_port_used`, `set_host`,
`/rnode/<host>/<port>/`) — read directly, not guessed from generic OOD docs.

**Two real bugs found by actually launching it, both fixed:**

1. **First launch timed out.** `script.sh.erb` built `.venv` and ran
   `pip install -r requirements.txt` *inside* the 60-second window
   `template/after.sh` waits for the port to open — installing Streamlit's
   dependency tree takes ~95s (timed it), so `after.sh` always killed the job
   first. Fixed by pre-building `.venv` once, out-of-band, with the same
   Python the compute node uses (`/shared/EL9/explorer/python/3.13.5`, matching
   `module load python/3.13.5`) — exactly the principle `auxilium-analyze`
   already follows with its own pre-built shared venv. `script.sh.erb`'s
   `if [ ! -x .venv/bin/streamlit ]` guard now finds it and skips straight to
   launching; verified end-to-end (`Uvicorn server started`, reachable on its
   network URL). If `requirements.txt` ever changes, rebuild `.venv` the same
   way ahead of time — don't rely on the guard's install path being fast enough.
2. **"Method Not Allowed" on clicking Connect.** `view.html.erb` originally
   copied `tensorboard`'s form, which POSTs to `/rnode/<host>/<port>/`.
   Cross-checking against **`rstudio`** and **`vscode`**'s `view.html.erb` (both
   `method="get"`) showed tensorboard's POST was the outlier — Streamlit's
   Tornado server, like RStudio and VS Code, has no endpoint that accepts POST
   at its root, and returns exactly `405: Method Not Allowed`. (`jupyterlab`
   also uses POST, but only because it targets Jupyter's own `/login` route,
   which genuinely handles POST — not the app root.) Fixed by switching to
   `method="get"`, matching RStudio/VS Code; no password/cookie needed since
   Streamlit has no OOD-specific auth to satisfy. This takes effect on the next
   card refresh — no need to end and relaunch the running session.

**Still not independently verified**, because this sandbox has no OOD web node and no
browser: the actual page rendering and websocket behavior once inside `/rnode/...`.
Keep `template/before.sh.erb`, `template/script.sh.erb`, and `template/after.sh`
executable — OOD copies the file mode when it stages the job (the same gotcha
`auxilium-analyze`'s README calls out).
