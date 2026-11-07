"""Etapa 3: criação do schema marts a partir dos arquivos SQL/Marts/*.sql.

Execução:
    uv run python -m pipeline.marts

1. ESCOPO
   Lê de refined, escreve no schema marts. Nunca escreve em raw nem em
   refined. O schema marts é apagado e recriado a cada execução
   (DROP SCHEMA IF EXISTS marts CASCADE).
   Por quê: um mart cujo arquivo foi apagado não pode continuar existindo no
   banco.

2. UM ARQUIVO, UMA TABELA
   Lê todos os SQL/Marts/*.sql em ordem alfabética.
   Nome da tabela = nome do arquivo sem a extensão e sem o prefixo numérico:
     SQL/Marts/04_atletas_mais_medalhados.sql -> marts.atletas_mais_medalhados
   Executa: CREATE TABLE marts.<nome> AS <conteúdo do arquivo>
   Tira espaços e um ponto e vírgula do final do conteúdo, e nada mais.
   O Python não altera, não monta e não completa a SQL.
   Por quê: a regra de negócio mora inteira no arquivo .sql.

3. SAÍDA NA TELA
   Uma linha por mart, com a contagem vinda do banco, milhar com ponto:
     ✓ marts.atletas_mais_medalhados        12.345 linhas
   Linha final com o número de marts e o total de linhas.
   stdout reconfigurado para utf-8.
   Por quê: a contagem lida do banco é a do que foi gravado; no Prompt de
   Comando do Windows o ✓ e os acentos saem embaralhados sem utf-8.

4. ERRO
   - Antes de tudo: se faltar qualquer uma das seis tabelas em refined,
     lista quais, diz para rodar "uv run python -m pipeline.transformacao"
     e encerra com sys.exit(1).
     Por quê: um mart sobre um refined incompleto falha com uma mensagem
     que não aponta a causa.
   - Se SQL/Marts/ não tiver nenhum arquivo: avisa e sys.exit(1).
     Por quê: apagar todos os marts em silêncio parece uma execução que
     deu certo.
   - Antes de executar qualquer SQL: arquivo sem prefixo NN_ ou dois
     arquivos que dão o mesmo nome de tabela -> lista quais e sys.exit(1).
     Por quê: sem prefixo a ordem não é controlada; dois arquivos com o
     mesmo nome fariam um sobrescrever o outro.
   - Se um .sql falhar: mostra o nome do arquivo e a mensagem do DuckDB,
     não executa os seguintes, sys.exit(1).
     Por quê: o nome do arquivo é o que se precisa para corrigir.
   - Se um mart voltar com zero linhas: mostra o nome e encerra com
     sys.exit(1).
     Por quê: mart vazio é quase sempre um JOIN que não casou, e um
     dashboard vazio parece um negócio parado.
   - Tudo roda numa transação só: se qualquer passo falhar (inclusive o
     mart vazio), o schema marts volta a ser o da última execução que deu
     certo.
     Por quê: um schema pela metade quebra o dashboard sem avisar.

ACEITE
   - Com SQL/Marts/00_teste.sql contendo "SELECT 1 AS x", cria marts.teste
     com 1 linha.
   - Apagar o arquivo e rodar de novo faz marts.teste desaparecer.
   - Um arquivo com erro de sintaxe para tudo, com o nome do arquivo na
     tela, e marts continua exatamente como estava antes da execução.
   - Um arquivo teste.sql, sem prefixo, para antes de executar qualquer SQL.
   - Rodar duas vezes seguidas imprime exatamente a mesma coisa.
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline.db import conectar, criar_schema
from pipeline.transformacao import COLUNAS

ORIGEM = "refined"
DESTINO = "marts"

# Resolvida a partir deste arquivo, como em db.py: rodar de outra pasta não
# pode fazer o script achar a pasta vazia e parar por engano.
PASTA_MARTS = Path(__file__).resolve().parent.parent / "SQL" / "Marts"

# NN_ = exatamente dois dígitos e um sublinhado; o resto é o nome da tabela.
PADRAO_ARQUIVO = re.compile(r"^\d{2}_(.+)\.sql$")


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def parar(mensagem: str) -> None:
    print(mensagem)
    sys.exit(1)


def verificar_refined(con: duckdb.DuckDBPyConnection) -> None:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", [ORIGEM]
        ).fetchall()
    }
    faltando = [t for t in COLUNAS if t not in existentes]
    if faltando:
        print(f"Tabelas faltando no schema {ORIGEM}:")
        for t in faltando:
            print(f"  {t}")
        parar("Rode antes: uv run python -m pipeline.transformacao")


def listar_marts() -> list[tuple[Path, str]]:
    """Devolve [(arquivo, nome_da_tabela)] em ordem alfabética, ou para."""
    arquivos = sorted(PASTA_MARTS.glob("*.sql"), key=lambda p: p.name)
    if not arquivos:
        parar(f"Nenhum arquivo .sql em {PASTA_MARTS}. Nada foi alterado.")

    sem_prefixo = [a.name for a in arquivos if not PADRAO_ARQUIVO.match(a.name)]
    if sem_prefixo:
        print("Arquivos sem o prefixo NN_ (ex.: 01_nome.sql):")
        for nome in sem_prefixo:
            print(f"  {nome}")
        parar("Nenhuma SQL foi executada.")

    por_nome: dict[str, list[str]] = {}
    for a in arquivos:
        por_nome.setdefault(PADRAO_ARQUIVO.match(a.name).group(1), []).append(a.name)
    repetidos = {nome: lista for nome, lista in por_nome.items() if len(lista) > 1}
    if repetidos:
        print("Arquivos que dão o mesmo nome de tabela:")
        for nome, lista in repetidos.items():
            print(f"  {DESTINO}.{nome}: {', '.join(lista)}")
        parar("Nenhuma SQL foi executada.")

    return [(a, PADRAO_ARQUIVO.match(a.name).group(1)) for a in arquivos]


def ler_sql(arquivo: Path) -> str:
    sql = arquivo.read_text(encoding="utf-8").rstrip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    return sql


def criar_marts(con: duckdb.DuckDBPyConnection, marts: list[tuple[Path, str]]) -> list[tuple[str, int]]:
    """Recria o schema marts numa transação; em qualquer falha, desfaz e para."""
    contagens: list[tuple[str, int]] = []
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f'DROP SCHEMA IF EXISTS "{DESTINO}" CASCADE')
        criar_schema(con, DESTINO)
        for arquivo, nome in marts:
            # A quebra de linha depois de AS impede que um comentário (--) na
            # primeira linha do arquivo engula o resto do comando.
            try:
                con.execute(f'CREATE TABLE "{DESTINO}"."{nome}" AS\n{ler_sql(arquivo)}')
            except duckdb.Error as erro:
                con.execute("ROLLBACK")
                parar(f"✗ {arquivo.name} falhou:\n{erro}\n\nO schema {DESTINO} não foi alterado.")
            linhas = con.execute(f'SELECT count(*) FROM "{DESTINO}"."{nome}"').fetchall()[0][0]
            if linhas == 0:
                con.execute("ROLLBACK")
                parar(
                    f"✗ {DESTINO}.{nome} ({arquivo.name}) voltou com zero linhas.\n"
                    f"O schema {DESTINO} não foi alterado."
                )
            contagens.append((nome, linhas))
        con.execute("COMMIT")
    except SystemExit:
        raise
    except BaseException:
        # Qualquer outra interrupção (Ctrl+C, erro inesperado) também desfaz.
        con.execute("ROLLBACK")
        raise
    return contagens


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        verificar_refined(con)
        marts = listar_marts()
        contagens = criar_marts(con, marts)
    finally:
        con.close()

    # Impresso só depois do COMMIT: um ✓ na tela significa mart gravado.
    largura_nome = max(len(f"{DESTINO}.{nome}") for nome, _ in contagens)
    largura_num = max(len(milhar(n)) for _, n in contagens)
    for nome, linhas in contagens:
        print(f"✓ {f'{DESTINO}.{nome}':<{largura_nome}}  {milhar(linhas):>{largura_num}} linhas")
    total = sum(n for _, n in contagens)
    print(f"{len(contagens)} marts, {milhar(total)} linhas no total")


if __name__ == "__main__":
    main()
