import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

BACKTEST_TICKER = os.getenv("BACKTEST_TICKER", "AI.PA")
BACKTEST_SHORT_WINDOW = int(os.getenv("BACKTEST_SHORT_WINDOW", "20"))
BACKTEST_LONG_WINDOW = int(os.getenv("BACKTEST_LONG_WINDOW", "50"))
BACKTEST_TRANSACTION_COST = float(
    os.getenv("BACKTEST_TRANSACTION_COST", "0.001")
)

BACKTEST_PERIODS = [
    {
        "nom": os.getenv("BACKTEST_PERIOD_1_NAME", "2018-2020"),
        "debut": os.getenv("BACKTEST_PERIOD_1_START", "2018-01-01"),
        "fin": os.getenv("BACKTEST_PERIOD_1_END") or None,
    },
    {
        "nom": os.getenv("BACKTEST_PERIOD_2_NAME", "2021-2023"),
        "debut": os.getenv("BACKTEST_PERIOD_2_START", "2021-01-01"),
        "fin": os.getenv("BACKTEST_PERIOD_2_END") or None,
    },
    {
        "nom": os.getenv("BACKTEST_PERIOD_3_NAME", "2024-a-aujourd-hui"),
        "debut": os.getenv("BACKTEST_PERIOD_3_START", "2024-01-01"),
        "fin": os.getenv("BACKTEST_PERIOD_3_END") or None,
    },
]
