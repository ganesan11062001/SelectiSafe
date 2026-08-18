#!/usr/bin/env python3
"""Confidence summary for the Nithish DiffDock run."""

import glob
import os
import re

OUT = "/scratch/g.murugan/Pfizer/selectisafe/Nithish/diffdock/output"


def top_conf(d):
    for p in glob.glob(os.path.join(d, "rank1_confidence*.sdf")):
        return float(re.search(r"confidence(-?[\d.]+)\.sdf$", p).group(1))
    return None


def main():
    rows = []
    for d in sorted(glob.glob(os.path.join(OUT, "mol_*"))):
        n_poses = len(glob.glob(os.path.join(d, "rank*_confidence*.sdf")))
        rows.append((os.path.basename(d), top_conf(d), n_poses))

    ok = [r for r in rows if r[1] is not None]
    v = sorted(r[1] for r in ok)
    n = len(v)
    print("molecules docked : %d" % len(rows))
    print("poses per molecule: %s" % sorted({r[2] for r in rows}))
    print("confidence       : min %.2f  median %.2f  mean %.2f  max %.2f"
          % (v[0], v[n // 2], sum(v) / n, v[-1]))
    print("positive confidence: %d of %d" % (sum(1 for x in v if x > 0), n))
    print()
    print("TOP 10 BY CONFIDENCE")
    for name, c, _ in sorted(ok, key=lambda r: -r[1])[:10]:
        print("  %-10s %6.2f" % (name, c))


if __name__ == "__main__":
    main()
