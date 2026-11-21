from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RACINE = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import (
    BACKTEST_LONG_WINDOW,
    BACKTEST_SHORT_WINDOW,
    BACKTEST_TICKER,
    BACKTEST_TRANSACTION_COST,
)
from document_reader import lire_pdf
from metrics import metriques
from strategy import backtest_moyennes


st.set_page_config(
    page_title="Salle de marche - Atelier d'analyse",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)
st.title("Atelier d'analyse dynamique")
st.caption("Backtests, cours historiques et lecture de documents")


with st.sidebar:
    st.header("Parametres")
    ticker = st.text_input("Ticker", BACKTEST_TICKER)
    courte = st.number_input(
        "Moyenne courte",
        min_value=2,
        max_value=500,
        value=BACKTEST_SHORT_WINDOW,
        step=1,
    )
    longue = st.number_input(
        "Moyenne longue",
        min_value=3,
        max_value=1000,
        value=BACKTEST_LONG_WINDOW,
        step=1,
    )
    cout = st.number_input(
        "Cout par changement de position",
        min_value=0.0,
        max_value=0.1,
        value=BACKTEST_TRANSACTION_COST,
        step=0.001,
        format="%.4f",
    )
    debut = st.date_input("Debut", pd.Timestamp("2018-01-01"))
    fin = st.date_input("Fin", value=None)

onglet_backtest, onglet_documents, onglet_csv = st.tabs(
    ["Backtest", "Documents", "Donnees CSV"]
)

with onglet_backtest:
    if st.button("Executer le backtest", type="primary", use_container_width=True):
        if int(longue) <= int(courte):
            st.error("La moyenne longue doit etre superieure a la moyenne courte.")
        else:
            with st.spinner("Telechargement des donnees et calcul..."):
                try:
                    donnees = backtest_moyennes(
                        ticker=ticker.strip(),
                        courte=int(courte),
                        longue=int(longue),
                        cout=float(cout),
                        debut=str(debut),
                        fin=str(fin) if fin else None,
                    )
                except Exception as erreur:
                    st.error(str(erreur))
                else:
                    base = (1 + donnees["strategie"].dropna()).cumprod() * 100
                    buy_hold = (1 + donnees["rendement"].dropna()).cumprod() * 100
                    figure = go.Figure()
                    figure.add_trace(
                        go.Scatter(
                            x=base.index,
                            y=base,
                            name="Strategie MM",
                            line={"width": 2},
                        )
                    )
                    figure.add_trace(
                        go.Scatter(
                            x=buy_hold.index,
                            y=buy_hold,
                            name="Achat-conservation",
                            line={"width": 2},
                        )
                    )
                    figure.update_layout(
                        title=f"{ticker.upper()} - moyennes mobiles {int(courte)}/{int(longue)}",
                        yaxis_title="Valeur (base 100)",
                        xaxis_title="Date",
                        hovermode="x unified",
                        template="plotly_white",
                    )
                    st.plotly_chart(figure, use_container_width=True)

                    metrique_strategie = metriques(donnees["strategie"])
                    metrique_benchmark = metriques(donnees["rendement"])
                    colonnes = st.columns(5)
                    for colonne, (nom, valeur) in zip(
                        colonnes,
                        metrique_strategie.items(),
                    ):
                        colonne.metric(nom, valeur)

                    st.subheader("Comparatif")
                    st.dataframe(
                        pd.DataFrame(
                            {
                                "Strategie": metrique_strategie,
                                "Achat-conservation": metrique_benchmark,
                            }
                        ),
                        use_container_width=True,
                    )
                    st.subheader("Positions recentes")
                    st.dataframe(
                        donnees[
                            ["Close", "mm_courte", "mm_longue", "signal", "position", "strategie"]
                        ].tail(100),
                        use_container_width=True,
                    )

with onglet_documents:
    fichier = st.file_uploader(
        "Importer un document",
        type=["csv", "txt", "pdf"],
    )
    if fichier:
        suffixe = Path(fichier.name).suffix.lower()
        if suffixe == ".csv":
            st.dataframe(pd.read_csv(fichier), use_container_width=True)
        elif suffixe == ".txt":
            st.text(fichier.getvalue().decode("utf-8"))
        elif suffixe == ".pdf":
            chemin_temporaire = RACINE / "backtest" / fichier.name
            chemin_temporaire.parent.mkdir(parents=True, exist_ok=True)
            chemin_temporaire.write_bytes(fichier.getvalue())
            try:
                st.text(lire_pdf(chemin_temporaire))
            finally:
                chemin_temporaire.unlink(missing_ok=True)

with onglet_csv:
    fichier_csv = st.file_uploader(
        "Charger un CSV d'analyse",
        type=["csv"],
        key="csv_analyse",
    )
    if fichier_csv:
        tableau = pd.read_csv(fichier_csv)
        st.caption(f"{len(tableau):,} lignes")
        st.dataframe(tableau, use_container_width=True)
        colonnes_numeriques = tableau.select_dtypes(include="number").columns.tolist()
        if len(colonnes_numeriques) >= 2:
            axe_x = st.selectbox("Axe X", colonnes_numeriques)
            axe_y = st.selectbox(
                "Axe Y",
                [colonne for colonne in colonnes_numeriques if colonne != axe_x],
            )
            figure_csv = go.Figure(
                go.Scatter(
                    x=tableau[axe_x],
                    y=tableau[axe_y],
                    mode="lines+markers",
                    name=axe_y,
                )
            )
            figure_csv.update_layout(template="plotly_white")
            st.plotly_chart(figure_csv, use_container_width=True)
