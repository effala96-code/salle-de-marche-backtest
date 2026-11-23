-- Projet 7 - Backtest SQL de retour a la moyenne (score Z)
-- Schema attendu:
-- prix(ticker TEXT, jour DATE, cloture NUMERIC)
-- Fenetre: 20 seances
-- Achat: Z <= -2
-- Sortie: Z >= +2
-- Cout: 0.001 (0,1 %) par variation de poids

CREATE OR REPLACE VIEW v_z_observations AS
WITH cours_ordonnes AS (
    SELECT
        ticker,
        jour,
        cloture,
        ROW_NUMBER() OVER (
            PARTITION BY ticker
            ORDER BY jour
        ) AS rang
    FROM prix
)
SELECT
    ticker,
    jour,
    rang,
    cloture,
    AVG(cloture) OVER (
        PARTITION BY ticker
        ORDER BY rang
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS moyenne_20,
    STDDEV_SAMP(cloture) OVER (
        PARTITION BY ticker
        ORDER BY rang
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS ecart_type_20
FROM cours_ordonnes;

CREATE OR REPLACE VIEW v_z_scores AS
SELECT
    ticker,
    jour,
    rang,
    cloture,
    moyenne_20,
    ecart_type_20,
    CASE
        WHEN ecart_type_20 IS NULL
          OR ecart_type_20 = 0
        THEN NULL
        ELSE (cloture - moyenne_20) / ecart_type_20
    END AS score_z
FROM v_z_observations;

CREATE OR REPLACE VIEW v_z_positions AS
WITH RECURSIVE
initiale AS (
    SELECT
        ticker,
        rang,
        jour,
        cloture,
        score_z,
        0::INTEGER AS position_brute
    FROM v_z_scores
    WHERE rang = 1
),
positions AS (
    SELECT * FROM initiale

    UNION ALL

    SELECT
        c.ticker,
        c.rang,
        c.jour,
        c.cloture,
        c.score_z,
        CASE
            WHEN c.score_z IS NULL THEN p.position_brute
            WHEN c.score_z <= -2 THEN 1
            WHEN c.score_z >= 2 THEN 0
            ELSE p.position_brute
        END::INTEGER AS position_brute
    FROM positions p
    JOIN v_z_scores c
      ON c.ticker = p.ticker
     AND c.rang = p.rang + 1
)
SELECT
    ticker,
    jour,
    rang,
    cloture,
    score_z,
    position_brute,
    COALESCE(
        LAG(position_brute) OVER (
            PARTITION BY ticker
            ORDER BY rang
        ),
        0
    )::INTEGER AS position
FROM positions;

CREATE OR REPLACE VIEW v_z_rendements AS
WITH rendements AS (
    SELECT
        ticker,
        jour,
        rang,
        position,
        cloture,
        cloture / NULLIF(
            LAG(cloture) OVER (
                PARTITION BY ticker
                ORDER BY rang
            ),
            0
        ) - 1 AS rendement
    FROM v_z_positions
),
poids AS (
    SELECT
        ticker,
        jour,
        rang,
        position,
        rendement,
        CASE
            WHEN position = 0 THEN 0
            ELSE position::NUMERIC
                 / NULLIF(
                     SUM(position) OVER (PARTITION BY jour),
                     0
                   )
        END AS poids
    FROM rendements
)
SELECT
    ticker,
    jour,
    rang,
    position,
    rendement,
    poids
FROM poids;

CREATE OR REPLACE VIEW v_z_portefeuille AS
WITH portefeuille_journalier AS (
    SELECT
        jour,
        SUM(poids * COALESCE(rendement, 0)) AS rendement_brut,
        AVG(COALESCE(rendement, 0)) AS rendement_benchmark,
        SUM(poids) AS exposition,
        SUM(
            ABS(
                poids
                - COALESCE(
                    LAG(poids) OVER (
                        PARTITION BY ticker
                        ORDER BY jour
                    ),
                    0
                )
            )
        ) AS turnover
    FROM v_z_rendements
    GROUP BY jour
),
net AS (
    SELECT
        jour,
        rendement_brut,
        rendement_benchmark,
        exposition,
        turnover,
        0.001 AS cout,
        rendement_brut - turnover * 0.001 AS rendement_net
    FROM portefeuille_journalier
)
SELECT
    jour,
    rendement_brut,
    rendement_benchmark,
    exposition,
    turnover,
    cout,
    rendement_net,
    EXP(
        COALESCE(
            SUM(LN(GREATEST(1 + rendement_net, 0.000001)))
                OVER (ORDER BY jour ROWS UNBOUNDED PRECEDING),
            0
        )
    ) AS valeur_base_1,
    EXP(
        COALESCE(
            SUM(LN(GREATEST(1 + rendement_benchmark, 0.000001)))
                OVER (ORDER BY jour ROWS UNBOUNDED PRECEDING),
            0
        )
    ) AS benchmark_base_1
FROM net;

CREATE OR REPLACE VIEW v_z_drawdown AS
SELECT
    jour,
    rendement_net,
    valeur_base_1,
    benchmark_base_1,
    MAX(valeur_base_1) OVER (
        ORDER BY jour
        ROWS UNBOUNDED PRECEDING
    ) AS sommet,
    valeur_base_1
        / NULLIF(
            MAX(valeur_base_1) OVER (
                ORDER BY jour
                ROWS UNBOUNDED PRECEDING
            ),
            0
        ) - 1 AS drawdown
FROM v_z_portefeuille;

CREATE OR REPLACE VIEW v_z_synthese AS
SELECT
    MIN(jour) AS date_debut,
    MAX(jour) AS date_fin,
    COUNT(*) AS nombre_seances,
    EXP(AVG(LN(GREATEST(1 + rendement_net, 0.000001))) * 252) - 1
        AS rendement_annuel_compose,
    STDDEV_SAMP(rendement_net) * SQRT(252)
        AS volatilite_annuelle,
    AVG(rendement_net) / NULLIF(STDDEV_SAMP(rendement_net), 0) * SQRT(252)
        AS sharpe_sans_risque,
    MIN(drawdown) AS perte_maximale,
    (
        SELECT valeur_base_1
        FROM v_z_drawdown
        ORDER BY jour DESC
        LIMIT 1
    ) - 1 AS rendement_cumule
FROM v_z_drawdown;

-- Résultats principaux
SELECT * FROM v_z_synthese;

-- Courbe journalière
SELECT * FROM v_z_portefeuille ORDER BY jour;
