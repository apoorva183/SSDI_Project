# PDF Resume Search (Hybrid: SQLite FTS5 + FAISS)

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1) Put your PDFs into ./resumes
# 2) Build the DB + vector index
python src/ingest.py

# 3) Search (CLI)
python src/search.py "python"
python src/search.py "machine learning" 0.5   # alpha=0.5 → more semantic weight

# 4) Optional: Run the API on http://127.0.0.1:5000/search?q=python
python src/api.py
