"""Deterministic signal extraction over a pipeline run's final_report.json.

Same role as `../auxilium-analyze/analyze/signals.py`: pure functions (no LLM)
that pull hard, computable facts out of the pipeline's own output, so the model
explains and prioritizes real numbers instead of inventing them. Deliberately
does *not* judge ADMET values against thresholds -- those column names and
"good" ranges aren't confirmed against admet-ai's actual output (see
`../prompts/admet_ai.md`), and asserting a false threshold to the model as
"authoritative" would be worse than not grounding it at all.
"""

from __future__ import annotations

from typing import Any


def extract_signals(report: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute grounded facts from a `final_report.json` list of candidate rows."""
    total = len(report)
    missing_smiles = [r["complex_name"] for r in report if not r.get("smiles")]
    docking_missing = [r["complex_name"] for r in report if r.get("docking_confidence") is None]
    retro_missing = [r["complex_name"] for r in report if not r.get("retrosynthesis")]
    admet_missing = [r["complex_name"] for r in report if not r.get("admet")]

    solved = [
        r["complex_name"] for r in report
        if isinstance(r.get("retrosynthesis"), dict) and r["retrosynthesis"].get("is_solved")
    ]
    unsolved = [
        r["complex_name"] for r in report
        if isinstance(r.get("retrosynthesis"), dict) and r["retrosynthesis"].get("is_solved") is False
    ]

    docked = [r for r in report if r.get("docking_confidence") is not None]
    best_docking = max(docked, key=lambda r: r["docking_confidence"]) if docked else None

    rescored = [r for r in report if r.get("gnina_cnn_score") is not None]
    best_gnina = max(rescored, key=lambda r: r["gnina_cnn_score"]) if rescored else None

    return {
        "total_candidates": total,
        "missing_smiles": missing_smiles,
        "docking_missing": docking_missing,
        "retrosynthesis_missing": retro_missing,
        "admet_missing": admet_missing,
        "retrosynthesis_solved": solved,
        "retrosynthesis_unsolved": unsolved,
        "best_docking": (
            {"complex_name": best_docking["complex_name"],
             "docking_confidence": best_docking["docking_confidence"]}
            if best_docking else None
        ),
        "best_gnina": (
            {"complex_name": best_gnina["complex_name"],
             "gnina_cnn_score": best_gnina["gnina_cnn_score"]}
            if best_gnina else None
        ),
    }


def signals_to_text(sig: dict[str, Any]) -> str:
    """Render signals as a compact block for the LLM prompt."""
    lines = [f"- total_candidates: {sig['total_candidates']}"]
    if sig["missing_smiles"]:
        lines.append(f"- missing_smiles ({len(sig['missing_smiles'])}): {sig['missing_smiles']}")
    if sig["docking_missing"]:
        lines.append(f"- docking_missing ({len(sig['docking_missing'])}): {sig['docking_missing']}")
    if sig["retrosynthesis_missing"]:
        lines.append(
            f"- retrosynthesis_missing ({len(sig['retrosynthesis_missing'])}): "
            f"{sig['retrosynthesis_missing']}"
        )
    if sig["admet_missing"]:
        lines.append(f"- admet_missing ({len(sig['admet_missing'])}): {sig['admet_missing']}")
    lines.append(
        f"- retrosynthesis_solved ({len(sig['retrosynthesis_solved'])}): "
        f"{sig['retrosynthesis_solved']}"
    )
    lines.append(
        f"- retrosynthesis_unsolved ({len(sig['retrosynthesis_unsolved'])}): "
        f"{sig['retrosynthesis_unsolved']}"
    )
    if sig["best_docking"]:
        lines.append(f"- best_docking (highest DiffDock confidence): {sig['best_docking']}")
    if sig["best_gnina"]:
        lines.append(f"- best_gnina (highest CNNscore): {sig['best_gnina']}")
    return "\n".join(lines)
