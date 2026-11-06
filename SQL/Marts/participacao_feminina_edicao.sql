-- Indicador: participação feminina por edição, de 1896 até a última edição
-- presente na fonte.
-- Grão: uma linha por temporada (Summer/Winter) e ano. Em 1956 a fonte tem
-- duas edições de verão (Melbourne e as provas hípicas de Estocolmo), que aqui
-- são somadas numa linha só; a coluna edicoes lista o que foi somado.
-- Atleta é contado uma vez por temporada e ano, mesmo que dispute várias
-- provas ou apareça por mais de um país em refined.resultado_atleta.
-- percentual_mulheres = mulheres / (mulheres + homens) * 100. Atletas sem
-- cadastro em refined.bio_atleta (sexo desconhecido) ficam em coluna própria e
-- fora do percentual, em vez de serem contados como homem ou mulher.
-- Art Competitions (1912–1948) ficam de fora: os participantes eram artistas,
-- não atletas.
-- 1906 (Jogos Intercalados) fica de fora: não é reconhecido oficialmente pelo COI.
WITH atleta_ano AS (
    SELECT DISTINCT
        j.temporada,
        j.ano_jogos AS ano,
        r.id_atleta
    FROM refined.resultado_atleta r
    JOIN refined.jogos_olimpicos j ON j.id_jogos = r.edicao_id
    WHERE r.sport <> 'Art Competitions'
      AND j.ano_jogos <> 1906
),
edicoes AS (
    SELECT DISTINCT j.temporada, j.ano_jogos AS ano, j.edicao_jogos
    FROM refined.resultado_atleta r
    JOIN refined.jogos_olimpicos j ON j.id_jogos = r.edicao_id
),
contagem AS (
    SELECT
        a.temporada,
        a.ano,
        CAST(count(*) AS INTEGER)                                         AS atletas,
        CAST(count(*) FILTER (WHERE b.sexo_atleta = 'Female') AS INTEGER) AS mulheres,
        CAST(count(*) FILTER (WHERE b.sexo_atleta = 'Male') AS INTEGER)   AS homens,
        CAST(count(*) FILTER (WHERE b.sexo_atleta IS NULL) AS INTEGER)    AS sexo_desconhecido
    FROM atleta_ano a
    LEFT JOIN refined.bio_atleta b ON b.id_atleta = a.id_atleta
    GROUP BY a.temporada, a.ano
)
SELECT
    c.temporada,
    c.ano,
    (SELECT string_agg(e.edicao_jogos, ' + ' ORDER BY e.edicao_jogos)
     FROM edicoes e
     WHERE e.temporada = c.temporada AND e.ano = c.ano)      AS edicoes,
    c.atletas,
    c.mulheres,
    c.homens,
    c.sexo_desconhecido,
    round(100.0 * c.mulheres / nullif(c.mulheres + c.homens, 0), 2) AS percentual_mulheres
FROM contagem c
ORDER BY c.temporada, c.ano;
