CREATE DATABASE IF NOT EXISTS recipes_db;
USE recipes_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(200) NOT NULL
);

CREATE TABLE IF NOT EXISTS recipes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100),
    kitchen VARCHAR(100),
    recipe_text TEXT,
    ingredient_num INT,
    portion_num INT,
    time VARCHAR(50),
    likes INT DEFAULT 0,
    dislikes INT DEFAULT 0,
    bookmarks INT DEFAULT 0,
    ingredients TEXT,
    text TEXT
);

CREATE TABLE IF NOT EXISTS interactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    recipe_id INT NOT NULL,
    liked BOOLEAN DEFAULT FALSE,
    bookmarked BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);

LOAD DATA INFILE '/docker-entrypoint-initdb.d/final_recipess.csv'
INTO TABLE recipes
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(name, type, kitchen, recipe_text, ingredient_num, portion_num, time, likes, dislikes, bookmarks, ingredients, text);