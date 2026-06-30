"""In-memory job store.

Single-user, local app, so an in-process dict with a lock is sufficient. Files
(uploads + generated output) live under a per-session work directory that is
cleaned up on process exit.
"""
from __future__ import annotations

import atexit
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Optional

from .models import Job


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self.workdir = Path(tempfile.mkdtemp(prefix="autobib_"))
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def create(self, **kwargs) -> Job:
        job = Job(**kwargs)
        with self._lock:
            self._jobs[job.id] = job
        (self.workdir / job.id).mkdir(parents=True, exist_ok=True)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def job_dir(self, job_id: str) -> Path:
        d = self.workdir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d


# Module-level singleton used by the API layer.
store = JobStore()
