"""Cluster paths and defaults shared by every agent."""

import os
from pathlib import Path

SELECTISAFE = Path("/scratch/g.murugan/Pfizer/selectisafe")
BUILDS = SELECTISAFE / "builds"

FLOWR_SIF = BUILDS / "flowr-v1.0.sif"
DIFFDOCK_SIF = BUILDS / "diffdock-v1.0.sif"
AIZYNTHFINDER_SIF = BUILDS / "aizynthfinder.sif"
ADMET_SIF = BUILDS / "admet-ai.sif"
GNINA_SIF = BUILDS / "gnina.sif"

FLOWR_CKPT = SELECTISAFE / "data" / "models" / "flowr_root_v2.2.ckpt"

# DiffDock caches its SO(3)/torus lookup tables relative to the working
# directory it is launched from. Those ~400MB tables already exist under
# SELECTISAFE; launching a diffdock job from anywhere else regenerates them
# on every run instead of reusing the cache.
DIFFDOCK_CHDIR = SELECTISAFE

# No default account: an explicit wrong one (e.g. a PI's account this user
# isn't a member of -- the original cause of "Invalid account or
# account/partition combination specified") fails sbatch outright, whereas
# omitting --account falls back to Slurm's own default association. Set
# SIF_AGENTS_SLURM_ACCOUNT if a specific project account is ever required.
ACCOUNT = os.environ.get("SIF_AGENTS_SLURM_ACCOUNT") or None

# "gpu-interactive" is the partition used for real GPU work by multiple
# general-access OOD apps on this cluster (tensorboard, rstudio) -- a better
# general bet than "sharing" (an earlier default here), which only appears in
# auxilium-analyze's own 10-minute one-shot job and is presumably a short-burst
# pool. Neither partition's actual MaxTime is confirmed via `sinfo` from this
# environment, though -- see GPU_WALLTIME below for how that's handled.
# Override via env if your account has access to a dedicated partition (the
# original selectisafe scripts used partition=gpu, account=a.barabasi,
# gres=gpu:a100:1, which may still be right for whoever owns that account).
GPU_PARTITION = os.environ.get("SIF_AGENTS_GPU_PARTITION", "gpu-interactive")
GPU_TYPE = os.environ.get("SIF_AGENTS_GPU_TYPE") or None  # None = unqualified gpu:N

# Harmless no-op if gpu-interactive doesn't include these nodes anyway; kept
# in case GPU_PARTITION is overridden back to a mixed-hardware pool like
# "sharing", which does have AMD mi50 nodes (FlowR/DiffDock/GNINA need CUDA).
GPU_EXCLUDE = os.environ.get("SIF_AGENTS_GPU_EXCLUDE") or None

# Unverified: confirm the cluster's general CPU partition name with `sinfo`
# before the first run. aizynthfinder and admet-ai do not need a GPU.
CPU_PARTITION = os.environ.get("SIF_AGENTS_CPU_PARTITION", "short")

# Conservative on purpose: two successive real submissions were rejected with
# "Requested time limit is invalid" at 4.5h (on "gpu") and again at 4.5h/2h/1h
# (on "gpu-interactive") -- the actual per-partition MaxTime isn't known from
# this environment (no `sinfo` access), and guessing upward burns a real queue
# slot per attempt. Start short; raise via env only after a run is actually
# killed for running out of time (not before), since that failure mode is
# unambiguous in a job's own .err file.
GPU_WALLTIME = os.environ.get("SIF_AGENTS_GPU_WALLTIME", "01:00:00")
CPU_WALLTIME = os.environ.get("SIF_AGENTS_CPU_WALLTIME", "00:30:00")

# Explicit binds for every apptainer exec call. The original selectisafe
# scripts passed none and relied on the node's default apptainer.conf bind
# paths; that held for the "gpu" partition but a run on "gpu-interactive"
# failed to see /scratch/g.murugan/Pfizer/selectisafe/data/models/*.ckpt
# inside the container (FileNotFoundError) despite the file existing on the
# host at that exact path -- consistent with gpu-interactive nodes having a
# more restrictive default bind config. Binding explicitly removes the
# dependency on that per-partition default.
#
# Deliberately NOT binding /home: the diffdock-v1.0.sif image bakes its own
# HOME=/home/appuser and MAMBA_ROOT_PREFIX=/home/appuser/micromamba (its
# Python interpreter lives there) -- binding the host's /home over it hides
# the image's own /home/appuser and DiffDock fails with "no such file or
# directory" for a path that only ever existed inside the container.
APPTAINER_BIND = os.environ.get(
    "SIF_AGENTS_APPTAINER_BIND", "/scratch:/scratch,/projects:/projects"
)

# aizynthfinder.sif ships a broken env: rdkit/sklearn are compiled against
# NumPy 1.x's C-API but NumPy 2.2.6 is what's installed (a real ABI mismatch
# inside this third-party image, confirmed from a real run's traceback --
# AttributeError: _ARRAY_API not found). The error's own suggested fix is to
# downgrade numpy; retrosynthesis_agent pip-installs a numpy<2 build here
# (using the container's own pip, so the ABI matches its Python) once, then
# shadows the broken one via PYTHONPATH on every run. Lives under this
# project (not inside the read-only .sif) so it survives across runs.
AIZYNTHFINDER_NUMPY_FIX = Path(__file__).parent / ".aizynthfinder_numpy_fix"


def gpu_gres(n: int) -> str:
    """`--gres` value for `n` GPUs, qualified by GPU_TYPE only if one is set."""
    return f"gpu:{GPU_TYPE}:{n}" if GPU_TYPE else f"gpu:{n}"
