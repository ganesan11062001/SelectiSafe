#!/usr/bin/env python3
"""
Rebuild the missing parts of the 4ZAU protein with PDBFixer.

4ZAU has 37 unmodelled residues, among them 747-755 -- immediately after pocket
residue Lys745. FLOWR was given --use_pdbfixer and so generated against a
repaired pocket; DiffDock was handed the raw file and docked against a pocket
with a hole in its wall. The self-docking control failed at 3.36 A, and that
inconsistency is the leading suspect.

This produces the repaired structure so both halves of the pipeline see the same
protein. Missing residues are rebuilt, missing heavy atoms added, and hydrogens
added at pH 7.0 -- the last also being what the ProLIF interaction check needed
and did not have.

Runs inside the FLOWR container, which is where PDBFixer lives.
"""

import os

from pdbfixer import PDBFixer
from openmm.app import PDBFile

HERE = os.path.dirname(os.path.abspath(__file__))

# Read the ORIGINAL deposition, not the stripped 4ZAU_protein.pdb. PDBFixer
# learns which residues are missing by comparing the modelled atoms against the
# SEQRES header, and the stripped file has no header -- fed that, it reports
# zero gaps and rebuilds nothing. The ligand and waters are removed here by
# PDBFixer instead of by line filtering, which keeps SEQRES intact.
IN_PDB = os.path.join(HERE, "4ZAU.pdb")
OUT_PDB = os.path.join(HERE, "4ZAU_protein_fixed.pdb")


def residue_ids(path):
    return sorted({int(l[22:26]) for l in open(path) if l.startswith("ATOM")})


def main():
    before = residue_ids(os.path.join(HERE, "4ZAU_protein.pdb"))
    print("input  : %s" % IN_PDB)
    print("         %d SEQRES lines present" % sum(
        1 for l in open(IN_PDB) if l.startswith("SEQRES")))
    print("         residues %d-%d, %d modelled"
          % (before[0], before[-1], len(before)))

    fixer = PDBFixer(filename=IN_PDB)
    # Drop the ligand and waters, but only after SEQRES has been parsed.
    fixer.removeHeterogens(keepWater=False)

    fixer.findMissingResidues()
    n_gaps = len(fixer.missingResidues)
    n_res = sum(len(v) for v in fixer.missingResidues.values())
    print("         %d gaps covering %d residues" % (n_gaps, n_res))
    if n_res == 0:
        print("         WARNING: no gaps detected -- is SEQRES present?")

    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.findMissingAtoms()
    n_atoms = sum(len(v) for v in fixer.missingAtoms.values())
    print("         %d residues missing heavy atoms" % n_atoms)

    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(7.0)

    with open(OUT_PDB, "w") as fh:
        PDBFile.writeFile(fixer.topology, fixer.positions, fh, keepIds=True)

    after = residue_ids(OUT_PDB)
    n_h = sum(1 for l in open(OUT_PDB)
              if l.startswith("ATOM") and l[76:78].strip() == "H")
    print()
    print("output : %s" % OUT_PDB)
    print("         residues %d-%d, %d modelled (was %d)"
          % (after[0], after[-1], len(after), len(before)))
    print("         %d hydrogens added" % n_h)
    still = sorted(set(range(after[0], after[-1] + 1)) - set(after))
    print("         still missing: %s" % (still if still else "none"))


if __name__ == "__main__":
    main()
