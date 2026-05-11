# tools/asset_dashboard/backend/jobs.py
"""In-memory job registry. Each job is a subprocess; output captured to a tempfile."""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobInfo:
    id: str
    cmd: list[str]
    cwd: Path
    log_path: Path
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    exit_code: int | None = None
    status: JobStatus = JobStatus.PENDING
    asset_name: str | None = None
    stage: str | None = None
    _process: subprocess.Popen | None = None

    def tail(self, n: int = 50) -> str:
        if not self.log_path.exists():
            return ""
        text = self.log_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return "\n".join(lines[-n:]) if len(lines) > n else text

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cmd": self.cmd,
            "asset_name": self.asset_name,
            "stage": self.stage,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobInfo] = {}
        self._lock = threading.Lock()

    def start(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        asset_name: str | None = None,
        stage: str | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        log_path = Path(tempfile.gettempdir()) / f"muzha_dashboard_{job_id}.log"
        log_path.write_text("", encoding="utf-8")
        info = JobInfo(
            id=job_id,
            cmd=list(cmd),
            cwd=cwd or Path.cwd(),
            log_path=log_path,
            status=JobStatus.RUNNING,
            asset_name=asset_name,
            stage=stage,
        )
        log_fh = log_path.open("ab", buffering=0)
        proc = subprocess.Popen(
            cmd,
            cwd=str(info.cwd),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
        info._process = proc
        with self._lock:
            self._jobs[job_id] = info

        threading.Thread(
            target=self._reaper, args=(job_id, log_fh), daemon=True
        ).start()
        return job_id

    def _reaper(self, job_id: str, log_fh) -> None:
        info = self._jobs[job_id]
        assert info._process is not None
        rc = info._process.wait()
        log_fh.close()
        info.finished_at = time.time()
        info.exit_code = rc
        info.status = JobStatus.COMPLETED if rc == 0 else JobStatus.FAILED

    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[JobInfo]:
        with self._lock:
            return list(self._jobs.values())

    def wait(self, job_id: str, timeout: float = 30) -> None:
        info = self._jobs[job_id]
        deadline = time.time() + timeout
        while time.time() < deadline:
            if info.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return
            time.sleep(0.05)
        raise TimeoutError(f"job {job_id} did not finish in {timeout}s")

    def remove(self, job_id: str) -> bool:
        """Drop a finished job from the registry. Returns False if not found
        or still running. Refuses to remove RUNNING/PENDING jobs."""
        with self._lock:
            info = self._jobs.get(job_id)
            if info is None:
                return False
            if info.status in (JobStatus.PENDING, JobStatus.RUNNING):
                return False
            try:
                info.log_path.unlink(missing_ok=True)
            except OSError:
                pass
            del self._jobs[job_id]
            return True

    def clear_finished(self) -> int:
        """Drop all completed + failed jobs. Returns the number removed."""
        with self._lock:
            finished_ids = [
                jid for jid, info in self._jobs.items()
                if info.status in (JobStatus.COMPLETED, JobStatus.FAILED)
            ]
            for jid in finished_ids:
                try:
                    self._jobs[jid].log_path.unlink(missing_ok=True)
                except OSError:
                    pass
                del self._jobs[jid]
            return len(finished_ids)
