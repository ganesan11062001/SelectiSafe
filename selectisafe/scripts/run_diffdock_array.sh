#!/bin/bash
#SBATCH --job-name=diffdock-array
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu
#SBATCH --array=0-7%4
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16GB
#SBATCH --time=04:30:00
#SBATCH --output=/scratch/g.murugan/Pfizer/selectisafe/logs/dock_array/task_%a_%A.log
#SBATCH --error=/scratch/g.murugan/Pfizer/selectisafe/logs/dock_array/task_%a_%A.err

# Dock all 29 FLOWR-generated molecules against BACE.
#
# The `gpu` QOS allows 8 submitted jobs per user and 4 running, so this is an
# 8-task array rather than one task per molecule. scripts/prepare_docking_inputs.py
# deals the 29 molecules round-robin across the 8 tasks and writes one multi-row
# CSV per task; DiffDock takes a multi-row CSV natively, so each task loads the
# model once and docks its 3-4 molecules in a single pass.
#
# data/docking_inputs/manifest.csv maps every molecule back to its source SDF
# record, its task id, and FLOWR's predicted pIC50.
#
# The cd below is load-bearing: DiffDock caches its SO(3) and torus lookup tables
# relative to the working directory. They already exist in the project root
# (~400 MB, built by the August 14 runs), so every task reads them instead of
# spending minutes regenerating them -- and concurrent tasks never race to write
# them.

set -uo pipefail

SELECTISAFE=/scratch/g.murugan/Pfizer/selectisafe
cd "$SELECTISAFE" || exit 1

# Defaults dock the FLOWR-generated set. Override both to reuse this script for
# another set through the identical path -- e.g. the known-inhibitor baseline:
#   sbatch --export=ALL,TASK_DIR=...,OUT_DIR=... scripts/run_diffdock_array.sh
TASK_DIR="${TASK_DIR:-${SELECTISAFE}/data/docking_inputs/tasks}"
OUT_DIR="${OUT_DIR:-${SELECTISAFE}/data/results/bace_docked_all}"

CSV="${TASK_DIR}/task_${SLURM_ARRAY_TASK_ID}.csv"

if [ ! -f "$CSV" ]; then
    echo "FATAL: no input csv for task ${SLURM_ARRAY_TASK_ID}: $CSV"
    echo "Run scripts/prepare_docking_inputs.py first."
    exit 1
fi

mkdir -p "$OUT_DIR"

# Molecule names this task is responsible for (first CSV column, minus header).
MOLS=$(tail -n +2 "$CSV" | cut -d, -f1)
N_EXPECTED=$(echo "$MOLS" | grep -c .)

echo "=========================================="
echo "DiffDock  array task ${SLURM_ARRAY_TASK_ID}"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "node      : $(hostname)"
echo "start     : $(date)"
echo "input     : ${CSV}"
echo "molecules : ${N_EXPECTED} (${MOLS//$'\n'/ })"
echo "=========================================="

apptainer exec --nv "${SELECTISAFE}/builds/diffdock-v1.0.sif" \
    /home/appuser/micromamba/envs/diffdock/bin/python \
    /home/appuser/DiffDock/inference.py \
    --config /home/appuser/DiffDock/default_inference_args.yaml \
    --protein_ligand_csv "$CSV" \
    --out_dir "$OUT_DIR"
rc=$?

# DiffDock exits 0 even when it skips a complex it could not build, so confirm
# per molecule that poses actually landed rather than trusting the return code.
echo "------------------------------------------"
echo "exit code : ${rc}"
n_ok=0
for mol in $MOLS; do
    n_poses=$(find "${OUT_DIR}/${mol}" -name 'rank*.sdf' 2>/dev/null | wc -l)
    if [ "$n_poses" -gt 0 ]; then
        echo "  OK      ${mol}  (${n_poses} poses)"
        n_ok=$((n_ok + 1))
    else
        echo "  MISSING ${mol}  (no poses written)"
    fi
done
echo "docked    : ${n_ok}/${N_EXPECTED}"
echo "end       : $(date)"

if [ "$rc" -ne 0 ] || [ "$n_ok" -ne "$N_EXPECTED" ]; then
    echo "RESULT: FAILED task ${SLURM_ARRAY_TASK_ID}"
    exit 1
fi

echo "RESULT: OK task ${SLURM_ARRAY_TASK_ID} (${n_ok} molecules)"
