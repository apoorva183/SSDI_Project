"""
MongoDB-based resume search - searches through profiles stored in MongoDB
"""

import sqlite3
from pathlib import Path
import re

# Get the search database path
DB_PATH = Path(__file__).parent / "data" / "search.db"

def init_mongodb_search_db():
    """Initialize SQLite FTS5 database for MongoDB resume search"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # Drop existing tables to start fresh
    c.execute("DROP TABLE IF EXISTS resumes_fts")
    c.execute("DROP TABLE IF EXISTS resumes")
    
    # Create base table to store resume data
    c.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            full_name TEXT,
            content TEXT NOT NULL,
            upload_date TEXT,
            updated_at TEXT
        )
    """)
    
    # Create FTS5 virtual table for full-text search
    c.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS resumes_fts USING fts5(
            profile_id UNINDEXED,
            email UNINDEXED,
            full_name,
            content,
            tokenize = 'porter unicode61'
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ MongoDB search database initialized")

def index_profile(profile_id, email, full_name, content, upload_date=None, updated_at=None):
    """Index a single profile for search
    
    Args:
        profile_id: MongoDB profile ID
        email: User email
        full_name: User's full name
        content: Resume text content (from llm_parsed_backup or extracted text)
        upload_date: When profile was created
        updated_at: When profile was last updated
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # Check if already indexed
        c.execute("SELECT id FROM resumes WHERE profile_id = ?", (profile_id,))
        existing = c.fetchone()
        
        if existing:
            # Update existing record
            c.execute("""
                UPDATE resumes 
                SET email = ?, full_name = ?, content = ?, updated_at = ?
                WHERE profile_id = ?
            """, (email, full_name, content, updated_at or upload_date, profile_id))
            
            # Update FTS
            c.execute("""
                DELETE FROM resumes_fts WHERE profile_id = ?
            """, (profile_id,))
        else:
            # Insert new record
            c.execute("""
                INSERT INTO resumes (profile_id, email, full_name, content, upload_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (profile_id, email, full_name, content, upload_date, updated_at))
        
        # Insert into FTS table
        c.execute("""
            INSERT INTO resumes_fts (profile_id, email, full_name, content)
            VALUES (?, ?, ?, ?)
        """, (profile_id, email, full_name, content))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error indexing profile {profile_id}: {e}")
        return False

def remove_profile_from_index(profile_id):
    """Remove a profile from the search index"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        c.execute("DELETE FROM resumes WHERE profile_id = ?", (profile_id,))
        c.execute("DELETE FROM resumes_fts WHERE profile_id = ?", (profile_id,))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error removing profile {profile_id}: {e}")
        return False

def search_profiles(query, topk=10):
    """Search indexed profiles
    
    Args:
        query: Search query string
        topk: Maximum number of results to return
    
    Returns:
        List of dicts with profile_id, email, full_name, score, snippet
    """
    try:
        if not DB_PATH.exists():
            return []
        
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # Prepare search query
        search_query = prepare_fts_query(query)
        
        # Search using FTS5
        c.execute("""
            SELECT 
                profile_id,
                email,
                full_name,
                snippet(resumes_fts, 3, '<mark>', '</mark>', '...', 30) as snippet,
                rank as score
            FROM resumes_fts
            WHERE resumes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (search_query, topk))
        
        results = []
        for row in c.fetchall():
            results.append({
                'profile_id': row[0],
                'email': row[1],
                'full_name': row[2],
                'snippet': row[3],
                'score': abs(row[4])  # FTS5 rank is negative, make positive
            })
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"Search error: {e}")
        return []

def prepare_fts_query(query):
    """Prepare query for FTS5 search"""
    # Remove special characters that might break FTS5
    query = re.sub(r'[^\w\s]', ' ', query)
    
    # Split into terms
    terms = query.strip().split()
    
    if not terms:
        return ""
    
    # Create OR query for better matching
    fts_query = " OR ".join(f'"{term}"' for term in terms)
    
    return fts_query

def get_index_stats():
    """Get statistics about the search index"""
    try:
        if not DB_PATH.exists():
            return {"indexed_profiles": 0}
        
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM resumes")
        count = c.fetchone()[0]
        
        conn.close()
        return {
            "indexed_profiles": count,
            "database_path": str(DB_PATH)
        }
        
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {"indexed_profiles": 0, "error": str(e)}
