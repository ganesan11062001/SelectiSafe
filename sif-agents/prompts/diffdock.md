# DiffDock (docking_agent.py)

- Container: `../selectisafe/builds/diffdock-v1.0.sif`
- Source: https://github.com/gcorso/DiffDock — image built from Docker Hub
  `rbgcsail/diffdock` (the DiffDock authors' own MIT CSAIL lab image; confirmed
  from the container's embedded OCI labels, `org.label-schema...from: rbgcsail/diffdock`)
- Role in the pipeline: scores each generated ligand's pose against the target protein.
  Confirmed against the repo README (`README.md`, "Running inference" section):
  `python -m inference --config default_inference_args.yaml --protein_ligand_csv <csv> --out_dir <dir>`
  — same flags this pipeline uses, just via the container's own module path.

## Command this pipeline runs

```bash
apptainer exec --nv diffdock-v1.0.sif \
    /home/appuser/micromamba/envs/diffdock/bin/python /home/appuser/DiffDock/inference.py \
    --config /home/appuser/DiffDock/default_inference_args.yaml \
    --protein_ligand_csv <csv> --out_dir <out_dir>
```

Verified working on this cluster — copied from
`../selectisafe/scripts/run_diffdock_inference.sh`.

**Must be launched with cwd = `../selectisafe`** (see `config.DIFFDOCK_CHDIR`). DiffDock
caches its SO(3)/torus lookup tables relative to the working directory; those tables
(~400MB) already exist there, and launching elsewhere regenerates them from scratch.

**Input CSV must reference single-molecule ligand files.** A row's `ligand_description`
pointed at a multi-record SDF silently docks only the first molecule in it — this is why
`sdf_utils.write_per_molecule_files` splits FlowR's batch before this stage runs. CSV
columns: `complex_name,protein_path,ligand_description,protein_sequence`.

## Standalone smoke test

```bash
apptainer exec --nv ../selectisafe/builds/diffdock-v1.0.sif \
    /home/appuser/micromamba/envs/diffdock/bin/python /home/appuser/DiffDock/inference.py \
    --config /home/appuser/DiffDock/default_inference_args.yaml \
    --protein_ligand_csv ../selectisafe/data/bace_docking_input.csv \
    --out_dir /tmp/diffdock_smoke_test
```

Run from `../selectisafe` (or wherever the cached SO(3)/torus tables live), on a GPU node.
