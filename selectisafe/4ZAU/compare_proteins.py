#!/usr/bin/env python3
"""Confirm what PDBFixer actually rebuilt in the 4ZAU protein."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def info(path):
    lines = [l for l in open(path) if l.startswith("ATOM")]
    res = sorted({int(l[22:26]) for l in lines})
    hyd = sum(1 for l in lines if l[76:78].strip() == "H")
    gaps = sorted(set(range(res[0], res[-1] + 1)) - set(res))
    return res, len(lines), hyd, gaps


for name in ("4ZAU_protein.pdb", "4ZAU_protein_fixed.pdb"):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print("%s : MISSING" % name)
        continue
    res, n_atoms, hyd, gaps = info(path)
    print(name)
    print("  residues   %d-%d, %d modelled" % (res[0], res[-1], len(res)))
    print("  atoms      %d  (%d hydrogens)" % (n_atoms, hyd))
    print("  missing    %d %s" % (len(gaps), gaps[:20]))
