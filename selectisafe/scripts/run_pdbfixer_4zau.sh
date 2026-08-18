#!/bin/bash
#SBATCH --job-name=pdbfixer-4zau
#SBATCH --account=a.barabasi
#SBATCH --partition=short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/g.murugan/Pfizer/selectisafe/logs/pdbfixer_4zau_%j.log
#SBATCH --error=/scratch/g.murugan/Pfizer/selectisafe/logs/pdbfixer_4zau_%j.err

# Rebuild 4ZAU's missing residues so DiffDock and FLOWR see the same protein.
#
# FLOWR generated against a PDBFixer-repaired pocket (--use_pdbfixer); DiffDock
# was handed the raw file, whose pocket wall has a hole where residues 747-755
# should be. The self-docking control failed at 3.36 A and that mismatch is the
# leading suspect.
#
# Rebuilding 37 residues including a 9-residue loop takes minutes, not seconds,
# which is why this is a batch job rather than an interactive call. python -u
# keeps the progress output unbuffered so a killed run still leaves a trace.

set -uo pipefail
cd /scratch/g.murugan/Pfizer/selectisafe || exit 1

echo "start : $(date)"
apptainer exec builds/flowr-v1.0.sif python -u 4ZAU/fix_protein.py
rc=$?
echo "exit  : ${rc}"
echo "end   : $(date)"
ls -la 4ZAU/4ZAU_protein_fixed.pdb 2>&1
exit $rc
