import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.market import get_mark_price
from core.account import get_wallet_balance, get_open_positions

print("=== MARK PRICE ===")
print(get_mark_price("BTCUSDT"))

print("=== WALLET BALANCE ===")
print(get_wallet_balance())

print("=== OPEN POSITIONS ===")
positions = get_open_positions()
if not positions:
    print("No open positions")
else:
    for p in positions:
        print(
            p["symbol"],
            p["positionAmt"],
            p["unRealizedProfit"]
        )
