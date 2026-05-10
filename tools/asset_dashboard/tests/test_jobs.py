# tools/asset_dashboard/tests/test_jobs.py
import sys
import time

import pytest

from tools.asset_dashboard.backend.jobs import JobRegistry, JobStatus


@pytest.fixture
def registry():
    return JobRegistry()


def test_start_records_running_job(registry):
    job_id = registry.start([sys.executable, "-c", "import time; time.sleep(0.5)"])
    info = registry.get(job_id)
    assert info is not None
    assert info.status in (JobStatus.RUNNING, JobStatus.COMPLETED)
    registry.wait(job_id, timeout=5)


def test_completed_job_has_zero_exit(registry):
    job_id = registry.start([sys.executable, "-c", "print('hi')"])
    registry.wait(job_id, timeout=5)
    info = registry.get(job_id)
    assert info.status == JobStatus.COMPLETED
    assert info.exit_code == 0
    assert "hi" in info.tail()


def test_failed_job_records_nonzero_exit(registry):
    job_id = registry.start([sys.executable, "-c", "import sys; sys.exit(2)"])
    registry.wait(job_id, timeout=5)
    info = registry.get(job_id)
    assert info.status == JobStatus.FAILED
    assert info.exit_code == 2


def test_list_jobs_returns_all(registry):
    j1 = registry.start([sys.executable, "-c", "pass"])
    j2 = registry.start([sys.executable, "-c", "pass"])
    registry.wait(j1, timeout=5)
    registry.wait(j2, timeout=5)
    ids = {j.id for j in registry.list()}
    assert ids == {j1, j2}


def test_tail_returns_last_n_lines(registry):
    code = "for i in range(20): print(f'line{i}')"
    job_id = registry.start([sys.executable, "-c", code])
    registry.wait(job_id, timeout=5)
    info = registry.get(job_id)
    last = info.tail(n=5).splitlines()
    assert last == ["line15", "line16", "line17", "line18", "line19"]
