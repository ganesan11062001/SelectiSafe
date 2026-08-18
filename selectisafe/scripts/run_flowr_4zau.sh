#!/bin/bash
#SBATCH --job-name=flowr-4zau
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:a100:1
#SBATCH --mem=32GB
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/g.murugan/Pfizer/selectisafe/logs/flowr_4zau_%j.log
#SBATCH --error=/scratch/g.murugan/Pfizer/selectisafe/logs/flowr_4zau_%j.err

# Generate molecules for the EGFR ATP pocket of 4ZAU (osimertinib complex).
#
# Inputs come from 4ZAU/prepare_4zau.py, which splits the deposition into a
# protein PDB and a chemically-correct reference ligand. The ligand defines the
# pocket; it is not itself a template for what gets generated.
#
# Differences from the BACE run, each deliberate:
#
#   --gpus 1              The BACE script asked the program for 2 GPUs while
#                         Slurm granted 1. Corrected.
#   --sample_mol_sizes    The BACE run produced 29 molecules all locked at
#                         exactly 27 heavy atoms -- it explored shape but not
#                         size. This samples a size distribution instead.
#   --use_pdbfixer        4ZAU is missing 37 residues, including 747-755, which
#                         sits immediately after pocket residue Lys745. Without
#                         rebuilding it the pocket has an artificial opening and
#                         molecules can grow into space the real protein fills.
#   --compute_interactions / --compute_interaction_recovery
#                         Asks, via ProLIF, whether generated molecules make the
#                         same protein contacts real EGFR inhibitors make -- the
#                         hinge hydrogen bond to Met793 above all. This is the
#                         closest thing to a mechanistic check that needs no
#                         affinity model, and we skipped it on BACE.
#   --calculate_strain_energies
#                         Flags molecules held in contorted, high-energy
#                         conformations they would not really adopt.
#
# NOT used: --calculate_pb_valid. PoseBusters is vendored in the flowr checkout
# but is not installed in the container, so that flag fails at import. Physical
# validity has to be checked separately.

set -uo pipefail

SELECTISAFE=/scratch/g.murugan/Pfizer/selectisafe
SIF="${SELECTISAFE}/builds/flowr-v1.0.sif"
CKPT="${SELECTISAFE}/data/models/flowr_root_v2.2.ckpt"
PDB="${SELECTISAFE}/4ZAU/4ZAU_protein.pdb"
LIGAND="${SELECTISAFE}/4ZAU/4ZAU_ligand.sdf"
OUT_DIR="${SELECTISAFE}/data/results/4zau_gen"

cd "$SELECTISAFE" || exit 1
mkdir -p "$OUT_DIR"

echo "=========================================="
echo "FLOWR.root generation -- EGFR (4ZAU)"
echo "job     : ${SLURM_JOB_ID}"
echo "node    : $(hostname)"
echo "protein : ${PDB}"
echo "pocket  : defined by ${LIGAND} (osimertinib), 7 A"
echo "start   : $(date)"
echo "=========================================="

apptainer exec --nv --env PYTHONPATH=/opt/flowr_root "$SIF" \
    python -m flowr.gen.generate_from_pdb \
    --pdb_file "$PDB" \
    --ligand_file "$LIGAND" \
    --arch pocket \
    --pocket_type holo \
    --cut_pocket \
    --pocket_cutoff 7.0 \
    --use_pdbfixer \
    --ckpt_path "$CKPT" \
    --save_dir "$OUT_DIR" \
    --gpus 1 \
    --num_workers 4 \
    --batch_cost 20 \
    --max_sample_iter 30 \
    --coord_noise_scale 0.1 \
    --sample_n_molecules_per_target 50 \
    --sample_mol_sizes \
    --categorical_strategy uniform-sample \
    --filter_valid_unique \
    --filter_diversity \
    --diversity_threshold 0.7 \
    --compute_interactions \
    --compute_interaction_recovery \
    --calculate_strain_energies
rc=$?

echo "------------------------------------------"
echo "exit code : ${rc}"
n_sdf=$(find "$OUT_DIR" -name '*.sdf' | wc -l)
echo "sdf files : ${n_sdf}"
find "$OUT_DIR" -name '*.sdf' -printf '  %f  %s bytes\n' 2>/dev/null
echo "end       : $(date)"

if [ "$rc" -ne 0 ] || [ "$n_sdf" -eq 0 ]; then
    echo "RESULT: FAILED"
    exit 1
fi
echo "RESULT: OK"
