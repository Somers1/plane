import logging
import time
from functools import wraps

from bs4 import BeautifulSoup
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


def retry_with_timeout(
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        exceptions: tuple = (RequestException,),
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for retry in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e
                    if retry == max_retries:
                        logger.error(f"Failed after {max_retries} retries: {str(e)}")
                        raise

                    # Calculate wait time with exponential backoff
                    wait_time = backoff_factor * (2 ** retry)
                    logger.warning(
                        f"Request failed: {str(e)}. "
                        f"Retrying in {wait_time:.1f} seconds... "
                        f"(Attempt {retry + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)

            if last_exception:
                raise last_exception
            return None  # To satisfy mypy, this line should never be reached

        return wrapper

    return decorator



def clean_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator='\n')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return '\n'.join(lines)
