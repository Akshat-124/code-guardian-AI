import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# App Configurations
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")

# AI / ML Configurations
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-flash")

# Storage Configurations
DB_DIR = os.getenv("DB_DIR", "data/chroma")
