"""Local Ollama client: same runtime, proxy handling, and readiness check as
`../auxilium-analyze/analyze/script.sh` + `analyze_logs.py` -- reused rather
than reinvented, since that pattern is already proven working on this cluster.

Three things carried over on purpose:

* **Shared runtime.** `/projects/rc/projects/Auxilium` ships the model weights
  and (preferably) a native `ollama` binary; this is a dependency, not our code.
* **Proxy bypass.** Explorer compute nodes set an HTTP proxy; Ollama listens on
  localhost, so both the subprocess env and every HTTP request must bypass it
  explicitly, or requests get silently routed through the proxy and fail.
* **Readiness is polled, never assumed.** `wait_ready()` polls `/api/tags`
  instead of a blind sleep, exactly like the analyzer does before its first call.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request

AUX = "/projects/rc/projects/Auxilium"
OLLAMA_BIN = os.environ.get("OLLAMA_BIN", f"{AUX}/ollama_local/bin/ollama")
OLLAMA_SIF = os.environ.get("OLLAMA_SIF", f"{AUX}/ollama.sif")
OLLAMA_MODELS = os.environ.get("OLLAMA_MODELS", f"{AUX}/ollama_models")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
REQUEST_TIMEOUT = 300
TEMPERATURE = 0.2

_NO_PROXY_ENV = {
    "no_proxy": "localhost,127.0.0.1,::1",
    "NO_PROXY": "localhost,127.0.0.1,::1",
}


class OllamaError(RuntimeError):
    pass


def _opener():
    """Bypass any proxy the cluster injects via env -- Ollama is on localhost."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def is_ready(timeout: float = 2.0) -> bool:
    try:
        with _opener().open(f"{OLLAMA_HOST}/api/tags", timeout=timeout):
            return True
    except Exception:
        return False


def start_background() -> subprocess.Popen | None:
    """Launch `ollama serve` if it isn't already answering. Returns the Popen
    handle (so the caller can keep/kill it), or None if one was already running.

    Prefers the native binary (matches the migration in auxilium-analyze's
    `script.sh`: apptainer was the original path, native is the current default),
    falls back to the apptainer image if only that exists.
    """
    if is_ready():
        return None

    env = dict(os.environ)
    env.update(_NO_PROXY_ENV)
    env.pop("http_proxy", None)
    env.pop("https_proxy", None)
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    env["OLLAMA_MODELS"] = OLLAMA_MODELS

    if os.path.isfile(OLLAMA_BIN) and os.access(OLLAMA_BIN, os.X_OK):
        lib_dir = os.path.join(os.path.dirname(OLLAMA_BIN), "..", "lib", "ollama")
        env["LD_LIBRARY_PATH"] = lib_dir + ":" + env.get("LD_LIBRARY_PATH", "")
        return subprocess.Popen([OLLAMA_BIN, "serve"], env=env)

    if os.path.isfile(OLLAMA_SIF):
        return subprocess.Popen(
            [
                "apptainer", "exec", "--nv",
                "-B", "/projects:/projects,/home:/home,/scratch:/scratch",
                OLLAMA_SIF, "bash", "-c", "unset http_proxy https_proxy; ollama serve",
            ],
            env=env,
        )

    raise OllamaError(f"no Ollama runtime found: neither {OLLAMA_BIN} nor {OLLAMA_SIF} exists")


def wait_ready(timeout_s: int = 60) -> bool:
    for _ in range(timeout_s):
        if is_ready():
            return True
        time.sleep(1)
    return False


def model_digest(model: str = DEFAULT_MODEL) -> str | None:
    try:
        with _opener().open(f"{OLLAMA_HOST}/api/tags", timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        for m in body.get("models", []):
            name = m.get("name", "")
            if name == model or name.startswith(model + ":"):
                return (m.get("digest") or "")[:16] or None
    except Exception:
        return None
    return None


def chat(messages: list[dict], model: str = DEFAULT_MODEL, fmt: str | None = "json",
          timeout: int = REQUEST_TIMEOUT) -> tuple[str, dict]:
    """One POST to /api/chat. Returns (content, meta) -- meta mirrors the
    token/timing fields analyze_logs.py records into its trace."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    }
    if fmt:
        payload["format"] = fmt
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with _opener().open(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    wall_ms = int((time.time() - t0) * 1000)

    def _ms(key):
        v = body.get(key)
        return int(v / 1e6) if isinstance(v, (int, float)) else None

    meta = {
        "model": body.get("model"),
        "done_reason": body.get("done_reason"),
        "wall_ms": wall_ms,
        "total_ms": _ms("total_duration"),
        "load_ms": _ms("load_duration"),
        "prompt_eval_count": body.get("prompt_eval_count"),
        "eval_count": body.get("eval_count"),
        "eval_ms": _ms("eval_duration"),
    }
    if meta["eval_count"] and meta["eval_ms"]:
        meta["tokens_per_sec"] = round(meta["eval_count"] / (meta["eval_ms"] / 1000.0), 2)

    content = body.get("message", {}).get("content", "")
    if not content:
        raise OllamaError(f"empty response from Ollama: {body}")
    return content, meta
