import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from .prompt_loader import PromptNotConfiguredError, read_prompt, prompt_path
from .normalization import (
    collapse_whitespace,
    normalize_name_no_diacritics,
    normalize_for_label_match,
    normalize_name_fold_d,
    local_now_str,
)

__all__ = [
    "PromptNotConfiguredError",
    "read_prompt",
    "prompt_path",
    "collapse_whitespace",
    "normalize_name_no_diacritics",
    "normalize_for_label_match",
    "normalize_name_fold_d",
    "local_now_str",
]
