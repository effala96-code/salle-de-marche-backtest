schema_sql = """
CREATE TABLE IF NOT EXISTS prix(
    ticker TEXT NOT NULL,
    jour DATE NOT NULL,
    cloture NUMERIC(18, 6),
    PRIMARY KEY (ticker, jour)
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    jour DATE NOT NULL,
    ticker TEXT NOT NULL,
    sens TEXT NOT NULL CHECK (sens IN ('ACHAT', 'VENTE')),
    quantite NUMERIC(18,6) NOT NULL CHECK (quantite > 0),
    prix NUMERIC(18,6) NOT NULL,
    frais NUMERIC(18,6) NOT NULL DEFAULT 0
);

CREATE OR REPLACE VIEW v_positions AS
SELECT
    ticker,
    SUM(CASE WHEN sens = 'ACHAT' THEN quantite ELSE -quantite END) AS quantite,
    SUM(CASE WHEN sens = 'ACHAT' THEN quantite * prix + frais ELSE 0 END)
        / NULLIF(SUM(CASE WHEN sens = 'ACHAT' THEN quantite ELSE 0 END), 0)
        AS prix_revient_moyen
FROM transactions
GROUP BY ticker
    HAVING SUM(CASE WHEN sens = 'ACHAT' THEN quantite ELSE -quantite END) <> 0;

CREATE OR REPLACE VIEW v_dernier_cours As
SELECT DISTINCT ON (ticker) jour, cloture
FROM prix
ORDER BY ticker, jour DESC;

CREATE OR REPLACE VIEW v_valorisation As
SELECT
p.ticker,
p.quantite,
p.prix_revient_moyen,
d.cloture AS dernier_cours,
d.jour AS date_cours,
p.quantite * d.cloture AS valeur_marche,
p.quantite * (d.cloture - p.prix_revient_moyen) AS plus_value_latente,
(d.cloture / p.prix_revient_moyen - 1) AS performance_pct,
(p.quantite * d.cloture)
/ SUM(p.quantite * d.cloture) OVER () AS poids_portefeuille
FROM v_positions p
JOIN v_dernier_cours d USING (ticker);

CREATE OR REPLACE VIEW v_synthese As
SELECT
SUM(valeur_marche) AS valeur_totale,
SUM(plus_value_latente) AS plus_value_latente_totale,
SUM(plus_value_latente) / NULLIF(SUM(valeur_marche - plus_value_latente),
                                 0) AS performance_globale,
                                    COUNT(*) AS nb_lignes,
                                    MAX(poids_portefeuille) AS poids_plus_grosse_ligne
FROM v_valorisation;

CREATE OR REPLACE VIEW v_historique AS
WITH jours AS (
    SELECT DISTINCT jour FROM prix
),
quantites AS (
    SELECT
        j.jour,
        t.ticker,
        SUM(CASE WHEN t.sens = 'ACHAT' THEN t.quantite ELSE -t.quantite END)
        AS quantite
        FROM jours j
        JOIN transactions t ON t.jour <= j.jour
        GROUP BY j.jour, t.ticker
)
SELECT 
q.jour,
SUM(q.quantite * p.cloture) AS valeur_portefeuille
FROM quantites q
JOIN prix p ON p.ticker = q.ticker AND p.jour = q.jour
GROUP BY q.jour
ORDER BY q.jour;

CREATE OR REPLACE VIEW v_risque AS
WITH rend AS (
    SELECT
    jour,
    valeur_portefeuille,
    valeur_portefeuille / LAG(valeur_portefeuille) OVER (ORDER BY jour) - 1 AS rendement
    FROM v_historique
),
dd AS (
    SELECT
    *,
    MAX(valeur_portefeuille) OVER (ORDER BY jour) AS sommet,
    valeur_portefeuille / MAX(valeur_portefeuille) OVER (ORDER BY jour) - 1 AS drawdown
    FROM rend
)
SELECT
jour,
valeur_portefeuille,
rendement,
drawdown,
STDDEV_SAMP(rendement) OVER (ORDER BY jour ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
* SQRT(252) AS volatilite_20J_annualisee
FROM dd;

SELECT
MIN(drawdown) AS drawdown_maximum,
STDDEV_SAMP(rendement) * SQRT(252) AS volatilite_annualisee,
AVG(rendement) / NULLIF(STDDEV_SAMP(rendement), 0) * SQRT(252) AS sharpe_sans_taux_sans_risque,
(SELECT valeur_portefeuille FROM v_risque ORDER BY jour DESC LIMIT 1)
/ (SELECT valeur_portefeuille FROM v_risque ORDER BY jour ASC LIMIT 1) - 1 AS performance_sur_periode
FROM v_risque;

CREATE OR REPLACE VIEW v_alertes AS
SELECT
ticker,
ROUND(poids_portefeuille * 100, 2) AS poids_pct
,
ROUND(performance_pct * 100, 2) AS performance,
CASE
WHEN poids_portefeuille > 0.20 THEN 'CONCENTRATION'
WHEN performance_pct < -0.10 THEN 'MOINS-VALUE > 10 %'
ELSE 'OK'
END AS statut
FROM v_valorisation
ORDER BY poids_portefeuille DESC;

CREATE MATERIALIZED VIEW mv_historique AS
SELECT * FROM v_historique;

REFRESH MATERIALIZED VIEW mv_historique;

SELECT * FROM v_historique;
"""
