# GNINA (gnina_agent.py)

- Container: `../selectisafe/builds/gnina.sif`
- Source: https://github.com/gnina/gnina — image built from Docker Hub
  `gnina/gnina:latest` (confirmed from the container's OCI labels,
  `deffile.from: gnina/gnina:latest`, CUDA 12.6)
- Role in the pipeline: rescores DiffDock's best pose per molecule with GNINA's
  CNN-based scoring function, giving a second, independent binding estimate
  (CNNscore/CNNaffinity/minimizedAffinity) alongside DiffDock's own confidence.

## Verified against the real source

Fetched `README.md` directly from the repo. Confirmed:

- The binary is a single executable, `gnina`, no config file required — flags are
  passed directly on the command line (unlike aizynthfinder).
- Its primary documented usage is full blind docking with an explicit box:
  `gnina -r rec.pdb -l lig.sdf --autobox_ligand orig.sdf -o docked.sdf.gz`
- It also documents a second mode for *already-positioned* ligands — no search,
  just minimize and score: `gnina -r rec.pdb -l ligs.sdf --minimize -o minimized.sdf.gz`.
  This pipeline uses that mode on DiffDock's poses, rather than running a second
  independent blind-docking search that would duplicate DiffDock's job.
- `--pose_sort_order` documents exactly three score names — `CNNscore`, `CNNaffinity`,
  `Energy` — which, combined with the well-known `minimizedAffinity` empirical score
  tag, is what `gnina_agent._read_first_record_tags` looks for in the output SDF.
- `--autobox_ligand`'s help text notes "a multi-ligand file still only defines a single
  box" — i.e. `-l` accepts multi-molecule SDFs directly for full docking, unlike
  DiffDock, which silently keeps only the first record of a multi-molecule ligand file.
  Not used here since this pipeline runs one call per complex_name for output-identity
  reasons (see the module docstring), but worth knowing if you use gnina standalone.

## What is still unconfirmed

The exact SD tag names in the output file were not observed directly (no apptainer
here to run it) — they're taken from the `--pose_sort_order` help text and general
gnina convention, not printed verbatim in the README's usage examples. Run the smoke
test below and inspect the output file if `cnn_score`/`cnn_affinity` come back `None`.

## Command this pipeline runs (per complex, looped in one job)

```bash
apptainer exec --nv gnina.sif gnina \
    -r <protein.pdb> -l <docked_pose.sdf> --minimize \
    --cnn_scoring rescore -o <out_dir>/<complex_name>.sdf.gz
```

## Standalone smoke test

```bash
apptainer exec --nv ../selectisafe/builds/gnina.sif gnina \
    -r ../selectisafe/4ZAU/4ZAU_protein.pdb \
    -l ../selectisafe/4ZAU/4ZAU_ligand.sdf \
    --autobox_ligand ../selectisafe/4ZAU/4ZAU_ligand.sdf \
    -o /tmp/gnina_smoke_test.sdf.gz
zcat /tmp/gnina_smoke_test.sdf.gz | head -60   # check the SD tag names directly
```

Needs a GPU node (`--nv`) for CNN scoring — run inside an `sbatch`/`srun` job on the
`gpu` partition. `--no_gpu` exists if you ever need a CPU-only fallback.
