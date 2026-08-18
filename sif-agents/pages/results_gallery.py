"""Results Gallery: funnel view + molecule cards with 2D/3D structure viewing.

Routed to by ../streamlit.py via st.navigation -- see that file for the nav
menu. (An earlier version relied on Streamlit's automatic `pages/` directory
discovery; that stopped being visible in a long-running session because its
file-watcher doesn't reliably pick up new files over a network filesystem
like /scratch, so navigation is now built explicitly instead of inferred.)

Two data sources, one page: this project's own pipeline runs, or the
reference EGFR/osimertinib (4ZAU) example in `../../selectisafe/Nithish/`
(see `viz/data_sources.py` for what each one actually has data for -- the
reference example never got a retrosynthesis or ADMET pass, and that's shown
as "--", not invented).
"""

from __future__ import annotations

import os
import sys

# Same self-shadowing guard as ../streamlit.py: belt-and-suspenders here too,
# even though by the time a page runs the main script has already imported
# the real `streamlit` into sys.modules (which subsequent imports reuse
# regardless of sys.path) -- see that file's comment for the full reasoning.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path = [p for p in sys.path if os.path.abspath(p or ".") not in (_HERE, _ROOT)]

import streamlit as st

sys.path.insert(0, _ROOT)

import altair as alt

from viz import data_sources, molecule_render

# Status colors (fixed, never themed) from the project's dataviz reference
# palette -- reserved for pass/fail state, distinct from any categorical use.
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"

st.title("Results Gallery")

# ---- data source ----

source = st.radio(
    "Data source",
    ["My pipeline runs", "Reference example: EGFR / osimertinib (4ZAU)"],
    horizontal=True,
)

if source == "My pipeline runs":
    runs = data_sources.list_pipeline_runs()
    if not runs:
        st.info("No completed runs yet -- launch one from the main page.")
        st.stop()
    run_id = st.selectbox("Run", runs)
    candidates = data_sources.load_pipeline_run(run_id)
    st.caption(f"{len(candidates)} candidates from `runs/{run_id}/final_report.json`.")
else:
    if not data_sources.nithish_available():
        st.error("Reference dataset not found under ../selectisafe/Nithish/")
        st.stop()
    candidates = data_sources.load_nithish_reference()
    st.caption(
        f"{len(candidates)} candidates from a colleague's manual FlowR/DiffDock run on "
        "EGFR (PDB 4ZAU, osimertinib). Retrosynthesis and ADMET were never run for this "
        "set, so those fields show as —. **Read the caveats before trusting the "
        "numbers**: DiffDock failed its own self-docking control on this target "
        "(3.36 Å RMSD vs. a 2 Å threshold, likely because osimertinib binds "
        "covalently and DiffDock can't model that) -- see "
        "`../selectisafe/Nithish/diffdock/README.md`."
    )

if not candidates:
    st.info("No candidates to show.")
    st.stop()

# ---- funnel thresholds ----

st.subheader("Filter funnel")
col_a, col_b = st.columns(2)
pic50_cut = col_a.slider(
    "Tier 1: predicted pIC50 >", min_value=0.0, max_value=10.0, value=6.5, step=0.1
)
conf_cut = col_b.slider(
    "Tier 2: docking confidence >", min_value=-3.0, max_value=3.0, value=-1.0, step=0.1
)
st.caption(
    "Defaults (6.5 / −1.0) match the thresholds used in the reference example's own "
    "filtering report -- a documented precedent, not a validated cutoff. Adjust freely."
)

with_pic50 = [c for c in candidates if c["pic50"] is not None]
with_conf = [c for c in candidates if c["docking_confidence"] is not None]
pass_t1 = [c for c in with_pic50 if c["pic50"] > pic50_cut]
pass_t2 = [c for c in with_conf if c["docking_confidence"] > conf_cut]
pass_both_ids = {c["id"] for c in pass_t1} & {c["id"] for c in pass_t2}
pass_both = [c for c in candidates if c["id"] in pass_both_ids]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total candidates", len(candidates))
m2.metric("Passed Tier 1 (pIC50)", len(pass_t1), f"of {len(with_pic50)} scored")
m3.metric("Passed Tier 2 (docking)", len(pass_t2), f"of {len(with_conf)} scored")
m4.metric("Passed both", len(pass_both))

