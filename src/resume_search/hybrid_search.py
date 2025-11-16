"""
Hybrid search system combining keyword-based FTS5 search with semantic embeddings search
Provides the best of both traditional and AI-powered search approaches
"""

from typing import List, Dict, Any, Optional
from .mongodb_search import search_profiles as keyword_search
from .semantic_search import search_semantic, is_semantic_available

def normalize_scores(results: List[Dict[str, Any]], max_score: float = 1.0) -> List[Dict[str, Any]]:
    """Normalize scores to a 0-1 range for fair comparison"""
    if not results:
        return results
    
    # Find min and max scores
    scores = [r['score'] for r in results if 'score' in r]
    if not scores:
        return results
    
    min_score = min(scores)
    max_score_actual = max(scores)
    
    # Avoid division by zero
    if max_score_actual == min_score:
        for result in results:
            result['normalized_score'] = max_score
        return results
    
    # Normalize to 0-1 range
    for result in results:
        if 'score' in result:
            normalized = (result['score'] - min_score) / (max_score_actual - min_score)
            result['normalized_score'] = normalized * max_score
        else:
            result['normalized_score'] = 0.0
    
    return results

def merge_search_results(keyword_results: List[Dict[str, Any]], 
                        semantic_results: List[Dict[str, Any]], 
                        keyword_weight: float = 0.4,
                        semantic_weight: float = 0.6) -> List[Dict[str, Any]]:
    """Merge and rank results from both search methods"""
    
    # Normalize scores for fair comparison
    keyword_results = normalize_scores(keyword_results)
    semantic_results = normalize_scores(semantic_results)
    
    # Create a dictionary to merge results by profile_id
    merged = {}
    
    # Add keyword search results
    for result in keyword_results:
        profile_id = result.get('profile_id')
        if profile_id:
            result['keyword_score'] = result.get('normalized_score', 0.0)
            result['semantic_score'] = 0.0
            result['search_methods'] = ['keyword']
            merged[profile_id] = result.copy()
    
    # Add or merge semantic search results
    for result in semantic_results:
        profile_id = result.get('profile_id')
        if profile_id:
            if profile_id in merged:
                # Profile found by both methods - merge scores
                merged[profile_id]['semantic_score'] = result.get('normalized_score', 0.0)
                merged[profile_id]['search_methods'].append('semantic')
                # Keep the keyword snippet (which has actual content) but add semantic info
                keyword_snippet = merged[profile_id].get('snippet', '')
                if keyword_snippet and not keyword_snippet.startswith('Found by both'):
                    # Preserve the actual content snippet from keyword search
                    merged[profile_id]['snippet'] = keyword_snippet
                elif not keyword_snippet:
                    # Fallback to semantic snippet if no keyword snippet
                    merged[profile_id]['snippet'] = result.get('snippet', f"Semantic match (similarity: {result.get('score', 0):.3f})")
            else:
                # Profile only found by semantic search
                result['keyword_score'] = 0.0
                result['semantic_score'] = result.get('normalized_score', 0.0)
                result['search_methods'] = ['semantic']
                merged[profile_id] = result.copy()
    
    # Calculate combined scores and create final results
    final_results = []
    for profile_id, result in merged.items():
        keyword_score = result.get('keyword_score', 0.0)
        semantic_score = result.get('semantic_score', 0.0)
        
        # Calculate weighted combined score
        combined_score = (keyword_score * keyword_weight) + (semantic_score * semantic_weight)
        
        # Boost score if found by both methods
        if len(result.get('search_methods', [])) > 1:
            combined_score *= 1.2  # 20% boost for multi-method matches
        
        result['final_score'] = combined_score
        result['score'] = combined_score  # Update main score field
        
        final_results.append(result)
    
    # Sort by final score (descending)
    final_results.sort(key=lambda x: x.get('final_score', 0), reverse=True)
    
    return final_results

def hybrid_search(query: str, topk: int = 10, 
                 use_semantic: bool = True, 
                 semantic_weight: float = 0.6) -> Dict[str, Any]:
    """
    Perform hybrid search using both keyword and semantic methods
    
    Args:
        query: Search query string
        topk: Maximum number of results to return
        use_semantic: Whether to include semantic search
        semantic_weight: Weight for semantic results (0.0-1.0)
    
    Returns:
        Dict containing results and metadata
    """
    
    if not query or not query.strip():
        return {
            'results': [],
            'query': query,
            'methods_used': [],
            'total_found': 0,
            'semantic_available': is_semantic_available()
        }
    
    methods_used = []
    
    # Perform semantic search if available and requested
    semantic_results = []
    if use_semantic and is_semantic_available():
        print(f"SEMANTIC: Performing semantic search for: '{query}'")
        semantic_results = search_semantic(query, topk=topk)
        if semantic_results:
            methods_used.append('semantic')
            # Use semantic results directly - no keyword mixing
            merged_results = semantic_results
        else:
            # Fallback to keyword search if semantic returns no results
            print(f"SEARCH: Semantic found no results, falling back to keyword search")
            keyword_results = keyword_search(query, topk=topk)
            methods_used.append('keyword')
            merged_results = keyword_results
    else:
        # Fallback to keyword search when semantic not available
        print(f"SEARCH: Performing keyword search for: '{query}'")
        keyword_results = keyword_search(query, topk=topk)
        methods_used.append('keyword')
        merged_results = keyword_results
        for result in merged_results:
            result['search_methods'] = ['keyword']
            result['final_score'] = result.get('score', 0)
    
    # Limit to requested number of results
    final_results = merged_results[:topk]
    
    # Add metadata to results
    for result in final_results:
        # Set search method information
        if 'search_methods' not in result:
            result['search_methods'] = methods_used
        if 'final_score' not in result:
            result['final_score'] = result.get('score', 0)
        if 'search_type' not in result:
            result['search_type'] = methods_used[0] if methods_used else 'semantic'
    
    return {
        'results': final_results,
        'query': query,
        'methods_used': methods_used,
        'total_found': len(merged_results),
        'semantic_available': is_semantic_available(),
        'search_method': 'semantic' if 'semantic' in methods_used else 'keyword'
    }

def search_with_fallback(query: str, topk: int = 10) -> Dict[str, Any]:
    """
    Search with automatic fallback to keyword-only if semantic fails
    """
    try:
        # Try hybrid search first
        return hybrid_search(query, topk=topk, use_semantic=True)
    except Exception as e:
        print(f"WARNING: Hybrid search failed, falling back to keyword search: {e}")
        # Fallback to keyword-only search
        keyword_results = keyword_search(query, topk=topk)
        return {
            'results': keyword_results,
            'query': query,
            'methods_used': ['keyword'],
            'total_found': len(keyword_results),
            'semantic_available': False,
            'fallback_used': True,
            'error': str(e)
        }

def get_search_capabilities() -> Dict[str, Any]:
    """Get information about available search capabilities"""
    return {
        'keyword_search': True,
        'semantic_search': is_semantic_available(),
        'hybrid_search': is_semantic_available(),
        'openai_configured': is_semantic_available()
    }