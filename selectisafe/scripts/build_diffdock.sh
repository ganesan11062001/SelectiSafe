#!/bin/bash
#SBATCH --job-name=diffdock-build
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=16GB
#SBATCH --time=02:00:00
#SBATCH --output=../logs/diffdock_build_%j.log
#SBATCH --error=../logs/diffdock_build_%j.err

cd /scratch/g.murugan/Pfizer/selectisafe/builds

echo "=========================================="
echo "DiffDock Container Build"
echo "=========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Start time: $(date)"
echo ""

echo "Building diffdock-v1.0.sif from diffdock.def..."
apptainer build diffdock-v1.0.sif diffdock.def

if [ -f diffdock-v1.0.sif ]; then
    echo ""
    echo "=========================================="
    echo "✓ Build successful!"
    echo "=========================================="
    ls -lah diffdock-v1.0.sif
    echo "End time: $(date)"
else
    echo "✗ Build failed - check error messages above"
fi
