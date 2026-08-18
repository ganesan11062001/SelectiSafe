#!/usr/bin/env python3
"""
SelectiSafe two-tier filter: FLOWR affinity AND DiffDock pose confidence.

Tier 1 (FLOWR)   keep pIC50 > 6.5 and a chemically valid structure
Tier 2 (DiffDock) keep rank-1 confidence > -1.0
Combined          keep only molecules passing both

Validity is checked here rather than assumed. FLOWR's --filter_valid_unique
already screened the batch, but the affinity-prediction path was observed
earlier to hand back a molecule whose formula differed from the one supplied,
so the check is repeated on the files that actually exist.

Writes, under Nithish/aizynthfinder/:
  input/candidates.smi   SMILES, one per line -- AiZynthFinder's input format
  input/candidates.csv   molecule, SMILES, pIC50, confidence
  molecules/             the passing SDFs
  filtering_report.txt   the summary

Runs inside the DiffDock container, which is where RDKit lives.
"""

import csv
import glob
import os
import re
from datetime import datetime

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

NITHISH = "/scratch/g.murugan/Pfizer/selectisafe/Nithish"
MOL_DIR = os.path.join(NITHISH, "output")
DOCK_DIR = os.path.join(NITHISH, "diffdock/output")
OUT = os.path.join(NITHISH, "aizynthfinder")

PIC50_MIN = 6.5
CONF_MIN = -1.0


def pic50_of(path):
    text = open(path).read()
    m = re.search(r"^>\s*<pic50>.*\n(.+)$", text, re.MULTILINE)
    return float(m.group(1).strip()) if m else None


def smiles_of(path):
    """SMILES if the structure is chemically valid, else None."""
    mol = Chem.SDMolSupplier(path, sanitize=True, removeHs=True)[0]
    return Chem.MolToSmiles(mol) if mol is not None else None


def confidence_of(name):
    for p in glob.glob(os.path.join(DOCK_DIR, name, "rank1_confidence*.sdf")):
        return float(re.search(r"confidence(-?[\d.]+)\.sdf$", p).group(1))
    return None


def main():
    os.makedirs(os.path.join(OUT, "input"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "molecules"), exist_ok=True)

    rows = []
    for path in sorted(glob.glob(os.path.join(MOL_DIR, "mol_*.sdf"))):
        name = os.path.basename(path)[:-4]
        pic50 = pic50_of(path)
        smiles = smiles_of(path)
        conf = confidence_of(name)
        rows.append({
            "molecule": name,
            "path": path,
            "pic50": pic50,
            "smiles": smiles,
            "confidence": conf,
            "valid": smiles is not None,
            "pass_flowr": (pic50 is not None and pic50 > PIC50_MIN
                           and smiles is not None),
            "pass_diffdock": conf is not None and conf > CONF_MIN,
        })

    for r in rows:
        r["pass_both"] = r["pass_flowr"] and r["pass_diffdock"]

    keep = [r for r in rows if r["pass_both"]]
    keep.sort(key=lambda r: -r["pic50"])

    # Deliverables for AiZynthFinder
    with open(os.path.join(OUT, "input/candidates.smi"), "w") as fh:
        for r in keep:
            fh.write("%s %s\n" % (r["smiles"], r["molecule"]))

    with open(os.path.join(OUT, "input/candidates.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["molecule", "smiles", "pic50", "diffdock_confidence"])
        for r in keep:
            w.writerow([r["molecule"], r["smiles"], "%.3f" % r["pic50"],
                        "%.2f" % r["confidence"]])

    for r in keep:
        dst = os.path.join(OUT, "molecules", r["molecule"] + ".sdf")
        with open(r["path"]) as src, open(dst, "w") as out:
            out.write(src.read())

    # Full audit trail: every molecule, every verdict.
    with open(os.path.join(OUT, "all_molecules_scored.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["molecule", "pic50", "diffdock_confidence", "valid",
                    "pass_flowr", "pass_diffdock", "pass_both"])
        for r in rows:
            w.writerow([r["molecule"],
                        "%.3f" % r["pic50"] if r["pic50"] is not None else "",
                        "%.2f" % r["confidence"] if r["confidence"] is not None else "",
                        r["valid"], r["pass_flowr"], r["pass_diffdock"], r["pass_both"]])

    report(rows, keep)


def report(rows, keep):
    n = len(rows)
    n_valid = sum(1 for r in rows if r["valid"])
    n_flowr = sum(1 for r in rows if r["pass_flowr"])
    n_dock = sum(1 for r in rows if r["pass_diffdock"])
    n_docked = sum(1 for r in rows if r["confidence"] is not None)

    L = []
    a = L.append
    a("===== SELECTISAFE TIER 2 FILTERING REPORT =====")
    a("")
    a("Target      : EGFR, PDB 4ZAU (osimertinib complex)")
    a("Generated   : FLOWR.root, Slurm job 9254354")
    a("Docked      : DiffDock-L, Slurm job 9258960")
    a("Generated   : %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    a("")
    a("TIER 1 (FLOWR) Results:")
    a("- Total molecules generated: %d" % n)
    a("- Chemically valid: %d" % n_valid)
    a("- Passed pIC50 > %.1f: %d" % (PIC50_MIN, n_flowr))
    a("- Failed pIC50 filter: %d" % (n - n_flowr))
    a("")
    a("TIER 2 (DiffDock) Results:")
    a("- Docked molecules: %d" % n_docked)
    a("- Passed confidence > %.1f: %d" % (CONF_MIN, n_dock))
    a("- Failed confidence filter: %d" % (n_docked - n_dock))
    a("")
    a("COMBINED (passed BOTH filters): %d of %d" % (len(keep), n))
    a("")
    a("-" * 62)
    a("SELECTED CANDIDATES -- forwarded to AiZynthFinder")
    a("-" * 62)
    a("%-10s %8s %12s" % ("molecule", "pIC50", "confidence"))
    for r in keep:
        a("%-10s %8.2f %12.2f" % (r["molecule"], r["pic50"], r["confidence"]))
    a("")
    a("-" * 62)
    a("REJECTED")
    a("-" * 62)
    a("%-10s %8s %12s  %s" % ("molecule", "pIC50", "confidence", "reason"))
    for r in rows:
        if r["pass_both"]:
            continue
        why = []
        if not r["valid"]:
            why.append("invalid structure")
        if r["pic50"] is not None and r["pic50"] <= PIC50_MIN:
            why.append("pIC50 <= %.1f" % PIC50_MIN)
        if r["confidence"] is None:
            why.append("not docked")
        elif r["confidence"] <= CONF_MIN:
            why.append("confidence <= %.1f" % CONF_MIN)
        a("%-10s %8s %12s  %s"
          % (r["molecule"],
             "%.2f" % r["pic50"] if r["pic50"] is not None else "-",
             "%.2f" % r["confidence"] if r["confidence"] is not None else "-",
             "; ".join(why)))

    text = "\n".join(L) + "\n"
    with open(os.path.join(OUT, "filtering_report.txt"), "w") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
