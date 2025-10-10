
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
RESUME_DIR = BASE_DIR / "resumes"
DATA_DIR   = BASE_DIR / "data"

DB_PATH      = DATA_DIR / "search.db"
FAISS_PATH   = DATA_DIR / "vectors.faiss"
MAP_PATH     = DATA_DIR / "vectors_map.json"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Simple skill expansion for keyword side (tweak freely)
SKILL_MAP = {
    "python": ["pandas", "numpy", "scikit-learn", "sklearn", "flask", "fastapi", "pytest", "pyspark"],
    "ml": ["machine learning", "scikit-learn", "xgboost", "random forest"],
    "nlp": ["transformers", "bert", "text classification", "tokenization"],
    "data": ["analytics", "analysis", "etl", "sql"]
}
