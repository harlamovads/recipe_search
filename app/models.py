from app import db


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