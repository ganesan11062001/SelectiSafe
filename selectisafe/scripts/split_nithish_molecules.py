#!/usr/bin/env python3
"""
Split the FLOWR output in Nithish/output/ into one SDF per molecule.

Records are copied through byte-for-byte -- the split is a text operation on the
"$$$$" terminator, so the predicted affinity tags on each molecule survive
unchanged.

Also writes molecules.csv listing each molecule's predicted affinities, so the
folder can be read without opening 50 files.
"""

import csv
import os
import re

OUT = "/scratch/g.murugan/Pfizer/selectisafe/Nithish/output"
SOURCES = [
    ("samples_4ZAU_protein.sdf", "molecules", "mol"),
    ("samples_4ZAU_protein_hs_optimized-hs.sdf", "molecules_hs_optimized", "mol"),
]
TAGS = ("pic50", "pki", "pkd", "pec50")


def split_records(path):
    with open(path) as fh:
        record = []
        for line in fh:
            record.append(line)
            if line.startswith("$$$$"):
                yield "".join(record)
                record = []
        if any(l.strip() for l in record):
            raise ValueError("trailing data after the last $$$$ in %s" % path)


def tag_value(record, tag):
    m = re.search(r"^>\s*<%s>.*\n(.+)$" % tag, record, re.MULTILINE)
    return float(m.group(1).strip()) if m else None


def main():
    summary = []
    for filename, dirname, stem in SOURCES:
        src = os.path.join(OUT, filename)
        if not os.path.exists(src):
            print("skip (missing): %s" % filename)
            continue
        dest = os.path.join(OUT, dirname)
        os.makedirs(dest, exist_ok=True)

        n = 0
        for idx, record in enumerate(split_records(src)):
            path = os.path.join(dest, "%s_%02d.sdf" % (stem, idx))
            with open(path, "w") as fh:
                fh.write(record)
            n += 1
            if dirname == "molecules":
                row = {"molecule": "%s_%02d" % (stem, idx)}
                row.update({t: tag_value(record, t) for t in TAGS})
                summary.append(row)
        print("%-44s -> %s/  (%d files)" % (filename, dirname, n))

    if summary:
        csv_path = os.path.join(OUT, "molecules.csv")
        with open(csv_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["molecule"] + list(TAGS))
            w.writeheader()
            w.writerows(summary)
        print("%-44s -> molecules.csv (%d rows)" % ("predicted affinities", len(summary)))

        vals = sorted(r["pic50"] for r in summary if r["pic50"] is not None)
        if vals:
            print("pic50: min %.2f  median %.2f  max %.2f"
                  % (vals[0], vals[len(vals) // 2], vals[-1]))


if __name__ == "__main__":
    main()
