#!/bin/bash
#SBATCH --job-name=flowr-aff-baseline
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=32GB
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/g.murugan/Pfizer/selectisafe/logs/flowr_aff_%j.log
#SBATCH --error=/scratch/g.murugan/Pfizer/selectisafe/logs/flowr_aff_%j.err

# Calibrate FLOWR's affinity head against ground truth.
#
# The 36 ligands in examples/bace_ligands.sdf are known BACE inhibitors whose
# binding free energies were MEASURED in a lab (the r_exp_dg tag). FLOWR did not
# design them. Asking FLOWR to predict their affinity and comparing against the
# measurements is the only check available that can say whether its predicted
# pIC50 means anything -- and therefore whether the 6.84 mean it reported for the
# generated molecules is evidence or decoration.
#
# Four seeds, as in the upstream predict_aff.sl template: affinity prediction
# injects coordinate noise, so a single seed is one draw from a distribution.
# Running four lets us both average them and measure how much the prediction
# moves for a fixed input -- the spread bounds how finely any ranking can be
# trusted.

set -uo pipefail

SELECTISAFE=/scratch/g.murugan/Pfizer/selectisafe
SIF="${SELECTISAFE}/builds/flowr-v1.0.sif"
CKPT="${SELECTISAFE}/data/models/flowr_root_v2.2.ckpt"
PDB="${SELECTISAFE}/flowr_root_temp/examples/bace_protein.pdb"

# Defaults score the known-inhibitor baseline. Override to re-score another set
# through the identical path -- e.g. the generated molecules, which were scored
# with a single seed at generation time and need the same 4-seed treatment:
#   sbatch --export=ALL,LIGANDS=...,OUT_ROOT=... scripts/run_flowr_affinity_baseline.sh
LIGANDS="${LIGANDS:-${SELECTISAFE}/flowr_root_temp/examples/bace_ligands.sdf}"
OUT_ROOT="${OUT_ROOT:-${SELECTISAFE}/data/results/bace_ref_affinity}"

cd "$SELECTISAFE" || exit 1
mkdir -p "$OUT_ROOT"

echo "=========================================="
echo "FLOWR affinity prediction -- known BACE inhibitors"
echo "job    : ${SLURM_JOB_ID}"
echo "node    : $(hostname)"
echo "ligands : ${LIGANDS}"
echo "start   : $(date)"
echo "=========================================="

for seed in 2 42 512 1000; do
    save_dir="${OUT_ROOT}/seed_${seed}"
    mkdir -p "$save_dir"
    echo ""
    echo "--- seed ${seed} ---"

    # Pocket settings mirror the generation run exactly (holo pocket, 7 A cutoff,
    # 0.1 coordinate noise) so the predictions are made under the same conditions
    # that produced the pIC50 values on the generated molecules.
    apptainer exec --nv --env PYTHONPATH=/opt/flowr_root "$SIF" \
        python -m flowr.predict.predict_from_pdb \
        --pdb_file "$PDB" \
        --ligand_file "$LIGANDS" \
        --multiple_ligands \
        --arch pocket \
        --pocket_type holo \
        --pocket_noise fix \
        --cut_pocket \
        --pocket_cutoff 7 \
        --ckpt_path "$CKPT" \
        --save_dir "$save_dir" \
        --gpus 1 \
        --num_workers 4 \
        --batch_cost 20 \
        --seed "$seed" \
        --coord_noise_scale 0.1
    echo "seed ${seed} exit: $?"
    find "$save_dir" -name '*.sdf' | head
done

echo ""
echo "=========================================="
echo "end : $(date)"
find "$OUT_ROOT" -name '*.sdf' | wc -l
echo "=========================================="
