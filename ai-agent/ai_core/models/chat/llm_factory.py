from threading import Lock
from langchain_ollama import ChatOllama


class LLMFactory:
    """
    Enterprise LLM Factory (Ollama private infra).
    - Model caching
    - Thread-safe
    """

    _cache = {}
    _lock = Lock()

    @staticmethod
    def create_chat_model(
        model_name: str,
        temperature: float = 0,
        base_url: str = None,
    ):
        key = f"{model_name}:{temperature}:{base_url}"

        with LLMFactory._lock:
            if key in LLMFactory._cache:
                return LLMFactory._cache[key]

            client = ChatOllama(
                model=model_name,
                temperature=temperature,
                base_url=base_url or "http://localhost:11434"
            )

            LLMFactory._cache[key] = client
            return client