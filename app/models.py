from app import db


class User(db.Model):
    """User model for storing user account information."""
    
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    interactions = db.relationship('Interaction', backref='user', lazy=True)


class Recipe(db.Model):
    """Recipe model for storing recipe information."""
    
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
    ingredients = db.Column(db.String(200))
    text = db.Column(db.String(1000))
    interactions = db.relationship('Interaction', backref='recipe', lazy=True)


class Interaction(db.Model):
    """Model for storing user interactions with recipes."""
    
    __tablename__ = 'interactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    liked = db.Column(db.Boolean, default=False)
    bookmarked = db.Column(db.Boolean, default=False)