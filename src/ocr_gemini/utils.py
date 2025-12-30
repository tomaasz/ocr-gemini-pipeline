import time
from typing import Callable, Tuple, Type, TypeVar, Optional

T = TypeVar("T")

def retry_call(
    fn: Callable[[], T],
    retries: int,
    backoff_ms: int,
    retry_on: Tuple[Type[Exception], ...]
) -> T:
    """
    Retries a function call upon encountering specific exceptions.

    Args:
        fn: The function to call.
        retries: The maximum number of retries (0 means try once).
        backoff_ms: The time to sleep in milliseconds between retries.
        retry_on: A tuple of exception classes to catch and retry on.

    Returns:
        The result of the function call.

    Raises:
        The last exception encountered if all retries fail.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except retry_on as e:
            if attempt >= retries:
                raise e
            attempt += 1
            time.sleep(backoff_ms / 1000.0)


def wait_for_generation_complete(
    is_generating: Callable[[], bool],
    has_completed: Callable[[], bool],
    timeout_ms: int,
    poll_interval_ms: int
) -> None:
    """
    Waits for a generation process to complete.

    Args:
        is_generating: Function returning True if generation is in progress.
        has_completed: Function returning True if generation has completed successfully.
        timeout_ms: Maximum time to wait in milliseconds.
        poll_interval_ms: Interval between checks in milliseconds.

    Raises:
        TimeoutError: If the process does not complete within timeout_ms.
    """
    start_time = time.time()

    while (time.time() - start_time) * 1000 < timeout_ms:
        if has_completed():
            return

        # We can also check if it is still generating to potentially handle
        # cases where it stops generating but hasn't completed (error state?),
        # but the prompt specifically asked for poll until completed or timeout.
        # However, checking is_generating() can be useful if the caller provides logic there.
        # But based on the prompt "poll until completed or timeout", strict adherence:

        time.sleep(poll_interval_ms / 1000.0)

    raise TimeoutError(f"Generation did not complete within {timeout_ms}ms")
