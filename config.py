import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MongoDB Atlas Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://username:password@cluster.mongodb.net/ninermatch?retryWrites=true&w=majority')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'ninermatch')
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'pdf'}

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)