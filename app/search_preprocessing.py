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
    """
    Creates a Whoosh index from the recipes data with proper configuration for BM25 searching.
    Includes detailed logging and validation to ensure proper index creation.
    """
    print("Starting Whoosh index creation process...")
    
    # Define schema with proper field types and analysis
    schema = Schema(
        id=ID(stored=True, unique=True),
        name=TEXT(stored=True, field_boost=2.0),
        ingredients=TEXT(stored=True),
        text=TEXT(stored=True)
    )

    # Ensure the index directory exists
    if not os.path.exists(WHOOSH_INDEX_DIR):
        os.makedirs(WHOOSH_INDEX_DIR)
        print(f"Created index directory at {WHOOSH_INDEX_DIR}")

    # Create the index
    ix = create_in(WHOOSH_INDEX_DIR, schema)
    writer = ix.writer()

    try:
        # Fetch all recipes and log the count
        recipes = Recipe.query.all()
        total_recipes = len(recipes)
        print(f"Found {total_recipes} recipes to index")

        if total_recipes == 0:
            print("Warning: No recipes found in the database!")
            return

        # Add documents to the index with validation
        for i, recipe in enumerate(recipes, 1):
            # Validate and clean the data before indexing
            recipe_data = {
                'id': str(recipe.id),
                'name': recipe.name if recipe.name else '',
                'ingredients': recipe.ingredients if recipe.ingredients else '',
                'text': recipe.text if recipe.text else ''
            }

            # Log some sample data for verification
            if i <= 3:  # Show first 3 recipes for verification
                print(f"\nIndexing recipe {i}/{total_recipes}:")
                print(f"ID: {recipe_data['id']}")
                print(f"Name: {recipe_data['name'][:50]}...")
                print(f"Ingredients: {recipe_data['ingredients'][:50]}...")
                print(f"Text: {recipe_data['text'][:50]}...")

            # Add the document to the index
            writer.add_document(**recipe_data)

            # Log progress for every 1000 recipes
            if i % 1000 == 0:
                print(f"Indexed {i}/{total_recipes} recipes...")

        # Commit changes and verify
        print("\nCommitting changes to index...")
        writer.commit()
        
        # Verify the index was created successfully
        with ix.searcher() as searcher:
            doc_count = searcher.doc_count()
            print(f"\nIndex creation completed:")
            print(f"Total documents in index: {doc_count}")
            if doc_count != total_recipes:
                print("Warning: Number of indexed documents doesn't match recipe count!")
            
        print("Whoosh index created successfully")
        return ix

    except Exception as e:
        print(f"Error during index creation: {str(e)}")
        # Attempt to clean up in case of error
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