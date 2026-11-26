"""Prevision des rendements journaliers et evaluation chronologique."""

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data import telecharger


FEATURE_COLUMNS = (
    "r_lag_1",
    "r_lag_2",
    "r_lag_3",
    "r_lag_5",
    "sma_ratio",
    "vol_21",
    "vol_z",
)


def prepare_features(data: pd.DataFrame, tau: int = 1) -> pd.DataFrame:
    """Construit des variables connues a la cloture et une cible future."""
    if not isinstance(tau, int) or isinstance(tau, bool) or tau < 1:
        raise ValueError("L'horizon tau doit etre un entier strictement positif.")
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Les cours doivent etre un DataFrame non vide.")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Les cours doivent avoir un index de dates.")
    if data.index.has_duplicates:
        raise ValueError("Les dates de cours doivent etre uniques.")

    result = data.sort_index().copy()
    column_map = {str(column).casefold(): column for column in result.columns}
    if "close" not in column_map or "volume" not in column_map:
        raise ValueError("Les colonnes close/Close et Volume/volume sont requises.")
    result = result.rename(
        columns={
            column_map["close"]: "close",
            column_map["volume"]: "Volume",
        }
    )
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result["Volume"] = pd.to_numeric(result["Volume"], errors="coerce")
    if result[["close", "Volume"]].isna().any().any():
        raise ValueError("Les cours de cloture et volumes doivent etre numeriques.")
    if not np.isfinite(result[["close", "Volume"]].to_numpy()).all():
        raise ValueError("Les cours et volumes doivent etre finis.")
    if (result["close"] <= 0).any() or (result["Volume"] < 0).any():
        raise ValueError("Les cours doivent etre positifs et les volumes non negatifs.")

    log_close = np.log(result["close"])
    result["log_close"] = log_close
    result["r"] = log_close.diff()
    result["r_target"] = log_close.shift(-tau) - log_close

    for lag in (1, 2, 3, 5):
        result[f"r_lag_{lag}"] = result["r"].shift(lag - 1)

    result["sma_5"] = result["close"].rolling(window=5).mean()
    result["sma_20"] = result["close"].rolling(window=20).mean()
    result["sma_ratio"] = result["sma_5"] / result["sma_20"]
    result["vol_21"] = result["r"].rolling(window=21).std()
    prior_volume_mean = result["Volume"].rolling(window=21).mean().shift(1)
    prior_volume_std = result["Volume"].rolling(window=21).std().shift(1)
    result["vol_z"] = (result["Volume"] - prior_volume_mean) / prior_volume_std

    required = [*FEATURE_COLUMNS, "r_target"]
    result[required] = result[required].replace([np.inf, -np.inf], np.nan)
    return result.dropna(subset=required)


def backtest_predictions(
    data: pd.DataFrame,
    predictions,
    sigma_target: float = 0.1,
    slippage: float = 0.0005,
    commission: float = 0.0002,
    min_signal_strength: float = 0.0,
    long_only: bool = False,
) -> pd.DataFrame:
    """Evalue une strategie quotidienne a partir de previsions hors echantillon."""
    if not np.isfinite(
        [sigma_target, slippage, commission, min_signal_strength]
    ).all():
        raise ValueError("Les parametres du backtest doivent etre finis.")
    if sigma_target < 0 or slippage < 0 or commission < 0 or min_signal_strength < 0:
        raise ValueError("Les risques, seuils et couts doivent etre positifs ou nuls.")
    if not {"r_target", "vol_21"}.issubset(data.columns):
        raise ValueError("Les colonnes r_target et vol_21 sont requises.")

    predicted = np.asarray(predictions, dtype=float)
    if predicted.ndim != 1 or len(predicted) != len(data):
        raise ValueError("Une prediction est requise pour chaque ligne.")
    if not np.isfinite(predicted).all():
        raise ValueError("Les predictions doivent etre finies.")

    result = data.copy()
    result["prediction"] = predicted
    volatility = result["vol_21"].where(result["vol_21"] > 0)
    normalized_signal = result["prediction"].div(volatility).replace(
        [np.inf, -np.inf], np.nan
    )
    position = normalized_signal.mul(sigma_target).fillna(0.0)
    position = position.where(
        normalized_signal.abs() >= min_signal_strength,
        0.0,
    )
    result["position"] = (
        position.clip(0.0, 1.0)
        if long_only
        else position.clip(-1.0, 1.0)
    )
    result["turnover"] = result["position"].diff().abs()
    if not result.empty:
        result.iloc[0, result.columns.get_loc("turnover")] = abs(
            result["position"].iloc[0]
        )
    result["costs"] = (commission + slippage) * result["turnover"]
    result["strategy_return"] = (
        result["position"] * np.expm1(result["r_target"]) - result["costs"]
    )
    result["cumulative_return"] = (1.0 + result["strategy_return"]).cumprod() - 1.0
    return result


