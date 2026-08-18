#!/usr/bin/env python3
"""
Heavy-atom-only copy of the PDBFixer-repaired protein.

PDBFixer protonated the whole structure while rebuilding the missing loop
(2177 -> 4609 atoms, most of them hydrogens). The original docking protein was
heavy-atom only, so stripping them back out leaves exactly one difference
between the two runs -- the rebuilt loop -- which is the variable under test.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
IN_PDB = os.path.join(HERE, "4ZAU_protein_fixed.pdb")
OUT_PDB = os.path.join(HERE, "4ZAU_protein_fixed_heavy.pdb")


def is_hydrogen(line):
    element = line[76:78].strip()
    if element:
        return element == "H"
    return line[12:16].strip().startswith("H")  # fall back to the atom name


kept = []
for line in open(IN_PDB):
    if line.startswith("ATOM"):
        if is_hydrogen(line):
            continue
        kept.append(line)
    elif line.startswith("TER"):
        kept.append(line)
kept.append("END\n")

with open(OUT_PDB, "w") as fh:
    fh.writelines(kept)

atoms = [l for l in kept if l.startswith("ATOM")]
res = sorted({int(l[22:26]) for l in atoms})
gaps = sorted(set(range(res[0], res[-1] + 1)) - set(res))
print("heavy atoms    : %d" % len(atoms))
print("residues       : %d (%d-%d)" % (len(res), res[0], res[-1]))
print("remaining gaps : %d  %s" % (len(gaps), gaps))
print("written        : %s" % OUT_PDB)
