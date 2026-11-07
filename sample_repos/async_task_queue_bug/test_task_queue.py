from task_queue import TaskRecord, RetryScheduler


def test_initial_task_state():
    t = TaskRecord("task-101", {"job": "send_email"})
    assert t.status == "PENDING"
    assert t.attempts == 0

