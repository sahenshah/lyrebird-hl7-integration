# app/core/retry.py
import time
import logging
from app.core.config import MAX_RETRIES, RETRY_BACKOFF_BASE

def retry(
    func,
    max_attempts=MAX_RETRIES,
    backoff_base=RETRY_BACKOFF_BASE,
    exceptions=(Exception,),
    logger=None
):
    """
    Retry a callable up to max_attempts with exponential backoff.
    """
    attempt = 0
    while attempt < max_attempts:
        try:
            return func()
        except exceptions as e:
            attempt += 1
            if logger:
                logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")
            if attempt >= max_attempts:
                raise
            sleep_time = backoff_base * (2 ** (attempt - 1))
            time.sleep(sleep_time)