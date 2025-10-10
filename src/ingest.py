import re
import sqlite3
import json
import pdfplumber
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss

from config import RESUME_DIR, DATA_DIR, DB_PATH, FAISS_PATH, MAP_PATH, MODEL_NAME

DATA_DIR.mkdir(exist_ok=True)

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def check_fts5(conn: sqlite3.Connection):
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts5_check USING fts5(x)")
        conn.execute("DROP TABLE fts5_check;")
    except sqlite3.OperationalError as e:
        raise SystemExit(
            "Your Python/SQLite build lacks FTS5 support. Install a Python build with SQLite FTS5."
        ) from e

def create_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id TEXT NOT NULL,   -- filename
        path   TEXT NOT NULL,
        page   INTEGER NOT NULL,
        text   TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS resumes_fts
    USING fts5(text, doc_id UNINDEXED, page UNINDEXED, content='resumes', content_rowid='id');
    """)
    cur.execute("""
    CREATE VIEW IF NOT EXISTS doc_fulltext AS
    SELECT doc_id, GROUP_CONCAT(text, ' ') AS full_text
    FROM resumes
    GROUP BY doc_id;
    """)
    conn.commit()

def extract_pdf(path: Path):
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for i, p in enumerate(pdf.pages):
            t = normalize_ws(p.extract_text() or "")
            pages.append((i + 1, t))
    return pages

def upsert_resume(conn: sqlite3.Connection, path: Path):
    doc_id = path.name
    conn.execute("DELETE FROM resumes WHERE doc_id = ?", (doc_id,))
    pages = extract_pdf(path)
    for page, text in pages:
        conn.execute(
            "INSERT INTO resumes (doc_id, path, page, text) VALUES (?, ?, ?, ?)",
            (doc_id, str(path), page, text)
        )
    conn.commit()
    if not any(t for _, t in pages):
        print(f"[WARN] No extractable text in {doc_id}. (If scanned, consider adding OCR fallback)")

def rebuild_fts(conn: sqlite3.Connection):
    conn.execute("INSERT INTO resumes_fts(resumes_fts) VALUES('rebuild');")
    conn.commit()

def build_embeddings(conn: sqlite3.Connection):
    rows = conn.execute("SELECT doc_id, GROUP_CONCAT(text, ' ') FROM resumes GROUP BY doc_id").fetchall()
    if not rows:
        print("No text to embed. Put PDFs in ./resumes and re-run.")
        return
    doc_ids = [r[0] for r in rows]
    texts   = [normalize_ws(r[1]) for r in rows]

    print(f"[EMB] Encoding {len(doc_ids)} documents with {MODEL_NAME} …")
    model = SentenceTransformer(MODEL_NAME)
    embs = model.encode(texts, show_progress_bar=True, normalize_embeddings=True).astype(np.float32)

    dim = embs.shape[1]
    index = faiss.IndexFlatIP(dim)  # cosine sim (embeddings are normalized)
    index.add(embs)

    faiss.write_index(index, str(FAISS_PATH))
    with open(MAP_PATH, "w") as f:
        json.dump({"doc_ids": doc_ids}, f)
    print(f"[OK] FAISS index written: {FAISS_PATH} | Doc map: {MAP_PATH}")

def main():
    if not RESUME_DIR.exists():
        raise SystemExit(f"Missing {RESUME_DIR}. Create it and place PDFs inside.")

    pdfs = sorted([p for p in RESUME_DIR.glob("*.pdf")])
    if not pdfs:
        raise SystemExit(f"No PDFs in {RESUME_DIR}. Add files and run again.")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON;")
    check_fts5(conn)
    create_schema(conn)

    for p in pdfs:
        upsert_resume(conn, p)
        print(f"[OK] Ingested {p.name}")

    rebuild_fts(conn)
    print("[OK] Rebuilt FTS index")

    build_embeddings(conn)
    conn.close()
    print("[DONE] Ingest complete")

if __name__ == "__main__":
    main()
