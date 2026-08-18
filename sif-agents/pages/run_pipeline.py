"""Run Pipeline page: launch, monitor, and review runs, plus Ollama analysis.

Routed to by ../streamlit.py via st.navigation -- see that file for the nav
menu. Launch, monitor, and review runs of `run_pipeline.py` (FlowR -> DiffDock
-> GNINA -> AiZynthFinder -> ADMET-AI), then ask a local Ollama model to
summarize a run's `final_report.json` -- same "Analyze with Auxilium" idea as
`../../auxilium-analyze`, applied to this pipeline's own output instead of a
Slurm job log.

Follows the same file-as-message-bus convention `auxilium-analyze` uses (see
its `docs/architecture.md` S2): the pipeline runs as a detached background
process so it survives a page reload, and this UI only ever learns its state
by polling files under `runs/<run_id>/` -- `status.txt`, `pipeline.pid`,
`final_report.json` -- never in-memory process handles.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Belt-and-suspenders self-shadowing guard (see ../streamlit.py for the full
# reasoning) -- by the time a routed page runs, the entrypoint has already
# imported the real `streamlit` into sys.modules, which this import reuses
# regardless of sys.path, but this keeps the page independently runnable too
# (e.g. `streamlit run pages/run_pipeline.py` directly, for testing).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path = [p for p in sys.path if os.path.abspath(p or ".") not in (_HERE, _ROOT)]

import streamlit as st

sys.path.insert(0, _ROOT)

from llm import ollama_client, report_agent  # noqa: E402

ROOT = Path(_ROOT)
RUNS_ROOT = ROOT / "runs"


# ---- run bookkeeping (files are the source of truth, not session_state) ----

def run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id


def read_status(rdir: Path) -> str:
    status_file = rdir / "status.txt"
    if (rdir / "final_report.json").is_file():
        return "DONE"
    if not status_file.is_file():
        return "UNKNOWN"
    status = status_file.read_text().strip()
    if status == "RUNNING":
        pid_file = rdir / "pipeline.pid"
        if pid_file.is_file():
            try:
                os.kill(int(pid_file.read_text().strip()), 0)
            except (ProcessLookupError, ValueError):
                exit_code = rdir / "exit_code.txt"
                return "FAILED" if exit_code.is_file() and exit_code.read_text().strip() != "0" else "UNKNOWN"
    return status


def launch_run(run_id: str, pdb: str, ligand: str, n_molecules: int, n_gpus: int) -> None:
    rdir = run_dir(run_id)
    rdir.mkdir(parents=True, exist_ok=True)
    log_path = rdir / "pipeline.log"
    (rdir / "status.txt").write_text("RUNNING")

    cmd = (
        f"cd {ROOT} && "
        f"{sys.executable} run_pipeline.py --pdb {pdb} --ligand {ligand} "
        f"--run-id {run_id} --n-molecules {n_molecules} --n-gpus {n_gpus} "
        f"> {log_path} 2>&1; echo $? > {rdir}/exit_code.txt"
    )
    # start_new_session so the process survives this Streamlit session ending
    # or the page reloading -- the run's own files are the only state anyone
    # reads back, matching auxilium-analyze's "scratch is the message bus".
    proc = subprocess.Popen(["bash", "-c", cmd], start_new_session=True)
    (rdir / "pipeline.pid").write_text(str(proc.pid))


def existing_runs() -> list[str]:
    if not RUNS_ROOT.is_dir():
        return []
    return sorted((p.name for p in RUNS_ROOT.iterdir() if p.is_dir()), reverse=True)


# ---- UI ----

st.title("sif-agents: FlowR -> DiffDock -> GNINA -> AiZynthFinder -> ADMET-AI")

with st.sidebar:
    st.header("Launch a run")
    run_id_input = st.text_input("Run ID", value=time.strftime("run_%Y%m%dT%H%M%S"))
    pdb_input = st.text_input("Target protein PDB", value="../selectisafe/4ZAU/4ZAU_protein.pdb")
    ligand_input = st.text_input("Reference ligand SDF", value="../selectisafe/4ZAU/4ZAU_ligand.sdf")
    n_molecules_input = st.number_input("Molecules to generate", min_value=1, value=10)
    n_gpus_input = st.number_input("GPUs for generation", min_value=1, value=1)
    if st.button("Run pipeline", type="primary"):
        if run_dir(run_id_input).exists():
            st.error(f"runs/{run_id_input} already exists -- pick a different Run ID")
        else:
            launch_run(run_id_input, pdb_input, ligand_input, int(n_molecules_input), int(n_gpus_input))
            st.success(f"Launched {run_id_input} -- each stage submits its own SLURM job (sbatch --wait)")
            st.rerun()

    st.divider()
    st.caption(
        "Each stage submits its own SLURM job and blocks on `sbatch --wait`, "
        "so a full run can take from minutes to hours depending on queue wait. "
        "This page only reads files under runs/<run_id>/ -- reload any time."
    )

runs = existing_runs()
if not runs:
    st.info("No runs yet. Launch one from the sidebar.")
    st.stop()

selected = st.selectbox("Run", runs, index=0)
rdir = run_dir(selected)
status = read_status(rdir)

status_color = {"DONE": "green", "RUNNING": "orange", "FAILED": "red"}.get(status, "gray")
st.markdown(f"**Status:** :{status_color}[{status}]")

log_path = rdir / "pipeline.log"
if status == "RUNNING" and log_path.is_file():
    with st.expander("Live pipeline log (tail)", expanded=True):
        lines = log_path.read_text(errors="replace").splitlines()
        st.code("\n".join(lines[-40:]) or "(no output yet)")
    if st.button("Refresh"):
        st.rerun()

if status == "FAILED":
    st.error("The pipeline failed. Log:")
    if log_path.is_file():
        st.code(log_path.read_text(errors="replace")[-4000:])

report_path = rdir / "final_report.json"
if report_path.is_file():
    report = json.loads(report_path.read_text())
    st.subheader(f"Results ({len(report)} candidates)")
    st.dataframe(
        [
            {
                "complex_name": r["complex_name"],
                "smiles": r["smiles"],
                "docking_confidence": r["docking_confidence"],
                "gnina_cnn_score": r.get("gnina_cnn_score"),
                "gnina_minimized_affinity": r.get("gnina_minimized_affinity"),
                "retrosynthesis_solved": (r.get("retrosynthesis") or {}).get("is_solved"),
            }
            for r in report
        ],
        use_container_width=True,
    )
    with st.expander("Raw final_report.json"):
        st.json(report)
    st.page_link("pages/results_gallery.py", label="View 2D/3D structures and the filter funnel ->", icon="🧪")

    st.subheader("Ollama analysis")
    ollama_ready = ollama_client.is_ready()
    st.caption(
        f"Ollama: {'reachable' if ollama_ready else 'not running -- will be started on demand'} "
        f"(model: {ollama_client.DEFAULT_MODEL})"
    )
    if st.button("Analyze with Ollama"):
        with st.spinner("Starting Ollama (cold start can take ~20-30s) and summarizing..."):
            try:
                result = report_agent.analyze(report, rdir)
            except Exception as e:
                st.error(f"Analysis failed: {e}")
            else:
                st.session_state["llm_result"] = result

    result = st.session_state.get("llm_result")
    if result:
        st.markdown(f"**Summary:** {result['summary']}")
        if result["top_candidates"]:
            st.markdown("**Top candidates:** " + ", ".join(result["top_candidates"]))
        if result["concerns"]:
            st.markdown("**Concerns:**")
            for c in result["concerns"]:
                st.markdown(f"- {c}")

        col1, col2 = st.columns(2)
        feedback_path = Path(result["trace_dir"]) / "feedback.json"
        if col1.button("👍 Useful"):
            feedback_path.write_text(json.dumps({"rating": "up", "ts": time.time()}))
            st.toast("Thanks for the feedback")
        if col2.button("👎 Not useful"):
            feedback_path.write_text(json.dumps({"rating": "down", "ts": time.time()}))
            st.toast("Thanks for the feedback")
else:
    st.caption("final_report.json not written yet.")
