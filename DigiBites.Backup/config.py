import os
import secrets
from dotenv import load_dotenv

load_dotenv()

_configured_secret = os.environ.get('SECRET_KEY')
if not _configured_secret or _configured_secret in {
    'digibites-secret-key-2026',
    'your-secret-key-here',
}:
    _configured_secret = secrets.token_hex(32)

class Config:
    DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'root')
    DB_NAME = os.environ.get('DB_NAME', 'digibites_db')
    SECRET_KEY = _configured_secret
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
