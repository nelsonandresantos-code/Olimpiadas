-- Indicador: especialidade de cada país (heatmap país × esporte).
-- Grão: uma linha por país (abrev_pais) e esporte em que o país ganhou ao
-- menos uma medalha. Combinações sem medalha não têm linha (célula vazia = 0).
-- percentual_do_pais = medalhas do país no esporte / total de medalhas do
-- país * 100: é o valor do heatmap, pois compara países de tamanhos
-- diferentes. ranking_no_pais = 1 indica o esporte em que o país mais
-- concentra medalhas (empate divide a posição).
-- Medalhas vêm de refined.resultado_atleta, a única fonte com esporte, e são
-- contadas como no quadro de medalhas: uma medalha de equipe vale 1 para o
-- país, não 1 por atleta. Unidade: (resultado, país, medalha) em provas
-- coletivas e (resultado, atleta, medalha) em provas individuais.
-- Art Competitions (1912–1948) ficam de fora: os participantes eram artistas,
-- não atletas. 1906 (Jogos Intercalados) fica de fora: não é reconhecido
-- oficialmente pelo COI.
WITH linha AS (
    SELECT
        r.*,
        -- Uma prova é coletiva só se todas as linhas dela dizem isso: o monobob
        -- 2022 (individual) tem linhas marcadas das duas formas na fonte.
        bool_and(r.esporte_coletivo) OVER (PARTITION BY r.id_resultado) AS prova_coletiva
    FROM refined.resultado_atleta r
    JOIN refined.jogos_olimpicos j ON j.id_jogos = r.edicao_id
    WHERE r.medalha IS NOT NULL
      AND r.sport <> 'Art Competitions'
      AND j.ano_jogos <> 1906
),
medalha AS (
    SELECT DISTINCT
        id_resultado,
        abrev_pais_atleta                               AS abrev_pais,
        sport                                           AS esporte,
        medalha,
        CASE WHEN prova_coletiva THEN NULL ELSE id_atleta END AS id_atleta
    FROM linha
),
pais_esporte AS (
    SELECT
        abrev_pais,
        esporte,
        CAST(count(*) FILTER (WHERE medalha = 'Gold') AS INTEGER)   AS ouro,
        CAST(count(*) FILTER (WHERE medalha = 'Silver') AS INTEGER) AS prata,
        CAST(count(*) FILTER (WHERE medalha = 'Bronze') AS INTEGER) AS bronze,
        CAST(count(*) AS INTEGER)                                   AS total
    FROM medalha
    GROUP BY abrev_pais, esporte
),
nomes AS (
    -- Nome do país: o de medalhas_pais (um por código) e, se faltar, o de
    -- pais. ROC tem dois nomes em pais, mas aparece em medalhas_pais.
    SELECT DISTINCT abrev_pais_medalha AS abrev_pais, pais_medalha AS nome_pais
    FROM refined.medalhas_pais
    UNION ALL
    SELECT abrev_pais, nome_pais
    FROM refined.pais
    WHERE abrev_pais NOT IN (SELECT abrev_pais_medalha FROM refined.medalhas_pais)
)
SELECT
    p.abrev_pais,
    n.nome_pais,
    p.esporte,
    p.ouro,
    p.prata,
    p.bronze,
    p.total,
    CAST(sum(p.total) OVER (PARTITION BY p.abrev_pais) AS INTEGER) AS total_pais,
    round(100.0 * p.total / sum(p.total) OVER (PARTITION BY p.abrev_pais), 2) AS percentual_do_pais,
    rank() OVER (
        PARTITION BY p.abrev_pais
        ORDER BY p.total DESC, p.ouro DESC, p.prata DESC
    ) AS ranking_no_pais
FROM pais_esporte p
LEFT JOIN nomes n ON n.abrev_pais = p.abrev_pais
ORDER BY total_pais DESC, p.abrev_pais, ranking_no_pais, p.esporte;
