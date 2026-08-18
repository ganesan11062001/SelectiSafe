#!/bin/bash
#SBATCH --job-name=flowr-egfr
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=16GB
#SBATCH --time=04:30:00
#SBATCH --output=../logs/flowr_egfr_%j.log
#SBATCH --error=../logs/flowr_egfr_%j.err

cd /scratch/g.murugan/Pfizer/selectisafe
mkdir -p data/results/egfr_gen

apptainer exec --nv --env PYTHONPATH=/opt/flowr_root /scratch/g.murugan/Pfizer/selectisafe/builds/flowr-v1.0.sif python -m flowr.gen.generate_from_pdb --pdb_file /scratch/g.murugan/Pfizer/selectisafe/data/input/4ZAU.pdb --ligand_file /scratch/g.murugan/Pfizer/selectisafe/data/input/egfr_reference_ligands.sdf --arch pocket --pocket_type holo --cut_pocket --pocket_cutoff 10.0 --gpus 1 --num_workers 2 --batch_cost 20 --ckpt_path /scratch/g.murugan/Pfizer/selectisafe/data/models/flowr_root_v2.2.ckpt --save_dir data/results/egfr_gen --max_sample_iter 30 --coord_noise_scale 0.1 --sample_n_molecules_per_target 50 --categorical_strategy uniform-sample --filter_valid_unique --filter_diversity --diversity_threshold 0.7

