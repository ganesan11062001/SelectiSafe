#!/usr/bin/env python3
"""
Do the generated molecules actually occupy the same site as the known drugs?

The pose-agreement check compared each molecule against itself (FLOWR's pose vs
DiffDock's). It never compared the generated set against the real drugs, so
"they sit where the real drugs sit" has been assumed rather than measured --
plausible, since FLOWR was told to design into a 7 A shell cut around the
reference ligands, but assumed.

This measures it directly, using the DiffDock poses for both sets so the
comparison runs through one consistent method:

  centre offset   distance from a molecule's centroid to the mean centroid of
                  the 36 known drugs -- "is it in the same place"
  occupancy       fraction of the molecule's heavy atoms lying within 2 A of any
                  known-drug heavy atom -- "does it fill the same volume"

The known drugs are also scored against their own mean, which gives the natural
yardstick: how far apart 36 real BACE inhibitors sit from each other.
"""

import glob
import math
import os

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

SELECTISAFE = "/scratch/g.murugan/Pfizer/selectisafe"
GEN_DOCK = os.path.join(SELECTISAFE, "data/results/bace_docked_all")
REF_DOCK = os.path.join(SELECTISAFE, "data/results/bace_ref_docked")
NEAR = 2.0


def load_coords(path):
    supplier = Chem.SDMolSupplier(path, sanitize=False, removeHs=False)
    mol = supplier[0] if len(supplier) else None
    if mol is None:
        return None
    try:
        mol = Chem.RemoveAllHs(mol, sanitize=False)
    except Exception:
        pass
    conf = mol.GetConformer()
    return [(conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z)
            for i in range(mol.GetNumAtoms())]


def poses(root):
    out = {}
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        p = os.path.join(d, "rank1.sdf")
        if os.path.exists(p):
            c = load_coords(p)
            if c:
                out[os.path.basename(d)] = c
    return out


def centroid(coords):
    n = len(coords)
    return tuple(sum(c[i] for c in coords) / n for i in range(3))


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def occupancy(coords, ref_atoms):
    near = sum(1 for a in coords if any(dist(a, r) < NEAR for r in ref_atoms))
    return near / len(coords)


def main():
    gen = poses(GEN_DOCK)
    ref = poses(REF_DOCK)
    print("generated poses: %d   known-drug poses: %d\n" % (len(gen), len(ref)))

    ref_atoms = [a for c in ref.values() for a in c]
    ref_centre = centroid([centroid(c) for c in ref.values()])

    def summarize(label, group, exclude_self):
        offs, occs = [], []
        for name, coords in sorted(group.items()):
            offs.append(dist(centroid(coords), ref_centre))
            others = ([a for n, c in ref.items() if n != name for a in c]
                      if exclude_self else ref_atoms)
            occs.append(occupancy(coords, others))
        offs_s, occs_s = sorted(offs), sorted(occs)
        print("%-22s n=%d" % (label, len(offs)))
        print("   centre offset  median %.2f A   min %.2f   max %.2f"
              % (offs_s[len(offs_s) // 2], offs_s[0], offs_s[-1]))
        print("   occupancy      median %.0f%%      min %.0f%%     max %.0f%%"
              % (100 * occs_s[len(occs_s) // 2], 100 * occs_s[0], 100 * occs_s[-1]))
        return offs, occs

    print("Distance to the centre of the known-drug binding site,")
    print("and overlap with the volume those drugs occupy:\n")
    summarize("known drugs", ref, exclude_self=True)
    print()
    summarize("generated molecules", gen, exclude_self=False)


if __name__ == "__main__":
    main()
