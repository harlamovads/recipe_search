import argparse
from app import create_app
from app.models import Recipe
from app.search_preprocessing import load_whoosh_index, load_embeddings, verify_whoosh_index
from sentence_transformers import SentenceTransformer
import torch
from sentence_transformers import util
from whoosh.qparser import MultifieldParser
import time

def search_bm25(query, whoosh_index, limit=10):
    """
    Perform BM25 search using Whoosh index.
    
    Args:
        query (str): Search query
        whoosh_index: Whoosh index object
        limit (int): Maximum number of results
        
    Returns:
        list: List of recipe IDs matching the query
    """
    with whoosh_index.searcher() as searcher:
        parser = MultifieldParser(["name", "ingredients", "text"], 
                                schema=whoosh_index.schema)
        parsed_query = parser.parse(query)
        results = searcher.search(parsed_query, limit=limit)
        return [int(hit['id']) for hit in results]

def search_embeddings(query, model, stored_embeddings, recipe_ids, limit=10):
    """
    Perform embedding-based search.
    
    Args:
        query (str): Search query
        model: SentenceTransformer model
        stored_embeddings: Pre-computed embeddings
        recipe_ids: List of recipe IDs
        limit (int): Maximum number of results
        
    Returns:
        list: List of recipe IDs matching the query
    """
    query_embedding = model.encode(query, convert_to_tensor=True)
    query_embedding = util.normalize_embeddings(query_embedding.unsqueeze(0))
    similarities = util.pytorch_cos_sim(query_embedding, stored_embeddings)[0]
    top_indices = torch.topk(similarities, min(limit, len(similarities)))[1]
    return [recipe_ids[idx] for idx in top_indices.tolist()]

def format_recipe(recipe):
    """Format recipe details for display."""
    return (f"ID: {recipe.id}\n"
            f"Name: {recipe.name}\n"
            f"Type: {recipe.type}\n"
            f"Kitchen: {recipe.kitchen}\n"
            f"Ingredients: {recipe.ingredients}\n"
            f"Text: {recipe.text}\n"
            f"Likes: {recipe.likes} | Dislikes: {recipe.dislikes} | "
            f"Bookmarks: {recipe.bookmarks}\n"
            f"{'-'*80}")

def main():
    parser = argparse.ArgumentParser(description='Recipe Search CLI')
    parser.add_argument('--query', '-q', type=str, required=True,
                      help='Search query')
    parser.add_argument('--method', '-m', type=str, choices=['bm25', 'embedding'],
                      default='bm25', help='Search method (default: bm25)')
    parser.add_argument('--limit', '-l', type=int, default=10,
                      help='Maximum number of results (default: 10)')
    parser.add_argument('--verify-index', action='store_true',
                      help='Verify the Whoosh index before searching')

    args = parser.parse_args()

    # Create Flask app context
    app = create_app()
    with app.app_context():
        try:
            if args.verify_index:
                print("Verifying Whoosh index...")
                verify_whoosh_index()
                print("\n" + "="*80 + "\n")

            start_time = time.time()
            
            if args.method == 'bm25':
                print(f"Performing BM25 search for: {args.query}")
                whoosh_index = load_whoosh_index()
                recipe_ids = search_bm25(args.query, whoosh_index, args.limit)
                recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
                # Sort recipes to match search order
                id_to_recipe = {r.id: r for r in recipes}
                recipes = [id_to_recipe[rid] for rid in recipe_ids if rid in id_to_recipe]

            else:  # embedding search
                print(f"Performing embedding search for: {args.query}")
                recipe_ids, stored_embeddings = load_embeddings()
                model = SentenceTransformer('all-MiniLM-L6-v2')
                recipe_ids = search_embeddings(args.query, model, stored_embeddings, 
                                            recipe_ids, args.limit)
                recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
                # Sort recipes to match search order
                id_to_recipe = {r.id: r for r in recipes}
                recipes = [id_to_recipe[rid] for rid in recipe_ids if rid in id_to_recipe]

            end_time = time.time()
            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds

            print(f"\nFound {len(recipes)} results in {execution_time:.2f}ms\n")
            print("="*80)
            
            for recipe in recipes:
                print(format_recipe(recipe))

        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == '__main__':
    main()