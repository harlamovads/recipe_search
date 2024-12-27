import logging
from fastapi import FastAPI, Query, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app import create_app
from contextlib import contextmanager
from sqlalchemy.orm import Session
from .schemas import SearchMethod, CorpusInfo, SearchResponse, SearchResult
from .models import Recipe as DBRecipe
from .search_preprocessing import load_whoosh_index, load_embeddings
from sentence_transformers import SentenceTransformer, util
import torch
from whoosh.qparser import MultifieldParser
import time
import nltk
from typing import Optional, List, Dict
from . import db
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = create_app()

app = FastAPI(
    title="Recipe Search API",
    description="API for searching recipes using various methods",
    version="1.0.0"
)


class FlaskContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that creates a Flask application context for each request.
    This allows us to use Flask-SQLAlchemy models seamlessly within FastAPI.
    """
    def __init__(self, app, flask_app):
        super().__init__(app)
        self.flask_app = flask_app

    async def dispatch(self, request, call_next):
        # Create Flask context for the duration of the request
        with self.flask_app.app_context():
            response = await call_next(request)
            return response
        

app.add_middleware(FlaskContextMiddleware, flask_app=flask_app)


@app.on_event("startup")
async def startup_event():
    """Log when the API starts up"""
    logger.info("API is starting up...")
    logger.info("Initializing search components...")


@app.get("/")
async def root():
    """Root endpoint to verift API is running"""
    logger.info("Root endpoint accesed")
    return {"API is running"}


@app.get("/methods", response_model=List[SearchMethod])
async def get_search_methods():
    """Get list of available search methods."""
    return list(SearchMethod)

@app.get("/corpus-info", response_model=CorpusInfo)
async def get_corpus_info():
    """Get information about the recipe corpus."""
    # Count total recipes
    total_recipes = DBRecipe.query.count()
    
    # Calculate total tokens and average recipe length
    total_tokens = 0
    total_length = 0
    
    for recipe in DBRecipe.query.all():
        text = f"{recipe.name} {recipe.ingredients} {recipe.text}"
        tokens = nltk.word_tokenize(text)
        total_tokens += len(tokens)
        total_length += len(text)
    
    avg_length = total_length / total_recipes if total_recipes > 0 else 0
    
    return CorpusInfo(
        total_recipes=total_recipes,
        total_tokens=total_tokens,
        corpus_name="Recipe Collection",
        average_recipe_length=avg_length
    )

@app.get("/search", response_model=SearchResponse)
async def search_recipes(
    query: str,
    method: SearchMethod = SearchMethod.BM25,
    limit: int = Query(default=10, ge=1, le=100),
    include_scores: bool = False
):
    """
    Search recipes using specified method.
    
    Args:
        query: Search query
        method: Search method to use
        limit: Maximum number of results
        include_scores: Whether to include relevance scores
        
    Returns:
        SearchResponse object containing search results
    """
    start_time = time.time()
    results = []
    
    try:
        if method == SearchMethod.BM25:
            whoosh_index = load_whoosh_index()
            with whoosh_index.searcher() as searcher:
                parser = MultifieldParser(["name", "ingredients", "text"], 
                                       schema=whoosh_index.schema)
                parsed_query = parser.parse(query)
                search_results = searcher.search(parsed_query, limit=limit)
                
                recipe_ids = [int(hit['id']) for hit in search_results]
                scores = [hit.score for hit in search_results] if include_scores else None
                
                recipes = DBRecipe.query.filter(DBRecipe.id.in_(recipe_ids)).all()
                id_to_recipe = {r.id: r for r in recipes}
                
                for i, rid in enumerate(recipe_ids):
                    if rid in id_to_recipe:
                        results.append(SearchResult(
                            recipe=id_to_recipe[rid],
                            score=scores[i] if scores else None
                        ))
                        
        elif method == SearchMethod.EMBEDDING:
            recipe_ids, stored_embeddings = load_embeddings()
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            query_embedding = model.encode(query, convert_to_tensor=True)
            query_embedding = util.normalize_embeddings(query_embedding.unsqueeze(0))
            similarities = util.pytorch_cos_sim(query_embedding, stored_embeddings)[0]
            
            top_k = torch.topk(similarities, min(limit, len(similarities)))
            top_indices = top_k.indices.tolist()
            scores = top_k.values.tolist() if include_scores else None
            
            recipe_ids = [recipe_ids[idx] for idx in top_indices]
            recipes = DBRecipe.query.filter(DBRecipe.id.in_(recipe_ids)).all()
            id_to_recipe = {r.id: r for r in recipes}

            for i, rid in enumerate(recipe_ids):
                if rid in id_to_recipe:
                    results.append(SearchResult(
                        recipe=id_to_recipe[rid],
                        score=scores[i] if scores else None
                    ))
                    
        elif method == SearchMethod.SIMPLE:
            recipes = DBRecipe.query.filter(
                (DBRecipe.name.like(f"%{query}%")) |
                (DBRecipe.type.like(f"%{query}%")) |
                (DBRecipe.kitchen.like(f"%{query}%")) |
                (DBRecipe.text.like(f"%{query}%"))
            ).limit(limit).all()
            
            results = [SearchResult(recipe=recipe) for recipe in recipes]
            
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return SearchResponse(
            query=query,
            method=method,
            execution_time_ms=execution_time,
            total_results=len(results),
            results=results
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")