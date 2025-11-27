from pathlib import Path
from database import Database
from dotenv import load_dotenv

import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_BOT_API = os.getenv("CRYPTO_BOT_API")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS")
TRON_API_KEY= os.getenv("TRON_API_KEY")

NOTIFY_DELAYS = [5, 3, 2, 1, 0.5]

db_file = Path(BASE_DIR, "misc", 'db.sqlite')

BDB = Database(db_file)
