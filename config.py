import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "company_bi.db"


def get_llm():
    """Returns a ChatOpenAI instance dynamically routed via environment keys."""
    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    headers = {}
    if groq_key:
        api_key = groq_key
        base_url = "https://api.groq.com/openai/v1"
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    elif openrouter_key:
        api_key = openrouter_key
        base_url = "https://openrouter.ai/api/v1"
        model = os.getenv("OPENROUTER_MODEL", "cohere/north-mini-code:free")
        headers = {
            "HTTP-Referer": "https://github.com/parth231103/insight-sql",
            "X-Title": "InsightSQL"
        }
    elif openai_key:
        api_key = openai_key
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    else:
        api_key = "local"
        base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:31415/v1")
        model = "auto"

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,  # Zero temperature for deterministic SQL generation
        request_timeout=25.0,
        max_retries=2,
        default_headers=headers if headers else None,
    )
