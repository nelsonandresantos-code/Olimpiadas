"""Etapa 1: ingestão dos seis .csv.gz das Olimpíadas no schema raw.

Execução:
    uv run python -m pipeline.ingestao

1. ESCOPO E NOMES
   Schema de destino: raw. Mapa arquivo -> tabela, completo e literal:
     world_olympedia_olympics_athlete_bio.csv.gz           -> bio_atleta
     world_olympedia_olympics_athlete_event_result.csv.gz  -> resultado_atleta
     world_olympedia_olympics_country.csv.gz               -> pais
     world_olympedia_olympics_game.csv.gz                  -> jogos_olimpicos
     world_olympedia_olympics_game_medal_tally.csv.gz      -> medalhas_pais
     world_olympedia_olympics_result.csv.gz                -> resultados
   Por quê: os nomes estão em português porque é o vocabulário que será
   digitado de memória nos JOINs das próximas aulas.

2. PROIBIÇÕES (a regra central desta etapa)
   Nenhuma conversão de tipo. Nenhuma linha descartada ou deduplicada.
   Nenhum nome de coluna alterado. Nenhum valor corrigido, preenchido ou
   normalizado. Data continua texto, nulo continua nulo.
   Por quê: a fronteira entre "o dado que chegou" e "o dado que eu decidi"
   precisa existir em algum lugar, e esse lugar é a passagem de raw para
   refined, na etapa 2. Se a correção acontecer aqui, a fronteira some.

3. REEXECUÇÃO
   Rodar dez vezes dá o mesmo resultado que rodar uma: a tabela é recriada
   (CREATE OR REPLACE), nunca acrescentada.
   Por quê: é o que permite errar sem medo.

4. LEITURA DO ARQUIVO
   encoding declarado como utf-8, nunca adivinhado. Os .csv.gz são lidos
   direto, sem descompactar. Campo vazio continua virando nulo; não vira
   string vazia.
   Por quê: adivinhar encoding troca acento sem aviso, e string vazia no
   lugar de nulo é uma correção de valor feita escondida (item 2).

5. TIPAGEM
   Toda coluna entra como texto (dtype=str), inferência desligada.
   Por quê: inferência lê código com zero à esquerda como número e o zero
   desaparece sem aviso. A conversão acontece na etapa 2, onde é uma
   decisão registrada.

6. SAÍDA NA TELA
   Uma linha por tabela, com nome qualificado e contagem de linhas vinda do
   banco (não do DataFrame), milhar separado por ponto. Uma linha final com
   o total. stdout reconfigurado para utf-8.
   Por quê: essa saída é o único instrumento de conferência desta etapa, e
   no Prompt de Comando do Windows acento sai embaralhado por padrão.

7. ERRO
   Antes de abrir o banco, verifica se os seis arquivos existem. Faltando
   qualquer um: lista os que faltam, diz em que pasta procurou e encerra com
   sys.exit(1). Não ingere parcialmente.
   Por quê: ingerir cinco de seis tabelas em silêncio produz um dashboard
   errado que parece certo.

Este módulo não importa ui.py: a ingestão não sobe servidor, não abre
navegador e não depende da extensão ui do DuckDB.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

SCHEMA = "raw"

ARQUIVOS = {
    "world_olympedia_olympics_athlete_bio.csv.gz": "bio_atleta",
    "world_olympedia_olympics_athlete_event_result.csv.gz": "resultado_atleta",
    "world_olympedia_olympics_country.csv.gz": "pais",
    "world_olympedia_olympics_game.csv.gz": "jogos_olimpicos",
    "world_olympedia_olympics_game_medal_tally.csv.gz": "medalhas_pais",
    "world_olympedia_olympics_result.csv.gz": "resultados",
}


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    faltando = [nome for nome in ARQUIVOS if not (PASTA_RAW / nome).is_file()]
    if faltando:
        print(f"Arquivos faltando em {PASTA_RAW}:")
        for nome in faltando:
            print(f"  {nome}")
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, SCHEMA)
        total = 0
        for arquivo, tabela in ARQUIVOS.items():
            df = pd.read_csv(
                PASTA_RAW / arquivo,
                dtype=str,
                encoding="utf-8",
                # Só campo vazio vira nulo. O padrão do pandas também anula
                # textos como "NA", "null" e "N/A", o que seria corrigir valor.
                keep_default_na=False,
                na_values=[""],
            )
            n = gravar(con, df, SCHEMA, tabela)
            total += n
            print(f"{SCHEMA}.{tabela:<20} {milhar(n):>12}")
        print(f"{'Total':<24} {milhar(total):>12}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
