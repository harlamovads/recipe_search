from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional

class SearchMethod(str, Enum):
    """Available search methods."""
    BM25 = "bm25"
    EMBEDDING = "embedding"
    SIMPLE = "simple"

class CorpusInfo(BaseModel):
    """Information about the recipe corpus."""
    total_recipes: int = Field(1806, description="Total number of recipes in the corpus")
    total_tokens: int = Field(5000, description="Total number of tokens in the corpus")
    corpus_name: str = Field("recipe_project", description="Name of the corpus")
    average_recipe_length: float = Field(250, description="Average recipe text length")

class Recipe(BaseModel):
    """Recipe information model."""
    id: int
    name: str
    type: Optional[str]
    kitchen: Optional[str]
    ingredients: Optional[str]
    text: Optional[str]
    likes: int = 0
    dislikes: int = 0
    bookmarks: int = 0
    
    class Config:
        from_attributes = True

class SearchResult(BaseModel):
    """Search result model."""
    recipe: Recipe
    score: Optional[float] = None

class SearchResponse(BaseModel):
    """Search response model."""
    query: str
    method: SearchMethod
    execution_time_ms: float
    total_results: int
    results: List[SearchResult]