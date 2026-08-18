#!/usr/bin/env python3
"""
Turn the raw 4ZAU deposition into the two files FLOWR.root needs.

4ZAU is osimertinib (ligand YY3) bound to wild-type EGFR. FLOWR takes a protein
PDB plus a reference ligand, and uses the ligand to decide which residues form
the pocket -- so both have to be separated out of the deposited complex.

The ligand needs care. PDB HETATM records carry coordinates but no bond orders,
so a ligand read straight out of a PDB comes back with every bond single and the
aromatic rings gone. The fix is to take bond orders from the chemical component
definition (YY3_ideal.sdf, correct chemistry but idealised geometry) and map them
onto the crystallographic coordinates, giving a ligand that is both chemically
right and in the real binding pose.

Waters are dropped: FLOWR models the pocket from protein and ligand, and the four
ordered waters here are not part of that representation.

Runs inside the DiffDock container, which is where RDKit lives.
"""

import os
import sys

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")

HERE = os.path.dirname(os.path.abspath(__file__))
PDB_IN = os.path.join(HERE, "4ZAU.pdb")
IDEAL = os.path.join(HERE, "YY3_ideal.sdf")
PROTEIN_OUT = os.path.join(HERE, "4ZAU_protein.pdb")
LIGAND_OUT = os.path.join(HERE, "4ZAU_ligand.sdf")
LIG_CODE = "YY3"


def write_protein():
    kept = []
    for line in open(PDB_IN):
        if line.startswith(("ATOM", "TER")):
            kept.append(line)
        elif line.startswith("HETATM"):
            continue  # ligand and waters both go
    kept.append("END\n")
    with open(PROTEIN_OUT, "w") as fh:
        fh.writelines(kept)
    n = sum(1 for l in kept if l.startswith("ATOM"))
    res = {(l[21], l[22:27]) for l in kept if l.startswith("ATOM")}
    return n, len(res)


def ligand_block():
    """HETATM lines for the ligand, as a minimal PDB block RDKit can parse."""
    lines = [l for l in open(PDB_IN)
             if l.startswith("HETATM") and l[17:20].strip() == LIG_CODE]
    return "".join(lines) + "END\n", len(lines)


def write_ligand():
    block, n_atoms = ligand_block()
    crystal = Chem.MolFromPDBBlock(block, sanitize=False, removeHs=False)
    if crystal is None:
        raise SystemExit("could not parse %s out of the PDB" % LIG_CODE)

    template = Chem.SDMolSupplier(IDEAL, sanitize=True, removeHs=True)[0]
    if template is None:
        raise SystemExit("could not read the ideal SDF template")

    # The deposited ligand is heavy-atom only; match the template to it.
    template = Chem.RemoveHs(template)
    try:
        mol = AllChem.AssignBondOrdersFromTemplate(template, crystal)
    except Exception as e:
        raise SystemExit("bond order assignment failed: %s" % e)

    mol.SetProp("_Name", "YY3_osimertinib_4ZAU")
    with Chem.SDWriter(LIGAND_OUT) as w:
        w.write(mol)

    smiles = Chem.MolToSmiles(mol)
    arom = sum(1 for b in mol.GetBonds() if b.GetIsAromatic())
    return n_atoms, mol.GetNumAtoms(), arom, smiles, Chem.MolToSmiles(template)


def main():
    n_at, n_res = write_protein()
    print("protein : %s" % PROTEIN_OUT)
    print("          %d atoms, %d residues" % (n_at, n_res))

    n_pdb, n_mol, arom, smi, tmpl_smi = write_ligand()
    print("ligand  : %s" % LIGAND_OUT)
    print("          %d heavy atoms from the PDB, %d in the written molecule"
          % (n_pdb, n_mol))
    print("          %d aromatic bonds recovered" % arom)
    print("          SMILES   %s" % smi)
    print("          template %s" % tmpl_smi)
    print("          chemistry matches template: %s"
          % ("yes" if smi == tmpl_smi else "NO -- check this"))


if __name__ == "__main__":
    main()
