import yfinance as yf
import pandas as pd
import requests
from curl_cffi import requests as curl_requests
from datetime import timedelta


def telecharger(ticker, debut="2018-01-01", fin=None):
    """Télécharge les cours de clôture ajustés d'un titre."""
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Le ticker doit être une chaîne non vide.")
    try:
        debut_dt = pd.Timestamp(debut)
        fin_dt = pd.Timestamp(fin) if fin else pd.Timestamp.now()
    except (TypeError, ValueError) as erreur:
        raise ValueError("Les dates de début et de fin sont invalides.") from erreur
    if debut_dt.tz is not None:
        debut_dt = debut_dt.tz_convert(None)
    if fin_dt.tz is not None:
        fin_dt = fin_dt.tz_convert(None)
    if debut_dt >= fin_dt:
        raise ValueError("La date de début doit être antérieure à la date de fin.")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
            )
        }
    )

    primary_error = None
    try:
        df = yf.download(
            ticker,
            start=debut,
            end=fin,
            auto_adjust=True,
            progress=False,
            session=session,
            timeout=30,
        )
    except (requests.RequestException, ValueError, KeyError) as erreur:
        primary_error = erreur
        df = pd.DataFrame()

    if df.empty:
        try:
            df = _telecharger_avec_chart_api(ticker, debut, fin)
        except ValueError as fallback_error:
            if primary_error:
                raise ValueError(
                    f"Téléchargement impossible pour {ticker}: "
                    f"{primary_error}; repli: {fallback_error}"
                ) from fallback_error
            raise

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if "Close" not in df.columns:
        raise ValueError(f"Les données téléchargées pour {ticker} ne contiennent pas de clôture.")

    df = df.dropna(subset=["Close"])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if df.empty:
        raise ValueError(f"Aucune clôture valide disponible pour {ticker}.")
    return df


def _telecharger_avec_chart_api(ticker, debut, fin):
    """Repli direct sur l'API Yahoo Chart lorsque yfinance échoue."""
    debut_dt = pd.Timestamp(debut).tz_localize("UTC")
    fin_dt = (
        pd.Timestamp(fin).tz_localize("UTC")
        if fin
        else pd.Timestamp.now(tz="UTC").normalize()
    )
    fin_dt += timedelta(days=1)

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    response = curl_requests.get(
        url,
        params={
            "period1": int(debut_dt.timestamp()),
            "period2": int(fin_dt.timestamp()),
            "interval": "1d",
            "events": "div,splits",
        },
        impersonate="chrome",
        verify=False,
        timeout=30,
    )

    if response.status_code != 200:
        raise ValueError(
            f"Téléchargement impossible pour {ticker} "
            f"(Yahoo Finance HTTP {response.status_code})."
        )

    payload = response.json()
    result = payload.get("chart", {}).get("result")
    if not result:
        erreur = payload.get("chart", {}).get("error")
        detail = erreur.get("description") if erreur else "aucune donnée retournée"
        raise ValueError(f"Aucune donnée disponible pour {ticker}: {detail}")

    data = result[0]
    timestamps = data.get("timestamp") or []
    quote = data.get("indicators", {}).get("quote", [{}])[0]
    adjclose = data.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose")

    if not timestamps:
        raise ValueError(f"Aucune donnée disponible pour {ticker}.")

    df = pd.DataFrame(
        {
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": adjclose if adjclose is not None else quote.get("close"),
            "Volume": quote.get("volume"),
        },
        index=pd.to_datetime(timestamps, unit="s", utc=True),
    )
    df.index = df.index.tz_localize(None).normalize()
    return df.dropna(subset=["Close"])









        
    