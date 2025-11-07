"""
Advanced semantic search using OpenAI embeddings
Provides meaning-based search capabilities for resume profiles
"""

import os
import json
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .mongodb_search import DB_PATH

# Embedding configuration
EMBEDDING_MODEL = "text-embedding-3-small"  # Cost-effective OpenAI model
EMBEDDING_DIMENSION = 1536  # Dimension for text-embedding-3-small
SIMILARITY_THRESHOLD = 0.32  # Minimum similarity score for results (high precision mode)

class SemanticSearchEngine:
    """Handles semantic search using OpenAI embeddings"""
    
    def __init__(self):
        self.client = None
        self.db_path = DB_PATH
        self.embeddings_table = "profile_embeddings"
        
        # Initialize OpenAI client
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = OpenAI(api_key=api_key)
            else:
                print("⚠️  OPENAI_API_KEY not found - semantic search will be disabled")
        else:
            print("⚠️  OpenAI package not available - semantic search will be disabled")
    
    def is_available(self) -> bool:
        """Check if semantic search is available"""
        return self.client is not None
    
    def init_embeddings_table(self):
        """Initialize the embeddings table in SQLite"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            
            # Create embeddings table
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.embeddings_table} (
                    profile_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    full_name TEXT,
                    embedding BLOB NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create index for faster lookups
            c.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_embeddings_profile 
                ON {self.embeddings_table}(profile_id)
            """)
            
            conn.commit()
            conn.close()
            print("✅ Semantic search database initialized")
            return True
            
        except Exception as e:
            print(f"❌ Error initializing embeddings table: {e}")
            return False
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate OpenAI embedding for text"""
        if not self.client:
            return None
        
        try:
            # Clean and prepare text
            text = text.strip()
            if not text:
                return None
            
            # Truncate if too long (OpenAI has token limits)
            if len(text) > 8000:  # Rough character limit
                text = text[:8000]
            
            # Generate embedding
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # Small delay to avoid rate limits
            time.sleep(0.2)
            
            return embedding
            
        except Exception as e:
            print(f"❌ Error generating embedding: {e}")
            return None
    
    def content_hash(self, content: str) -> str:
        """Generate a simple hash for content to check if re-embedding is needed"""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()
    
    def store_profile_embedding(self, profile_id: str, email: str, full_name: str, content: str) -> bool:
        """Store or update profile embedding"""
        if not self.client:
            return False
        
        try:
            # Generate content hash
            content_hash = self.content_hash(content)
            
            # Check if we already have this exact content
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            
            c.execute(f"""
                SELECT content_hash FROM {self.embeddings_table} 
                WHERE profile_id = ?
            """, (profile_id,))
            
            existing = c.fetchone()
            if existing and existing[0] == content_hash:
                print(f"⚡ Embedding already up-to-date for {email}")
                conn.close()
                return True
            
            # Generate new embedding
            print(f"🔄 Generating embedding for {email}...")
            embedding = self.generate_embedding(content)
            if not embedding:
                conn.close()
                return False
            
            # Convert embedding to bytes for storage
            embedding_bytes = json.dumps(embedding).encode()
            
            # Store or update
            now = datetime.now().isoformat()
            
            if existing:
                c.execute(f"""
                    UPDATE {self.embeddings_table}
                    SET email = ?, full_name = ?, embedding = ?, content_hash = ?, updated_at = ?
                    WHERE profile_id = ?
                """, (email, full_name, embedding_bytes, content_hash, now, profile_id))
                print(f"✅ Updated embedding for {email}")
            else:
                c.execute(f"""
                    INSERT INTO {self.embeddings_table} 
                    (profile_id, email, full_name, embedding, content_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (profile_id, email, full_name, embedding_bytes, content_hash, now, now))
                print(f"✅ Created embedding for {email}")
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Error storing embedding for {profile_id}: {e}")
            return False
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            
            # Calculate dot product
            dot_product = np.dot(vec1, vec2)
            
            # Calculate norms
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            # Avoid division by zero
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception:
            return 0.0
    
    def semantic_search(self, query: str, topk: int = 10) -> List[Dict[str, Any]]:
        """Perform semantic search using embeddings"""
        if not self.client:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Get all stored embeddings
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            
            c.execute(f"""
                SELECT profile_id, email, full_name, embedding
                FROM {self.embeddings_table}
            """)
            
            results = []
            
            for row in c.fetchall():
                profile_id, email, full_name, embedding_bytes = row
                
                try:
                    # Decode embedding
                    stored_embedding = json.loads(embedding_bytes.decode())
                    
                    # Calculate similarity
                    similarity = self.cosine_similarity(query_embedding, stored_embedding)
                    
                    # Only include if above threshold
                    if similarity >= SIMILARITY_THRESHOLD:
                        # Get actual content snippet from profile
                        snippet = self._generate_snippet(profile_id, query)
                        
                        results.append({
                            'profile_id': profile_id,
                            'email': email,
                            'full_name': full_name,
                            'score': similarity,
                            'snippet': snippet,
                            'search_type': 'semantic'
                        })
                
                except Exception as e:
                    print(f"WARNING: Error processing embedding for {profile_id}: {e}")
                    continue
            
            conn.close()
            
            # Sort by similarity score (descending)
            results.sort(key=lambda x: x['score'], reverse=True)
            
            # If we have very few results, try a slightly lower threshold for more matches
            if len(results) < 3 and SIMILARITY_THRESHOLD > 0.25:
                print(f"Only {len(results)} results with threshold {SIMILARITY_THRESHOLD}, trying lower threshold...")
                conn = sqlite3.connect(str(self.db_path))
                c = conn.cursor()
                
                c.execute(f"""
                    SELECT profile_id, email, full_name, embedding
                    FROM {self.embeddings_table}
                """)
                
                lower_threshold = SIMILARITY_THRESHOLD - 0.05  # Try 5% lower
                additional_results = []
                
                for row in c.fetchall():
                    profile_id, email, full_name, embedding_bytes = row
                    
                    try:
                        stored_embedding = json.loads(embedding_bytes.decode())
                        similarity = self.cosine_similarity(query_embedding, stored_embedding)
                        
                        # Get results in the lower threshold range
                        if lower_threshold <= similarity < SIMILARITY_THRESHOLD:
                            snippet = self._generate_snippet(profile_id, query)
                            
                            additional_results.append({
                                'profile_id': profile_id,
                                'email': email,
                                'full_name': full_name,
                                'score': similarity,
                                'snippet': snippet,
                                'search_type': 'semantic'
                            })
                    
                    except Exception as e:
                        continue
                
                # Add best additional results
                additional_results.sort(key=lambda x: x['score'], reverse=True)
                results.extend(additional_results[:max(0, min(3, 6-len(results)))])  # Up to 6 total
                results.sort(key=lambda x: x['score'], reverse=True)
                
                conn.close()
            
            # Return top results
            return results[:topk]
            
        except Exception as e:
            print(f"ERROR: Semantic search error: {e}")
            return []
    
    def remove_profile_embedding(self, profile_id: str) -> bool:
        """Remove profile embedding from storage"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            
            c.execute(f"""
                DELETE FROM {self.embeddings_table} 
                WHERE profile_id = ?
            """, (profile_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Error removing embedding for {profile_id}: {e}")
            return False
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        try:
            if not Path(self.db_path).exists():
                return {"total_embeddings": 0}
            
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            
            # Check if table exists
            c.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{self.embeddings_table}'
            """)
            
            if not c.fetchone():
                conn.close()
                return {"total_embeddings": 0, "table_exists": False}
            
            # Get count
            c.execute(f"SELECT COUNT(*) FROM {self.embeddings_table}")
            count = c.fetchone()[0]
            
            # Get latest update
            c.execute(f"""
                SELECT MAX(updated_at) FROM {self.embeddings_table}
            """)
            latest_update = c.fetchone()[0]
            
            conn.close()
            
            return {
                "total_embeddings": count,
                "latest_update": latest_update,
                "table_exists": True,
                "semantic_search_available": self.is_available()
            }
            
        except Exception as e:
            return {
                "total_embeddings": 0,
                "error": str(e),
                "semantic_search_available": self.is_available()
            }
    
    def _generate_snippet(self, profile_id: str, query: str) -> str:
        """Generate a meaningful snippet from profile content for the given query"""
        try:
            # Try to get profile from keyword search first
            from . import mongodb_search
            
            # Get profile content from keyword search
            results = mongodb_search.search_profiles(query, topk=100)
            
            # Find the matching profile in keyword results
            for result in results:
                if result.get('profile_id') == profile_id:
                    keyword_snippet = result.get('snippet', '')
                    if keyword_snippet and len(keyword_snippet.strip()) > 10:
                        return keyword_snippet
            
            # If not found in keyword search, get profile data directly from MongoDB
            from src.core.database import db_manager
            
            # Get profile from MongoDB directly using ObjectId
            from bson import ObjectId
            if db_manager.db is not None:
                try:
                    profile = db_manager.db.profiles.find_one({'_id': ObjectId(profile_id)})
                except:
                    # If ObjectId conversion fails, try string
                    profile = db_manager.db.profiles.find_one({'_id': profile_id})
            else:
                profile = None
            
            if profile:
                content_parts = []
                
                # Extract relevant content for snippet
                personal_info = profile.get('personal_info', {})
                if personal_info.get('major'):
                    content_parts.append(f"Major: {personal_info.get('major')}")
                
                skills = profile.get('skills', {})
                tech_skills = skills.get('technical', [])
                if tech_skills and isinstance(tech_skills, list):
                    tech_str = ', '.join([str(s) for s in tech_skills[:5] if isinstance(s, str)])
                    if tech_str:
                        content_parts.append(f"Skills: {tech_str}")
                
                academic = profile.get('academic', {})
                courses = academic.get('courses', [])
                if courses and isinstance(courses, list):
                    courses_str = ', '.join([str(c) for c in courses[:3] if isinstance(c, str)])
                    if courses_str:
                        content_parts.append(f"Courses: {courses_str}")
                
                interests = profile.get('interests', {})
                academic_int = interests.get('academic', [])
                if academic_int and isinstance(academic_int, list):
                    int_str = ', '.join([str(i) for i in academic_int[:3] if isinstance(i, str)])
                    if int_str:
                        content_parts.append(f"Interests: {int_str}")
                
                if content_parts:
                    return '. '.join(content_parts)[:250] + '...'
                
                # Fallback to basic profile info
                name = personal_info.get('full_name', 'Unknown')
                major = personal_info.get('major', 'Unknown Major')
                return f"{name} - {major}"
            
            # Final fallback
            return f"Semantic match for profile {profile_id}"
            
        except Exception as e:
            print(f"WARNING: Error generating snippet for {profile_id}: {e}")
            return f"Semantic match (profile: {profile_id})"

# Global instance
semantic_engine = SemanticSearchEngine()

def init_semantic_search():
    """Initialize semantic search system"""
    return semantic_engine.init_embeddings_table()

def generate_profile_embedding(profile_id: str, email: str, full_name: str, content: str) -> bool:
    """Generate and store embedding for a profile"""
    return semantic_engine.store_profile_embedding(profile_id, email, full_name, content)

def search_semantic(query: str, topk: int = 10) -> List[Dict[str, Any]]:
    """Perform semantic search"""
    return semantic_engine.semantic_search(query, topk)

def remove_embedding(profile_id: str) -> bool:
    """Remove profile embedding"""
    return semantic_engine.remove_profile_embedding(profile_id)

def get_stats() -> Dict[str, Any]:
    """Get embedding statistics"""
    return semantic_engine.get_embedding_stats()

def is_semantic_available() -> bool:
    """Check if semantic search is available"""
    return semantic_engine.is_available()