from dotenv import load_dotenv

load_dotenv('.env', override=True)

import os  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from src.config import config as config  # noqa: E402

__version__ = '0.5.1'

if os.getenv('AI_INTERVIEW_SKIP_APP_INIT') != '1':
    from src.knowledge import knowledge_base as knowledge_base  # noqa: E402

executor = ThreadPoolExecutor()  # noqa: E402


def get_version():
    """Return the AI-interview version."""
    return __version__
