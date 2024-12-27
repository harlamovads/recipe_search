from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os
import time
import logging

logger = logging.getLogger(__name__)

def wait_for_db(database_url: str, max_retries: int = 30, retry_interval: int = 1):
    """
    Wait for database to become available.
    
    Args:
        database_url: Database connection URL
        max_retries: Maximum number of connection attempts
        retry_interval: Time between attempts in seconds
    """
    engine = create_engine(database_url)
    for attempt in range(max_retries):
        try:
            engine.connect()
            logger.info("Successfully connected to the database")
            return engine
        except Exception as e:
            if attempt + 1 == max_retries:
                logger.error(f"Could not connect to database after {max_retries} attempts")
                raise
            logger.warning(f"Database connection attempt {attempt + 1} failed. Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)

# Get database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://app_user:app_password@db/recipes_db')

# Create engine with retry logic
engine = wait_for_db(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a function to get database sessions
def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()