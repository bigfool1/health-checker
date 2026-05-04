import os

LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-xxx")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/anthropic")
