#!/bin/bash
#SBATCH --job-name=diffdock-inference
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16GB
#SBATCH --time=02:00:00
#SBATCH --output=../logs/diffdock_inference_%j.log
#SBATCH --error=../logs/diffdock_inference_%j.err

cd /scratch/g.murugan/Pfizer/selectisafe

mkdir -p data/results/bace_docked

echo "Starting DiffDock docking..."
apptainer exec --nv /scratch/g.murugan/Pfizer/selectisafe/builds/diffdock-v1.0.sif /home/appuser/micromamba/envs/diffdock/bin/python /home/appuser/DiffDock/inference.py --config /home/appuser/DiffDock/default_inference_args.yaml --protein_ligand_csv /scratch/g.murugan/Pfizer/selectisafe/data/bace_docking_input.csv --out_dir /scratch/g.murugan/Pfizer/selectisafe/data/results/bace_docked

if [ $? -eq 0 ]; then
    echo "✓ Docking completed!"
    ls -lah data/results/bace_docked/
else
    echo "✗ Docking failed"
fi
