import numpy as np


JOURS_BOURSE = 252 



def metriques(rendements, rf=0.0):
    """Calcule les indicateurs de performance à partir d'une série de rendements quotidiens."""
    if rf < 0:
        raise ValueError("Le taux sans risque ne peut pas être négatif.")

    rendements = rendements.replace([np.inf, -np.inf], np.nan).dropna()
    if len(rendements) == 0:
        return {
            "Rendement annuel": float("nan"),
            "Volatilité": float("nan"),
            "Sharpe": float("nan"),
            "Perte maximale": float("nan"),
            "Rendement total": float("nan"),
        }

    cumul = (1 + rendements).cumprod()
    annees = len(rendements) / JOURS_BOURSE
    if annees <= 0:
        raise ValueError("La durée du backtest doit être strictement positive.")

    rendement_annuel = cumul.iloc[-1] ** (1 /annees) - 1
    volatilite = (
        rendements.std(ddof=1) * np.sqrt(JOURS_BOURSE)
        if len(rendements) > 1
        else 0.0
    )
    ecart_type = rendements.std(ddof=1) if len(rendements) > 1 else 0.0
    rf_quotidien = (1 + rf) ** (1 / JOURS_BOURSE) - 1
    sharpe = (
        ((rendements.mean() - rf_quotidien) / ecart_type) * np.sqrt(JOURS_BOURSE)
        if ecart_type > 0
        else np.nan
    )
    sommet = cumul.cummax()
    perte_max = (cumul / sommet - 1).min()
    return {
        "Rendement annuel": round(rendement_annuel, 4),
        "Volatilité": round(volatilite, 4),
        "Sharpe": round(sharpe, 2),
        "Perte maximale": round(perte_max, 4),
        "Rendement total": round(cumul.iloc[-1] - 1, 4),
    }
