"""Service protocols (interfaces) for LLM, search, and vector store. Enables mocking and swapping implementations."""
from typing import List, Optional, Protocol


class LLMProvider(Protocol):
    """LLM completion: given messages, return assistant text."""

    def invoke(self, messages: List[dict], **kwargs) -> str:
        """Return assistant reply text. Raises on API/validation errors."""
        ...


class SearchProvider(Protocol):
    """Web/search: given query, return relevant snippets or content."""

    def search(self, query: str, max_results: int = 5, **kwargs) -> List[dict]:
        """Return list of search results (e.g. dicts with 'content', 'url')."""
        ...


class VectorStoreProvider(Protocol):
    """Vector store for RAG: similarity search and optional memory append."""

    def load(self) -> bool:
        """Load index from disk. Return True if loaded."""
        ...

    def build(self) -> bool:
        """Build index from learning data. Return True on success."""
        ...

    def search(self, query: str, k: int = 4) -> List[str]:
        """Return top-k relevant text chunks."""
        ...

    def add_memory(self, text: str) -> None:
        """Add text to conversation memory (optional)."""
        ...
