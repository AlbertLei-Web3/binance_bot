from core.client import get_client

client = get_client()

def get_wallet_balance() -> float:
    account = client.futures_account()
    return float(account["totalWalletBalance"])

def get_open_positions():
    positions = client.futures_position_information()
    return [
        p for p in positions
        if float(p["positionAmt"]) != 0
    ]
