-- Projet 6 - Backtest SQL du croisement des moyennes mobiles 20/50
-- Schema attendu:
-- prix(ticker TEXT, jour DATE, cloture NUMERIC)
-- cout: 0.001 (0,1 %) modifiable dans v_mm_rendements_portefeuille.

CREATE OR REPLACE VIEW v_mm_cours AS
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
    cloture,
    AVG(cloture) OVER (
        PARTITION BY ticker
        ORDER BY rang
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS mm_courte,
    AVG(cloture) OVER (
        PARTITION BY ticker
        ORDER BY rang
        ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
    ) AS mm_longue
FROM cours_ordonnes;

CREATE OR REPLACE VIEW v_mm_signaux AS
SELECT
    ticker,
    jour,
    cloture,
    mm_courte,
    mm_longue,
    CASE
        WHEN mm_courte IS NULL
          OR mm_longue IS NULL
          OR mm_courte <= mm_longue
        THEN 0
        ELSE 1
    END AS signal,
    CASE
        WHEN mm_courte IS NULL
          OR mm_longue IS NULL
          OR mm_courte <= mm_longue
        THEN 0
        ELSE 1
    END AS position
FROM v_mm_cours;

-- Décalage d'une séance: la position connue à la clôture est appliquée le lendemain.
CREATE OR REPLACE VIEW v_mm_positions AS
SELECT
    ticker,
    jour,
    cloture,
    mm_courte,
    mm_longue,
    COALESCE(
        LAG(position) OVER (
            PARTITION BY ticker
            ORDER BY jour
        ),
        0
    )::INTEGER AS position
FROM v_mm_signaux;

CREATE OR REPLACE VIEW v_mm_rendements AS
WITH rendements AS (
    SELECT
        ticker,
        jour,
        cloture,
        position,
        cloture / NULLIF(
            LAG(cloture) OVER (
                PARTITION BY ticker
                ORDER BY jour
            ),
            0
        ) - 1 AS rendement
    FROM v_mm_positions
),
poids AS (
    SELECT
        ticker,
        jour,
        position,
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
    r.ticker,
    r.jour,
    r.position,
    r.rendement,
    p.poids
FROM rendements r
JOIN poids p USING (ticker, jour);

CREATE OR REPLACE VIEW v_mm_portefeuille AS
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
    FROM v_mm_rendements
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

CREATE OR REPLACE VIEW v_mm_drawdown AS
WITH portefeuille AS (
    SELECT
        jour,
        rendement_net,
        valeur_base_1,
        MAX(valeur_base_1) OVER (
            ORDER BY jour
            ROWS UNBOUNDED PRECEDING
        ) AS sommet
    FROM v_mm_portefeuille
)
SELECT
    jour,
    rendement_net,
    valeur_base_1,
    valeur_base_1 / NULLIF(sommet, 0) - 1 AS drawdown
FROM portefeuille;

CREATE OR REPLACE VIEW v_mm_synthese AS
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
        FROM v_mm_drawdown
        WHERE valeur_base_1 IS NOT NULL
        ORDER BY jour DESC
        LIMIT 1
    ) - 1 AS rendement_cumule
FROM v_mm_drawdown;

-- Résultats principaux
SELECT * FROM v_mm_synthese;

-- Courbe journalière
SELECT * FROM v_mm_portefeuille ORDER BY jour;
