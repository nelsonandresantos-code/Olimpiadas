-- Indicador: quadro de medalhas histórico por país e temporada (ranking geral).
-- Grão: uma linha por temporada (Summer/Winter) e país (abrev_pais), somando
-- todas as edições daquela temporada em refined.medalhas_pais. Verão e inverno
-- têm rankings independentes, pois são competições com esportes diferentes.
-- Ranking no critério olímpico: mais ouros, depois pratas, depois bronzes;
-- empate total divide a mesma posição (RANK).
-- 1906 (Jogos Intercalados) fica de fora: não é reconhecido oficialmente pelo COI.
-- Art Competitions (1912–1948) estão incluídas: refined.medalhas_pais segue o
-- quadro oficial e não tem esporte para filtrá-las. Por isso os totais diferem
-- um pouco dos indicadores calculados a partir de refined.resultado_atleta
-- (atletas mais medalhados, especialidade país × esporte), que as excluem.
-- Países históricos (URS, GDR, FRG, EUN...) aparecem separados, como no
-- quadro oficial: cada código de país é uma entidade.
WITH historico AS (
    SELECT
        temporada,
        abrev_pais_medalha                   AS abrev_pais,
        pais_medalha                         AS nome_pais,
        CAST(count(*) AS INTEGER)            AS edicoes_com_medalha,
        CAST(sum(medalha_ouro) AS INTEGER)   AS ouro,
        CAST(sum(medalha_prata) AS INTEGER)  AS prata,
        CAST(sum(medalha_bronze) AS INTEGER) AS bronze,
        CAST(sum(total_medalha) AS INTEGER)  AS total
    FROM refined.medalhas_pais
    WHERE ano <> 1906
    GROUP BY temporada, abrev_pais_medalha, pais_medalha
)
SELECT
    temporada,
    rank() OVER (
        PARTITION BY temporada
        ORDER BY ouro DESC, prata DESC, bronze DESC
    ) AS ranking_geral,
    abrev_pais,
    nome_pais,
    ouro,
    prata,
    bronze,
    total,
    edicoes_com_medalha
FROM historico
ORDER BY temporada, ranking_geral, nome_pais;
