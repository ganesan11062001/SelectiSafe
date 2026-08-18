#!/usr/bin/env python3
"""
Do FLOWR and DiffDock-L agree on how each molecule binds?

FLOWR designs a molecule *and* its pose together. DiffDock discards that pose
entirely -- it strips the coordinates, builds a fresh random conformer, and
re-derives the placement from scratch -- so the two poses are independent
answers to the same question. Where they agree, two methods built on different
principles corroborate each other. Where they diverge, at least one is wrong
about the binding mode, and every affinity number attached to that molecule was
computed assuming a pose that may be the wrong one.

Three numbers per molecule:

  rmsd_inplace  symmetry-corrected RMSD in the protein frame, no superposition.
                This is the one that matters -- it asks whether the molecule is
                in the same place, in the same orientation, in the same shape.
  rmsd_aligned  RMSD after optimal superposition. Comparing it against the
                in-place value separates "wrong location" from "wrong shape":
                if aligned is small but in-place is large, both models built the
                same conformer and put it in different places.
  centroid_d    distance between the two centres of mass, in Angstrom. The
                blunt, readable version of "how far apart are they".

2.0 A is the long-standing convention for a correct pose in docking.

Runs inside the DiffDock container, which is where RDKit lives.
"""

import glob
import math
import os
import sys

from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolAlign

RDLogger.DisableLog("rdApp.*")

SELECTISAFE = "/scratch/g.murugan/Pfizer/selectisafe"

# Defaults compare FLOWR's designed poses against DiffDock's. Override to run the
# control -- the 36 known drugs, whose reference poses are crystallographic, which
# calibrates whether ~1 A agreement is impressive or just what this system gives:
#   REF_DIR=.../ref_ligands DOCK_DIR=.../bace_ref_docked python3 pose_agreement.py
GEN_DIR = os.environ.get("REF_DIR", os.path.join(SELECTISAFE, "data/docking_inputs/ligands"))
DOCK_DIR = os.environ.get("DOCK_DIR", os.path.join(SELECTISAFE, "data/results/bace_docked_all"))
GOOD = 2.0


def load(path):
    """Read a single-molecule SDF without sanitizing -- several generated
    structures trip RDKit's valence rules, and geometry is all we need."""
    supplier = Chem.SDMolSupplier(path, sanitize=False, removeHs=False)
    mol = supplier[0] if len(supplier) else None
    if mol is None:
        return None
    try:
        mol.UpdatePropertyCache(strict=False)
    except Exception:
        pass
    # removeHs on the supplier is a no-op without sanitization, and the crystal
    # ligands carry explicit hydrogens while DiffDock returns heavy atoms only.
    # Strip them explicitly so the two sides are comparable.
    try:
        mol = Chem.RemoveAllHs(mol, sanitize=False)
    except Exception:
        pass
    return mol


def centroid(mol):
    conf = mol.GetConformer()
    n = mol.GetNumAtoms()
    xs = [conf.GetAtomPosition(i) for i in range(n)]
    return (sum(p.x for p in xs) / n, sum(p.y for p in xs) / n, sum(p.z for p in xs) / n)


def main():
    names = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(GEN_DIR, "*.sdf")))
    rows = []
    for name in names:
        gen = load(os.path.join(GEN_DIR, name + ".sdf"))
        dock_path = os.path.join(DOCK_DIR, name, "rank1.sdf")
        dock = load(dock_path) if os.path.exists(dock_path) else None
        if gen is None or dock is None:
            rows.append((name, None, None, None, "unreadable"))
            continue
        if gen.GetNumAtoms() != dock.GetNumAtoms():
            rows.append((name, None, None, None,
                         "atom count %d vs %d" % (gen.GetNumAtoms(), dock.GetNumAtoms())))
            continue

        cg, cd = centroid(gen), centroid(dock)
        dist = math.sqrt(sum((cg[i] - cd[i]) ** 2 for i in range(3)))
        try:
            inplace = rdMolAlign.CalcRMS(dock, gen)
        except Exception as e:
            inplace = None
        try:
            aligned = rdMolAlign.GetBestRMS(Chem.Mol(dock), Chem.Mol(gen))
        except Exception:
            aligned = None
        rows.append((name, inplace, aligned, dist, ""))

    print("=" * 74)
    print("POSE AGREEMENT: FLOWR designed pose vs DiffDock-L predicted pose")
    print("=" * 74)
    print("%-14s %11s %11s %11s  %s" % ("molecule", "rmsd_inplace", "rmsd_align", "centroid_d", "note"))
    for name, ip, al, d, note in rows:
        if ip is None:
            print("%-14s %11s %11s %11s  %s" % (name, "-", "-", "-", note))
        else:
            print("%-14s %11.2f %11.2f %11.2f  %s"
                  % (name, ip, al if al is not None else float("nan"), d,
                     "AGREE" if ip < GOOD else ""))

    ok = [r for r in rows if r[1] is not None]
    agree = [r for r in ok if r[1] < GOOD]
    print("\n" + "=" * 74)
    print("compared            : %d of %d" % (len(ok), len(rows)))
    print("agree (<%.1f A)      : %d  (%.0f%%)"
          % (GOOD, len(agree), 100.0 * len(agree) / len(ok) if ok else 0))
    if ok:
        vals = sorted(r[1] for r in ok)
        print("rmsd_inplace        : median %.2f   min %.2f   max %.2f"
              % (vals[len(vals) // 2], vals[0], vals[-1]))
        av = sorted(r[2] for r in ok if r[2] is not None)
        if av:
            print("rmsd_aligned        : median %.2f   min %.2f   max %.2f"
                  % (av[len(av) // 2], av[0], av[-1]))
        cd = sorted(r[3] for r in ok)
        print("centroid distance   : median %.2f   max %.2f A" % (cd[len(cd) // 2], cd[-1]))


if __name__ == "__main__":
    main()
