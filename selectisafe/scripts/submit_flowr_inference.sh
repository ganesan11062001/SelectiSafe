#!/bin/bash
#SBATCH --job-name=flowr-inference
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu                        # ← GPU partition
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:a100:1                      # ← 1 A100 GPU
#SBATCH --mem=16GB
#SBATCH --time=04:30:00
#SBATCH --output=../logs/flowr_inference_%j.log
#SBATCH --error=../logs/flowr_inference_%j.err

cd /scratch/g.murugan/Pfizer/selectisafe

echo "=========================================="
echo "FLOWR.ROOT Inference Job"
echo "=========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Start time: $(date)"
echo ""

mkdir -p data/results/bace_gen

apptainer exec --nv --env PYTHONPATH=/opt/flowr_root /scratch/g.murugan/Pfizer/selectisafe/builds/flowr-v1.0.sif python -m flowr.gen.generate_from_pdb --pdb_file /scratch/g.murugan/Pfizer/selectisafe/flowr_root_temp/examples/bace_protein.pdb --ligand_file /scratch/g.murugan/Pfizer/selectisafe/flowr_root_temp/examples/bace_ligands.sdf --arch pocket --pocket_type holo --cut_pocket --pocket_cutoff 7.0 --gpus 2 --num_workers 4 --batch_cost 20 --ckpt_path /scratch/g.murugan/Pfizer/selectisafe/data/models/flowr_root_v2.2.ckpt --save_dir data/results/bace_gen --max_sample_iter 30 --coord_noise_scale 0.1 --sample_n_molecules_per_target 50 --categorical_strategy uniform-sample --filter_valid_unique --filter_diversity --diversity_threshold 0.7

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Generation completed successfully!"
    echo "=========================================="
    echo "Results saved to: data/results/bace_gen"
    ls -lah data/results/bace_gen/
else
    echo ""
    echo "=========================================="
    echo "✗ Generation failed"
    echo "=========================================="
fi

echo "End time: $(date)"
