"""Signaux de tendance/momentum et backtest quotidien long-only."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _validate_window(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} doit etre un entier strictement positif.")


def _validate_ohlc(data: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Les donnees OHLC doivent former un DataFrame non vide.")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Les donnees doivent avoir un index de dates.")
    if data.index.has_duplicates:
        raise ValueError("Les dates doivent etre uniques.")

    names = {str(column).casefold(): column for column in data.columns}
    required = ("open", "high", "low", "close")
    missing = [column for column in required if column not in names]
    if missing:
        raise ValueError("Colonnes OHLC absentes : " + ", ".join(missing))

    result = data.rename(
        columns={names[column]: column.title() for column in required}
    ).copy()
    result = result.sort_index()
    for column in ("Open", "High", "Low", "Close"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    prices = result[["Open", "High", "Low", "Close"]]
    values = prices.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Les cours OHLC doivent etre numeriques et finis.")
    if (prices <= 0).any().any():
        raise ValueError("Les cours OHLC doivent etre strictement positifs.")
    if (prices["High"] < prices[["Open", "Low", "Close"]].max(axis=1)).any():
        raise ValueError("High doit etre superieur ou egal aux autres cours de la barre.")
    if (prices["Low"] > prices[["Open", "High", "Close"]].min(axis=1)).any():
        raise ValueError("Low doit etre inferieur ou egal aux autres cours de la barre.")
    return result


def sma(series: pd.Series, window: int) -> pd.Series:
    """Moyenne mobile disponible seulement apres une fenetre complete."""
    _validate_window("window", window)
    return series.rolling(window=window, min_periods=window).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """ATR par moyenne glissante du true range."""
    _validate_window("window", window)
    if not high.index.equals(low.index) or not high.index.equals(close.index):
        raise ValueError("High, Low et Close doivent avoir le meme index.")
    true_range = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window=window, min_periods=window).mean()


def calculer_signaux(
    data: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 50,
    atr_window: int = 14,
    momentum_window: int = 21,
    z_window: int = 252,
    z_min_periods: int = 50,
    z_threshold: float = 1.0,
    max_atr_ratio: float = 0.02,
) -> pd.DataFrame:
    """Construit des signaux long-only a partir des cours connus a la cloture."""
    for name, value in (
        ("short_window", short_window),
        ("long_window", long_window),
        ("atr_window", atr_window),
        ("momentum_window", momentum_window),
        ("z_window", z_window),
        ("z_min_periods", z_min_periods),
    ):
        _validate_window(name, value)
    if short_window >= long_window:
        raise ValueError("short_window doit etre inferieur a long_window.")
    if z_min_periods > z_window:
        raise ValueError("z_min_periods ne peut pas depasser z_window.")
    if not np.isfinite([z_threshold, max_atr_ratio]).all():
        raise ValueError("Les seuils doivent etre finis.")
    if max_atr_ratio <= 0:
        raise ValueError("max_atr_ratio doit etre strictement positif.")

    result = _validate_ohlc(data)
    close = result["Close"]
    result["sma_short"] = sma(close, short_window)
    result["sma_long"] = sma(close, long_window)
    result["signal_trend"] = (
        result["sma_short"].gt(result["sma_long"]).fillna(False).astype(int)
    )

    result["atr"] = atr(
        result["High"],
        result["Low"],
        close,
        window=atr_window,
    )
    result["atr_ratio"] = result["atr"] / close
    result["vol_filter"] = result["atr_ratio"].lt(max_atr_ratio).fillna(False)

    log_close = np.log(close)
    result["momentum"] = log_close - log_close.shift(momentum_window)
    prior_momentum = result["momentum"].shift(1)
    momentum_mean = prior_momentum.rolling(
        window=z_window,
        min_periods=z_min_periods,
    ).mean()
    momentum_std = prior_momentum.rolling(
        window=z_window,
        min_periods=z_min_periods,
    ).std()
    result["z_momentum"] = (
        (result["momentum"] - momentum_mean)
        .div(momentum_std.where(momentum_std > 0))
        .replace([np.inf, -np.inf], np.nan)
    )
    result["signal_momentum"] = (
        result["z_momentum"].gt(z_threshold).fillna(False).astype(int)
    )
    result["signal"] = (
        result["signal_trend"].eq(1)
        & result["signal_momentum"].eq(1)
        & result["vol_filter"]
    ).astype(int)
    return result


def backtester_signaux(
    signals: pd.DataFrame,
    commission: float = 0.001,
    slippage: float = 0.0005,
) -> tuple[pd.DataFrame, dict]:
    """Backteste les signaux a l'ouverture suivante, avec couts de turnover."""
    if not np.isfinite([commission, slippage]).all():
        raise ValueError("Commission et slippage doivent etre finis.")
    if commission < 0 or slippage < 0:
        raise ValueError("Commission et slippage doivent etre positifs ou nuls.")
    required = {"Open", "signal"}
    if not required.issubset(signals.columns):
        raise ValueError("Le backtest requiert les colonnes Open et signal.")
    if len(signals) < 2:
        raise ValueError("Au moins deux seances sont requises pour le backtest.")
    if signals["signal"].isna().any() or not signals["signal"].isin([0, 1]).all():
        raise ValueError("Les signaux doivent contenir uniquement 0 ou 1.")

    result = signals.copy()
    result["next_open"] = result["Open"].shift(-1)
    result["position"] = result["signal"].shift(1).fillna(0.0).astype(float)
    result["open_to_next_open_return"] = result["next_open"].div(result["Open"]).sub(1)
    result = result.loc[result["next_open"].notna()].copy()
    result["turnover"] = result["position"].diff().abs().fillna(
        result["position"].abs()
    )
    result["costs"] = result["turnover"] * (commission + slippage)
    result["strategy_return"] = (
        result["position"] * result["open_to_next_open_return"] - result["costs"]
    )
    result["buy_and_hold_return"] = result["open_to_next_open_return"]
    result["strategy_equity"] = (1.0 + result["strategy_return"]).cumprod()
    result["buy_and_hold_equity"] = (1.0 + result["buy_and_hold_return"]).cumprod()

    strategy_metrics = _performance_metrics(result["strategy_return"])
    strategy_metrics["trade_turnover"] = float(result["turnover"].sum())
    strategy_metrics["trade_count"] = int((result["turnover"] > 0).sum())
    benchmark_metrics = _performance_metrics(result["buy_and_hold_return"])
    report = {
        "strategy": strategy_metrics,
        "buy_and_hold": benchmark_metrics,
        "commission_rate": float(commission),
        "slippage_rate": float(slippage),
        "return_convention": "open-to-next-open; signal from previous close",
        "start": result.index[0].date().isoformat(),
        "end": result.index[-1].date().isoformat(),
        "observations": int(len(result)),
    }
    return result, report


