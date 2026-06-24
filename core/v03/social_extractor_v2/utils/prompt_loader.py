import os


class PromptNotConfiguredError(RuntimeError):
    """Raised when a prompt file is missing or empty/whitespace-only.

    This module intentionally does NOT fall back to any hardcoded prompt: an
    unconfigured prompt must surface loudly so the LLM stage stops clearly until
    the user defines the prompt content.
    """


def _prompts_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def prompt_path(name: str) -> str:
    return os.path.join(_prompts_dir(), f"{name}.md")


def read_prompt(name: str) -> str:
    """
    Read prompt 'core/v03/social_extractor_v2/utils/prompts/{name}.md' (UTF-8).

    Raises PromptNotConfiguredError if the file does not exist or is
    empty/whitespace-only. No hardcoded fallback.
    """
    path = prompt_path(name)
    if not os.path.exists(path):
        raise PromptNotConfiguredError(
            f"Prompt '{name}' is not configured: file not found at {path}"
        )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        raise PromptNotConfiguredError(
            f"Prompt '{name}' is not configured: file is empty at {path}"
        )
    return content
