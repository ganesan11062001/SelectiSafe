#!/usr/bin/env python3
"""
Rebuild the missing parts of the 4ZAU protein with PDBFixer.

Why: FLOWR generated against a PDBFixer-repaired protein (--use_pdbfixer), but
DiffDock was given the raw one. 4ZAU is missing 37 residues, including 747-755,
which sits immediately after pocket residue Lys745 -- so the docking protein had
a hole in the pocket wall that the generation protein did not. That inconsistency
is the leading suspect for the self-docking control failing at 3.36 A.

Only *internal* gaps are rebuilt. Missing residues at a chain terminus are left
alone: they are disordered tails with no defined position, and modelling them
produces a long arm of invented coordinates flapping off the structure, which
would do more harm than the gap. The C-terminal stretch here (985-1007) is
exactly that case; 747-755 is the internal gap that matters.

Hydrogens are not added -- DiffDock works on heavy atoms, and adding them would
change atom counts relative to everything already computed.

Runs inside the FLOWR container, which has pdbfixer and openmm.
"""

import os

from openmm.app import PDBFile
from pdbfixer import PDBFixer

HERE = os.path.dirname(os.path.abspath(__file__))
IN_PDB = os.path.join(HERE, "4ZAU_protein.pdb")
OUT_PDB = os.path.join(HERE, "4ZAU_protein_fixed.pdb")


def residue_numbers(path):
    return sorted({int(l[22:26]) for l in open(path) if l.startswith("ATOM")})


def main():
    before = residue_numbers(IN_PDB)
    gaps_before = sorted(set(range(before[0], before[-1] + 1)) - set(before))

    fixer = PDBFixer(filename=IN_PDB)
    fixer.findMissingResidues()

    # Drop terminal gaps, keep internal ones.
    chains = list(fixer.topology.chains())
    keep = {}
    for key, residues in fixer.missingResidues.items():
        chain_idx, insert_at = key
        n_res = len(list(chains[chain_idx].residues()))
        if insert_at == 0 or insert_at == n_res:
            print("  skipping terminal gap at chain %d position %d (%d residues)"
                  % (chain_idx, insert_at, len(residues)))
            continue
        keep[key] = residues
        print("  rebuilding internal gap at chain %d position %d (%d residues)"
              % (chain_idx, insert_at, len(residues)))
    fixer.missingResidues = keep

    fixer.findMissingAtoms()
    n_atom_gaps = sum(len(v) for v in fixer.missingAtoms.values())
    print("  incomplete side chains to complete: %d" % n_atom_gaps)
    fixer.addMissingAtoms()

    with open(OUT_PDB, "w") as fh:
        PDBFile.writeFile(fixer.topology, fixer.positions, fh, keepIds=True)

    after = residue_numbers(OUT_PDB)
    gaps_after = sorted(set(range(after[0], after[-1] + 1)) - set(after))
    n_before = sum(1 for l in open(IN_PDB) if l.startswith("ATOM"))
    n_after = sum(1 for l in open(OUT_PDB) if l.startswith("ATOM"))

    print()
    print("residues : %d -> %d" % (len(before), len(after)))
    print("atoms    : %d -> %d" % (n_before, n_after))
    print("gaps     : %d -> %d" % (len(gaps_before), len(gaps_after)))
    print("remaining gaps: %s" % gaps_after)
    print("written  : %s" % OUT_PDB)


if __name__ == "__main__":
    main()
