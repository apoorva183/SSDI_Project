from flask import Flask, request, jsonify
import sqlite3, json, numpy as np, faiss
from sentence_transformers import SentenceTransformer
from config import DB_PATH, FAISS_PATH, MAP_PATH, MODEL_NAME, SKILL_MAP

app = Flask(__name__)
model = SentenceTransformer(MODEL_NAME)

def expand_query(q: str) -> str:
    base = q.lower().strip()
    terms = base.split()
    expanded = terms[:]
    for t in terms:
        expanded += SKILL_MAP.get(t, [])
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

def keyword(conn, query, limit=200):
    q_expanded = expand_query(query)
    sql = """
    SELECT doc_id,
           page,
           snippet(resumes_fts, '<b>', '</b>', '…', -1, 64) AS snip,
           text
    FROM resumes_fts
    WHERE resumes_fts MATCH ?
    LIMIT ?;
    """
    rows = conn.execute(sql, (q_expanded, limit)).fetchall()
    doc_hits = {}
    raw_terms = query.lower().split()
    for doc_id, page, snip, fulltext in rows:
        hits = sum(fulltext.lower().count(t) for t in raw_terms)
        if hits <= 0: hits = 1
        best = doc_hits.get(doc_id)
        if not best or hits > best["hits"]:
            doc_hits[doc_id] = {"hits": hits, "page": page, "snippet": snip}
    doc_ids = list(doc_hits.keys())
    scores  = [doc_hits[d]["hits"] for d in doc_ids]
    return doc_ids, np.array(scores, dtype=float), doc_hits

def semantic(query):
    index = faiss.read_index(str(FAISS_PATH))
    with open(MAP_PATH) as f:
        mapping = json.load(f)
    doc_ids = mapping["doc_ids"]
    q_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)
    sim, idxs = index.search(q_vec, len(doc_ids))
    scores = np.zeros(len(doc_ids), dtype=float)
    scores[idxs[0]] = sim[0]
    return doc_ids, scores

def combine(all_doc_ids, kw_doc_ids, kw_scores, sem_doc_ids, sem_scores, alpha=0.6):
    pos = {d: i for i, d in enumerate(all_doc_ids)}
    kw_vec  = np.zeros(len(all_doc_ids), dtype=float)
    sem_vec = np.zeros(len(all_doc_ids), dtype=float)
    for d, s in zip(kw_doc_ids, kw_scores):
        if d in pos: kw_vec[pos[d]] = s
    for i, d in enumerate(sem_doc_ids):
        sem_vec[i] = sem_scores[i]
    kw_norm, sem_norm = normalize_scores(kw_vec), normalize_scores(sem_vec)
    final = alpha * kw_norm + (1 - alpha) * sem_norm
    order = np.argsort(-final)
    return order, final

@app.get("/search")
def do_search():
    q = request.args.get("q", "").strip()
    alpha = float(request.args.get("alpha", 0.6))
    topk = int(request.args.get("topk", 10))
    if not q:
        return jsonify({"error": "Missing ?q= query param"}), 400

    conn = sqlite3.connect(str(DB_PATH))
    kw_ids, kw_scores, kw_meta = keyword(conn, q, limit=200)
    sem_ids, sem_scores = semantic(q)
    all_ids = sem_ids
    order, final = combine(all_ids, kw_ids, kw_scores, sem_ids, sem_scores, alpha=alpha)

    results = []
    for idx in order[:topk]:
        did = all_ids[idx]
        results.append({
            "doc_id": did,
            "score": float(final[idx]),
            "page": kw_meta.get(did, {}).get("page"),
            "snippet": kw_meta.get(did, {}).get("snippet")
        })
    conn.close()
    return jsonify({"query": q, "alpha": alpha, "results": results})

if __name__ == "__main__":
    app.run(debug=True)
