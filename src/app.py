from pathlib import Path
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from curl_cffi.requests.exceptions import RequestException as CurlRequestException

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
from strategy import backtest_moyennes, signal_actuel
from data import telecharger, telecharger_intraday
from rsi_strategy import comparer_strategies_rsi
from momentum_strategy import backtest_momentum


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

(
    onglet_backtest,
    onglet_rsi,
    onglet_momentum,
    onglet_documents,
    onglet_csv,
) = st.tabs(
    [
        "Backtest MM",
        "Projet 2 - RSI",
        "Projet 3 - Momentum",
        "Documents",
        "Donnees CSV",
    ]
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

                    signal = signal_actuel(donnees)
                    if signal["action"] == "ACHAT":
                        st.success(
                            f"Signal actuel : ACHAT - {ticker.upper()} "
                            f"a {signal['cours']} EUR ({signal['date']})"
                        )
                    else:
                        st.error(
                            f"Signal actuel : VENTE - {ticker.upper()} "
                            f"a {signal['cours']} EUR ({signal['date']})"
                        )

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

with onglet_rsi:
    st.subheader("RSI et retour a la moyenne")
    st.caption(
        "Comparaison RSI 7/21, seuils 20/80 et 40/60, "
        "avec et sans filtre de tendance MM200."
    )
    actualisation_auto = st.checkbox(
        "Actualiser automatiquement le cours toutes les 15 minutes",
        value=True,
    )
    st.caption(
        "Le cours intrajournalier utilise des bougies de 15 minutes "
        "sur les 5 derniers jours. L'historique du backtest suit les dates "
        "choisies ci-dessous."
    )

    @st.fragment(run_every="15m" if actualisation_auto else None)
    def afficher_cours_intraday():
        symbole = ticker.strip().upper()
        forcer_actualisation = st.button(
            "Actualiser le cours maintenant",
            key="actualiser_cours_intraday",
        )
        dernier_essai = st.session_state.get("heure_actualisation_intraday", 0)
        changement_symbole = (
            st.session_state.get("symbole_intraday") != symbole
        )
        actualisation_due = (
            actualisation_auto and time.time() - dernier_essai >= 15 * 60
        )
        if forcer_actualisation or changement_symbole or actualisation_due:
            try:
                cours_intraday = telecharger_intraday(symbole, intervalle="15m")
            except (ValueError, OSError, CurlRequestException) as erreur:
                st.session_state["erreur_intraday"] = str(erreur)
                st.session_state["heure_actualisation_intraday"] = time.time()
            else:
                st.session_state["cours_intraday"] = cours_intraday
                st.session_state["symbole_intraday"] = symbole
                st.session_state["heure_actualisation_intraday"] = time.time()
                st.session_state.pop("erreur_intraday", None)

        if st.session_state.get("erreur_intraday"):
            st.warning(
                f"Impossible d'actualiser le cours : "
                f"{st.session_state['erreur_intraday']}"
            )
        cours_intraday = st.session_state.get("cours_intraday")
        if (
            cours_intraday is None
            or st.session_state.get("symbole_intraday") != symbole
            or cours_intraday.empty
        ):
            st.info("Aucun cours intrajournalier disponible pour ce ticker.")
            return

        clotures = cours_intraday["Close"].dropna()
        if clotures.empty:
            st.info("Aucun cours de clôture intrajournalier disponible.")
            return
        variation = (
            (clotures.iloc[-1] / clotures.iloc[-2] - 1) * 100
            if len(clotures) > 1 and clotures.iloc[-2] != 0
            else None
        )
        valeur_variation = f"{variation:.2f}%" if variation is not None else None
        st.metric(
            f"Dernier cours - {symbole}",
            f"{clotures.iloc[-1]:.2f}",
            delta=valeur_variation,
        )
        heure_maj = time.strftime(
            "%d/%m/%Y %H:%M:%S",
            time.localtime(st.session_state["heure_actualisation_intraday"]),
        )
        st.caption(
            f"Dernière actualisation : {heure_maj}. "
            "Les données Yahoo Finance peuvent être différées; "
            "hors séance, le dernier cours disponible est conservé."
        )
        st.dataframe(cours_intraday.tail(10), use_container_width=True)
        st.download_button(
            "Telecharger les cours intrajournaliers CSV",
            data=cours_intraday.to_csv(index=True).encode("utf-8"),
            file_name=f"{symbole}_cours_intraday.csv",
            mime="text/csv",
            key="telecharger_cours_intraday",
        )

    afficher_cours_intraday()

    debut_rsi = st.date_input(
        "Debut de l'analyse RSI",
        pd.Timestamp("2018-01-01"),
        key="debut_rsi",
    )
    cles_cours_rsi = (
        ticker.strip().upper(),
        str(debut_rsi),
        str(fin) if fin else None,
    )
    if st.button("Charger / actualiser les cours"):
        st.session_state.pop("cles_cours_rsi", None)
        st.session_state.pop("cles_resultats_rsi", None)
        st.session_state.pop("resultats_rsi", None)
        with st.spinner("Telechargement des cours..."):
            try:
                st.session_state["cours_rsi"] = telecharger(
                    cles_cours_rsi[0],
                    debut=str(debut_rsi),
                    fin=str(fin) if fin else None,
                )
                st.session_state["cles_cours_rsi"] = cles_cours_rsi
            except (ValueError, OSError) as erreur:
                st.error(str(erreur))

    cours_charge = (
        st.session_state.get("cles_cours_rsi") == cles_cours_rsi
    )
    if cours_charge:
        cours_rsi = st.session_state["cours_rsi"]
        st.caption(
            f"{len(cours_rsi):,} séances chargées pour {ticker.upper()} "
            f"(du {cours_rsi.index[0].date()} au {cours_rsi.index[-1].date()})."
        )
        st.dataframe(cours_rsi.tail(20), use_container_width=True)
        st.download_button(
            "Telecharger les cours en CSV",
            data=cours_rsi.to_csv(index=True).encode("utf-8"),
            file_name=f"{ticker.upper()}_cours.csv",
            mime="text/csv",
            key="telecharger_cours_rsi",
        )
    else:
        st.info("Chargez les cours pour afficher leur aperçu et lancer l'analyse.")

    if st.button("Comparer les strategies RSI", type="primary"):
        if not cours_charge:
            st.warning("Chargez d'abord les cours correspondant au ticker et aux dates.")
        else:
            try:
                st.session_state["resultats_rsi"] = comparer_strategies_rsi(
                    st.session_state["cours_rsi"],
                    cout=float(cout),
                )
                st.session_state["cles_resultats_rsi"] = (
                    cles_cours_rsi,
                    float(cout),
                )
            except ValueError as erreur:
                st.error(str(erreur))

    cles_resultats = (cles_cours_rsi, float(cout))
    if st.session_state.get("cles_resultats_rsi") == cles_resultats:
        cours_rsi = st.session_state["cours_rsi"]
        resultats_rsi = st.session_state["resultats_rsi"]
        lignes = []
        figure_rsi = go.Figure()
        benchmark = (1 + cours_rsi["Close"].pct_change().fillna(0)).cumprod() * 100
        figure_rsi.add_trace(
            go.Scatter(
                x=benchmark.index,
                y=benchmark,
                name="Achat-conservation",
            )
        )
        for nom, donnees_rsi in resultats_rsi.items():
            metriques_rsi = metriques(donnees_rsi["strategie"])
            entrees = int(
                donnees_rsi["position"]
                .diff()
                .fillna(donnees_rsi["position"])
                .gt(0)
                .sum()
            )
            lignes.append(
                {
                    "Strategie": nom,
                    "Entrees": entrees,
                    **metriques_rsi,
                }
            )
            courbe = (1 + donnees_rsi["strategie"]).cumprod() * 100
            figure_rsi.add_trace(
                go.Scatter(
                    x=courbe.index,
                    y=courbe,
                    name=nom,
                )
            )
        lignes.append(
            {
                "Strategie": "Achat-conservation",
                "Entrees": "-",
                **metriques(benchmark.pct_change().fillna(0)),
            }
        )
        figure_rsi.update_layout(
            title=f"{ticker.upper()} - comparaison RSI et MM200",
            yaxis_title="Valeur (base 100)",
            xaxis_title="Date",
            hovermode="x unified",
            template="plotly_white",
        )
        st.plotly_chart(figure_rsi, use_container_width=True)
        tableau_rsi = pd.DataFrame(lignes).set_index("Strategie")
        st.dataframe(
            tableau_rsi.sort_values("Rendement total", ascending=False),
            use_container_width=True,
        )
        st.download_button(
            "Telecharger le comparatif CSV",
            data=tableau_rsi.to_csv().encode("utf-8"),
            file_name=f"{ticker.upper()}_comparaison_rsi.csv",
            mime="text/csv",
            key="telecharger_comparatif_rsi",
        )

with onglet_momentum:
    st.subheader("Momentum et rotation mensuelle")
    st.caption(
        "Chaque mois, les trois titres ayant le meilleur rendement sur "
        "126 seances sont detenus a poids egaux."
    )
    tickers_momentum = st.text_input(
        "Tickers separes par une virgule",
        value="AI.PA, MC.PA, OR.PA",
        key="tickers_momentum",
    )
    periode_momentum = st.number_input(
        "Periode de momentum",
        min_value=20,
        max_value=500,
        value=126,
        step=1,
        key="periode_momentum",
    )
    nombre_titres = st.number_input(
        "Nombre de titres",
        min_value=1,
        max_value=20,
        value=3,
        step=1,
        key="nombre_titres_momentum",
    )

    if st.button("Executer le momentum", type="primary"):
        liste_tickers = [
            symbole.strip().upper()
            for symbole in tickers_momentum.split(",")
            if symbole.strip()
        ]
        if len(liste_tickers) < int(nombre_titres):
            st.error("Le nombre de titres doit etre inferieur ou egal au nombre de tickers.")
        else:
            with st.spinner("Telechargement des cours et calcul du portfolio..."):
                try:
                    donnees_momentum = backtest_momentum(
                        liste_tickers,
                        periode=int(periode_momentum),
                        nombre_titres=int(nombre_titres),
                        cout=float(cout),
                        debut=str(debut),
                        fin=str(fin) if fin else None,
                    )
                except Exception as erreur:
                    st.error(str(erreur))
                else:
                    courbe_momentum = (
                        (1 + donnees_momentum["strategie"]).cumprod() * 100
                    )
                    benchmark_momentum = (
                        (1 + donnees_momentum["rendement"]).cumprod() * 100
                    )
                    figure_momentum = go.Figure()
                    figure_momentum.add_trace(
                        go.Scatter(
                            x=courbe_momentum.index,
                            y=courbe_momentum,
                            name="Momentum",
                        )
                    )
                    figure_momentum.add_trace(
                        go.Scatter(
                            x=benchmark_momentum.index,
                            y=benchmark_momentum,
                            name="Panier equilibre",
                        )
                    )
                    figure_momentum.update_layout(
                        title="Momentum mensuel",
                        yaxis_title="Valeur (base 100)",
                        xaxis_title="Date",
                        hovermode="x unified",
                        template="plotly_white",
                    )
                    st.plotly_chart(figure_momentum, use_container_width=True)

                    colonnes_momentum = st.columns(5)
                    for colonne, (nom, valeur) in zip(
                        colonnes_momentum,
                        metriques(donnees_momentum["strategie"]).items(),
                    ):
                        colonne.metric(nom, valeur)

                    poids_momentum = donnees_momentum.attrs["poids"]
                    st.subheader("Poids du portefeuille")
                    st.dataframe(
                        poids_momentum.tail(126),
                        use_container_width=True,
                    )
                    st.download_button(
                        "Telecharger les resultats momentum CSV",
                        data=donnees_momentum.to_csv(index=True).encode("utf-8"),
                        file_name="momentum_portefeuille.csv",
                        mime="text/csv",
                        key="telecharger_momentum",
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
