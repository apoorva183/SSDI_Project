# app/streamlit_app.py
import sqlite3
import numpy as np
import streamlit as st

# Import your existing config and search helpers
# (works with either FAISS or NPZ embeddings depending on what you have)
from pathlib import Path
import sys

# Ensure project root is on sys.path so 'src' can be imported when running from ./app
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, MODEL_NAME, SKILL_MAP
from sentence_transformers import SentenceTransformer

# ---- If you used the FAISS path earlier ----
# We'll auto-detect whether you're using FAISS or NPZ embeddings.
FAISS_PATH = (ROOT / "data" / "vectors.faiss")
MAP_PATH   = (ROOT / "data" / "vectors_map.json")
EMB_PATH   = (ROOT / "data" / "vectors.npz")

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

# Safer FTS query (quotes tokens; handles scikit-learn, C#, etc.)
import re
def fts_term_quote(term: str) -> str:
    clean = re.sub(r"[-_/]+", " ", term.lower()).strip()
    if not clean:
        return ""
    clean = clean.replace('"', '""')
    return f'"{clean}"'

def to_fts_query(expanded_query: str) -> str:
    pieces = [p for p in expanded_query.split() if p]
    quoted = [fts_term_quote(p) for p in pieces]
    quoted = [q for q in quoted if q]
    return " OR ".join(quoted) if quoted else '""'

def keyword_search(conn: sqlite3.Connection, query: str, limit=200):
    q_expanded = expand_query(query)
    q_match = to_fts_query(q_expanded)
    sql = """
    SELECT doc_id, page,
           snippet(resumes_fts, '<b>', '</b>', '…', -1, 64) AS snip,
           text
    FROM resumes_fts
    WHERE resumes_fts MATCH ?
    LIMIT ?;
    """
    rows = conn.execute(sql, (q_match, limit)).fetchall()
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

# ---- Semantic search: pick FAISS if present, else NPZ ----
def semantic_search(query: str, model: SentenceTransformer):
    if EMB_PATH.exists():
        data = np.load(EMB_PATH, allow_pickle=True)
        doc_ids = list(data["doc_ids"])
        embs    = data["embs"]  # normalized
        q_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)[0]
        sims = embs @ q_vec
        return doc_ids, sims

    elif FAISS_PATH.exists() and MAP_PATH.exists():
        import faiss, json
        index = faiss.read_index(str(FAISS_PATH))
        mapping = json.loads(Path(MAP_PATH).read_text())
        doc_ids = mapping["doc_ids"]
        q_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)
        sim, idxs = index.search(q_vec, len(doc_ids))
        scores = np.zeros(len(doc_ids), dtype=float)
        scores[idxs[0]] = sim[0]
        return doc_ids, scores

    else:
        raise RuntimeError("No embeddings found. Run: python src/ingest.py")

def combine_scores(all_doc_ids, kw_doc_ids, kw_scores, sem_doc_ids, sem_scores, alpha=0.6):
    pos = {d:i for i,d in enumerate(all_doc_ids)}
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

def format_name(doc_id: str) -> str:
    return re.sub(r'[_\-]+', ' ', re.sub(r'\.[^.]+$', '', doc_id)).strip()

def get_doc_path(conn: sqlite3.Connection, doc_id: str) -> str | None:
    row = conn.execute("SELECT path FROM resumes WHERE doc_id=? LIMIT 1;", (doc_id,)).fetchone()
    return row[0] if row else None

# ----------------- UI -----------------
st.set_page_config(page_title="Resume Search", page_icon="🔎", layout="centered")

st.title("🔎 Resume Search (Hybrid)")
st.caption("Keyword (FTS5) + Semantic (embeddings). Uses your existing index; no code changes needed.")

q = st.text_input("Search skills or phrases (e.g., python, machine learning, scikit-learn)", value="")
col1, col2, col3 = st.columns([1,1,1])
with col1:
    alpha = st.slider("Keyword weight (alpha)", 0.0, 1.0, 0.6, 0.05, help="Higher = more exact keyword weight; Lower = more semantic weight.")
with col2:
    topk = st.number_input("Top K", min_value=1, max_value=50, value=10, step=1)
with col3:
    run = st.button("Search", use_container_width=True)

# Cache heavy objects across reruns
@st.cache_resource(show_spinner=False)
def load_model():
    return SentenceTransformer(MODEL_NAME)

@st.cache_resource(show_spinner=False)
def open_db():
    # allow usage across Streamlit threads
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)

if run and q.strip():
    try:
        with st.spinner("Searching…"):
            model = load_model()
            conn = open_db()

            kw_ids, kw_scores, kw_meta = keyword_search(conn, q, limit=200)
            sem_ids, sem_scores = semantic_search(q, model)
            all_ids = sem_ids
            order, final = combine_scores(all_ids, kw_ids, kw_scores, sem_ids, sem_scores, alpha=alpha)

            shown = 0
            for idx in order:
                doc_id = all_ids[idx]
                score  = float(final[idx])
                page   = kw_meta.get(doc_id, {}).get("page")
                snip   = kw_meta.get(doc_id, {}).get("snippet")

                with st.container(border=True):
                    left, right = st.columns([4,1])
                    with left:
                        st.markdown(f"### {format_name(doc_id)}")
                        meta = f"**Score:** {score:.3f}" + (f" • **Page:** {page}" if page else "")
                        st.markdown(meta)
                        if snip:
                            st.markdown(snip, unsafe_allow_html=True)
                        else:
                            st.caption("No snippet available.")
                    with right:
                        # Try to show the filesystem path (if helpful)
                        path = get_doc_path(conn, doc_id)
                        if path:
                            st.caption("File")
                            st.code(path, language=None)

                shown += 1
                if shown >= topk:
                    break

            if shown == 0:
                st.info("No results.")
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")
