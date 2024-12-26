from ensurepip import bootstrap
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
bootstrap = Bootstrap(app)
app.secret_key = 'your_secret_key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:app_password@localhost/recipes_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Recipe(db.Model):
    __tablename__ = 'recipes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(100))
    kitchen = db.Column(db.String(100))
    recipe_text = db.Column(db.Text)
    ingredient_num = db.Column(db.Integer)
    portion_num = db.Column(db.Integer)
    time = db.Column(db.String(50))
    likes = db.Column(db.Integer, default=0)
    dislikes = db.Column(db.Integer, default=0)
    bookmarks = db.Column(db.Integer, default=0)


class Interaction(db.Model):
    __tablename__ = 'interactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'))
    liked = db.Column(db.Boolean, default=False)
    bookmarked = db.Column(db.Boolean, default=False)


@app.route('/')
def home():
    return render_template('home.html', title="Welcome to Recipe Finder")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title="Register")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        flash('Invalid username or password!', 'danger')
    return render_template('login.html', title="Login")


@app.route('/search', methods=['GET', 'POST'])
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


@app.route('/recipe/<int:recipe_id>', methods=['GET', 'POST'])
def recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if request.method == 'POST':
        user_id = session.get('user_id')
        if not user_id:
            flash('You must be logged in to interact with recipes.', 'danger')
            return redirect(url_for('login'))
        action = request.form['action']
        interaction = Interaction.query.filter_by(user_id=user_id, recipe_id=recipe_id).first()
        if not interaction:
            interaction = Interaction(user_id=user_id, recipe_id=recipe_id)
            db.session.add(interaction)
        if action == 'like':
            recipe.likes += 1
            interaction.liked = True
        elif action == 'dislike':
            recipe.dislikes += 1
            interaction.liked = False
        elif action == 'bookmark':
            recipe.bookmarks += 1
            interaction.bookmarked = True
        db.session.commit()
        flash('Your interaction has been recorded.', 'success')
    return render_template('recipe.html', recipe=recipe, title=recipe.name)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to view your profile.', 'danger')
        return redirect(url_for('login'))
    user = User.query.get_or_404(user_id)
    interactions = Interaction.query.filter_by(user_id=user_id).all()
    liked_recipes = [interaction.recipe_id for interaction in interactions if interaction.liked]
    bookmarked_recipes = [interaction.recipe_id for interaction in interactions if interaction.bookmarked]
    if request.method == 'POST':
        if 'update' in request.form:
            new_username = request.form['username']
            new_password = request.form['password']
            if new_username:
                user.username = new_username
            if new_password:
                user.password = generate_password_hash(new_password, method='sha256')
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        elif 'delete' in request.form:
            db.session.delete(user)
            db.session.commit()
            session.clear()
            flash('Account deleted successfully!', 'success')
            return redirect(url_for('home'))
    return render_template('profile.html', user=user, liked_recipes=liked_recipes, bookmarked_recipes=bookmarked_recipes, title="Your Profile")


if __name__ == '__main__':
    app.run(debug=True)