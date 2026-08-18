#!/usr/bin/env python3
"""
Build DiffDock inputs for the 50 molecules in Nithish/output/.

Reads the per-molecule SDFs already sitting there rather than re-splitting a
combined file, so the docking result names line up one-to-one with the
generation output: mol_07.sdf in, mol_07/ out.

Writes:
  Nithish/diffdock/input/diffdock_input.csv   the full 50-row specification
  <work>/tasks/task_N.csv                     one slice per array task

The gpu QOS allows 8 submitted jobs, so the set is dealt round-robin across 8
tasks; DiffDock takes a multi-row CSV natively, so each task loads the model
once and docks its share in a single pass.
"""

import csv
import glob
import os

NITHISH = "/scratch/g.murugan/Pfizer/selectisafe/Nithish"
PROTEIN = os.path.join(NITHISH, "input/4ZAU_protein.pdb")
MOL_DIR = os.path.join(NITHISH, "output")
DD_INPUT = os.path.join(NITHISH, "diffdock/input")
WORK = "/scratch/g.murugan/Pfizer/selectisafe/data/docking_inputs_nithish"
N_TASKS = 8
HEADER = ["complex_name", "protein_path", "ligand_description", "protein_sequence"]


def write_csv(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)


def main():
    os.makedirs(DD_INPUT, exist_ok=True)
    os.makedirs(os.path.join(WORK, "tasks"), exist_ok=True)

    mols = sorted(glob.glob(os.path.join(MOL_DIR, "mol_*.sdf")))
    if not mols:
        raise SystemExit("no mol_*.sdf found in %s" % MOL_DIR)

    rows = [[os.path.basename(p)[:-4], PROTEIN, p, ""] for p in mols]
    write_csv(os.path.join(DD_INPUT, "diffdock_input.csv"), rows)

    for t in range(N_TASKS):
        write_csv(os.path.join(WORK, "tasks", "task_%d.csv" % t),
                  [r for i, r in enumerate(rows) if i % N_TASKS == t])

    print("molecules      : %d" % len(rows))
    print("protein        : %s" % PROTEIN)
    print("input csv      : %s/diffdock_input.csv" % DD_INPUT)
    print("task csvs      : %s/tasks" % WORK)
    print("per task       : %s"
          % "/".join(str(sum(1 for i in range(len(rows)) if i % N_TASKS == t))
                     for t in range(N_TASKS)))


if __name__ == "__main__":
    main()
