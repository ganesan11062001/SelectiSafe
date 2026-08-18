#!/usr/bin/env python3
"""
Compare the 4-seed re-scoring of the generated molecules against the single-seed
values they were given at generation time.

The calibration run showed FLOWR's affinity head moves by ~0.31 log units (up to
0.77) across seeds for a fixed input, and that its correlation with measured
affinity swings between +0.09 and +0.41 depending on the seed alone. The 29
generated molecules carried single-seed scores, so this asks the practical
question: how much of the original ranking was real, and which molecules are
actually separated once the seed noise is averaged out?

Ordering is verified by heavy-atom formula, as in analyze_affinity_baseline.py --
predict_from_pdb names every output record after the protein, not the ligand.
"""

import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_affinity_baseline import (SEEDS, heavy_formula, pearson, records,
                                       spearman, tag_value)

SELECTISAFE = "/scratch/g.murugan/Pfizer/selectisafe"
GEN_SDF = os.path.join(SELECTISAFE, "data/results/bace_gen/samples_bace_protein.sdf")
AFF_ROOT = os.path.join(SELECTISAFE, "data/results/bace_gen_affinity")
MANIFEST = os.path.join(SELECTISAFE, "data/docking_inputs/manifest.csv")


def main():
    src = records(GEN_SDF)
    src_formulas = [heavy_formula(r) for r in src]
    n = len(src)

    manifest = list(csv.DictReader(open(MANIFEST)))
    names = [m["complex_name"] for m in manifest]
    single = [float(m["pic50"]) for m in manifest]
    assert len(manifest) == n, "manifest and generated SDF disagree in length"

    per_seed = {}
    for seed in SEEDS:
        path = os.path.join(AFF_ROOT, "seed_%d" % seed, "gen_lig_with_aff.sdf")
        recs = records(path)
        if len(recs) != n:
            raise SystemExit("seed %d: %d records, expected %d" % (seed, len(recs), n))
        bad = [i for i, r in enumerate(recs) if heavy_formula(r) != src_formulas[i]]
        if bad:
            raise SystemExit("seed %d: output order differs from input at %s"
                             % (seed, bad[:10]))
        per_seed[seed] = [tag_value(r, "pic50") for r in recs]

    mean4 = [sum(per_seed[s][i] for s in SEEDS) / len(SEEDS) for i in range(n)]
    spread = [max(per_seed[s][i] for s in SEEDS) - min(per_seed[s][i] for s in SEEDS)
              for i in range(n)]

    def stat(v):
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
        return m, sd, min(v), max(v)

    print("=" * 70)
    print("GENERATED MOLECULES: single seed vs 4-seed mean")
    print("=" * 70)
    print("%-22s mean %.2f  sd %.2f  min %.2f  max %.2f" % (("single seed",) + stat(single)))
    print("%-22s mean %.2f  sd %.2f  min %.2f  max %.2f" % (("4-seed mean",) + stat(mean4)))
    shift = [mean4[i] - single[i] for i in range(n)]
    print("\nper-molecule shift : mean %+.2f   largest %+.2f log units"
          % (sum(shift) / n, max(shift, key=abs)))
    print("agreement          : Spearman %+.3f   Pearson %+.3f"
          % (spearman(single, mean4), pearson(single, mean4)))

    print("\nSEED SPREAD ON THIS SET")
    print("  mean %.3f   max %.3f log units" % (sum(spread) / n, max(spread)))

    print("\nRANK CHANGES (top 10 by 4-seed mean)")
    order4 = sorted(range(n), key=lambda i: -mean4[i])
    order1 = sorted(range(n), key=lambda i: -single[i])
    rank1 = {idx: r for r, idx in enumerate(order1, 1)}
    print("  %-14s %6s %6s %7s %8s" % ("molecule", "4seed", "1seed", "spread", "rank was"))
    for r, i in enumerate(order4[:10], 1):
        print("  %-14s %6.2f %6.2f %7.2f %8d" % (names[i], mean4[i], single[i],
                                                 spread[i], rank1[i]))

    # A gap between two molecules only means something if it exceeds the noise.
    top = order4[0]
    sep = [i for i in order4[1:] if mean4[top] - mean4[i] > spread[top]]
    print("\n  molecules the top candidate (%s) is separated from by more than"
          % names[top])
    print("  its own seed spread (%.2f): %d of %d" % (spread[top], len(sep), n - 1))


if __name__ == "__main__":
    main()
