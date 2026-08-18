#!/usr/bin/env python3
"""
Prepare the known-BACE-inhibitor baseline for docking.

The generated molecules only mean something next to a reference. flowr_root's
examples ship 36 known BACE inhibitors from a Schrodinger free-energy benchmark
set, each tagged with r_exp_dg -- an *experimentally measured* binding free
energy in kcal/mol. Pushing them through the identical DiffDock path gives the
scale against which the generated set's pose confidences can be read.

Reuses the record splitter from prepare_docking_inputs.py so both sets are cut
apart by exactly the same code.
"""

import csv
import os
import re

from prepare_docking_inputs import (N_TASKS, PROTEIN, SELECTISAFE,
                                    split_records, title_of, write_csv)

SDF_IN = os.path.join(SELECTISAFE, "flowr_root_temp/examples/bace_ligands.sdf")
OUT_DIR = os.path.join(SELECTISAFE, "data/docking_inputs")
LIG_DIR = os.path.join(OUT_DIR, "ref_ligands")
TASK_DIR = os.path.join(OUT_DIR, "ref_tasks")

# dG = -2.303 * R * T * log10(K), so pKd = -dG / 1.3727 at 300 K. Converting to
# a p-scale puts the measured affinities in the same units as FLOWR's predicted
# pIC50 -- comparable in magnitude, though one is measured and one predicted.
KCAL_PER_LOG_UNIT = 1.3727


def exp_dg_of(record):
    m = re.search(r"^>\s*<r_exp_dg>.*\n(.+)$", record, re.MULTILINE)
    return float(m.group(1).strip()) if m else None


def main():
    os.makedirs(LIG_DIR, exist_ok=True)
    os.makedirs(TASK_DIR, exist_ok=True)

    manifest = []
    for idx, record in enumerate(split_records(SDF_IN)):
        name = "ref_mol_%02d" % idx
        lig_path = os.path.join(LIG_DIR, name + ".sdf")
        with open(lig_path, "w") as fh:
            fh.write(record)

        dg = exp_dg_of(record)
        manifest.append({
            "index": idx,
            "complex_name": name,
            "task": idx % N_TASKS,
            "source_title": title_of(record),
            "exp_dg": dg,
            "exp_pkd": None if dg is None else round(-dg / KCAL_PER_LOG_UNIT, 3),
            "ligand_sdf": lig_path,
        })

    for task in range(N_TASKS):
        rows = [[m["complex_name"], PROTEIN, m["ligand_sdf"], ""]
                for m in manifest if m["task"] == task]
        write_csv(os.path.join(TASK_DIR, "task_%d.csv" % task), rows)

    man_path = os.path.join(OUT_DIR, "manifest_ref.csv")
    with open(man_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)

    print("known inhibitors : %d" % len(manifest))
    print("ligand sdfs      : %s" % LIG_DIR)
    print("per-task csv     : %s" % TASK_DIR)
    print("manifest         : %s" % man_path)
    print("array range      : 0-%d" % (N_TASKS - 1))
    for task in range(N_TASKS):
        n = sum(1 for m in manifest if m["task"] == task)
        print("  task %d : %d mols" % (task, n))

    missing = [m["complex_name"] for m in manifest if m["exp_dg"] is None]
    if missing:
        print("WARNING: no r_exp_dg on: %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
