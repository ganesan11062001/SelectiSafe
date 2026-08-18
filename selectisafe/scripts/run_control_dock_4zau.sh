#!/bin/bash
#SBATCH --job-name=dock-ctrl-4zau
#SBATCH --account=a.barabasi
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16GB
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/g.murugan/Pfizer/selectisafe/logs/dock_ctrl_4zau_%j.log
#SBATCH --error=/scratch/g.murugan/Pfizer/selectisafe/logs/dock_ctrl_4zau_%j.err

# Re-dock osimertinib against the PDBFixer-repaired 4ZAU protein.
#
# The first attempt used the raw structure, whose pocket wall is missing
# residues 747-755, and failed the self-docking control at 3.36 A. FLOWR had
# generated against a repaired pocket, so the two halves of the pipeline were
# looking at different proteins. This tests whether that mismatch explains the
# failure -- one molecule, because there is no point re-docking 51 until the
# control passes.

set -uo pipefail
SELECTISAFE=/scratch/g.murugan/Pfizer/selectisafe
cd "$SELECTISAFE" || exit 1

CSV="${SELECTISAFE}/data/docking_inputs_4zau/control_fixed.csv"
OUT_DIR="${SELECTISAFE}/data/results/4zau_control_fixed"
mkdir -p "$OUT_DIR"

cat > "$CSV" <<EOF
complex_name,protein_path,ligand_description,protein_sequence
control_fixed,${SELECTISAFE}/4ZAU/4ZAU_protein_fixed.pdb,${SELECTISAFE}/4ZAU/4ZAU_ligand.sdf,
EOF

echo "start : $(date)"
apptainer exec --nv "${SELECTISAFE}/builds/diffdock-v1.0.sif" \
    /home/appuser/micromamba/envs/diffdock/bin/python \
    /home/appuser/DiffDock/inference.py \
    --config /home/appuser/DiffDock/default_inference_args.yaml \
    --protein_ligand_csv "$CSV" \
    --out_dir "$OUT_DIR"
echo "exit  : $?"
echo "end   : $(date)"
find "$OUT_DIR" -name 'rank1*.sdf' -printf '  %f\n'
