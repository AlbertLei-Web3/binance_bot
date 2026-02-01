from core.client import get_client

client = get_client()

def get_mark_price(symbol: str) -> float:
    data = client.futures_mark_price(symbol=symbol)
    return float(data["markPrice"])

def get_klines(symbol: str, interval="1m", limit=100):
    return client.futures_klines(
        symbol=symbol,
        interval=interval,
        limit=limit
    )
