"""Etapa 2: transformação do schema raw no schema refined.

Execução:
    uv run python -m pipeline.transformacao

1. ESCOPO
   Lê de raw, escreve em refined. Nunca escreve em raw. Seis tabelas:
   bio_atleta, jogos_olimpicos, medalhas_pais, pais, resultado_atleta,
   resultados.
   Por quê: raw é "o dado que chegou". Se esta etapa o alterasse, não haveria
   mais com o que comparar o resultado de uma decisão.

2. NOMES
   Colunas renomeadas pelo mapa em COLUNAS, completo e literal, em snake_case
   minúsculo (o mapa original tinha 'pais atleta', 'URL_bandeira' etc.; foram
   normalizados para pais_atleta, url_bandeira). Nenhuma coluna do raw fica
   fora do mapa e nenhuma é descartada. A única coluna nova é temporada
   (item 4).
   Por quê: é o vocabulário que será digitado de memória nos JOINs da aula 3.
   Nome com espaço ou maiúscula obrigaria aspas em toda consulta.

3. TIPOS
   DATE, formato '%Y-%m-%d': data_nascimento, data_inicio_jogos,
     data_fim_jogos. (A spec declarava '%d-%m-%y', mas 100% dos valores
     preenchidos estão em ISO; o formato declarado é o que o dado tem.)
   INTEGER: ids, anos, contagens de medalha, altura_atleta, peso_atleta.
   BOOLEAN: esporte_coletivo (is_team_sport).
   VARCHAR: todo o resto, incluindo:
     - posicao: 114.617 valores não são inteiros ('=9', 'Did not start',
       '2 h8 r1/3', 'HM'...). Fica texto como veio.
     - data_resultado: texto livre com cerca de 150 formatos, quase todos
       intervalos ('27 – 30 September 1988 — 10:30'). Fica texto, só com
       trim.
   A conversão é feita em SQL pelo DuckDB (strptime, CAST), disparada pelo
   Python.
   Por quê: o dado já está no banco; não há por que trazê-lo para a memória
   só para converter tipo. posicao e data_resultado não são convertidos
   porque qualquer conversão para número ou data descartaria informação
   ('=9' é empate; um intervalo não cabe em um DATE).

4. TRANSFORMAÇÕES DE VALOR
   - trim em bio_atleta.country e resultados.result_date, que vêm com espaço
     à esquerda (' Cuba', ' 2 October 1900').
   - result_detail = 'na' vira NULL.
   - temporada ('Summer'/'Winter') extraída de edition em toda tabela que
     tem edition (jogos_olimpicos, medalhas_pais, resultado_atleta,
     resultados). '1906 Intercalated Games' e '1956 Equestrian Olympics' não
     trazem a palavra e são mapeadas para 'Summer'. Qualquer outra edição sem
     temporada reconhecível para o script, como na regra 5.
   - jogos_olimpicos NÃO é filtrado: jogos futuros (2024, 2028, 2032) e
     cancelados (guerras) continuam lá; realizado_jogos diz quais aconteceram.
   Por quê: o espaço à esquerda quebra igualdade em JOIN e filtro; 'na' é um
   nulo disfarçado de texto; temporada é a primeira coisa por que se agrupa
   Olimpíadas, e extrair de texto em cada consulta é repetir a mesma regra em
   vários lugares. As edições de 1906 e 1956 foram jogos de verão. Não filtrar
   jogos mantém o aceite "linhas que saem = linhas que entram" sem exceção.

5. CONVERSÃO QUE FALHA
   Para tudo. Só strptime e CAST, que estouram; nunca try_strptime, TRY_CAST
   ou errors="coerce". Ao falhar, informa tabela, coluna e um exemplo do valor
   e encerra com sys.exit(1). Cada coluna convertida é testada antes de
   qualquer gravação, então uma falha não deixa refined pela metade.
   Por quê: um nulo fabricado pela conversão fica indistinguível de um nulo
   verdadeiro do dado, para sempre.

6. DUPLICATAS
   Chave de cada tabela:
     bio_atleta        (id_atleta)
     jogos_olimpicos   (id_jogos)
     medalhas_pais     (edicao_id, pais_medalha)
     pais              (nome_pais, abrev_pais)
     resultado_atleta  linha inteira
     resultados        (id_resultado)
   Linha inteira repetida: mantém uma e conta quantas saíram. Chave repetida
   com conteúdo diferente: para, mostra a chave e as linhas conflitantes e
   encerra com sys.exit(1).
   resultado_atleta não tem chave de negócio: o mesmo atleta aparece no mesmo
   resultado com países diferentes (Howard Somervell, Alpinismo 1924:
   AUS/GBR/IND/NEP) ou com posições diferentes. Só sai o que é cópia exata.
   Por quê: escolher em silêncio entre duas linhas é decidir sem dizer que
   decidiu. Uma chave que o dado não respeita faria o script parar sempre.

7. NULOS
   Nenhuma linha é apagada por ter nulo; nenhum nulo é preenchido.
   medalhas_pais e pais não podem ter nulo: se tiverem, para, mostra chave e
   linha e encerra com sys.exit(1).
   Por quê: nos atletas, nulo é falta de coleta na época; em realizado_jogos,
   nulo significa que os jogos aconteceram; em medalha, que o atleta não
   ficou entre os três primeiros. Já um quadro de medalhas ou um país sem
   valor indica uma ingestão quebrada.

8. SAÍDA NA TELA
   Uma linha por tabela:
     refined.bio_atleta         155.861 -> 155.861 linhas  (0 duplicatas)
   Abaixo, indentadas, as colunas com nulo e a contagem. Contagens vêm do
   banco, com milhar separado por ponto. Linha final com o total. stdout
   reconfigurado para utf-8.
   Por quê: essa saída é o instrumento de conferência da etapa, e no Prompt
   de Comando do Windows acento sai embaralhado por padrão.

REEXECUÇÃO
   CREATE OR REPLACE TABLE, dentro de uma única transação. Rodar dez vezes dá
   o mesmo resultado que rodar uma.
   Por quê: é o que permite errar sem medo, e a transação impede um refined
   com metade das tabelas novas e metade antigas.

ERRO
   Antes de transformar, verifica se as seis tabelas existem em raw. Faltando
   qualquer uma: lista quais, manda rodar "uv run python -m pipeline.ingestao"
   e encerra com sys.exit(1).
   Por quê: transformar cinco de seis tabelas em silêncio produz um refined
   errado que parece certo.

ACEITE
   Seis tabelas em refined. Em cada uma, linhas que saem = linhas que entram
   menos duplicatas exatas. Com o dado atual, só resultado_atleta tem
   duplicatas (1.208 linhas idênticas).

FORA DO ESCOPO
   Os testes sugeridos (unicidade, integridade referencial, ouro + prata +
   bronze = total, domínio de medalha, faixas de altura e peso) ficam para
   uma etapa futura.
"""

