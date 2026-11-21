import argparse

from config import (
    BACKTEST_LONG_WINDOW,
    BACKTEST_SHORT_WINDOW,
    BACKTEST_TICKER,
    BACKTEST_TRANSACTION_COST,
)
from strategy import backtest_moyennes, signal_actuel


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calcule un signal achat ou vente par moyennes mobiles."
    )
    parser.add_argument("ticker", nargs="?", default=BACKTEST_TICKER)
    arguments = parser.parse_args()

    donnees = backtest_moyennes(
        ticker=arguments.ticker,
        courte=BACKTEST_SHORT_WINDOW,
        longue=BACKTEST_LONG_WINDOW,
        cout=BACKTEST_TRANSACTION_COST,
    )
    signal = signal_actuel(donnees)

    print(f"Ticker : {arguments.ticker}")
    print(f"Date : {signal['date']}")
    print(f"Cours : {signal['cours']}")
    print(f"Conseil : {signal['action']}")
    print(
        "Avertissement : signal indicatif, pas un conseil financier "
        "personnalise."
    )


if __name__ == "__main__":
    main()
