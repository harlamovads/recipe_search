import os
import pickle
from typing import List, Dict

from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import MultifieldParser
import torch
from sentence_transformers import SentenceTransformer
import numpy as np

from .models import Recipe
from .extensions import db

PREPROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../preprocessed')
WHOOSH_INDEX_DIR = os.path.join(PREPROCESSED_DIR, 'whoosh_index')
EMBEDDINGS_FILE = os.path.join(PREPROCESSED_DIR, 'embeddings.pkl')

def ensure_preprocessed_data():
    """
    Ensures that preprocessed data exists. If not, preprocess and save.
    """
    if not os.path.exists(PREPROCESSED_DIR):
        os.makedirs(PREPROCESSED_DIR)
        print(f"Created preprocessed directory at {PREPROCESSED_DIR}")

    # Check for Whoosh index
    if not os.path.exists(WHOOSH_INDEX_DIR):
        create_whoosh_index()
    else:
        print("Whoosh index already exists. Skipping index creation.")

    # Check for embeddings
    if not os.path.exists(EMBEDDINGS_FILE):
        create_embeddings()
    else:
        print("Embeddings already exist. Skipping embeddings creation.")

def create_whoosh_index():
    """Creates a Whoosh index from preprocessed recipe data."""
    print("Starting Whoosh index creation process...")
   
   # Import preprocessing tools
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords 
    from nltk.stem import WordNetLemmatizer
    import string

   # Download required NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('corpora/stopwords')
        nltk.data.find('corpora/wordnet')
    except LookupError:
        nltk.download('punkt')
        nltk.download('stopwords')
        nltk.download('wordnet')

   # Initialize preprocessor
    lemmatizer = WordNetLemmatizer()
    stop_words = set(stopwords.words('english'))
   
    def preprocess_text(text):
        if not text:
            return ""
        # Lowercase
        text = text.lower()
        # Remove punctuation
        text = text.translate(str.maketrans("", "", string.punctuation))
        # Tokenize
        tokens = word_tokenize(text)
        # Remove stopwords and lemmatize
        tokens = [lemmatizer.lemmatize(token) for token in tokens if token not in stop_words]
        # Rejoin text
        return " ".join(tokens)

    schema = Schema(
        id=ID(stored=True, unique=True),
        name=TEXT(stored=True, field_boost=2.0),
        ingredients=TEXT(stored=True),
        text=TEXT(stored=True)
    )

    if not os.path.exists(WHOOSH_INDEX_DIR):
        os.makedirs(WHOOSH_INDEX_DIR)

    ix = create_in(WHOOSH_INDEX_DIR, schema)
    writer = ix.writer()

    try:
        recipes = Recipe.query.all()
        total_recipes = len(recipes)
        print(f"Found {total_recipes} recipes to index")

        if total_recipes == 0:
            print("Warning: No recipes found in database!")
            return

        for i, recipe in enumerate(recipes, 1):
            recipe_data = {
                'id': str(recipe.id),
                'name': preprocess_text(recipe.name),
                'ingredients': preprocess_text(recipe.ingredients),
                'text': preprocess_text(recipe.text)
            }

            if i <= 3:
                print(f"\nIndexing recipe {i}/{total_recipes}:")
                for key, value in recipe_data.items():
                    print(f"{key}: {value[:50]}...")
 
            writer.add_document(**recipe_data)
 
            if i % 1000 == 0:
                print(f"Indexed {i}/{total_recipes} recipes...")

        writer.commit()
       
        with ix.searcher() as searcher:
            doc_count = searcher.doc_count()
            print(f"\nIndex creation completed: {doc_count} documents indexed")
           
        return ix

    except Exception as e:
        print(f"Error during index creation: {str(e)}")
        writer.cancel()
        raise

def verify_whoosh_index():
    """
    Verifies the content of the Whoosh index and prints statistics.
    """
    if not os.path.exists(WHOOSH_INDEX_DIR):
        print("Index directory does not exist!")
        return
        
    ix = open_dir(WHOOSH_INDEX_DIR)
    with ix.searcher() as searcher:
        print(f"Number of documents in index: {searcher.doc_count()}")
        
        # Convert generator to list for the first 5 documents
        sample_docs = []
        for i, doc in enumerate(searcher.documents()):
            if i >= 5:  # Only take the first 5 documents
                break
            sample_docs.append(doc)
            print(f"Sample document {i+1}: {doc}")
            
        if not sample_docs:
            print("No documents found in the index!")


def create_embeddings():
    """
    Creates sentence-transformer embeddings from the recipes data.
    """
    print("Creating sentence-transformer embeddings...")
    # Fetch data from the database
    recipes = Recipe.query.all()

    # Concatenate relevant fields
    texts = [f"{recipe.name} {recipe.ingredients} {recipe.text}" for recipe in recipes]
    recipe_ids = [recipe.id for recipe in recipes]

    # Load the model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Generate embeddings and convert to numpy for storage
    embeddings = model.encode(texts, convert_to_tensor=True)
    embeddings = embeddings.detach().cpu().numpy()

    # Save embeddings and recipe_ids
    with open(EMBEDDINGS_FILE, 'wb') as f:
        pickle.dump({
            'recipe_ids': recipe_ids, 
            'embeddings': embeddings
        }, f)

    print("Embeddings created and saved successfully.")

def load_whoosh_index():
    """
    Loads the Whoosh index.
    """
    if not os.path.exists(WHOOSH_INDEX_DIR):
        raise FileNotFoundError("Whoosh index directory does not exist.")
    ix = open_dir(WHOOSH_INDEX_DIR)
    return ix

def load_embeddings():
    """
    Loads the sentence-transformer embeddings.
    """
    if not os.path.exists(EMBEDDINGS_FILE):
        raise FileNotFoundError("Embeddings file does not exist.")
    with open(EMBEDDINGS_FILE, 'rb') as f:
        data = pickle.load(f)
    return data['recipe_ids'], data['embeddings']