import re
import sys

import duckdb

from pipeline.db import conectar, criar_schema

ORIGEM = "raw"
DESTINO = "refined"

# Expressões de conversão. {c} é a coluna de origem, já entre aspas.
TEXTO = "{c}"
TRIM = "trim({c})"
INTEIRO = "CAST({c} AS INTEGER)"
DATA = "CAST(strptime({c}, '%Y-%m-%d') AS DATE)"
BOOLEANO = "CAST({c} AS BOOLEAN)"
NA_PARA_NULO = "NULLIF({c}, 'na')"

TEMPORADA = """CASE
    WHEN {c} LIKE '%Summer%' THEN 'Summer'
    WHEN {c} LIKE '%Winter%' THEN 'Winter'
    WHEN {c} LIKE '%Intercalated%' OR {c} LIKE '%Equestrian%' THEN 'Summer'
END"""

# tabela -> [(coluna_raw, coluna_refined, expressão)], na ordem do raw.
COLUNAS = {
    "bio_atleta": [
        ("athlete_id", "id_atleta", INTEIRO),
        ("name", "nome_atleta", TEXTO),
        ("sex", "sexo_atleta", TEXTO),
        ("birth_date", "data_nascimento", DATA),
        ("birth_year", "ano_nascimento", INTEIRO),
        ("height", "altura_atleta", INTEIRO),
        ("weight", "peso_atleta", INTEIRO),
        ("country", "pais_atleta", TRIM),
        ("country_noc", "abrev_pais_atleta", TEXTO),
        ("description", "descricao_atleta", TEXTO),
        ("special_notes", "notas_especiais", TEXTO),
    ],
    "jogos_olimpicos": [
        ("year", "ano_jogos", INTEIRO),
        ("edition", "edicao_jogos", TEXTO),
        ("edition_id", "id_jogos", INTEIRO),
        ("city", "cidade_jogos", TEXTO),
        ("country_flag_url", "url_bandeira", TEXTO),
        ("country_noc", "abrev_pais_jogos", TEXTO),
        ("start_date", "data_inicio_jogos", DATA),
        ("end_date", "data_fim_jogos", DATA),
        ("competition_date", "periodo_competicao", TEXTO),
        ("is_held", "realizado_jogos", TEXTO),
        ("edition", "temporada", TEMPORADA),
    ],
    "medalhas_pais": [
        ("year", "ano", INTEIRO),
        ("edition", "edicao", TEXTO),
        ("edition_id", "edicao_id", INTEIRO),
        ("country", "pais_medalha", TEXTO),
        ("country_noc", "abrev_pais_medalha", TEXTO),
        ("gold", "medalha_ouro", INTEIRO),
        ("silver", "medalha_prata", INTEIRO),
        ("bronze", "medalha_bronze", INTEIRO),
        ("total", "total_medalha", INTEIRO),
        ("edition", "temporada", TEMPORADA),
    ],
    "pais": [
        ("noc", "abrev_pais", TEXTO),
        ("name", "nome_pais", TEXTO),
    ],
    "resultado_atleta": [
        ("edition", "edicao", TEXTO),
        ("edition_id", "edicao_id", INTEIRO),
        ("country_noc", "abrev_pais_atleta", TEXTO),
        ("sport", "sport", TEXTO),
        ("event", "evento", TEXTO),
        ("result_id", "id_resultado", INTEIRO),
        ("athlete", "atleta", TEXTO),
        ("athlete_id", "id_atleta", INTEIRO),
        ("position", "posicao", TEXTO),
        ("medal", "medalha", TEXTO),
        ("is_team_sport", "esporte_coletivo", BOOLEANO),
        ("edition", "temporada", TEMPORADA),
    ],
    "resultados": [
        ("result_id", "id_resultado", INTEIRO),
        ("event_title", "titulo_evento", TEXTO),
        ("edition", "edicao", TEXTO),
        ("edition_id", "id_edicao", INTEIRO),
        ("sport", "esporte", TEXTO),
        ("result_date", "data_resultado", TRIM),
        ("result_location", "local_resultado", TEXTO),
        ("result_participants", "participants", TEXTO),
        ("result_format", "formato_resultado", TEXTO),
        ("result_detail", "detalhe_resultado", NA_PARA_NULO),
        ("result_description", "descricao_resultado", TEXTO),
        ("edition", "temporada", TEMPORADA),
    ],
}

