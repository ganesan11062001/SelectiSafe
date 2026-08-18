"""Ollama-backed summary of a pipeline run's final_report.json.

Same shape as `../auxilium-analyze/analyze/analyze_logs.py`: a fact pipeline
with a language model at the end of it, not a chatbot over raw data.
`report_signals.py` computes grounded facts first; the model's job is to
explain and prioritize those facts, not discover them. Every call writes a
trace -- prompt, raw response, signals, token counts -- to the same per-run,
never-overwritten layout auxilium-analyze uses, for the same reason: without
the exact prompt, a bad answer can't be attributed to a bad model vs. a bad
prompt vs. a fact the signals step missed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from llm import ollama_client
from llm.report_signals import extract_signals, signals_to_text

PROMPT_VERSION = "p1"

SYSTEM_PROMPT = (
    "You are a computational drug-discovery analyst reviewing the output of an "
    "automated hit-generation pipeline: FlowR generates candidate ligands into a "
    "target's binding pocket, DiffDock scores docking poses, GNINA rescores the "
    "best pose with a CNN-based binding estimate, AiZynthFinder checks whether a "
    "retrosynthetic route to each candidate was found, and ADMET-AI predicts "
    "pharmacokinetic/safety properties. "
    "You are given DETERMINISTIC FINDINGS computed directly from the pipeline's "
    "own output (treat these as authoritative -- do not contradict them, e.g. "
    "do not name a top candidate other than the one in best_docking/best_gnina "
    "without explaining why), plus the full per-candidate JSON rows. "
    "Recommend a short list of the most promising candidates by complex_name, "
    "reasoning about docking confidence, GNINA rescoring, retrosynthetic "
    "feasibility, and any ADMET values that stand out -- but do not assert an "
    "ADMET property is good or bad unless the column name makes the direction "
    "unambiguous (e.g. obviously a probability of a toxicity endpoint). "
    "If a candidate has no retrosynthesis route (is_solved: false) or is missing "
    "SMILES/docking/ADMET data, say so rather than silently ranking it. "
    "Respond with ONLY a JSON object of the form "
    '{"summary": "<one paragraph>", "top_candidates": ["<complex_name>", ...], '
    '"concerns": ["<concern 1>", "<concern 2>"]}. Do not include any text outside the JSON.'
)


class ReportAgentError(RuntimeError):
    pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def build_messages(report: list[dict[str, Any]], findings_text: str) -> list[dict[str, str]]:
    """The exact prompt sent to the model. Pure function, so a trace's prompt
    can be reconstructed from `report` + `findings_text` alone."""
    user = (
        "=== deterministic findings (authoritative) ===\n"
        f"{findings_text}\n\n"
        "=== final_report.json (per-candidate rows) ===\n"
        f"{json.dumps(report, indent=2)}\n"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def normalize(content: str) -> dict[str, Any]:
    data = json.loads(content)
    summary = str(data.get("summary", "")).strip()
    top = data.get("top_candidates", [])
    concerns = data.get("concerns", [])
    if isinstance(top, str):
        top = [top]
    if isinstance(concerns, str):
        concerns = [concerns]
    top = [str(t).strip() for t in top if str(t).strip()]
    concerns = [str(c).strip() for c in concerns if str(c).strip()]
    if not summary and not top and not concerns:
        raise ReportAgentError(f"model returned no usable content: {content!r}")
    return {"summary": summary, "top_candidates": top, "concerns": concerns}


def write_trace(trace_dir: Path, trace: dict, messages=None, raw_response=None) -> Path | None:
    """Never raises -- losing a trace must not turn a good analysis into a failure."""
    if not trace_dir:
        return None
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        if messages is not None:
            (trace_dir / "prompt.json").write_text(json.dumps(messages, indent=2))
        if raw_response is not None:
            (trace_dir / "response.txt").write_text(raw_response)
        path = trace_dir / "trace.json"
        path.write_text(json.dumps(trace, indent=2))
        return path
    except Exception:
        return None


def analyze(
    report: list[dict[str, Any]],
    run_dir: str | Path,
    model: str = ollama_client.DEFAULT_MODEL,
) -> dict[str, Any]:
    """Summarize `report` with Ollama, writing a trace under `run_dir/llm_runs/<id>/`.

    Returns the normalized {"summary", "top_candidates", "concerns"} dict.
    Raises ReportAgentError (or OllamaError) on failure -- callers decide how
    to surface that, same as analyze_logs.py's non-zero exit convention.
    """
    run_dir = Path(run_dir)
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{os.getpid()}"
    trace_dir = run_dir / "llm_runs" / run_id

    sig = extract_signals(report)
    findings_text = signals_to_text(sig)
    messages = build_messages(report, findings_text)

    trace = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "signals": sig,
        "request": {
            "prompt_chars": sum(len(m["content"]) for m in messages),
            "prompt_sha256": _sha256(json.dumps(messages, sort_keys=True)),
        },
        "outcome": {"stage": "start", "error": None},
    }

    def finish(stage, error=None, raw=None):
        trace["outcome"] = {"stage": stage, "error": None if error is None else str(error)}
        trace["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_trace(trace_dir, trace, messages, raw)

    try:
        ollama_client.start_background()
        if not ollama_client.wait_ready(60):
            raise ollama_client.OllamaError("Ollama did not become ready within 60s")
        trace["model_digest"] = ollama_client.model_digest(model)
        raw, llm_meta = ollama_client.chat(messages, model=model)
        trace["llm"] = llm_meta
    except Exception as e:
        finish("llm_call", e)
        raise ReportAgentError(f"Ollama call failed: {e}") from e

    try:
        result = normalize(raw)
    except Exception as e:
        finish("normalize", e, raw)
        raise ReportAgentError(f"could not parse model response: {e}") from e

    trace["result"] = result
    finish("ok", raw=raw)
    return {**result, "run_id": run_id, "trace_dir": str(trace_dir)}
