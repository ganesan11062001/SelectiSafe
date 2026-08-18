#!/usr/bin/env python3
"""
Compare the FLOWR-generated molecules against the known BACE inhibitors.

Two comparisons, which answer different questions and must not be conflated:

1. AFFINITY. FLOWR's predicted pIC50 for the generated set vs the *measured*
   pKd of the 36 benchmark actives (converted from their r_exp_dg). This is the
   activity question -- but it sets a prediction beside a measurement, so it
   says what the model claims, not what is true.

2. POSE CONFIDENCE. DiffDock's rank-1 confidence for both sets, produced by the
   identical pipeline. This is a like-for-like comparison, but confidence is a
   statement about pose geometry, not potency.

Writes a plain-text report so the numbers survive the run.
"""

import csv
import glob
import os
import re

SELECTISAFE = "/scratch/g.murugan/Pfizer/selectisafe"
GEN_MAN = os.path.join(SELECTISAFE, "data/docking_inputs/manifest.csv")
REF_MAN = os.path.join(SELECTISAFE, "data/docking_inputs/manifest_ref.csv")
GEN_DOCK = os.path.join(SELECTISAFE, "data/results/bace_docked_all")
REF_DOCK = os.path.join(SELECTISAFE, "data/results/bace_ref_docked")
REPORT = os.path.join(SELECTISAFE, "data/results/comparison_report.txt")


def rank1_confidence(out_dir, name):
    hits = glob.glob(os.path.join(out_dir, name, "rank1_confidence*.sdf"))
    if not hits:
        return None
    return float(re.search(r"confidence(-?[\d.]+)\.sdf$", hits[0]).group(1))


def stats(v):
    s = sorted(v)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {"n": n, "min": s[0], "med": med, "mean": sum(s) / n, "max": s[-1]}


def spearman(a, b):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6.0 * d2 / (n * (n * n - 1))


def main():
    gen = list(csv.DictReader(open(GEN_MAN)))
    ref = list(csv.DictReader(open(REF_MAN)))

    gen_aff = [float(r["pic50"]) for r in gen if r["pic50"] not in ("", "None")]
    ref_aff = [float(r["exp_pkd"]) for r in ref if r["exp_pkd"] not in ("", "None")]

    gen_conf, ref_conf = [], []
    gen_pairs, ref_pairs = [], []
    for r in gen:
        c = rank1_confidence(GEN_DOCK, r["complex_name"])
        if c is not None:
            gen_conf.append(c)
            gen_pairs.append((c, float(r["pic50"])))
    for r in ref:
        c = rank1_confidence(REF_DOCK, r["complex_name"])
        if c is not None:
            ref_conf.append(c)
            ref_pairs.append((c, float(r["exp_pkd"])))

    out = []
    def w(line=""):
        out.append(line)
        print(line)

    w("=" * 66)
    w("GENERATED vs KNOWN BACE INHIBITORS")
    w("=" * 66)
    w()
    w("1. AFFINITY  (predicted for generated, MEASURED for known)")
    w("-" * 66)
    w("%-34s %3s %6s %6s %6s %6s" % ("", "n", "min", "med", "mean", "max"))
    for lab, v in (("generated  FLOWR predicted pIC50", gen_aff),
                   ("known      measured pKd", ref_aff)):
        s = stats(v)
        w("%-34s %3d %6.2f %6.2f %6.2f %6.2f"
          % (lab, s["n"], s["min"], s["med"], s["mean"], s["max"]))
    sr = stats(ref_aff)
    w()
    w("generated above median known (%.2f) : %d/%d"
      % (sr["med"], sum(1 for x in gen_aff if x > sr["med"]), len(gen_aff)))
    w("generated above best   known (%.2f) : %d/%d"
      % (sr["max"], sum(1 for x in gen_aff if x > sr["max"]), len(gen_aff)))
    w()
    w("2. DOCKING POSE CONFIDENCE  (identical pipeline, like for like)")
    w("-" * 66)
    w("%-34s %3s %6s %6s %6s %6s" % ("", "n", "min", "med", "mean", "max"))
    for lab, v in (("generated", gen_conf), ("known actives", ref_conf)):
        if not v:
            w("%-34s  (no results yet)" % lab)
            continue
        s = stats(v)
        w("%-34s %3d %6.2f %6.2f %6.2f %6.2f"
          % (lab, s["n"], s["min"], s["med"], s["mean"], s["max"]))
    if ref_conf:
        sc = stats(ref_conf)
        w()
        w("generated above median known confidence (%.2f) : %d/%d"
          % (sc["med"], sum(1 for x in gen_conf if x > sc["med"]), len(gen_conf)))
    w()
    w("3. DO THE TWO SCORES AGREE?")
    w("-" * 66)
    if len(gen_pairs) > 2:
        w("generated : confidence vs predicted pIC50   rho = %+.3f (n=%d)"
          % (spearman([p[0] for p in gen_pairs], [p[1] for p in gen_pairs]),
             len(gen_pairs)))
    if len(ref_pairs) > 2:
        w("known     : confidence vs MEASURED pKd      rho = %+.3f (n=%d)"
          % (spearman([p[0] for p in ref_pairs], [p[1] for p in ref_pairs]),
             len(ref_pairs)))
        w()
        w("The second number is the one that matters: it is DiffDock confidence")
        w("tested against ground truth. It bounds how much any confidence-based")
        w("ranking of the generated set can be trusted.")

    with open(REPORT, "w") as fh:
        fh.write("\n".join(out) + "\n")
    print("\nreport written to %s" % REPORT)


if __name__ == "__main__":
    main()