def _performance_metrics(returns: pd.Series) -> dict:
    returns = pd.to_numeric(returns, errors="coerce").dropna()
    if returns.empty:
        raise ValueError("Aucun rendement disponible pour calculer les performances.")
    equity = (1.0 + returns).cumprod()
    volatility = returns.std(ddof=1)
    sharpe = (
        float(np.sqrt(252) * returns.mean() / volatility)
        if len(returns) > 1 and volatility > 0
        else None
    )
    annualized_return = (
        float(equity.iloc[-1] ** (252 / len(returns)) - 1)
        if equity.iloc[-1] > 0
        else -1.0
    )
    drawdown = equity.div(equity.cummax()).sub(1.0)
    return {
        "total_return": float(equity.iloc[-1] - 1),
        "annualized_return": annualized_return,
        "annualized_volatility": float(volatility * np.sqrt(252)),
        "sharpe_ratio": sharpe,
        "max_drawdown": float(drawdown.min()),
    }


def _load_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    date_column = next(
        (
            column
            for column in raw.columns
            if str(column).casefold() in {"date", "datetime"}
        ),
        None,
    )
    if date_column is None:
        raise ValueError("Le CSV doit contenir une colonne Date ou Datetime.")
    raw[date_column] = pd.to_datetime(raw[date_column], errors="raise")
    return raw.set_index(date_column)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calcule des signaux AAPL et leur backtest avec frictions."
    )
    parser.add_argument("--ticker", default="AAPL", help="Ticker Yahoo Finance.")
    parser.add_argument("--start", default="2015-01-01", help="Date de debut incluse.")
    parser.add_argument("--end", default=None, help="Date de fin exclusive.")
    parser.add_argument("--input-csv", type=Path, help="CSV local avec Date et OHLC.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backtest") / "trading_signals",
        help="Dossier pour les signaux et le rapport de backtest.",
    )
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    arguments = parser.parse_args(argv)

    try:
        if arguments.input_csv:
            prices = _load_csv(arguments.input_csv)
        else:
            from data import telecharger

            prices = telecharger(
                arguments.ticker,
                debut=arguments.start,
                fin=arguments.end,
            )
        signals = calculer_signaux(prices)
        backtest, report = backtester_signaux(
            signals,
            commission=arguments.commission,
            slippage=arguments.slippage,
        )
        arguments.output.mkdir(parents=True, exist_ok=True)
        backtest.to_csv(arguments.output / "signals_backtest.csv", index_label="Date")
        (arguments.output / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except (OSError, ValueError, pd.errors.ParserError) as error:
        parser.error(str(error))

    latest = signals.iloc[-1]
    print(
        f"Dernier signal ({signals.index[-1].date()}): "
        f"{'ACHAT' if latest['signal'] else 'ATTENTE'}"
    )
    print(
        f"Tendance={int(latest['signal_trend'])}, "
        f"momentum={int(latest['signal_momentum'])}, "
        f"ATR/cours={latest['atr_ratio']:.2%}"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Resultats enregistres dans {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
