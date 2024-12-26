from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from app.models import User, Recipe, Interaction
from app import db

main_bp = Blueprint('main', __name__)


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


@main_bp.route('/search', methods=['GET', 'POST'])
def search():
    recipes = []
    if request.method == 'POST':
        query = request.form['query']
        recipes = Recipe.query.filter(
            (Recipe.name.like(f"%{query}%")) |
            (Recipe.type.like(f"%{query}%")) |
            (Recipe.kitchen.like(f"%{query}%")) |
            (Recipe.recipe_text.like(f"%{query}%"))
        ).all()
    return render_template('search.html', recipes=recipes, title="Search Recipes")


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