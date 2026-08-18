"""Browse Files: raw output files for a run or the reference dataset.

Routed to by ../streamlit.py via st.navigation. The Results Gallery page shows
a curated, parsed summary (funnel + gallery); this page is the complement --
a plain file tree and preview over the actual files on disk, for when you
want to see exactly what's there (a README, a raw CSV, one specific SDF)
rather than a derived view of it.

Scoped to two kinds of root on purpose, not an arbitrary path field: this
project's own `runs/<run_id>/` directories, and the reference example under
`../../selectisafe/Nithish/`. Browsing your own scratch data doesn't need
protecting against itself, but there's no reason to expose a free-text path
box when the two roots people actually want are already known.
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path = [p for p in sys.path if os.path.abspath(p or ".") not in (_HERE, _ROOT)]

import streamlit as st

sys.path.insert(0, _ROOT)

from pathlib import Path

from viz import data_sources, molecule_render

st.title("Browse Files")

roots: dict[str, Path] = {}
if data_sources.nithish_available():
    roots["Reference example: EGFR / osimertinib (4ZAU)"] = data_sources.NITHISH_ROOT
for run_id in data_sources.list_pipeline_runs():
    roots[f"Pipeline run: {run_id}"] = data_sources.RUNS_ROOT / run_id

if not roots:
    st.info("Nothing to browse yet -- no completed runs, and the reference dataset isn't present.")
    st.stop()

root_label = st.selectbox("Root", list(roots.keys()))
root = roots[root_label]
st.caption(f"`{root}`")

# ---- build the file list ----

files: list[tuple[str, Path, int]] = []
for dirpath, _dirnames, filenames in os.walk(root):
    for name in filenames:
        p = Path(dirpath) / name
        try:
            size = p.stat().st_size
        except OSError:
            continue
        files.append((str(p.relative_to(root)), p, size))
files.sort(key=lambda f: f[0])

search = st.text_input("Filter by filename (substring)", value="")
if search:
    files = [f for f in files if search.lower() in f[0].lower()]

st.caption(f"{len(files)} files")
if not files:
    st.info("No files match.")
    st.stop()

rel_paths = [f[0] for f in files]
chosen_rel = st.selectbox("File", rel_paths)
chosen_path = next(p for rel, p, _ in files if rel == chosen_rel)
chosen_size = next(size for rel, _, size in files if rel == chosen_rel)
st.caption(f"{chosen_size:,} bytes")

suffix = chosen_path.suffix.lower()
text_suffixes = {".md", ".txt", ".log", ".yml", ".yaml", ".py", ".sh", ".erb", ".csv"}

# ---- preview ----

if suffix == ".md":
    st.markdown(chosen_path.read_text(errors="replace"))

elif suffix == ".csv":
    with open(chosen_path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    st.dataframe(rows, use_container_width=True)

elif suffix == ".json":
    st.json(json.loads(chosen_path.read_text()))

elif chosen_path.name.endswith(".json.gz"):
    with gzip.open(chosen_path, "rt") as fh:
        st.json(json.load(fh))

elif suffix in (".sdf", ".mol"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**2D**")
        img = molecule_render.depict_2d_from_sdf(chosen_path)
        if img is not None:
            st.image(img, use_container_width=True)
        else:
            st.caption("Could not parse a molecule from this file.")
    with col2:
        st.markdown("**3D**")
        html = molecule_render.view_3d_html(chosen_path)
        if html:
            st.components.v1.html(html, height=400)
        else:
            st.caption("Could not render a 3D view.")
    with st.expander("Raw file contents"):
        st.code(chosen_path.read_text(errors="replace"))

elif suffix == ".pdb":
    html = molecule_render.view_3d_html(chosen_path)
    if html:
        st.components.v1.html(html, height=500)
    else:
        st.caption("Could not render a 3D view.")
    with st.expander("Raw file contents"):
        st.code(chosen_path.read_text(errors="replace")[:20000])

elif suffix in text_suffixes:
    st.code(chosen_path.read_text(errors="replace")[:50000])

else:
    st.caption(f"No preview available for `{suffix or '(no extension)'}` files.")
    if chosen_size < 200_000:
        try:
            st.code(chosen_path.read_text(errors="replace")[:20000])
        except Exception:
            pass
