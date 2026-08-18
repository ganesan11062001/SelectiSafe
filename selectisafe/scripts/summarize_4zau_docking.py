#!/usr/bin/env python3
"""
Docking summary for the EGFR/4ZAU set, stdlib only.

Includes control_osimertinib -- the crystal ligand re-docked against its own
structure. Because its true pose is known, its RMSD is an accuracy measure, not
an agreement measure: it says whether DiffDock works on this target at all.

RMSD here assumes the docked SDF preserves the input atom order, which DiffDock
does, and is not symmetry-corrected. For a symmetric molecule that can overstate
the error slightly; it never understates it, so a good number is trustworthy.
"""

import csv
import glob
import math
import os
import re

SELECTISAFE = "/scratch/g.murugan/Pfizer/selectisafe"
DOCK = os.path.join(SELECTISAFE, "data/results/4zau_docked")
LIGS = os.path.join(SELECTISAFE, "data/docking_inputs_4zau/ligands")
MANIFEST = os.path.join(SELECTISAFE, "data/docking_inputs_4zau/manifest.csv")
CONTROL = "control_osimertinib"


def coords(path):
    """Heavy-atom coordinates from the first record of an SDF."""
    lines = open(path).read().split("\n")
    ci = next(i for i, l in enumerate(lines) if "V2000" in l)
    n = int(lines[ci][0:3])
    out = []
    for i in range(n):
        l = lines[ci + 1 + i]
        el = l[31:34].strip()
        if el != "H":
            out.append((float(l[0:10]), float(l[10:20]), float(l[20:30])))
    return out


def centroid(c):
    n = len(c)
    return tuple(sum(p[i] for p in c) / n for i in range(3))


def d(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def top_conf(name):
    for p in glob.glob(os.path.join(DOCK, name, "rank1_confidence*.sdf")):
        return float(re.search(r"confidence(-?[\d.]+)\.sdf$", p).group(1))
    return None


def stats(v):
    v = sorted(v)
    n = len(v)
    return v[0], v[n // 2], sum(v) / n, v[-1]


def main():
    man = {r["complex_name"]: r for r in csv.DictReader(open(MANIFEST))}

    rows = []
    for name in sorted(man):
        conf = top_conf(name)
        ref = os.path.join(LIGS, name + ".sdf")
        docked = os.path.join(DOCK, name, "rank1.sdf")
        rmsd = cdist = None
        if os.path.exists(ref) and os.path.exists(docked):
            a, b = coords(ref), coords(docked)
            if len(a) == len(b):
                rmsd = math.sqrt(sum(d(a[i], b[i]) ** 2 for i in range(len(a))) / len(a))
                cdist = d(centroid(a), centroid(b))
        rows.append((name, conf, rmsd, cdist))

    ctrl = [r for r in rows if r[0] == CONTROL][0]
    gen = [r for r in rows if r[0] != CONTROL]

    print("=" * 66)
    print("CONTROL -- osimertinib re-docked against its own crystal structure")
    print("=" * 66)
    print("  confidence        : %.2f" % ctrl[1])
    print("  RMSD to crystal   : %.2f A" % ctrl[2])
    print("  centroid distance : %.2f A" % ctrl[3])
    verdict = ("PASS -- DiffDock reproduces the known pose"
               if ctrl[2] is not None and ctrl[2] < 2.0
               else "FAIL -- DiffDock cannot reproduce a pose we already know")
    print("  verdict           : %s" % verdict)

    print()
    print("=" * 66)
    print("GENERATED MOLECULES (n=%d)" % len(gen))
    print("=" * 66)
    c = [r[1] for r in gen if r[1] is not None]
    print("  confidence  min %.2f   median %.2f   mean %.2f   max %.2f" % stats(c))
    print("  above the control's %.2f : %d of %d"
          % (ctrl[1], sum(1 for x in c if x > ctrl[1]), len(c)))

    ag = [r[2] for r in gen if r[2] is not None]
    if ag:
        print()
        print("  FLOWR pose vs DiffDock pose (agreement, not accuracy)")
        print("  rmsd        min %.2f   median %.2f   mean %.2f   max %.2f" % stats(ag))
        print("  agree <2 A  : %d of %d" % (sum(1 for x in ag if x < 2.0), len(ag)))

    print()
    print("TOP 10 BY DOCKING CONFIDENCE")
    print("  %-16s %7s %8s %8s" % ("molecule", "conf", "rmsd", "pIC50"))
    for name, conf, rmsd, _ in sorted(gen, key=lambda r: -(r[1] or -99))[:10]:
        pic = man[name].get("pic50") or ""
        print("  %-16s %7.2f %8s %8s"
              % (name, conf, "%.2f" % rmsd if rmsd else "-",
                 "%.2f" % float(pic) if pic else "-"))


if __name__ == "__main__":
    main()
