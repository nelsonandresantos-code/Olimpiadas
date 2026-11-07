-- Indicador: eficiência de conversão — medalhas por atleta enviado, por país e
-- edição. Destaca países com delegações pequenas que rendem muitas medalhas.
-- Grão: uma linha por edição e país (edicao_id, abrev_pais) que teve ao menos
-- um atleta na edição, com temporada (Summer/Winter) para separar Verão e
-- Inverno. Países que participaram sem medalha aparecem com 0.
-- medalhas_por_atleta = total de medalhas do quadro oficial / atletas
-- distintos do país na edição. Pode passar de 1: um atleta ganha várias
-- medalhas, e uma medalha de equipe vale 1 para o país mesmo com vários
-- atletas. percentual_atletas_medalhistas = atletas que voltaram com ao menos
-- uma medalha / atletas enviados * 100.
-- Delegações minúsculas distorcem a razão (1 atleta e 1 medalha = 1,0): o
-- dashboard deve filtrar por um mínimo de atletas. ranking_eficiencia é
-- calculado sobre todos os países da edição; empate divide a posição (RANK).
-- Numerador e denominador têm o mesmo escopo: medalhas vêm de
-- refined.medalhas_pais (quadro oficial, que inclui Art Competitions de
-- 1912–1948 e não tem esporte para filtrá-las), então os artistas também
-- contam como atletas enviados.
-- 1906 (Jogos Intercalados) fica de fora: não é reconhecido oficialmente pelo
-- COI. MIX ("Mixed team") fica de fora: não é um país e não tem atletas
-- próprios (cada atleta da equipe mista está no seu país).
-- 1956 Equestrian é edição própria na fonte (provas hípicas de Melbourne,
-- disputadas em Estocolmo) e é calculada separadamente.
WITH delegacao AS (
    -- DISTINCT por atleta: resultado_atleta tem uma linha por atleta e prova.
    SELECT
        edicao_id,
        abrev_pais_atleta                                AS abrev_pais,
        CAST(count(DISTINCT id_atleta) AS INTEGER)       AS atletas,
        CAST(count(DISTINCT id_atleta) FILTER (WHERE medalha IS NOT NULL) AS INTEGER)
                                                         AS atletas_medalhistas
    FROM refined.resultado_atleta
    GROUP BY edicao_id, abrev_pais_atleta
),
nomes AS (
    -- Nome do país: o de medalhas_pais (um por código) e, para quem nunca
    -- ganhou medalha, o de pais. ROC tem dois nomes em pais, mas aparece em
    -- medalhas_pais e por isso não duplica.
    SELECT DISTINCT abrev_pais_medalha AS abrev_pais, pais_medalha AS nome_pais
    FROM refined.medalhas_pais
    UNION ALL
    SELECT abrev_pais, nome_pais
    FROM refined.pais
    WHERE abrev_pais NOT IN (SELECT abrev_pais_medalha FROM refined.medalhas_pais)
),
base AS (
    SELECT
        j.temporada,
        d.edicao_id,
        j.edicao_jogos                    AS edicao,
        j.ano_jogos                       AS ano,
        d.abrev_pais,
        n.nome_pais,
        d.atletas,
        d.atletas_medalhistas,
        coalesce(m.medalha_ouro, 0)       AS ouro,
        coalesce(m.medalha_prata, 0)      AS prata,
        coalesce(m.medalha_bronze, 0)     AS bronze,
        coalesce(m.total_medalha, 0)      AS total
    FROM delegacao d
    JOIN refined.jogos_olimpicos j ON j.id_jogos = d.edicao_id
    LEFT JOIN refined.medalhas_pais m
        ON m.edicao_id = d.edicao_id AND m.abrev_pais_medalha = d.abrev_pais
    LEFT JOIN nomes n ON n.abrev_pais = d.abrev_pais
    WHERE j.ano_jogos <> 1906
      AND d.abrev_pais <> 'MIX'
)
SELECT
    temporada,
    edicao_id,
    edicao,
    ano,
    rank() OVER (
        PARTITION BY edicao_id
        ORDER BY total * 1.0 / atletas DESC, ouro * 1.0 / atletas DESC
    )                                                       AS ranking_eficiencia,
    abrev_pais,
    nome_pais,
    atletas,
    atletas_medalhistas,
    ouro,
    prata,
    bronze,
    total,
    round(total * 1.0 / atletas, 4)                         AS medalhas_por_atleta,
    round(ouro * 1.0 / atletas, 4)                          AS ouros_por_atleta,
    round(100.0 * atletas_medalhistas / atletas, 2)         AS percentual_atletas_medalhistas
FROM base
ORDER BY temporada, ano, edicao_id, ranking_eficiencia, nome_pais;
