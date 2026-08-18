# AiZynthFinder (retrosynthesis_agent.py)

- Container: `../selectisafe/builds/aizynthfinder.sif`
- Source: https://github.com/MolecularAI/aizynthfinder — image built from Docker Hub
  `dhanus12/aizynthfinder:latest` (a third-party repackaging, not the official image;
  confirmed from the container's OCI labels)
- Role in the pipeline: for each generated molecule's SMILES, plans a retrosynthetic
  route back to purchasable starting materials and reports whether one was found.

This container took three real, distinct failures to get working — each one only
visible by actually submitting a job, not by reading source or `strings`. All three
fixes live in `retrosynthesis_agent._write_wrapper`'s generated shell script, run
inside the container in place of calling `aizynthcli` directly.

## Verified against the real source

Fetched `aizynthfinder/interfaces/aizynthcli.py` and `aizynthfinder/aizynthfinder.py`
directly from GitHub to confirm, rather than guessing from the README alone:

- `_get_arguments()` in `aizynthcli.py` confirms the flags: `--smiles` (required, a file
  or a single SMILES), `--config` (required), `--output` (JSON or HDF5 filename).
- Multi-SMILES output is written by `aizynthfinder/utils/files.py:save_datafile()` via
  `pandas.DataFrame.to_json(filename, orient="table")`. This is plain JSON
  (`{"schema": ..., "data": [...]}`) — gzip is inferred from the `.gz` suffix, not a
  separate format — so `retrosynthesis_agent.parse_results()` reads it with the stdlib
  `gzip`+`json` modules and no pandas dependency.
- Each row of `data` is one target's stats from `AiZynthFinder.extract_statistics()`:
  `target` (the input SMILES), `is_solved` (bool), plus tree-search statistics.

## Failure 1: `aizynthcli` not on the base PATH

`FATAL: "aizynthcli": executable file not found in $PATH` — the image's own PATH
(`/opt/conda/bin`) doesn't include it. Turned out to be installed in a conda env
named **`aizynthfinder`** (`/opt/conda/envs/aizynthfinder`) — not `aizynth-env`,
the name the upstream README's install instructions use as an example. The
wrapper doesn't hardcode either name: it searches every `/opt/conda/envs/*/bin`
for the binary at run time and prepends whichever one has it to `PATH`.

## Failure 2: NumPy/RDKit ABI mismatch inside the image

Once `aizynthcli` started, it crashed importing `rdkit`:
`AttributeError: _ARRAY_API not found` (and the same for `sklearn`) — `rdkit`
and `sklearn` in that conda env are compiled against NumPy 1.x's C-API, but
NumPy 2.2.6 is what's installed. A real, upstream packaging defect in this
third-party image (the official aizynthfinder pins numpy properly). The
error's own text names the fix: *"the easiest solution will be to downgrade
to 'numpy<2'"*.

Fix: the wrapper pip-installs a `numpy<2` build into
`config.AIZYNTHFINDER_NUMPY_FIX` (a directory under this project, persisted
across runs so this only happens once) using **that conda env's own `pip`**
(so the build's ABI matches its Python 3.10), then prepends that directory via
`PYTHONPATH` so it shadows the broken site-packages numpy without touching
the read-only `.sif`. Confirmed working: the pip install succeeded (needs
outbound network from the compute node, which this cluster provides), and a
subsequent run reused the already-installed fix directory instantly.

## Failure 3: config path guess was wrong

`AiZynthFinder(configfile=...)` raised `FileNotFoundError` for
`/opt/aizynthfinder/config.yml` — that guess (based on
`AIZYNTHFINDER_HOME=/opt/aizynthfinder` and the image bundling USPTO template
files, matching the layout `download_public_data` produces upstream) was
wrong. Same fix pattern as Failure 1: the wrapper searches
`/opt/aizynthfinder` for `config.yml`/`config.yaml` at run time instead of
assuming a path, and passes whatever it finds as `--config`. Not yet
confirmed this finds the right file — if this also fails, the error will name
the real problem (config not found at all, or found but pointing at
incomplete stock/policy data) and the search can be broadened from there
(`--maxdepth 3` currently, or beyond `/opt/aizynthfinder` into `/opt`/`/data`).

## Command this pipeline runs

```bash
apptainer exec aizynthfinder.sif bash <generated wrapper> \
    --smiles <smiles.smi file, one SMILES per line> \
    --output <out.json.gz>
```

where the wrapper (not a fixed command) does, in order: find `aizynthcli`,
fix numpy if not already fixed, find `config.yml`, then
`exec aizynthcli --config "$cfg" --smiles ... --output ...`.

## Standalone smoke test (manually reproducing what the wrapper does)

```bash
echo "CC(=O)Oc1ccccc1C(=O)O" > /tmp/aspirin.smi
apptainer exec ../selectisafe/builds/aizynthfinder.sif bash -c '
hit=$(find /opt/conda/envs -maxdepth 2 -type d -name bin 2>/dev/null | while read -r d; do [ -x "$d/aizynthcli" ] && echo "$d" && break; done)
[ -n "$hit" ] && export PATH="$hit:$PATH"
FIX_DIR=/tmp/aizynthfinder_numpy_fix
[ -d "$FIX_DIR/numpy" ] || { mkdir -p "$FIX_DIR"; "$(dirname "$(command -v aizynthcli)")/pip" install --quiet --target "$FIX_DIR" "numpy<2"; }
export PYTHONPATH="$FIX_DIR:${PYTHONPATH:-}"
cfg=$(find /opt/aizynthfinder -maxdepth 3 \( -iname "config.yml" -o -iname "config.yaml" \) 2>/dev/null | head -1)
aizynthcli --config "$cfg" --smiles /tmp/aspirin.smi --output /tmp/aizynth_smoke_test.json.gz
'
```

CPU-only — no `--nv` needed, run on the `CPU_PARTITION` from `config.py`.
