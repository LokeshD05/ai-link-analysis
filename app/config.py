import os

from dotenv import load_dotenv

load_dotenv()


def model_settings() -> tuple[str | None, str, str | None]:
    return (
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        os.getenv("OPENAI_FALLBACK_MODEL") or None,
    )


def gemini_settings() -> tuple[str | None, str]:
    return os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite"
