import sys
import re
import json
import sqlite3
import numpy as np
import faiss
import re
from sentence_transformers import SentenceTransformer
from config import DB_PATH, FAISS_PATH, MAP_PATH, MODEL_NAME, SKILL_MAP

def expand_query(q: str) -> str:
    base = q.lower().strip()
    terms = base.split()
    expanded = terms[:]
    for t in terms:
        expanded += SKILL_MAP.get(t, [])
    # de-dup while preserving order
    seen, out = set(), []
    for w in expanded:
        if w not in seen:
            seen.add(w); out.append(w)
    return " ".join(out)

def normalize_scores(x):
    x = np.array(x, dtype=float)
    if x.size == 0:
        return x
    mn, mx = x.min(), x.max()
    if mx <= mn:
        return np.ones_like(x) if mx != 0 else np.zeros_like(x)
    return (x - mn) / (mx - mn)

def keyword_search(conn, query: str, limit=200):
    q_expanded = expand_query(query)
    q_match = to_fts_query(q_expanded)  # <<< use safe, quoted MATCH query

    sql = """
    SELECT doc_id,
           page,
           snippet(resumes_fts, '<b>', '</b>', '…', -1, 64) AS snip,
           text
    FROM resumes_fts
    WHERE resumes_fts MATCH ?
    LIMIT ?;
    """
    rows = conn.execute(sql, (q_match, limit)).fetchall()

    # aggregate per-document with a crude hit count
    doc_hits = {}
    raw_terms = query.lower().split()
    for doc_id, page, snip, fulltext in rows:
        hits = sum(fulltext.lower().count(t) for t in raw_terms)
        if hits <= 0: hits = 1  # tiny positive signal for matched row
        best = doc_hits.get(doc_id)
        # keep the page/snippet with most hits
        if not best or hits > best["hits"]:
            doc_hits[doc_id] = {"hits": hits, "page": page, "snippet": snip}

    doc_ids = list(doc_hits.keys())
    scores  = [doc_hits[d]["hits"] for d in doc_ids]
    return doc_ids, np.array(scores, dtype=float), doc_hits

def semantic_search(query: str, model: SentenceTransformer):
    if not FAISS_PATH.exists() or not MAP_PATH.exists():
        raise SystemExit("Missing FAISS files. Run: python src/ingest.py")
    index = faiss.read_index(str(FAISS_PATH))
    with open(MAP_PATH) as f:
        mapping = json.load(f)
    doc_ids = mapping["doc_ids"]

    q_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)
    sim, idxs = index.search(q_vec, len(doc_ids))
    scores = np.zeros(len(doc_ids), dtype=float)
    scores[idxs[0]] = sim[0]
    return doc_ids, scores

def combine_scores(all_doc_ids, kw_doc_ids, kw_scores, sem_doc_ids, sem_scores, alpha=0.6):
    pos = {d: i for i, d in enumerate(all_doc_ids)}
    kw_vec  = np.zeros(len(all_doc_ids), dtype=float)
    sem_vec = np.zeros(len(all_doc_ids), dtype=float)

    for d, s in zip(kw_doc_ids, kw_scores):
        if d in pos: kw_vec[pos[d]] = s
    for i, d in enumerate(sem_doc_ids):
        sem_vec[i] = sem_scores[i]

    kw_norm  = normalize_scores(kw_vec)
    sem_norm = normalize_scores(sem_vec)

    final = alpha * kw_norm + (1 - alpha) * sem_norm
    order = np.argsort(-final)
    return order, final

def fts_term_quote(term: str) -> str:
    # turn hyphens/underscores/slashes into spaces so FTS5 sees words
    clean = re.sub(r"[-_/]+", " ", term.lower()).strip()
    if not clean:
        return ""
    # quote each term or phrase so MATCH treats it as text, not identifiers
    clean = clean.replace('"', '""')  # escape quotes
    return f'"{clean}"'

def to_fts_query(expanded_query: str) -> str:
    # split on whitespace and quote each piece; join with OR
    pieces = [p for p in expanded_query.split() if p]
    quoted = [fts_term_quote(p) for p in pieces]
    quoted = [q for q in quoted if q]
    return " OR ".join(quoted) if quoted else '""'

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/search.py \"your query\" [alpha]")
        sys.exit(1)

    query = sys.argv[1]
    alpha = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6

    conn = sqlite3.connect(str(DB_PATH))
    model = SentenceTransformer(MODEL_NAME)

    kw_doc_ids, kw_raw_scores, kw_meta = keyword_search(conn, query, limit=200)
    sem_doc_ids, sem_scores = semantic_search(query, model)

    all_doc_ids = sem_doc_ids  # embedding side defines the universe of docs
    order, final = combine_scores(all_doc_ids, kw_doc_ids, kw_raw_scores, sem_doc_ids, sem_scores, alpha=alpha)

    print(f"\n=== Results for: \"{query}\" (alpha={alpha}) ===\n")
    shown = 0
    for idx in order:
        doc_id = all_doc_ids[idx]
        score  = final[idx]
        if shown >= 10: break
        page = kw_meta.get(doc_id, {}).get("page")
        snip = kw_meta.get(doc_id, {}).get("snippet")
        page_info = f"(page {page})" if page else ""
        print(f"[{shown+1}] {doc_id}  score={score:.3f} {page_info}")
        if snip:
            print(snip)
        print("-" * 80)
        shown += 1

    conn.close()

if __name__ == "__main__":
    main()