def _strategy_metrics(returns: pd.Series) -> dict:
    returns = pd.to_numeric(returns, errors="coerce").dropna()
    if returns.empty:
        raise ValueError("Aucun rendement disponible pour le backtest.")
    equity = (1.0 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    annualized_volatility = float(returns.std(ddof=1) * np.sqrt(252))
    annualized_return = (
        float(equity.iloc[-1] ** (252.0 / len(returns)) - 1.0)
        if equity.iloc[-1] > 0
        else -1.0
    )
    sharpe = (
        float(np.sqrt(252) * returns.mean() / returns.std(ddof=1))
        if len(returns) > 1 and returns.std(ddof=1) > 0
        else None
    )
    drawdown = equity.div(equity.cummax().clip(lower=1.0)).sub(1.0)
    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "max_drawdown": float(drawdown.min()),
    }


def _model_candidates():
    return (
        (
            "ridge",
            Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("model", Ridge()),
                ]
            ),
            {"model__alpha": [0.01, 0.1, 1.0, 10.0]},
        ),
        (
            "random_forest",
            Pipeline(
                [
                    (
                        "model",
                        RandomForestRegressor(
                            n_estimators=50,
                            random_state=42,
                            n_jobs=1,
                        ),
                    )
                ]
            ),
            {"model__max_depth": [3, 5, None]},
        ),
    )


def _select_model(data: pd.DataFrame, cv_splits: int, horizon: int):
    if len(data) <= cv_splits + horizon:
        raise ValueError("Pas assez de donnees dans une fenetre de validation.")
    cross_validation = TimeSeriesSplit(n_splits=cv_splits, gap=horizon)
    x_train = data.loc[:, FEATURE_COLUMNS]
    y_train = data["r_target"]
    best_name = None
    best_search = None
    for name, pipeline, parameter_grid in _model_candidates():
        search = GridSearchCV(
            pipeline,
            parameter_grid,
            cv=cross_validation,
            scoring="neg_mean_squared_error",
            n_jobs=1,
            error_score="raise",
        )
        search.fit(x_train, y_train)
        if best_search is None or search.best_score_ > best_search.best_score_:
            best_name = name
            best_search = search
    if best_name is None or best_search is None:
        raise RuntimeError("Aucun modele n'a ete entraine.")
    return best_name, best_search


def _calibrate_strategy(
    training_data: pd.DataFrame,
    cv_splits: int,
    horizon: int,
) -> tuple[dict, dict]:
    """Choisit exposition et seuil sur des validations imbriquees du train."""
    outer_splits = min(3, cv_splits)
    outer_cv = TimeSeriesSplit(n_splits=outer_splits, gap=horizon)
    strategy_grid = [(0.0, 0.0, True)]
    strategy_grid.extend(
        (sigma_target, min_signal_strength, long_only)
        for sigma_target in (0.25, 0.5, 1.0)
        for min_signal_strength in (0.0, 0.1)
        for long_only in (False, True)
    )
    fold_returns = {parameters: [] for parameters in strategy_grid}
    fold_drawdowns = {parameters: [] for parameters in strategy_grid}
    fold_ends = []

    for train_indices, validation_indices in outer_cv.split(training_data):
        fold_train = training_data.iloc[train_indices]
        fold_validation = training_data.iloc[validation_indices]
        inner_splits = min(3, cv_splits)
        _, selected_search = _select_model(fold_train, inner_splits, horizon)
        fold_predictions = selected_search.predict(
            fold_validation.loc[:, FEATURE_COLUMNS]
        )
        fold_ends.append(fold_validation.index[-1].date().isoformat())

        for parameters in strategy_grid:
            sigma_target, min_signal_strength, long_only = parameters
            strategy = backtest_predictions(
                fold_validation,
                fold_predictions,
                sigma_target=sigma_target,
                min_signal_strength=min_signal_strength,
                long_only=long_only,
            )
            metrics = _strategy_metrics(strategy["strategy_return"])
            fold_returns[parameters].append(metrics["total_return"])
            fold_drawdowns[parameters].append(metrics["max_drawdown"])

    chosen = max(
        strategy_grid,
        key=lambda parameters: (
            float(np.mean(fold_returns[parameters])),
            float(np.mean(fold_drawdowns[parameters])),
        ),
    )
    return (
        {
            "sigma_target": chosen[0],
            "min_signal_strength": chosen[1],
            "long_only": chosen[2],
        },
        {
            "objective": "mean_net_return",
            "validation_folds": len(fold_ends),
            "mean_net_return": float(np.mean(fold_returns[chosen])),
            "mean_max_drawdown": float(np.mean(fold_drawdowns[chosen])),
            "last_validation_end": fold_ends[-1],
        },
    )


