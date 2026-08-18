from rdkit import Chem
import re

# Read 4ZAU.pdb
with open('/scratch/g.murugan/Pfizer/selectisafe/data/input/4ZAU.pdb', 'r') as f:
    lines = f.readlines()

# Keep ATOM (protein) and HETATM (ligand) lines, remove water/ions
clean_lines = []
for line in lines:
    if line.startswith('ATOM'):
        clean_lines.append(line)
    elif line.startswith('HETATM'):
        # Keep ligand atoms (YY3), remove water (HOH) and ions
        if 'YY3' in line:
            clean_lines.append(line)
    elif line.startswith(('END', 'CONECT')):
        clean_lines.append(line)

# Write cleaned PDB
with open('/scratch/g.murugan/Pfizer/selectisafe/data/input/4ZAU_clean.pdb', 'w') as f:
    f.writelines(clean_lines)

print(f"Cleaned PDB written: 4ZAU_clean.pdb")
print(f"Total lines: {len(clean_lines)}")

