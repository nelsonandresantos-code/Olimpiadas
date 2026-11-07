"""Testes de pipeline/ingestao.py (itens 1 a 7 da docstring do módulo).

Os seis .csv.gz são escritos pelo próprio teste em tmp_path; PASTA_RAW e a
raiz do banco são redirecionadas para lá.
"""

import gzip

import duckdb
import pytest

from pipeline import db, ingestao

# Conteúdo mínimo dos seis arquivos. bio_atleta concentra os casos da regra.
CSVS = {
    "world_olympedia_olympics_athlete_bio.csv.gz": (
        "athlete_id,name,country,birth_date\n"
        "007,Ana,São Paulo,1990-01-01\n"  # zero à esquerda e acento: têm que chegar intactos
        "2,NA,Brasil,\n"  # nome "NA" é texto; data vazia vira nulo
        "2,NA,Brasil,\n"  # linha repetida: a ingestão não deduplica
    ),
    "world_olympedia_olympics_athlete_event_result.csv.gz": "edition,athlete_id\n2020 Summer Olympics,1\n",
    "world_olympedia_olympics_country.csv.gz": "noc,country\nBRA,Brazil\n",
    "world_olympedia_olympics_game.csv.gz": "edition,year\n2020 Summer Olympics,2020\n",
    "world_olympedia_olympics_game_medal_tally.csv.gz": "edition,gold\n2020 Summer Olympics,7\n",
    "world_olympedia_olympics_result.csv.gz": "result_id,event_title\n1,Final\n",
}


def preparar(tmp_path, monkeypatch, sem=()):
    pasta = tmp_path / "raw_csv"
    pasta.mkdir()
    for nome, texto in CSVS.items():
        if nome in sem:
            continue
        with gzip.open(pasta / nome, "wt", encoding="utf-8", newline="") as f:
            f.write(texto)
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta)
    monkeypatch.setattr(db, "_RAIZ", tmp_path)
    return tmp_path / "olimpiadas.duckdb"


def consultar(banco, sql):
    con = duckdb.connect(str(banco), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_cada_csv_vira_uma_tabela_com_as_mesmas_linhas(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    ingestao.main()

    assert consultar(banco, "SELECT count(*) FROM raw.bio_atleta") == [(3,)]
    for tabela in ["resultado_atleta", "pais", "jogos_olimpicos", "medalhas_pais", "resultados"]:
        assert consultar(banco, f"SELECT count(*) FROM raw.{tabela}") == [(1,)]


def test_linha_repetida_nao_e_descartada(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    ingestao.main()

    assert consultar(banco, "SELECT count(*) FROM raw.bio_atleta WHERE athlete_id = '2'") == [(2,)]


def test_toda_coluna_entra_como_texto(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    ingestao.main()

    tipos = consultar(banco, "SELECT DISTINCT data_type FROM information_schema.columns WHERE table_schema = 'raw'")
    assert tipos == [("VARCHAR",)]


def test_zero_a_esquerda_acento_e_texto_na_chegam_como_vieram(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    ingestao.main()

    linhas = consultar(banco, "SELECT athlete_id, name, country FROM raw.bio_atleta ORDER BY athlete_id LIMIT 2")
    assert linhas == [("007", "Ana", "São Paulo"), ("2", "NA", "Brasil")]


def test_campo_vazio_vira_nulo_e_nao_string_vazia(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    ingestao.main()

    assert consultar(banco, "SELECT count(*) FROM raw.bio_atleta WHERE birth_date IS NULL") == [(2,)]
    assert consultar(banco, "SELECT count(*) FROM raw.bio_atleta WHERE birth_date = ''") == [(0,)]


def test_rodar_duas_vezes_recria_as_tabelas_sem_acrescentar(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    ingestao.main()
    ingestao.main()

    assert consultar(banco, "SELECT count(*) FROM raw.bio_atleta") == [(3,)]


def test_arquivo_faltando_encerra_sem_criar_o_banco(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch, sem=["world_olympedia_olympics_country.csv.gz"])

    with pytest.raises(SystemExit) as saida:
        ingestao.main()

    assert saida.value.code == 1
    assert not banco.exists()