funnel_rows = [
    {"stage": "Generated", "status": "total", "count": len(candidates)},
    {"stage": "Tier 1: pIC50", "status": "pass", "count": len(pass_t1)},
    {"stage": "Tier 1: pIC50", "status": "fail", "count": len(with_pic50) - len(pass_t1)},
    {"stage": "Tier 2: docking", "status": "pass", "count": len(pass_t2)},
    {"stage": "Tier 2: docking", "status": "fail", "count": len(with_conf) - len(pass_t2)},
    {"stage": "Combined", "status": "pass", "count": len(pass_both)},
    {"stage": "Combined", "status": "fail", "count": len(candidates) - len(pass_both)},
]
chart = (
    alt.Chart(alt.Data(values=funnel_rows))
    .mark_bar(cornerRadiusEnd=4)
    .encode(
        y=alt.Y("stage:N", sort=["Generated", "Tier 1: pIC50", "Tier 2: docking", "Combined"], title=None),
        x=alt.X("count:Q", title="Molecules"),
        color=alt.Color(
            "status:N",
            scale=alt.Scale(domain=["total", "pass", "fail"], range=["#86b6ef", GOOD, CRITICAL]),
            legend=alt.Legend(title="Status"),
        ),
        tooltip=["stage:N", "status:N", "count:Q"],
    )
    .properties(height=180)
)
st.altair_chart(chart, use_container_width=True)

# ---- gallery ----

st.subheader("Candidates")
show_pass_only = st.checkbox("Show only candidates that passed both tiers")
sort_key = st.selectbox(
    "Sort by", ["pIC50 (desc)", "Docking confidence (desc)", "ID"]
)

rows = pass_both if show_pass_only else candidates
if sort_key == "pIC50 (desc)":
    rows = sorted(rows, key=lambda c: (c["pic50"] is not None, c["pic50"]), reverse=True)
elif sort_key == "Docking confidence (desc)":
    rows = sorted(
        rows, key=lambda c: (c["docking_confidence"] is not None, c["docking_confidence"]), reverse=True
    )
else:
    rows = sorted(rows, key=lambda c: c["id"])

CARDS_PER_ROW = 4
for i in range(0, len(rows), CARDS_PER_ROW):
    cols = st.columns(CARDS_PER_ROW)
    for col, cand in zip(cols, rows[i : i + CARDS_PER_ROW]):
        with col.container(border=True):
            st.markdown(f"**{cand['id']}**")
            img = molecule_render.depict_2d(cand["smiles"]) if cand["smiles"] else None
            if img is not None:
                st.image(img, use_container_width=True)
            else:
                st.caption("(no 2D structure available)")

            passed = cand["id"] in pass_both_ids
            st.markdown(
                f":{'green' if passed else 'red'}[{'✓ passed both tiers' if passed else '✗ did not pass both tiers'}]"
            )
            st.caption(f"pIC50: {cand['pic50']:.2f}" if cand["pic50"] is not None else "pIC50: —")
            st.caption(
                f"Docking confidence: {cand['docking_confidence']:.2f}"
                if cand["docking_confidence"] is not None
                else "Docking confidence: —"
            )
            if cand["gnina_cnn_score"] is not None:
                st.caption(f"GNINA CNNscore: {cand['gnina_cnn_score']:.3f}")
            if cand["retro_solved"] is not None:
                st.caption(f"Retrosynthesis solved: {'yes' if cand['retro_solved'] else 'no'}")

# ---- 3D pose viewer (one at a time -- rendering all of these eagerly is slow) ----

st.subheader("3D pose viewer")
viewable = [c for c in rows if c["pose_sdf"] or c["ligand_sdf"]]
if not viewable:
    st.caption("No 3D structures available for the current filter/sort selection.")
else:
    chosen_id = st.selectbox("Molecule", [c["id"] for c in viewable])
    chosen = next(c for c in viewable if c["id"] == chosen_id)
    sdf_path = chosen["pose_sdf"] or chosen["ligand_sdf"]
    label = "docked pose" if chosen["pose_sdf"] else "generated 3D structure (not docked)"
    st.caption(f"Showing: {label} -- `{sdf_path}`")
    html = molecule_render.view_3d_html(sdf_path)
    if html:
        st.components.v1.html(html, height=420)
    else:
        st.warning(f"Could not load {sdf_path}")
