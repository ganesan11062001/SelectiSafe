# FlowR (generation_agent.py)

- Container: `../selectisafe/builds/flowr-v1.0.sif`
- Source: https://github.com/jule-c/flowr_root (packaged per `../selectisafe/builds/flowr.def`)
- Role in the pipeline: samples novel ligands into a target's binding pocket, conditioned
  on a reference protein + ligand. Output is a multi-molecule 3D SDF, one record per
  sampled molecule, tagged with predicted affinities (`pic50`/`pki`/`pkd`/`pec50`) but
  **no SMILES string** — `chem_utils.py` derives SMILES from the 3D coordinates downstream.

## Command this pipeline runs

```bash
apptainer exec --nv --env PYTHONPATH=/opt/flowr_root flowr-v1.0.sif \
    python -m flowr.gen.generate_from_pdb \
    --pdb_file <protein.pdb> --ligand_file <ref_ligand.sdf> \
    --arch pocket --pocket_type holo --cut_pocket --pocket_cutoff 7.0 \
    --gpus <n_gpus> --num_workers 4 --batch_cost 20 \
    --ckpt_path <flowr_root_v2.2.ckpt> --save_dir <save_dir> \
    --max_sample_iter 30 --coord_noise_scale 0.1 \
    --sample_n_molecules_per_target <n_molecules> \
    --categorical_strategy uniform-sample \
    --filter_valid_unique --filter_diversity --diversity_threshold 0.7
```

Verified working on this cluster — copied from
`../selectisafe/scripts/submit_flowr_inference.sh`, not re-derived from the repo.

## Standalone smoke test

```bash
apptainer exec --nv --env PYTHONPATH=/opt/flowr_root ../selectisafe/builds/flowr-v1.0.sif \
    python -m flowr.gen.generate_from_pdb \
    --pdb_file ../selectisafe/4ZAU/4ZAU_protein.pdb \
    --ligand_file ../selectisafe/4ZAU/4ZAU_ligand.sdf \
    --arch pocket --pocket_type holo --cut_pocket --pocket_cutoff 7.0 \
    --gpus 1 --num_workers 2 --batch_cost 10 \
    --ckpt_path ../selectisafe/data/models/flowr_root_v2.2.ckpt \
    --save_dir /tmp/flowr_smoke_test \
    --sample_n_molecules_per_target 2 --max_sample_iter 10
```

Needs a GPU node (`--nv`) — run inside an `sbatch`/`srun` job on the `gpu` partition,
not on a login node.
