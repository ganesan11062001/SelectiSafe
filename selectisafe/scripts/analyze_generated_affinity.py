#!/usr/bin/env python3
"""
Re-score of the 29 generated molecules across 4 seeds.

The pIC50 values FLOWR wrote at generation time came from a single seed. The
baseline calibration showed the affinity head moves by ~0.31 log units (up to
0.77) on the same molecule when only the seed changes, so a single-seed value is
one draw rather than an answer. This averages four seeds and, more importantly,
reports how far apart two molecules must be before the difference outlives that
noise.

Matching is positional (predict_from_pdb writes the protein's name into every
record) and is verified against the source SDF by heavy-atom formula, same as
the baseline analysis.
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
TAG = "pic50"

# Measured on the known inhibitors: mean absolute error of the affinity head
# against laboratory values. Differences smaller than this are not resolvable
# regardless of how stable the seeds are.
BASELINE_MAE = 0.66


def main():
    src = records(GEN_SDF)
    src_formulas = [heavy_formula(r) for r in src]
    n = len(src)

    manifest = list(csv.DictReader(open(MANIFEST)))
    assert len(manifest) == n, "manifest and generated SDF disagree in length"
    names = [m["complex_name"] for m in manifest]
    single_seed = [float(m["pic50"]) for m in manifest]

    # Per (molecule, seed) validity. The prediction path occasionally hands back a
    # rebuilt ligand whose heavy-atom formula differs from the input -- that is a
    # score for a different molecule, so it is dropped rather than averaged in.
    per_seed = {}
    rejected = []
    for seed in SEEDS:
        path = os.path.join(AFF_ROOT, "seed_%d" % seed, "gen_lig_with_aff.sdf")
        recs = records(path)
        if len(recs) != n:
            raise SystemExit("seed %d: %d records, expected %d" % (seed, len(recs), n))
        vals = []
        for i, r in enumerate(recs):
            if heavy_formula(r) != src_formulas[i]:
                rejected.append((i, seed, src_formulas[i], heavy_formula(r)))
                vals.append(None)
            else:
                vals.append(tag_value(r, TAG))
        per_seed[seed] = vals

    def valid(i):
        return [per_seed[s][i] for s in SEEDS if per_seed[s][i] is not None]

    n_used = [len(valid(i)) for i in range(n)]
    mean = [sum(valid(i)) / len(valid(i)) for i in range(n)]
    spread = [max(valid(i)) - min(valid(i)) for i in range(n)]
    sd = [math.sqrt(sum((v - mean[i]) ** 2 for v in valid(i)) / (len(valid(i)) - 1))
          if len(valid(i)) > 1 else float("nan") for i in range(n)]

    if rejected:
        print("DROPPED -- prediction returned a different molecule than supplied:")
        for i, seed, want, got in rejected:
            print("  %s seed %-5d supplied %s, scored %s"
                  % (names[i], seed, want, got))
        print()

    print("=" * 68)
    print("GENERATED MOLECULES -- 4-SEED RE-SCORE  (n=%d)" % n)
    print("=" * 68)

    m_all = sum(mean) / n
    print("4-seed mean pIC50 : %.2f  (range %.2f - %.2f)" % (m_all, min(mean), max(mean)))
    print("original 1 seed   : %.2f  (range %.2f - %.2f)"
          % (sum(single_seed) / n, min(single_seed), max(single_seed)))
    print("agreement with the original single-seed scores:")
    print("  Spearman %+.3f   Pearson %+.3f"
          % (spearman(mean, single_seed), pearson(mean, single_seed)))
    shift = [mean[i] - single_seed[i] for i in range(n)]
    print("  mean shift %+.2f   largest single shift %+.2f"
          % (sum(shift) / n, max(shift, key=abs)))

    print("\nSEED NOISE ON THIS SET")
    print("  mean spread %.3f   max spread %.3f log units"
          % (sum(spread) / n, max(spread)))

    print("\nRANKED BY 4-SEED MEAN")
    print("  %-14s %7s %6s %7s %7s %5s"
          % ("molecule", "mean", "sd", "spread", "1-seed", "n"))
    order = sorted(range(n), key=lambda i: -mean[i])
    for i in order:
        print("  %-14s %7.2f %6.2f %7.2f %7.2f %5d"
              % (names[i], mean[i], sd[i], spread[i], single_seed[i], n_used[i]))

    # How many molecules are actually distinguishable from the best one? Two
    # predictions closer than the model's own error are not telling us anything.
    best = mean[order[0]]
    within = [i for i in order if best - mean[i] < BASELINE_MAE]
    print("\nRESOLUTION")
    print("  model error against lab values (MAE) : %.2f log units" % BASELINE_MAE)
    print("  molecules within that of the top     : %d of %d" % (len(within), n))
    print("  -> the top %d are not distinguishable from each other" % len(within))


if __name__ == "__main__":
    main()
