#!/bin/bash
# Pose agreement for the EGFR/4ZAU set.
#
# The set includes control_osimertinib: the crystal ligand re-docked against its
# own structure. Its RMSD is not an agreement measure but an accuracy measure --
# the answer is known, so it says whether DiffDock works on this target at all.
# If the control is poor, nothing below it can be trusted.
cd /scratch/g.murugan/Pfizer/selectisafe || exit 1
export REF_DIR=/scratch/g.murugan/Pfizer/selectisafe/data/docking_inputs_4zau/ligands
export DOCK_DIR=/scratch/g.murugan/Pfizer/selectisafe/data/results/4zau_docked
exec apptainer exec builds/diffdock-v1.0.sif \
    /home/appuser/micromamba/envs/diffdock/bin/python \
    scripts/pose_agreement.py
