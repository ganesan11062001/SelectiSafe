#!/usr/bin/env python3
"""Quick profile of the molecules FLOWR generated for the 4ZAU EGFR pocket."""

import re
from collections import Counter

SDF = ("/scratch/g.murugan/Pfizer/selectisafe/data/results/4zau_gen/"
       "samples_4ZAU_protein.sdf")
REF = "/scratch/g.murugan/Pfizer/selectisafe/4ZAU/4ZAU_ligand.sdf"
TERM = "$" * 4


def profile(path):
    text = open(path).read()
    recs = [r for r in text.split(TERM) if r.strip()]
    sizes, formulas = [], []
    for r in recs:
        lines = r.strip().split("\n")
        ci = [i for i, l in enumerate(lines) if "V2000" in l][0]
        n_atoms = int(lines[ci][0:3])
        els = [lines[ci + 1 + i][31:34].strip() for i in range(n_atoms)]
        heavy = [e for e in els if e != "H"]
        sizes.append(len(heavy))
        formulas.append("".join(k + str(v) for k, v in sorted(Counter(heavy).items())))
    tags = sorted(set(re.findall(r"^>\s*<([^>]+)>", text, re.M)))
    return recs, sizes, formulas, tags


def tag_values(path, tag):
    out = []
    for r in [x for x in open(path).read().split(TERM) if x.strip()]:
        lines = r.strip().split("\n")
        for i, l in enumerate(lines):
            if l.startswith(">") and "<%s>" % tag in l:
                out.append(float(lines[i + 1].strip()))
                break
    return out


def main():
    recs, sizes, formulas, tags = profile(SDF)
    _, ref_sizes, _, _ = profile(REF)

    print("molecules generated : %d of 50 requested" % len(recs))
    print("property tags       : %s" % ", ".join(tags))
    print()
    print("SIZE")
    print("  heavy atoms       : %d-%d (mean %.1f)" % (min(sizes), max(sizes), sum(sizes) / len(sizes)))
    print("  distinct sizes    : %d  %s" % (len(set(sizes)), sorted(set(sizes))))
    print("  reference ligand  : %d (osimertinib)" % ref_sizes[0])
    print("  -> BACE run was locked at one size; --sample_mol_sizes %s"
          % ("worked" if len(set(sizes)) > 1 else "did NOT vary size"))
    print()
    print("DIVERSITY")
    print("  distinct formulas : %d of %d" % (len(set(formulas)), len(formulas)))
    dup = [f for f, n in Counter(formulas).most_common(3) if n > 1]
    if dup:
        print("  most repeated     : %s" % ", ".join(
            "%s x%d" % (f, Counter(formulas)[f]) for f in dup))

    for tag in ("pic50", "pki", "pkd", "pec50"):
        if tag in tags:
            v = tag_values(SDF, tag)
            if v:
                vs = sorted(v)
                print()
                print("PREDICTED %s" % tag.upper())
                print("  n=%d  min %.2f  median %.2f  mean %.2f  max %.2f"
                      % (len(v), vs[0], vs[len(vs) // 2], sum(v) / len(v), vs[-1]))
            break

    for tag in tags:
        if "strain" in tag.lower():
            v = tag_values(SDF, tag)
            if v:
                vs = sorted(v)
                print()
                print("STRAIN ENERGY (%s)" % tag)
                print("  min %.1f  median %.1f  max %.1f" % (vs[0], vs[len(vs) // 2], vs[-1]))


if __name__ == "__main__":
    main()