# None = a chave é a linha inteira: só cópias exatas existem como duplicata.
CHAVES = {
    "bio_atleta": ["id_atleta"],
    "jogos_olimpicos": ["id_jogos"],
    "medalhas_pais": ["edicao_id", "pais_medalha"],
    "pais": ["nome_pais", "abrev_pais"],
    "resultado_atleta": None,
    "resultados": ["id_resultado"],
}

SEM_NULOS = {"medalhas_pais", "pais"}


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def q(nome: str) -> str:
    return f'"{nome}"'


def expressao(origem: str, modelo: str) -> str:
    return modelo.format(c=q(origem))


def select_refinado(tabela: str) -> str:
    colunas = ",\n    ".join(
        f"{expressao(origem, modelo)} AS {q(destino)}" for origem, destino, modelo in COLUNAS[tabela]
    )
    return f"SELECT\n    {colunas}\nFROM {ORIGEM}.{q(tabela)}"


def consultar(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple]:
    # fetchall: no DuckDB 2 um resultado não consumido bloqueia a conexão.
    return con.execute(sql).fetchall()


def parar(mensagem: str) -> None:
    print(mensagem)
    sys.exit(1)


def verificar_entrada(con: duckdb.DuckDBPyConnection) -> None:
    existentes = {
        nome
        for (nome,) in consultar(
            con,
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{ORIGEM}'",
        )
    }
    faltando = [t for t in COLUNAS if t not in existentes]
    if faltando:
        print(f"Tabelas faltando no schema {ORIGEM}:")
        for t in faltando:
            print(f"  {t}")
        parar('Rode antes: uv run python -m pipeline.ingestao')


def verificar_conversoes(con: duckdb.DuckDBPyConnection, tabela: str) -> None:
    for origem, destino, modelo in COLUNAS[tabela]:
        if modelo in (TEXTO, TRIM, NA_PARA_NULO):
            continue
        expr = expressao(origem, modelo)
        if modelo == TEMPORADA:
            # A CASE não estoura sozinha: um edition sem temporada reconhecível
            # viraria nulo fabricado. Por isso é checado explicitamente.
            falhas = consultar(
                con,
                f"SELECT {q(origem)} FROM {ORIGEM}.{q(tabela)} "
                f"WHERE {q(origem)} IS NOT NULL AND ({expr}) IS NULL LIMIT 1",
            )
            if falhas:
                parar(
                    f"Conversão falhou: {ORIGEM}.{tabela}.{origem} -> {destino}\n"
                    f"  edição sem temporada reconhecível: {falhas[0][0]!r}"
                )
            continue
        try:
            consultar(con, f"SELECT count({expr}) FROM {ORIGEM}.{q(tabela)}")
        except duckdb.Error as erro:
            # O DuckDB cita o valor que falhou entre aspas simples na mensagem.
            achado = re.search(r"'(.*?)'", str(erro))
            exemplo = repr(achado.group(1)) if achado else str(erro)
            parar(
                f"Conversão falhou: {ORIGEM}.{tabela}.{origem} -> {destino}\n"
                f"  exemplo do valor que não converteu: {exemplo}"
            )


