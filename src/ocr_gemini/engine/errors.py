from enum import Enum
from typing import Optional

class ErrorKind(str, Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"

def classify_error(e: Exception) -> ErrorKind:
    """
    Classifies an exception into Transient, Permanent, or Unknown.
    """
    error_msg = str(e).lower()
    error_type = type(e).__name__

    # 1. Check for specific Playwright errors (by name to avoid hard dep)
    if "TimeoutError" in error_type:
        return ErrorKind.TRANSIENT
    if "TargetClosedError" in error_type:
        return ErrorKind.TRANSIENT

    # 2. Check for keywords in message
    if "detached" in error_msg:
        return ErrorKind.TRANSIENT
    if "execution context was destroyed" in error_msg:
        return ErrorKind.TRANSIENT
    if "navigating to" in error_msg and "timeout" in error_msg:
         return ErrorKind.TRANSIENT
    if "network" in error_msg and "error" in error_msg:
        return ErrorKind.TRANSIENT

    # 3. Permanent errors
    if isinstance(e, FileNotFoundError):
        return ErrorKind.PERMANENT
    if "login" in error_msg or "auth" in error_msg:
        return ErrorKind.PERMANENT
    if "cookie" in error_msg and "missing" in error_msg:
        return ErrorKind.PERMANENT
    if "invalid" in error_msg and "format" in error_msg:
        return ErrorKind.PERMANENT

    # 4. Unknown (default)
    return ErrorKind.UNKNOWN