def run_analysis(
    data: pd.DataFrame,
    horizon: int = 1,
    test_fraction: float = 0.2,
    cv_splits: int = 5,
    sigma_target: float | None = None,
) -> dict:
    """Selectionne un modele sur le passe et l'evalue sur un holdout final."""
    if horizon != 1:
        raise ValueError("Le backtest est defini pour une prevision a un jour (horizon=1).")
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction doit etre comprise entre 0 et 1.")
    if not isinstance(cv_splits, int) or cv_splits < 2:
        raise ValueError("cv_splits doit etre un entier superieur ou egal a 2.")

    features = prepare_features(data, tau=horizon)
    split = int(len(features) * (1.0 - test_fraction))
    train_stop = split - horizon
    train = features.iloc[:train_stop]
    test = features.iloc[split:]
    if len(train) <= cv_splits + horizon or test.empty:
        raise ValueError("Pas assez de donnees pour la validation temporelle et le test.")

    x_test = test.loc[:, FEATURE_COLUMNS]
    y_test = test["r_target"]
    best_name, best_search = _select_model(train, cv_splits, horizon)
    predicted = best_search.predict(x_test)
    mse = float(mean_squared_error(y_test, predicted))
    prediction_metrics = {
        "mean_squared_error": mse,
        "root_mean_squared_error": float(np.sqrt(mse)),
        "mean_absolute_error": float(mean_absolute_error(y_test, predicted)),
        "directional_accuracy": float(
            np.mean(np.sign(y_test.to_numpy()) == np.sign(predicted))
        ),
    }
    if sigma_target is None:
        strategy_parameters, strategy_calibration = _calibrate_strategy(
            train,
            cv_splits,
            horizon,
        )
    else:
        strategy_parameters = {
            "sigma_target": sigma_target,
            "min_signal_strength": 0.0,
            "long_only": False,
        }
        strategy_calibration = {
            "objective": "fixed_by_caller",
            "validation_folds": 0,
        }
    backtest = backtest_predictions(test, predicted, **strategy_parameters)
    predictions = pd.DataFrame(
        {
            "actual_log_return": y_test,
            "predicted_log_return": predicted,
            "strategy_return": backtest["strategy_return"],
            "cumulative_return": backtest["cumulative_return"],
            "position": backtest["position"],
        },
        index=test.index,
    )
    report = {
        "selected_model": best_name,
        "best_parameters": best_search.best_params_,
        "cross_validation_mse": float(-best_search.best_score_),
        "train_start": train.index[0].date().isoformat(),
        "train_end": train.index[-1].date().isoformat(),
        "test_start": test.index[0].date().isoformat(),
        "test_end": test.index[-1].date().isoformat(),
        "training_rows": int(len(train)),
        "test_rows": int(len(test)),
        "horizon": horizon,
        "strategy_parameters": strategy_parameters,
        "strategy_calibration": strategy_calibration,
        "prediction_metrics": prediction_metrics,
        "strategy_metrics": _strategy_metrics(backtest["strategy_return"]),
    }
    return {
        "model": best_search.best_estimator_,
        "predictions": predictions,
        "report": report,
    }


def _load_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    date_column = next(
        (column for column in raw.columns if str(column).casefold() in {"date", "datetime"}),
        None,
    )
    if date_column is None:
        raise ValueError("Le CSV doit contenir une colonne Date ou Datetime.")
    raw[date_column] = pd.to_datetime(raw[date_column], errors="raise")
    return raw.set_index(date_column)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Entraine et evalue des previsions de rendement hors echantillon."
    )
    parser.add_argument("--ticker", default="AI.PA", help="Ticker Yahoo Finance.")
    parser.add_argument("--start", default="2015-01-01", help="Date de debut incluse.")
    parser.add_argument("--end", default=None, help="Date de fin exclusive.")
    parser.add_argument("--input-csv", type=Path, help="Utilise un CSV local au lieu de Yahoo.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backtest") / "price_prediction",
        help="Dossier de sortie pour le modele, les predictions et le rapport.",
    )
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--cv-splits", type=int, default=5)
    arguments = parser.parse_args(argv)

    try:
        data = (
            _load_csv(arguments.input_csv)
            if arguments.input_csv
            else telecharger(arguments.ticker, debut=arguments.start, fin=arguments.end)
        )
        result = run_analysis(
            data,
            horizon=arguments.horizon,
            test_fraction=arguments.test_fraction,
            cv_splits=arguments.cv_splits,
        )
        arguments.output.mkdir(parents=True, exist_ok=True)
        joblib.dump(result["model"], arguments.output / "model.joblib")
        result["predictions"].to_csv(
            arguments.output / "predictions.csv",
            index_label="Date",
        )
        (arguments.output / "report.json").write_text(
            json.dumps(result["report"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except (OSError, ValueError, pd.errors.ParserError) as error:
        parser.error(str(error))

    print(json.dumps(result["report"], indent=2, ensure_ascii=False))
    print(f"Resultats enregistres dans {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
