"""
Embedding Providers for Knowledge Base Onboarding

Supports multiple embedding backends:
- Google Gemini (cloud)
- Ollama (local)

Easily extensible for other providers (OpenAI, HuggingFace, etc.)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import httpx

from ..config import get_settings


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/display"""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding vector dimensions"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier"""
        pass

    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        pass

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (default: sequential)"""
        return [self.generate_embedding(text) for text in texts]

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check if the provider is available and configured"""
        pass


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embedding provider"""

    def __init__(self):
        self.settings = get_settings()
        self._configured = False
        self._model = self.settings.GEMINI_EMBEDDING_MODEL

        # Configure Gemini
        if self.settings.GOOGLE_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=self.settings.GOOGLE_API_KEY)
            self._genai = genai
            self._configured = True

    @property
    def name(self) -> str:
        return "Google Gemini"

    @property
    def dimensions(self) -> int:
        # text-embedding-004 produces 768-dimensional vectors
        return 768

    @property
    def model_name(self) -> str:
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        if not self._configured:
            raise ValueError("Google API key not configured. Set GOOGLE_API_KEY in .env")

        response = self._genai.embed_content(
            model=self._model,
            content=text
        )
        return response["embedding"]

    def health_check(self) -> Dict[str, Any]:
        if not self._configured:
            return {
                "available": False,
                "provider": self.name,
                "model": self._model,
                "error": "GOOGLE_API_KEY not configured"
            }

        try:
            # Test with a simple embedding
            test_embedding = self.generate_embedding("test")
            return {
                "available": True,
                "provider": self.name,
                "model": self._model,
                "dimensions": len(test_embedding)
            }
        except Exception as e:
            return {
                "available": False,
                "provider": self.name,
                "model": self._model,
                "error": str(e)
            }


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama local embedding provider"""

    def __init__(self):
        self.settings = get_settings()
        self._base_url = self.settings.OLLAMA_BASE_URL
        self._model = self.settings.OLLAMA_EMBEDDING_MODEL
        self._timeout = self.settings.OLLAMA_TIMEOUT
        self._dimensions = None  # Will be determined on first call

    @property
    def name(self) -> str:
        return "Ollama (Local)"

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            # Common dimensions for popular models
            model_dimensions = {
                "nomic-embed-text": 768,
                "mxbai-embed-large": 1024,
                "all-minilm": 384,
                "snowflake-arctic-embed": 1024,
            }
            # Return known dimension or default
            for model_key, dim in model_dimensions.items():
                if model_key in self._model.lower():
                    return dim
            return 768  # Default assumption
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/api/embeddings",
                    json={
                        "model": self._model,
                        "prompt": text
                    }
                )
                response.raise_for_status()
                result = response.json()

                embedding = result.get("embedding", [])

                # Cache dimensions on first successful call
                if self._dimensions is None and embedding:
                    self._dimensions = len(embedding)

                return embedding

        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(
                    f"Model '{self._model}' not found. "
                    f"Pull it first: `ollama pull {self._model}`"
                )
            raise

    def health_check(self) -> Dict[str, Any]:
        try:
            # Check if Ollama is running
            with httpx.Client(timeout=5) as client:
                # Check Ollama API
                response = client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]

                # Check if our model is available
                model_available = any(
                    self._model.lower() in name.lower()
                    for name in model_names
                )

                if not model_available:
                    return {
                        "available": False,
                        "provider": self.name,
                        "model": self._model,
                        "error": f"Model '{self._model}' not found. Available: {model_names}",
                        "available_models": model_names
                    }

                # Test embedding generation
                test_embedding = self.generate_embedding("test")

                return {
                    "available": True,
                    "provider": self.name,
                    "model": self._model,
                    "dimensions": len(test_embedding),
                    "available_models": model_names
                }

        except httpx.ConnectError:
            return {
                "available": False,
                "provider": self.name,
                "model": self._model,
                "error": f"Ollama not running at {self._base_url}. Start with: `ollama serve`"
            }
        except Exception as e:
            return {
                "available": False,
                "provider": self.name,
                "model": self._model,
                "error": str(e)
            }


class EmbeddingProviderFactory:
    """Factory to create embedding providers based on configuration"""

    _providers = {
        "gemini": GeminiEmbeddingProvider,
        "ollama": OllamaEmbeddingProvider,
    }

    @classmethod
    def get_provider(cls, provider_name: Optional[str] = None) -> EmbeddingProvider:
        """
        Get an embedding provider instance.

        Args:
            provider_name: Provider name ("gemini", "ollama").
                          If None, uses EMBEDDING_PROVIDER from settings.

        Returns:
            EmbeddingProvider instance
        """
        if provider_name is None:
            settings = get_settings()
            provider_name = settings.EMBEDDING_PROVIDER.lower()

        provider_class = cls._providers.get(provider_name.lower())

        if provider_class is None:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown embedding provider: '{provider_name}'. "
                f"Available providers: {available}"
            )

        return provider_class()

    @classmethod
    def list_providers(cls) -> List[str]:
        """List available provider names"""
        return list(cls._providers.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a custom embedding provider"""
        if not issubclass(provider_class, EmbeddingProvider):
            raise TypeError("Provider must be a subclass of EmbeddingProvider")
        cls._providers[name.lower()] = provider_class

    @classmethod
    def check_all_providers(cls) -> Dict[str, Dict[str, Any]]:
        """Health check all registered providers"""
        results = {}
        for name in cls._providers:
            try:
                provider = cls.get_provider(name)
                results[name] = provider.health_check()
            except Exception as e:
                results[name] = {
                    "available": False,
                    "provider": name,
                    "error": str(e)
                }
        return results


# Singleton instance cache
_provider_instance: Optional[EmbeddingProvider] = None


def get_embedding_provider(force_new: bool = False) -> EmbeddingProvider:
    """
    Get the configured embedding provider (singleton).

    Args:
        force_new: If True, creates a new instance ignoring cache

    Returns:
        EmbeddingProvider instance
    """
    global _provider_instance

    if _provider_instance is None or force_new:
        _provider_instance = EmbeddingProviderFactory.get_provider()

    return _provider_instance


def reset_embedding_provider():
    """Reset the cached provider instance (useful when config changes)"""
    global _provider_instance
    _provider_instance = None
