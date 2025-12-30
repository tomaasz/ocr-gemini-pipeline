import pytest
from unittest.mock import MagicMock
from ocr_gemini.ui.worker_pool import WorkerPool, Worker

def test_worker_pool_initialization():
    pool = WorkerPool(size=2)
    pool.start()
    assert len(pool.workers) == 2
    assert pool.workers[0].id == 0
    assert pool.workers[1].id == 1
    pool.stop()
    assert len(pool.workers) == 0

def test_round_robin_scheduling():
    pool = WorkerPool(size=2)
    pool.start()

    # Mock job function
    job_mock = MagicMock()

    # First job should go to worker 0
    pool.submit_job(job_mock, "job1")
    job_mock.assert_called_with(pool.workers[0], "job1")

    # Second job should go to worker 1
    pool.submit_job(job_mock, "job2")
    job_mock.assert_called_with(pool.workers[1], "job2")

    # Third job should go back to worker 0
    pool.submit_job(job_mock, "job3")
    job_mock.assert_called_with(pool.workers[0], "job3")

def test_single_worker():
    pool = WorkerPool(size=1)
    pool.start()

    job_mock = MagicMock()

    pool.submit_job(job_mock, "job1")
    job_mock.assert_called_with(pool.workers[0], "job1")

    pool.submit_job(job_mock, "job2")
    job_mock.assert_called_with(pool.workers[0], "job2")
