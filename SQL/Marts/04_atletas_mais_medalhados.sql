-- Indicador: atletas mais medalhados, com ranking por total de medalhas e por
-- ouros, país e esporte.
-- Grão: uma linha por atleta medalhista (id_atleta). O "top N" é escolhido no
-- dashboard filtrando ranking_total <= N ou ranking_ouro <= N.
-- Unidade de medalha: (atleta, resultado, tipo de medalha) contada uma vez.
-- refined.resultado_atleta repete o mesmo atleta no mesmo resultado quando ele
-- aparece por mais de um país (ex.: alpinismo 1924, um ouro listado em 4
-- países), e isso não pode virar 4 medalhas. Já o mesmo atleta com medalhas
-- diferentes no mesmo resultado (ex.: dois barcos na mesma regata de 1900) são
-- medalhas distintas e contam ambas.
-- ranking_total: total, depois ouro, depois prata. ranking_ouro: critério
-- olímpico (ouro, depois prata, depois bronze). Empate divide a posição (RANK).
-- paises, esportes e temporadas listam todos em que o atleta ganhou medalha.
-- Art Competitions (1912–1948) ficam de fora: os participantes eram artistas,
-- não atletas. 1906 (Jogos Intercalados) fica de fora: não é reconhecido
-- oficialmente pelo COI.
WITH medalha AS (
    SELECT DISTINCT
        r.id_atleta,
        r.id_resultado,
        r.medalha
    FROM refined.resultado_atleta r
    JOIN refined.jogos_olimpicos j ON j.id_jogos = r.edicao_id
    WHERE r.medalha IS NOT NULL
      AND r.sport <> 'Art Competitions'
      AND j.ano_jogos <> 1906
),
contagem AS (
    SELECT
        id_atleta,
        CAST(count(*) FILTER (WHERE medalha = 'Gold') AS INTEGER)   AS ouro,
        CAST(count(*) FILTER (WHERE medalha = 'Silver') AS INTEGER) AS prata,
        CAST(count(*) FILTER (WHERE medalha = 'Bronze') AS INTEGER) AS bronze,
        CAST(count(*) AS INTEGER)                                   AS total
    FROM medalha
    GROUP BY id_atleta
),
atributos AS (
    SELECT
        r.id_atleta,
        any_value(r.atleta)                                                   AS nome_resultado,
        string_agg(DISTINCT r.abrev_pais_atleta, ', ' ORDER BY r.abrev_pais_atleta) AS paises,
        string_agg(DISTINCT r.sport, ', ' ORDER BY r.sport)                   AS esportes,
        string_agg(DISTINCT j.temporada, ', ' ORDER BY j.temporada)           AS temporadas
    FROM refined.resultado_atleta r
    JOIN refined.jogos_olimpicos j ON j.id_jogos = r.edicao_id
    WHERE r.medalha IS NOT NULL
      AND r.sport <> 'Art Competitions'
      AND j.ano_jogos <> 1906
    GROUP BY r.id_atleta
)
SELECT
    rank() OVER (ORDER BY c.total DESC, c.ouro DESC, c.prata DESC)  AS ranking_total,
    rank() OVER (ORDER BY c.ouro DESC, c.prata DESC, c.bronze DESC) AS ranking_ouro,
    c.id_atleta,
    -- Nome do cadastro do atleta; o de resultado_atleta só se faltar cadastro.
    coalesce(b.nome_atleta, a.nome_resultado) AS nome_atleta,
    b.sexo_atleta,
    a.paises,
    a.esportes,
    a.temporadas,
    c.ouro,
    c.prata,
    c.bronze,
    c.total
FROM contagem c
JOIN atributos a ON a.id_atleta = c.id_atleta
LEFT JOIN refined.bio_atleta b ON b.id_atleta = c.id_atleta
ORDER BY ranking_total, ranking_ouro, nome_atleta;
