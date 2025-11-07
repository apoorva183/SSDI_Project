# resume_search/config.py
from pathlib import Path

# Base folders
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# SQLite DB for search (both keyword and semantic)
DB_PATH = DATA_DIR / "search.db"

# Search system configuration
SEARCH_MODE = "hybrid"  # hybrid, keyword, semantic
SEMANTIC_MODEL = "text-embedding-3-small"  # OpenAI embedding model

# Small query-expansion map to catch common skill words
SKILL_MAP = {
    "python": ["pandas", "numpy", "scikit-learn", "sklearn", "flask", "fastapi", "pytest", "pyspark"],
    "ml": ["machine learning", "scikit-learn", "xgboost", "random forest"],
    "nlp": ["transformers", "bert", "text classification", "tokenization"],
    "data": ["analytics", "analysis", "etl", "sql"],
}
