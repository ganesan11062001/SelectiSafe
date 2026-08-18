"""2D/3D molecule rendering for the Results Gallery page.

2D depictions come from RDKit (`Draw.MolToImage`), rendered straight from
SMILES -- this is the pipeline's own designed structure, not a docked pose, so
2D is the honest representation (no 3D coordinates are implied by a SMILES
string). 3D viewing is for an actual docked/generated pose file (an SDF with
real coordinates) and uses py3Dmol, embedded via its own generated HTML/JS --
there is no Streamlit-native 3D molecule viewer, and py3Dmol's `_make_html()`
output is a self-contained iframe body meant for exactly this kind of embedding.
"""

from __future__ import annotations

from pathlib import Path

from PIL.Image import Image
from rdkit import Chem
from rdkit.Chem import Draw


def depict_2d(smiles: str, size: tuple[int, int] = (300, 300)) -> Image | None:
    """PIL image of `smiles`'s 2D structure, or None if it doesn't parse."""
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Draw.MolToImage(mol, size=size)


def depict_2d_from_sdf(sdf_path: str | Path, size: tuple[int, int] = (300, 300)) -> Image | None:
    """PIL image of the first molecule in an SDF file, laid out fresh in 2D.

    The SDF's own coordinates are 3D (a generated pose or structure); drawing
    those directly projects them flat and looks wrong, so 2D coordinates are
    computed from the parsed graph instead of using the file's conformer.
    """
    path = Path(sdf_path)
    if not path.is_file():
        return None
    supplier = Chem.SDMolSupplier(str(path))
    mol = next((m for m in supplier if m is not None), None)
    if mol is None:
        return None
    from rdkit.Chem import AllChem

    AllChem.Compute2DCoords(mol)
    return Draw.MolToImage(mol, size=size)


def view_3d_html(
    struct_path: str | Path, height: int = 400, width: int = 400, fmt: str | None = None
) -> str | None:
    """Self-contained HTML embedding a py3Dmol stick-and-sphere view of `struct_path`.

    `fmt` is inferred from the file extension (`.pdb` -> pdb, otherwise sdf) if
    not given explicitly. Returns None if the file is missing or empty -- the
    caller decides how to degrade (e.g. fall back to the 2D depiction instead).
    """
    path = Path(struct_path)
    if not path.is_file():
        return None
    block = path.read_text()
    if not block.strip():
        return None
    if fmt is None:
        fmt = "pdb" if path.suffix.lower() == ".pdb" else "sdf"

    import py3Dmol

    view = py3Dmol.view(width=width, height=height)
    view.addModel(block, fmt)
    if fmt == "pdb":
        view.setStyle({"cartoon": {"color": "spectrum"}})
    else:
        view.setStyle({"stick": {}, "sphere": {"scale": 0.25}})
    view.zoomTo()
    return view._make_html()
