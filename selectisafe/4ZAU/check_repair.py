#!/usr/bin/env python3
"""Compare the raw and PDBFixer-repaired 4ZAU protein."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def info(path):
    lines = [l for l in open(path) if l.startswith("ATOM")]
    res = sorted({int(l[22:26]) for l in lines})
    gaps = sorted(set(range(res[0], res[-1] + 1)) - set(res))
    return len(lines), len(res), res[0], res[-1], gaps


for name in ("4ZAU_protein.pdb", "4ZAU_protein_fixed.pdb"):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print("%-28s MISSING" % name)
        continue
    n_at, n_res, lo, hi, gaps = info(path)
    print("%-28s atoms %5d  residues %3d (%d-%d)  gaps %d"
          % (name, n_at, n_res, lo, hi, len(gaps)))
    print("   missing: %s" % gaps)
