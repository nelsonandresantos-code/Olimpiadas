"""Explorar o olist.duckdb pelo navegador com a extensão ui do DuckDB.

Execução:
    uv run python ui.py

U1. O QUE FAZ
    Abre o olist.duckdb da raiz do projeto, instala e carrega a extensão ui
    (INSTALL ui; LOAD ui;) e chama CALL start_ui(), que sobe o servidor em
    http://localhost:4213 e abre o navegador.
    Por quê: ler tabela no terminal não serve para explorar o banco.

U2. FICA DE PÉ ATÉ CTRL+C
    A extensão serve enquanto a conexão estiver viva. O script mantém o
    processo rodando, imprime a URL e a instrução "Ctrl+C para encerrar", e
    no Ctrl+C fecha a conexão e sai limpo, sem traceback.
    Por quê: o arquivo .duckdb aceita um único processo escrevendo. Com este
    script de pé, a ingestão falha com "Could not set lock on file". Saber
    exatamente como desligar o servidor faz parte da ferramenta.

U3. NÃO CRIA BANCO
    Se olist.duckdb não existir, avisa que é preciso rodar a ingestão antes
    e encerra com sys.exit(1). Por isso não usa conectar() de pipeline/db.py,
    que cria o arquivo quando ele falta.
    Por quê: um banco vazio aberto no navegador parece ingestão quebrada.

U4. SEPARAÇÃO
    ui.py não importa pipeline/ingestao.py, e a ingestão não importa ui.py.
    Por quê: a ingestão não sobe servidor, não abre navegador e não depende
    da extensão ui para rodar.

U5. SAÍDA NA TELA
    stdout reconfigurado para utf-8.
    Por quê: no Prompt de Comando do Windows acento sai embaralhado por
    padrão.
"""

import sys
import time
from pathlib import Path

import duckdb

# Mesmo critério do D1 de pipeline/db.py: caminho relativo a este arquivo,
# nunca ao diretório corrente.
BANCO = Path(__file__).resolve().parent / "olist.duckdb"
URL = "http://localhost:4213"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if not BANCO.is_file():
        print(f"Banco não encontrado: {BANCO}")
        print("Rode a ingestão antes: uv run python -m pipeline.ingestao")
        sys.exit(1)

    con = duckdb.connect(str(BANCO))
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print(f"DuckDB UI em {URL}")
        print("Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
