from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page


@dataclass
class Worker:
    """Represents a single browser worker instance."""
    id: int
    context: Optional['BrowserContext'] = None
    page: Optional['Page'] = None


class WorkerPool:
    """
    Manages a pool of browser workers for concurrent processing.

    This handles creating up to N workers (contexts/pages) and distributing work.
    """

    def __init__(self, size: int = 1) -> None:
        self.size = size
        self.workers: List[Worker] = []
        self._current_worker_index = 0

    def start(self) -> None:
        """Starts the workers (initializes browsers/contexts)."""
        # Placeholder for actual Playwright launch logic
        # In a real implementation, this would launch browser and contexts
        for i in range(self.size):
            self.workers.append(Worker(id=i))

    def stop(self) -> None:
        """Stops all workers."""
        self.workers.clear()

    def get_next_worker(self) -> Worker:
        """Round-robin scheduling of workers."""
        if not self.workers:
            raise RuntimeError("Worker pool not started")

        worker = self.workers[self._current_worker_index]
        self._current_worker_index = (self._current_worker_index + 1) % len(self.workers)
        return worker

    def submit_job(self, job_func: Callable, *args, **kwargs):
        """
        Submits a job to run on the next available worker.

        In this synchronous MVP, it executes immediately on the selected worker.
        """
        worker = self.get_next_worker()
        return job_func(worker, *args, **kwargs)
