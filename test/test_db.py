"""Testes de pipeline/db.py (spec D1 a D4 na docstring do módulo)."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from pipeline import db


def test_conectar_cria_o_banco_na_raiz_do_projeto_e_nao_no_diretorio_corrente(tmp_path, monkeypatch):
    raiz = tmp_path / "projeto"
    outra_pasta = tmp_path / "outra"
    raiz.mkdir()
    outra_pasta.mkdir()
    monkeypatch.setattr(db, "_RAIZ", raiz)
    monkeypatch.chdir(outra_pasta)

    db.conectar().close()

    assert (raiz / "olimpiadas.duckdb").is_file()
    assert not (outra_pasta / "olimpiadas.duckdb").exists()


def test_pasta_raw_e_resolvida_a_partir_do_arquivo_do_modulo():
    esperado = Path(db.__file__).resolve().parent.parent / "data" / "raw"
    assert db.PASTA_RAW == esperado


def test_criar_schema_duas_vezes_nao_falha(tmp_path):
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    db.criar_schema(con, "raw")
    db.criar_schema(con, "raw")
    schemas = con.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'raw'").fetchall()
    con.close()
    assert schemas == [("raw",)]


def test_gravar_devolve_a_contagem_lida_do_banco_e_mantem_nulo_e_texto(tmp_path):
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    db.criar_schema(con, "raw")
    df = pd.DataFrame(
        {
            "codigo": ["007", "1"],  # zero à esquerda: tem que continuar texto
            "nome": ["Ana", None],  # nulo: tem que continuar NULL, não "None"
        },
        dtype="str",
    )

    n = db.gravar(con, df, "raw", "pessoas")

    tipos = dict(con.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'pessoas'").fetchall())
    linhas = con.execute("SELECT codigo, nome FROM raw.pessoas ORDER BY codigo").fetchall()
    con.close()
    assert n == 2
    assert tipos == {"codigo": "VARCHAR", "nome": "VARCHAR"}
    assert linhas == [("007", "Ana"), ("1", None)]


def test_gravar_de_novo_recria_a_tabela_em_vez_de_acrescentar(tmp_path):
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    db.criar_schema(con, "raw")
    db.gravar(con, pd.DataFrame({"a": ["1", "2", "3"]}), "raw", "t")

    n = db.gravar(con, pd.DataFrame({"a": ["9"]}), "raw", "t")

    con.close()
    assert n == 1


def test_gravar_nao_deixa_a_view_temporaria_para_tras_nem_quando_falha(tmp_path):
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    df = pd.DataFrame({"a": ["1"]})

    # schema inexistente: o CREATE falha
    with pytest.raises(duckdb.CatalogException):
        db.gravar(con, df, "schema_que_nao_existe", "t")

    with pytest.raises(duckdb.CatalogException):
        con.execute("SELECT * FROM _gravar_df")
    con.close()
