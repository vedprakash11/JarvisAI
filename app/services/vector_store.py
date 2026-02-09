"""
FAISS vector store and embeddings.
Loads all .txt files from database/learning_data, embeds them, and provides similarity search.
Conversation memories are stored with timestamps so the most recent can be preferred.
"""
import time
from pathlib import Path
from typing import List

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from app.utils import ops_state

class VectorStore:
    """FAISS vector store for learning data (RAG)."""

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        self._store = None
        self._index_path = config.VECTOR_STORE_DIR / "faiss_index"

    def _load_learning_documents(self) -> List[Document]:
        """Load all .txt files from learning_data into LangChain documents."""
        documents = []
        learning_dir = Path(config.LEARNING_DATA_DIR)
        if not learning_dir.exists():
            return documents
        for file_path in learning_dir.glob("*.txt"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                if text.strip():
                    doc = Document(
                        page_content=text,
                        metadata={"source": str(file_path.name)},
                    )
                    documents.append(doc)
            except Exception:
                continue
        return documents

    def _split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks for embedding."""
        if not documents:
            return []
        return self.text_splitter.split_documents(documents)

    def build(self) -> None:
        """Build or rebuild FAISS index from learning_data .txt files."""
        raw_docs = self._load_learning_documents()
        if not raw_docs:
            self._store = None
            return
        chunks = self._split_documents(raw_docs)
        self._store = FAISS.from_documents(chunks, self.embeddings)
        self._store.save_local(str(self._index_path))
        ops_state.set_vector_store_stats(len(chunks), time.time())

    def load(self) -> bool:
        """Load existing FAISS index from disk. Returns True if loaded."""
        if not (self._index_path / "index.faiss").exists():
            return False
        try:
            self._store = FAISS.load_local(
                str(self._index_path),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
            return True
        except Exception:
            return False

    def get_retriever(self, k: int = 4):
        """Get a retriever for similarity search. Returns None if no index."""
        if self._store is None:
            if not self.load():
                self.build()
        if self._store is None:
            return None
        return self._store.as_retriever(search_kwargs={"k": k})

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        """Return top-k similar chunks for the query."""
        if self._store is None:
            if not self.load():
                self.build()
        if self._store is None:
            return []
        return self._store.similarity_search(query, k=k)

    def add_memory(self, user_id: int, user_message: str, assistant_reply: str) -> None:
        """Persist one exchange (user + assistant) into the vector store for future RAG. Scoped by user_id so users do not see each other's memories."""
        memory_text = f"User said: {user_message}\nAssistant replied: {assistant_reply}"
        doc = Document(
            page_content=memory_text,
            metadata={"source": "conversation_memory", "timestamp": time.time(), "user_id": user_id},
        )
        if self._store is None:
            if not self.load():
                self.build()
        if self._store is None:
            self._store = FAISS.from_documents([doc], self.embeddings)
            ops_state.set_vector_store_stats(1, last_rebuild=None)
        else:
            self._store.add_documents([doc])
            stats = ops_state.get_vector_store_status()
            ops_state.set_vector_store_stats(stats["doc_count"] + 1, last_rebuild=stats.get("last_rebuild_time"))
        self._store.save_local(str(self._index_path))

    def get_memory_context_for_query(self, query: str, user_id: int, k: int = 6) -> str:
        """
        Retrieve context for the query, with conversation memories ordered by recency (newest first).
        Only conversation memories for the given user_id are included (no cross-user leakage).
        Returns "" on any failure so chat can proceed without RAG.
        """
        try:
            if self._store is None:
                if not self.load():
                    self.build()
            if self._store is None:
                return ""
            docs = self._store.similarity_search(query, k=min(k * 2, 12))
        except Exception:
            return ""
        conversation = []
        learning = []
        for d in docs:
            meta = d.metadata or {}
            if meta.get("source") == "conversation_memory":
                # Only include memories that belong to this user
                if meta.get("user_id") == user_id:
                    conversation.append((meta.get("timestamp") or 0, d))
            else:
                learning.append(d)
        # Newest conversation memories first
        try:
            conversation.sort(key=lambda x: -x[0])
            ordered = [d for _, d in conversation[:k]] + learning[: max(0, k - len(conversation))]
            return "\n\n".join(d.page_content for d in ordered) if ordered else ""
        except Exception:
            return ""