def verificar_chave(con: duckdb.DuckDBPyConnection, tabela: str) -> None:
    chave = CHAVES[tabela]
    if chave is None:
        return
    cols = ", ".join(q(c) for c in chave)
    base = f"WITH t AS ({select_refinado(tabela)}), d AS (SELECT DISTINCT * FROM t)"
    conflitos = consultar(
        con, f"{base} SELECT {cols}, count(*) FROM d GROUP BY ALL HAVING count(*) > 1 ORDER BY ALL"
    )
    if not conflitos:
        return
    print(f"{DESTINO}.{tabela}: {milhar(len(conflitos))} chave(s) ({', '.join(chave)}) com conteúdo diferente.")
    nomes = [destino for _, destino, _ in COLUNAS[tabela]]
    for *valores, _ in conflitos[:5]:
        filtro = " AND ".join(f"{q(c)} IS NOT DISTINCT FROM ?" for c in chave)
        print(f"  chave {dict(zip(chave, valores))}:")
        for linha in con.execute(f"{base} SELECT * FROM d WHERE {filtro}", valores).fetchall():
            print(f"    {dict(zip(nomes, linha))}")
    parar("Nenhuma linha foi escolhida. Resolva o conflito na origem ou revise a chave na spec.")


def verificar_sem_nulos(con: duckdb.DuckDBPyConnection, tabela: str) -> None:
    if tabela not in SEM_NULOS:
        return
    nomes = [destino for _, destino, _ in COLUNAS[tabela]]
    filtro = " OR ".join(f"{q(c)} IS NULL" for c in nomes)
    linhas = consultar(con, f"WITH t AS ({select_refinado(tabela)}) SELECT * FROM t WHERE {filtro}")
    if not linhas:
        return
    print(f"{DESTINO}.{tabela}: {milhar(len(linhas))} linha(s) com nulo, o que esta tabela não admite.")
    for linha in linhas[:5]:
        registro = dict(zip(nomes, linha))
        print(f"  chave {({c: registro[c] for c in CHAVES[tabela]})}: {registro}")
    parar("Verifique a ingestão.")


def gravar(con: duckdb.DuckDBPyConnection, tabela: str) -> tuple[int, int]:
    entrada = consultar(con, f"SELECT count(*) FROM {ORIGEM}.{q(tabela)}")[0][0]
    con.execute(
        f"CREATE OR REPLACE TABLE {DESTINO}.{q(tabela)} AS "
        f"WITH t AS ({select_refinado(tabela)}) SELECT DISTINCT * FROM t"
    )
    saida = consultar(con, f"SELECT count(*) FROM {DESTINO}.{q(tabela)}")[0][0]
    return entrada, saida


def nulos(con: duckdb.DuckDBPyConnection, tabela: str) -> list[tuple[str, int]]:
    nomes = [destino for _, destino, _ in COLUNAS[tabela]]
    contagens = consultar(
        con,
        "SELECT " + ", ".join(f"count(*) - count({q(c)})" for c in nomes) + f" FROM {DESTINO}.{q(tabela)}",
    )[0]
    return [(c, n) for c, n in zip(nomes, contagens) if n]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        verificar_entrada(con)

        # Tudo é verificado antes de qualquer gravação: se algo para, refined
        # continua exatamente como estava.
        for tabela in COLUNAS:
            verificar_conversoes(con, tabela)
            verificar_chave(con, tabela)
            verificar_sem_nulos(con, tabela)

        criar_schema(con, DESTINO)
        con.execute("BEGIN TRANSACTION")
        try:
            resultados = {tabela: gravar(con, tabela) for tabela in COLUNAS}
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise

        total_entrada = total_saida = 0
        for tabela, (entrada, saida) in resultados.items():
            total_entrada += entrada
            total_saida += saida
            print(
                f"{DESTINO}.{tabela:<20} {milhar(entrada):>9} -> {milhar(saida):>9} linhas"
                f"  ({milhar(entrada - saida)} duplicatas)"
            )
            com_nulo = nulos(con, tabela)
            if com_nulo:
                print("    nulos mantidos: " + ", ".join(f"{c} {milhar(n)}" for c, n in com_nulo))
        print(
            f"{'Total':<28} {milhar(total_entrada):>9} -> {milhar(total_saida):>9} linhas"
            f"  ({milhar(total_entrada - total_saida)} duplicatas)"
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
