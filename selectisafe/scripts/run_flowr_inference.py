#!/usr/bin/env python3
"""
FLOWR.ROOT Inference Script
Generates ligands for a given protein pocket
"""

import sys
import os
from pathlib import Path

# Key parameters you can modify
PROTEIN_PDB = "/scratch/g.murugan/Pfizer/selectisafe/flowr_root_temp/examples/bace_protein.pdb"
REF_LIGAND_SDF = "/scratch/g.murugan/Pfizer/selectisafe/flowr_root_temp/examples/bace_ligands.sdf"
CKPT_PATH = "/opt/flowr_root/flowr_root.ckpt"

# Pocket definition (explicit coordinates)
POCKET_CENTER = (13.5, 17.0, 12.5)  # XYZ center in Angstroms
POCKET_RADIUS = 7.0  # Cutoff radius in Angstroms

# Generation parameters
NUM_MOLECULES = 50
SAMPLING_STEPS = 100
COORD_NOISE = 0.1

# Output
OUTPUT_DIR = "/scratch/g.murugan/Pfizer/selectisafe/data/results/bace_gen"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("FLOWR.ROOT Inference")
print("=" * 60)
print(f"Protein: {PROTEIN_PDB}")
print(f"Pocket center: {POCKET_CENTER}")
print(f"Pocket radius: {POCKET_RADIUS} Å")
print(f"Molecules to generate: {NUM_MOLECULES}")
print(f"Output directory: {OUTPUT_DIR}")
print("=" * 60)

# Import FLOWR.ROOT
sys.path.insert(0, "/opt/flowr_root")

print("\n✓ Setup complete. Ready to run generation.")
