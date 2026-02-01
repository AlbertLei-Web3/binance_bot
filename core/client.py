import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

def get_client():
    return Client(
        api_key=os.getenv("BINANCE_API_KEY"),
        api_secret=os.getenv("BINANCE_API_SECRET")
    )
