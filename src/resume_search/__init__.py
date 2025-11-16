# resume_search/__init__.py
"""
Advanced resume search with semantic and keyword capabilities.
Provides hybrid search using OpenAI embeddings and SQLite FTS5.
"""

from .hybrid_search import hybrid_search, search_with_fallback  # Main search functions
from .mongodb_search import search_profiles  # Keyword-only fallback
