from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from typing import List, Dict
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from app.models import User, Recipe, Interaction
from app import db
from .search_preprocessing import load_whoosh_index, verify_whoosh_index, load_embeddings
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.scoring import BM25F
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SearchResult:
    """Class to store search results along with timing information."""
    recipes: list
    execution_time: float
    total_results: int
    search_type: str
    details: Optional[dict] = None


class Timer:
    """Context manager for measuring execution time of code blocks."""
    
    def __init__(self, description: str = "Operation"):
        self.description = description
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
    
    @property
    def duration(self) -> float:
        """Returns the duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000  # Convert to milliseconds


verify_whoosh_index()
whoosh_index = load_whoosh_index()
recipe_ids, embeddings = load_embeddings()
embeddings = torch.from_numpy(embeddings)
embeddings = util.normalize_embeddings(embeddings)

main_bp = Blueprint('main', __name__)


def search_with_bm25(query_text: str, whoosh_index, limit: int = 10) -> List[int]:
    """
    Performs BM25 search using Whoosh index.
    
    Args:
        query_text: The search query string
        whoosh_index: The Whoosh index object
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        List of recipe IDs matching the search criteria
    """
    # Clean and prepare the query
    query_text = query_text.strip()
    if not query_text:
        return []

    # Create a searcher with BM25F scoring
    with whoosh_index.searcher(weighting=BM25F(B=0.75, K1=1.5)) as searcher:
        # Create parser with OR group to match any of the terms
        parser = MultifieldParser(
            ["name", "ingredients", "text"], 
            schema=whoosh_index.schema,
            group=OrGroup.factory(0.9)  # Allow partial matches
        )
        
        try:
            # Parse the query
            parsed_query = parser.parse(query_text)
            
            # Perform the search
            results = searcher.search(parsed_query, limit=limit)
            
            # Get recipe IDs and scores
            recipe_ids = [(int(hit['id']), hit.score) for hit in results]
            
            # Sort by score in descending order
            recipe_ids.sort(key=lambda x: x[1], reverse=True)
            
            return [rid for rid, _ in recipe_ids]
            
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []
        

@main_bp.route('/')
def home():
    return render_template('home.html', title="Welcome to Recipe Finder")


@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('main.register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title="Register")


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('main.home'))
        flash('Invalid username or password!', 'danger')
    return render_template('login.html', title="Login")


@main_bp.route('/recipes')
def recipes():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('order', 'asc')
    sort_options = {
        'name': Recipe.name,
        'type': Recipe.type,
        'kitchen': Recipe.kitchen,
        'portion_num': Recipe.portion_num,
        'likes': Recipe.likes,
        'bookmarks': Recipe.bookmarks,
    }

    if sort_by in sort_options:
        if sort_order == 'desc':
            recipes_query = Recipe.query.order_by(sort_options[sort_by].desc())
        else:
            recipes_query = Recipe.query.order_by(sort_options[sort_by].asc())
    else:
        recipes_query = Recipe.query.order_by(Recipe.name.asc())
    recipes = recipes_query.paginate(page=page, per_page=per_page)

    return render_template('recipes.html', recipes=recipes, sort_by=sort_by, sort_order=sort_order)


@main_bp.route('/recipe/<int:recipe_id>', methods=['GET', 'POST'])
def recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)

    # Ensure non-null values for counts
    recipe.likes = max(recipe.likes or 0, 0)
    recipe.dislikes = max(recipe.dislikes or 0, 0)
    recipe.bookmarks = max(recipe.bookmarks or 0, 0)

    user_id = session.get('user_id')

    if request.method == 'POST':
        if not user_id:
            flash('You must be logged in to interact with recipes.', 'danger')
            return redirect(url_for('main.login'))

        interaction = Interaction.query.filter_by(user_id=user_id, recipe_id=recipe_id).first()
        if not interaction:
            interaction = Interaction(user_id=user_id, recipe_id=recipe_id)
            db.session.add(interaction)

        action = request.form['action']

        if action == 'like':
            if not interaction.liked:  # If not liked
                recipe.likes += 1
                if interaction.liked is False:  # If switching from dislike
                    recipe.dislikes = max(recipe.dislikes - 1, 0)
                interaction.liked = True
            else:  # Undo like
                recipe.likes = max(recipe.likes - 1, 0)
                interaction.liked = None

        elif action == 'dislike':
            if interaction.liked is not False:  # If not disliked
                recipe.dislikes += 1
                if interaction.liked:  # If switching from like
                    recipe.likes = max(recipe.likes - 1, 0)
                interaction.liked = False
            else:  # Undo dislike
                recipe.dislikes = max(recipe.dislikes - 1, 0)
                interaction.liked = None

        elif action == 'bookmark':
            if not interaction.bookmarked:  # Bookmark the recipe
                recipe.bookmarks += 1
                interaction.bookmarked = True
            else:  # Undo bookmark
                recipe.bookmarks = max(recipe.bookmarks - 1, 0)
                interaction.bookmarked = False

        db.session.commit()
        flash('Your interaction has been recorded.', 'success')

    user_interaction = None
    if user_id:
        user_interaction = Interaction.query.filter_by(user_id=user_id, recipe_id=recipe_id).first()

    return render_template(
        'recipe.html',
        recipe=recipe,
        user_interaction=user_interaction,
        title=recipe.name
    )


@main_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to view your profile.', 'danger')
        return redirect(url_for('main.login'))

    user = User.query.get_or_404(user_id)
    interactions = Interaction.query.filter_by(user_id=user_id).all()
    liked_recipes = [Recipe.query.get(interaction.recipe_id) for interaction in interactions if interaction.liked]
    bookmarked_recipes = [Recipe.query.get(interaction.recipe_id) for interaction in interactions if interaction.bookmarked]

    if request.method == 'POST':
        if 'update' in request.form:
            new_username = request.form.get('new_username')
            new_password = request.form.get('new_password')

            if new_username:
                existing_user = User.query.filter_by(username=new_username).first()
                if existing_user and existing_user.id != user_id:
                    flash('Username already taken. Please choose another.', 'danger')
                    return redirect(url_for('main.profile'))
                user.username = new_username

            if new_password:
                user.password = generate_password_hash(new_password, method='pbkdf2:sha256')

            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('main.profile'))

        elif 'delete' in request.form:
            db.session.delete(user)
            db.session.commit()
            session.clear()
            flash('Account deleted successfully.', 'success')
            return redirect(url_for('main.home'))

    return render_template(
        'profile.html',
        user=user,
        liked_recipes=liked_recipes,
        bookmarked_recipes=bookmarked_recipes,
        title="Your Profile"
    )


@main_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.home'))


@main_bp.route('/rank', methods=['GET'])
def rank_users():
    query = text("""
        SELECT 
            users.username AS username,
            COUNT(interactions.id) AS total_interactions
        FROM 
            users
        INNER JOIN 
            interactions 
        ON 
            users.id = interactions.user_id
        GROUP BY 
            users.id
        ORDER BY 
            total_interactions DESC
        LIMIT 10;
    """)
    result = db.session.execute(query).fetchall()
    users = [{"username": row.username, "total_interactions": row.total_interactions} for row in result]
    return render_template('rank.html', users=users, enumerate=enumerate)


@main_bp.route('/search', methods=['GET', 'POST'])
def search():
    """
    Comprehensive search function that supports multiple search methods:
    - Simple text search (default)
    - BM25-based search
    - Embedding-based semantic search
    """
    recipes = []
    search_type = request.form.get('search_type', 'simple')
    query = request.form.get('query', '').strip()
    search_result = None
    search_performed = False
    if request.method == 'POST' and query:
        search_performed = True
        try:
            if search_type == 'simple':
                # Simple database search
                with Timer('Simple Search') as timer:
                        recipes = Recipe.query.filter(
                            (Recipe.name.like(f"%{query}%")) |
                            (Recipe.type.like(f"%{query}%")) |
                            (Recipe.kitchen.like(f"%{query}%")) |
                            (Recipe.recipe_text.like(f"%{query}%"))
                        ).all()

                search_result = SearchResult(
                    recipes=recipes,
                    execution_time=timer.duration,
                    total_results=len(recipes),
                    search_type="Simple Database Search",
                    details={"type": "SQL LIKE query"}
                )

            elif search_type == 'bm25':
                # Use the improved BM25 search function
                with Timer("BM25 Search") as timer:
                    recipe_ids = search_with_bm25(query, whoosh_index)
                    if recipe_ids:
                    # Fetch recipes while maintaining search order
                        id_to_pos = {id: pos for pos, id in enumerate(recipe_ids)}
                        recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
                        recipes.sort(key=lambda x: id_to_pos[x.id])
                
                search_result = SearchResult(
                    recipes=recipes,
                    execution_time=timer.duration,
                    total_results=len(recipes),
                    search_type="BM25 Search",
                    details={"type": "Whoosh BM25F", "indexed_fields": ["name", "ingredients", "text"]}
                )

            elif search_type == 'embedding':
                # Load embeddings and ids first
                with Timer("Embedding Search") as timer:
                    embedding_data = load_embeddings()  # This returns recipe_ids and embeddings
                    recipe_ids, stored_embeddings = embedding_data
                    model = SentenceTransformer('all-MiniLM-L6-v2')
                    query_embedding = model.encode(query, convert_to_tensor=True)
                    query_embedding = util.normalize_embeddings(query_embedding.unsqueeze(0))    
                    similarities = util.pytorch_cos_sim(query_embedding, stored_embeddings)[0]
                    top_k = 10
                    top_indices = torch.topk(similarities, min(top_k, len(similarities)))[1]
        
                    top_recipe_ids = [recipe_ids[idx] for idx in top_indices.tolist()]
                    if top_recipe_ids:
                        recipes = Recipe.query.filter(Recipe.id.in_(top_recipe_ids)).all()
                        recipes.sort(key=lambda x: top_recipe_ids.index(x.id))

                search_result = SearchResult(
                    recipes=recipes,
                    execution_time=timer.duration,
                    total_results=len(recipes),
                    search_type="Semantic Search",
                    details={
                        "type": "Sentence Transformers",
                        "model": "all-MiniLM-L6-v2",
                        "similarity": "Cosine"
                    }
                )
            
            if not recipes:
                flash('No recipes found matching your search criteria.', 'info')


        except Exception as e:
            flash(f'An error occurred during search: {str(e)}', 'danger')
            recipes = []
            search_result = SearchResult(
                recipes=[],
                execution_time=0,
                total_results=0,
                search_type=search_type,
                details={"error": str(e)}
            )

    return render_template(
        'search.html',
        recipes=recipes,
        search_result=search_result,
        search_type=search_type,
        query=query,
        title="Search Recipes"
    )