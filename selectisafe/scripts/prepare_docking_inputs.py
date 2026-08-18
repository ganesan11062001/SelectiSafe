#!/usr/bin/env python3
"""
Split the FLOWR-generated multi-molecule SDF into one file per molecule and
write a matching one-row DiffDock CSV for each.

Why this exists
---------------
FLOWR writes an entire generation batch into a single SDF. DiffDock reads one
molecule per input row -- given a path to a multi-record SDF it silently keeps
only the first record. Docking the whole batch therefore needs the set split
apart, one molecule per docking job.

Stdlib only: SDF records are separated by a "$$$$" line, so the split is a text
operation and each record is copied through byte-for-byte (tags such as the
predicted pIC50 survive intact).
"""

import csv
import os
import re

SELECTISAFE = "/scratch/g.murugan/Pfizer/selectisafe"

# Defaults prepare the BACE generated set. Override for another target -- the
# EGFR/4ZAU run, for instance:
#   SDF_IN=.../4zau_gen/samples_4ZAU_protein.sdf \
#   PROTEIN=.../4ZAU/4ZAU_protein.pdb \
#   OUT_DIR=.../data/docking_inputs_4zau \
#   EXTRA_SDF=.../4ZAU/4ZAU_ligand.sdf  python3 prepare_docking_inputs.py
SDF_IN = os.environ.get(
    "SDF_IN", os.path.join(SELECTISAFE, "data/results/bace_gen/samples_bace_protein.sdf"))
PROTEIN = os.environ.get(
    "PROTEIN", os.path.join(SELECTISAFE, "flowr_root_temp/examples/bace_protein.pdb"))
OUT_DIR = os.environ.get("OUT_DIR", os.path.join(SELECTISAFE, "data/docking_inputs"))
NAME = os.environ.get("NAME", "bace_mol")

# Optional single-molecule SDF appended to the set as a self-docking control.
# Re-docking a crystal ligand against its own structure is the only way to know
# whether DiffDock works on this target at all: if it cannot reproduce a pose we
# already know, nothing it says about the generated molecules is worth reading.
EXTRA_SDF = os.environ.get("EXTRA_SDF", "")
EXTRA_NAME = os.environ.get("EXTRA_NAME", "control_xtal")

LIG_DIR = os.path.join(OUT_DIR, "ligands")
CSV_DIR = os.path.join(OUT_DIR, "csv")
TASK_DIR = os.path.join(OUT_DIR, "tasks")

# The `gpu` QOS allows 8 submitted jobs per user (4 running), so one array task
# per molecule is not submittable. Molecules are dealt round-robin across this
# many tasks instead, and each task hands DiffDock a multi-row CSV -- which also
# means the model loads once per task rather than once per molecule.
N_TASKS = 8


def split_records(path):
    """Yield each SDF record (including its trailing $$$$ line) as text."""
    with open(path) as fh:
        record = []
        for line in fh:
            record.append(line)
            if line.startswith("$$$$"):
                yield "".join(record)
                record = []
        if any(l.strip() for l in record):
            raise ValueError("trailing data after the last $$$$ terminator")


def title_of(record):
    """First line of an SDF record is its title; may legitimately be blank."""
    return record.split("\n", 1)[0].strip()


def pic50_of(record):
    # RDKit writes the tag line as ">  <pic50>  (1) " -- the trailing index is
    # part of the line, so the value starts on the line after it.
    m = re.search(r"^>\s*<pic50>.*\n(.+)$", record, re.MULTILINE)
    return float(m.group(1).strip()) if m else None


def write_csv(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["complex_name", "protein_path",
                    "ligand_description", "protein_sequence"])
        w.writerows(rows)


def main():
    os.makedirs(LIG_DIR, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(TASK_DIR, exist_ok=True)

    sources = [(NAME, r) for r in split_records(SDF_IN)]
    if EXTRA_SDF:
        extra = list(split_records(EXTRA_SDF))
        if len(extra) != 1:
            raise SystemExit("EXTRA_SDF must hold exactly one molecule, found %d"
                             % len(extra))
        sources.append((EXTRA_NAME, extra[0]))

    manifest = []
    for idx, (stem, record) in enumerate(sources):
        # Keep the index in the name: it is what ties a result directory back to
        # a row of the source SDF.
        name = "%s_%02d" % (stem, idx) if stem != EXTRA_NAME else EXTRA_NAME
        lig_path = os.path.join(LIG_DIR, name + ".sdf")
        csv_path = os.path.join(CSV_DIR, name + ".csv")

        with open(lig_path, "w") as fh:
            fh.write(record)

        write_csv(csv_path, [[name, PROTEIN, lig_path, ""]])

        manifest.append({
            "index": idx,
            "complex_name": name,
            "task": idx % N_TASKS,
            "source_title": title_of(record),
            "pic50": pic50_of(record),
            "ligand_sdf": lig_path,
        })

    # One CSV per array task, holding every molecule assigned to it.
    for task in range(N_TASKS):
        rows = [[m["complex_name"], PROTEIN, m["ligand_sdf"], ""]
                for m in manifest if m["task"] == task]
        write_csv(os.path.join(TASK_DIR, "task_%d.csv" % task), rows)

    man_path = os.path.join(OUT_DIR, "manifest.csv")
    with open(man_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)

    print("molecules split : %d" % len(manifest))
    print("ligand sdfs     : %s" % LIG_DIR)
    print("per-molecule csv: %s" % CSV_DIR)
    print("per-task csv    : %s" % TASK_DIR)
    print("manifest        : %s" % man_path)
    print("array range     : 0-%d" % (N_TASKS - 1))
    for task in range(N_TASKS):
        names = [m["complex_name"] for m in manifest if m["task"] == task]
        print("  task %d : %d mols (%s)" % (task, len(names), " ".join(names)))
    missing = [m["complex_name"] for m in manifest if m["pic50"] is None]
    if missing:
        print("WARNING: no pic50 tag on: %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
