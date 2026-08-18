#!/usr/bin/env python3
"""
Compare FLOWR's predicted affinities for the 36 known BACE inhibitors against
their laboratory-measured binding free energies.

FLOWR designed the generated molecules and also scored them, so its predicted
pIC50 on that set cannot be checked against anything. These 36 compounds break
the circle: FLOWR did not design them, and their affinities were measured
experimentally. Whether its predictions track those measurements decides whether
its scores on the generated set are evidence or decoration.

Ordering caveat
---------------
predict_from_pdb writes every output record with the protein's name rather than
the ligand's, so predictions cannot be matched to compounds by name. They are
matched by position, and that assumption is *verified* here by comparing heavy
atom formulas element-wise against the input file. If the dataloader reordered
anything, the check fails loudly rather than silently scrambling the comparison.
"""

import csv
import math
import os
from collections import Counter

SELECTISAFE = "/scratch/g.murugan/Pfizer/selectisafe"
REF_SDF = os.path.join(SELECTISAFE, "flowr_root_temp/examples/bace_ligands.sdf")
AFF_ROOT = os.path.join(SELECTISAFE, "data/results/bace_ref_affinity")
MANIFEST = os.path.join(SELECTISAFE, "data/docking_inputs/manifest_ref.csv")
SEEDS = [2, 42, 512, 1000]
TAG = "pic50"


def records(path):
    return [r for r in open(path).read().split("$$$$") if r.strip()]


def heavy_formula(record):
    lines = record.strip().split("\n")
    counts = [i for i, l in enumerate(lines) if "V2000" in l]
    if not counts:
        return None
    ci = counts[0]
    n_atoms = int(lines[ci][0:3])
    els = [lines[ci + 1 + i][31:34].strip() for i in range(n_atoms)]
    els = [e for e in els if e != "H"]
    return "".join(k + str(v) for k, v in sorted(Counter(els).items()))


def tag_value(record, tag):
    lines = record.strip().split("\n")
    for i, l in enumerate(lines):
        if l.startswith(">") and "<%s>" % tag in l:
            return float(lines[i + 1].strip())
    return None


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    den = math.sqrt(sum((x[i] - mx) ** 2 for i in range(n))
                    * sum((y[i] - my) ** 2 for i in range(n)))
    return num / den if den else float("nan")


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def main():
    ref = records(REF_SDF)
    ref_formulas = [heavy_formula(r) for r in ref]

    manifest = list(csv.DictReader(open(MANIFEST)))
    names = [m["source_title"] for m in manifest]
    exp_pkd = [float(m["exp_pkd"]) for m in manifest]
    assert len(manifest) == len(ref), "manifest and reference SDF disagree in length"

    per_seed = {}
    for seed in SEEDS:
        path = os.path.join(AFF_ROOT, "seed_%d" % seed, "gen_lig_with_aff.sdf")
        recs = records(path)
        if len(recs) != len(ref):
            raise SystemExit("seed %d: %d records, expected %d"
                             % (seed, len(recs), len(ref)))
        # Verify positional correspondence before trusting the mapping.
        bad = [i for i, r in enumerate(recs) if heavy_formula(r) != ref_formulas[i]]
        if bad:
            raise SystemExit(
                "seed %d: output order does not match input at positions %s -- "
                "predictions cannot be matched to compounds" % (seed, bad[:10]))
        per_seed[seed] = [tag_value(r, TAG) for r in recs]

    n = len(ref)
    mean_pred = [sum(per_seed[s][i] for s in SEEDS) / len(SEEDS) for i in range(n)]
    spread = [max(per_seed[s][i] for s in SEEDS) - min(per_seed[s][i] for s in SEEDS)
              for i in range(n)]

    print("=" * 66)
    print("FLOWR AFFINITY vs LABORATORY MEASUREMENT  (36 known BACE inhibitors)")
    print("=" * 66)
    print("predicted tag : %s (mean of seeds %s)" % (TAG, SEEDS))
    print("ground truth  : exp_pkd, derived from measured r_exp_dg\n")

    print("CORRELATION WITH MEASURED AFFINITY")
    for seed in SEEDS:
        print("  seed %-5d Spearman %+.3f   Pearson %+.3f"
              % (seed, spearman(per_seed[seed], exp_pkd), pearson(per_seed[seed], exp_pkd)))
    print("  %-10s Spearman %+.3f   Pearson %+.3f"
          % ("MEAN", spearman(mean_pred, exp_pkd), pearson(mean_pred, exp_pkd)))

    err = [mean_pred[i] - exp_pkd[i] for i in range(n)]
    mae = sum(abs(e) for e in err) / n
    rmse = math.sqrt(sum(e * e for e in err) / n)
    bias = sum(err) / n
    print("\nABSOLUTE ACCURACY (log units)")
    print("  MAE %.2f   RMSE %.2f   mean bias %+.2f" % (mae, rmse, bias))
    print("  predicted range %.2f-%.2f   measured range %.2f-%.2f"
          % (min(mean_pred), max(mean_pred), min(exp_pkd), max(exp_pkd)))

    print("\nSEED-TO-SEED STABILITY (same molecule, same settings)")
    print("  mean spread %.3f   max spread %.3f log units"
          % (sum(spread) / n, max(spread)))

    print("\nMOST AND LEAST POTENT, AS MEASURED")
    order = sorted(range(n), key=lambda i: -exp_pkd[i])
    print("  %-12s %8s %8s" % ("compound", "measured", "FLOWR"))
    for i in order[:5]:
        print("  %-12s %8.2f %8.2f" % (names[i], exp_pkd[i], mean_pred[i]))
    print("  ...")
    for i in order[-5:]:
        print("  %-12s %8.2f %8.2f" % (names[i], exp_pkd[i], mean_pred[i]))


if __name__ == "__main__":
    main()
