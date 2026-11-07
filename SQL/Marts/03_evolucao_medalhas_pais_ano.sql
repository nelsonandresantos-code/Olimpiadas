-- Indicador: evolução de um país ao longo do tempo (gráfico de linha).
-- Grão: uma linha por temporada (Summer/Winter), ano e país (abrev_pais), com
-- ouro, prata, bronze e total de medalhas naquele ano.
-- Anos em que o país participou (tem atleta em refined.resultado_atleta) mas
-- não ganhou medalha aparecem com 0, para a linha do gráfico descer a zero em
-- vez de ligar direto os anos com medalha. Anos em que o país não participou
-- (ou não houve Jogos, como 1916/1940/1944) não têm linha.
-- 1956 tem duas edições de verão na fonte (Melbourne e as provas hípicas de
-- Estocolmo): por ser "por ano", são somadas.
-- 1906 (Jogos Intercalados) fica de fora: não é reconhecido oficialmente pelo COI.
-- Art Competitions (1912–1948) estão incluídas: refined.medalhas_pais segue o
-- quadro oficial e não tem esporte para filtrá-las. Por isso os totais diferem
-- um pouco dos indicadores calculados a partir de refined.resultado_atleta
-- (atletas mais medalhados, especialidade país × esporte), que as excluem.
-- MIX ("Mixed team") são equipes com atletas de países diferentes: não é um
-- país, mas é mantido para o total de medalhas fechar com refined.medalhas_pais.
WITH participacao AS (
    -- DISTINCT: resultado_atleta tem uma linha por atleta e prova; aqui só
    -- interessa se o país esteve na edição.
    SELECT DISTINCT edicao_id, abrev_pais_atleta AS abrev_pais
    FROM refined.resultado_atleta
),
medalhas AS (
    SELECT
        edicao_id,
        abrev_pais_medalha AS abrev_pais,
        medalha_ouro,
        medalha_prata,
        medalha_bronze,
        total_medalha
    FROM refined.medalhas_pais
),
edicao_pais AS (
    SELECT
        coalesce(m.edicao_id, p.edicao_id)   AS edicao_id,
        coalesce(m.abrev_pais, p.abrev_pais) AS abrev_pais,
        coalesce(m.medalha_ouro, 0)          AS ouro,
        coalesce(m.medalha_prata, 0)         AS prata,
        coalesce(m.medalha_bronze, 0)        AS bronze,
        coalesce(m.total_medalha, 0)         AS total
    FROM medalhas m
    FULL OUTER JOIN participacao p
        ON p.edicao_id = m.edicao_id AND p.abrev_pais = m.abrev_pais
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
)
SELECT
    j.temporada,
    j.ano_jogos                      AS ano,
    e.abrev_pais,
    n.nome_pais,
    CAST(sum(e.ouro) AS INTEGER)     AS ouro,
    CAST(sum(e.prata) AS INTEGER)    AS prata,
    CAST(sum(e.bronze) AS INTEGER)   AS bronze,
    CAST(sum(e.total) AS INTEGER)    AS total
FROM edicao_pais e
JOIN refined.jogos_olimpicos j ON j.id_jogos = e.edicao_id
LEFT JOIN nomes n ON n.abrev_pais = e.abrev_pais
WHERE j.ano_jogos <> 1906
GROUP BY j.temporada, j.ano_jogos, e.abrev_pais, n.nome_pais
ORDER BY e.abrev_pais, j.temporada, j.ano_jogos;
