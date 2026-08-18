"""Submit one Apptainer command as a SLURM job and block until it finishes.

Each agent assembles a single `apptainer exec ...` command string and hands it
here. `sbatch --wait` does the waiting: Slurm blocks in the foreground and
returns the submitted job's own exit code as its own, so a failure surfaces as
a normal non-zero return from `subprocess.run` instead of needing a separate
polling loop.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class JobFailed(RuntimeError):
    """Raised when the SLURM job's container command exited non-zero."""


@dataclass
class SlurmJob:
    name: str
    command: str
    log_dir: Path
    partition: str
    account: str | None = None
    time: str = "02:00:00"
    cpus: int = 4
    mem: str = "16GB"
    gres: str | None = None
    exclude: str | None = None
    chdir: Path | None = None

    def script(self) -> str:
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={self.name}",
            f"#SBATCH --partition={self.partition}",
            f"#SBATCH --cpus-per-task={self.cpus}",
            f"#SBATCH --mem={self.mem}",
            f"#SBATCH --time={self.time}",
            f"#SBATCH --output={self.log_dir}/{self.name}_%j.log",
            f"#SBATCH --error={self.log_dir}/{self.name}_%j.err",
        ]
        # Omitted unless set: an explicit but wrong --account (e.g. a PI's
        # account this user isn't a member of) fails sbatch outright, whereas
        # no --account at all falls back to Slurm's own default association --
        # the generic choice when the right account isn't known ahead of time.
        if self.account:
            lines.append(f"#SBATCH --account={self.account}")
        if self.gres:
            lines.append(f"#SBATCH --gres={self.gres}")
        if self.exclude:
            lines.append(f"#SBATCH --exclude={self.exclude}")
        lines.append("")
        lines.append("set -euo pipefail")
        if self.chdir:
            lines.append(f"cd {self.chdir}")
        lines.append("")
        lines.append(self.command)
        lines.append("")
        return "\n".join(lines)


def run_job(job: SlurmJob, script_path: Path) -> None:
    """Write `job`'s sbatch script and submit it, raising JobFailed on error."""
    job.log_dir.mkdir(parents=True, exist_ok=True)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(job.script())
    script_path.chmod(0o755)

    result = subprocess.run(["sbatch", "--wait", str(script_path)])
    if result.returncode != 0:
        raise JobFailed(
            f"{job.name} failed (sbatch exit {result.returncode}); "
            f"see {job.log_dir}/{job.name}_*.err"
        )
