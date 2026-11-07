-- Indicador: quadro de medalhas por país em cada edição (ranking por edição).
-- Grão: uma linha por edição e país (edicao_id, abrev_pais), direto de
-- refined.medalhas_pais, com a temporada (Summer/Winter) para separar
-- Jogos de Verão e de Inverno no dashboard.
-- Ranking no critério olímpico dentro de cada edição: mais ouros, depois
-- pratas, depois bronzes; empate total divide a mesma posição (RANK).
-- 1906 (Jogos Intercalados) fica de fora: não é reconhecido oficialmente pelo COI.
-- Art Competitions (1912–1948) estão incluídas: refined.medalhas_pais segue o
-- quadro oficial e não tem esporte para filtrá-las. Por isso os totais diferem
-- um pouco dos indicadores calculados a partir de refined.resultado_atleta
-- (atletas mais medalhados, especialidade país × esporte), que as excluem.
-- 1956 Equestrian é edição própria na fonte (provas hípicas de Melbourne,
-- disputadas em Estocolmo) e tem ranking próprio.
SELECT
    temporada,
    edicao_id,
    edicao,
    ano,
    rank() OVER (
        PARTITION BY edicao_id
        ORDER BY medalha_ouro DESC, medalha_prata DESC, medalha_bronze DESC
    )                   AS ranking_edicao,
    abrev_pais_medalha  AS abrev_pais,
    pais_medalha        AS nome_pais,
    medalha_ouro        AS ouro,
    medalha_prata       AS prata,
    medalha_bronze      AS bronze,
    total_medalha       AS total
FROM refined.medalhas_pais
WHERE ano <> 1906
ORDER BY temporada, ano, edicao_id, ranking_edicao, nome_pais;
