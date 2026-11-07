"""
Distributed Task Queue Retry & Rate Limiter Module
Contains intentional bugs in backoff calculation, mutable default arguments, and failure threshold handling.
"""

from typing import List, Dict, Any, Optional


class TaskRecord:
    # BUG 1: Mutable default argument `tags: List[str] = []` shared across all TaskRecord instances!
    def __init__(self, task_id: str, payload: Dict[str, Any], max_retries: int = 3, tags: List[str] = []):
        self.task_id = task_id
        self.payload = payload
        self.max_retries = max_retries
        self.attempts = 0
        self.tags = tags
        self.status = "PENDING"
        self.last_error: Optional[str] = None

    def add_tag(self, tag: str) -> None:
        if tag not in self.tags:
            self.tags.append(tag)


class RetryScheduler:
    def __init__(self, base_delay: float = 2.0, max_delay: float = 60.0):
        self.base_delay = base_delay
        self.max_delay = max_delay

    def compute_backoff(self, attempt: int) -> float:
        """
        Compute exponential backoff delay: base_delay * (2 ** (attempt - 1)),
        capped at max_delay. For attempt <= 0, raise ValueError.
        """
        if attempt <= 0:
            raise ValueError("Attempt number must be >= 1")
        # BUG 2: Uses multiplication `2 * attempt` instead of exponentiation `2 ** (attempt - 1)`
        # and forgets to cap at `self.max_delay`!
        delay = self.base_delay * (2 * attempt)
        return float(delay)

    def record_failure(self, task: TaskRecord, error_msg: str) -> str:
        """
        Increment task attempts, record error_msg, and update task.status:
        - If attempts < max_retries: status becomes 'RETRYING'
        - If attempts >= max_retries: status becomes 'DEAD_LETTER'
        """
        task.attempts += 1
        task.last_error = error_msg
        # BUG 3: Off-by-one comparison (`>` instead of `>=`) allows an extra retry beyond max_retries
        if task.attempts > task.max_retries:
            task.status = "DEAD_LETTER"
        else:
            task.status = "RETRYING"
        return task.status

