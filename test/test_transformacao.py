"""Testes de pipeline/transformacao.py (itens 1 a 8, REEXECUÇÃO e ERRO).

Cada teste monta o schema raw num DuckDB novo em tmp_path, com uma linha
válida por tabela, e troca só o que o caso precisa.
"""

import copy

import duckdb
import pytest

from pipeline import db, transformacao

# Uma linha válida por tabela, com os nomes de coluna do raw.
BASE = {
    "bio_atleta": [
        {
            "athlete_id": "1", "name": "Ana", "sex": "Female", "birth_date": "1990-05-01",
            "birth_year": "1990", "height": "170", "weight": "60",
            "country": " Cuba",  # espaço à esquerda, como vem da fonte
            "country_noc": "CUB", "description": None, "special_notes": None,
        }
    ],
    "jogos_olimpicos": [
        {
            "year": "2020", "edition": "2020 Summer Olympics", "edition_id": "61", "city": "Tokyo",
            "country_flag_url": "x", "country_noc": "JPN", "start_date": "2021-07-23",
            "end_date": "2021-08-08", "competition_date": "23 July – 8 August", "is_held": None,
        },
        {
            # edição sem "Summer" no nome: a spec manda mapear para Verão
            "year": "1906", "edition": "1906 Intercalated Games", "edition_id": "5", "city": "Athina",
            "country_flag_url": "x", "country_noc": "GRE", "start_date": None,
            "end_date": None, "competition_date": None, "is_held": None,
        },
    ],
    "medalhas_pais": [
        {
            "year": "2020", "edition": "2020 Summer Olympics", "edition_id": "61", "country": "Cuba",
            "country_noc": "CUB", "gold": "7", "silver": "3", "bronze": "5", "total": "15",
        }
    ],
    "pais": [{"noc": "CUB", "name": "Cuba"}],
    "resultado_atleta": [
        {
            "edition": "2020 Summer Olympics", "edition_id": "61", "country_noc": "CUB", "sport": "Boxing",
            "event": "Flyweight", "result_id": "100", "athlete": "Ana", "athlete_id": "1",
            "position": "=9",  # empate: tem que continuar texto
            "medal": None, "is_team_sport": "False",
        }
    ],
    "resultados": [
        {
            "result_id": "100", "event_title": "Flyweight", "edition": "2020 Summer Olympics",
            "edition_id": "61", "sport": "Boxing",
            "result_date": " 2 October 1900",  # espaço à esquerda, como vem da fonte
            "result_location": "Tokyo", "result_participants": "10", "result_format": "x",
            "result_detail": "na",  # nulo disfarçado de texto
            "result_description": None,
        }
    ],
}


def preparar(tmp_path, monkeypatch, alterar=None, sem=()):
    """Cria raw em tmp_path/olimpiadas.duckdb. alterar(tabelas) muda as linhas antes."""
    tabelas = copy.deepcopy(BASE)
    if alterar:
        alterar(tabelas)
    banco = tmp_path / "olimpiadas.duckdb"
    con = duckdb.connect(str(banco))
    con.execute("CREATE SCHEMA raw")
    for tabela, linhas in tabelas.items():
        if tabela in sem:
            continue
        colunas = list(linhas[0])
        definicao = ", ".join(f'"{c}" VARCHAR' for c in colunas)  # aspas: "position" é palavra reservada
        con.execute(f"CREATE TABLE raw.{tabela} ({definicao})")
        con.executemany(
            f"INSERT INTO raw.{tabela} VALUES ({', '.join('?' * len(colunas))})",
            [[linha[c] for c in colunas] for linha in linhas],
        )
    con.close()
    monkeypatch.setattr(db, "_RAIZ", tmp_path)
    return banco


def consultar(banco, sql):
    con = duckdb.connect(str(banco), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def existe_refined(banco, tabela):
    sql = f"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'refined' AND table_name = '{tabela}'"
    return consultar(banco, sql) == [(1,)]


def test_cria_as_seis_tabelas_em_refined(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    transformacao.main()

    for tabela in transformacao.COLUNAS:
        assert existe_refined(banco, tabela)


def test_duplicata_exata_sai_e_as_demais_linhas_ficam(tmp_path, monkeypatch):
    def duplicar(t):
        t["resultado_atleta"].append(dict(t["resultado_atleta"][0]))  # cópia exata da primeira

    banco = preparar(tmp_path, monkeypatch, duplicar)

    transformacao.main()

    assert consultar(banco, "SELECT count(*) FROM raw.resultado_atleta") == [(2,)]
    assert consultar(banco, "SELECT count(*) FROM refined.resultado_atleta") == [(1,)]


def test_mesmo_atleta_no_mesmo_resultado_por_outro_pais_nao_e_duplicata(tmp_path, monkeypatch):
    def outro_pais(t):
        linha = dict(t["resultado_atleta"][0])
        linha["country_noc"] = "MEX"  # mesmo atleta e resultado, país diferente: fica
        t["resultado_atleta"].append(linha)

    banco = preparar(tmp_path, monkeypatch, outro_pais)

    transformacao.main()

    assert consultar(banco, "SELECT count(*) FROM refined.resultado_atleta") == [(2,)]


def test_datas_viram_date(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    transformacao.main()

    tipos = dict(
        consultar(
            banco,
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'refined' AND column_name IN ('data_nascimento', 'data_inicio_jogos', 'data_fim_jogos')",
        )
    )
    assert tipos == {"data_nascimento": "DATE", "data_inicio_jogos": "DATE", "data_fim_jogos": "DATE"}
    assert str(consultar(banco, "SELECT data_nascimento FROM refined.bio_atleta")[0][0]) == "1990-05-01"


def test_data_que_nao_converte_encerra_sem_virar_nulo(tmp_path, monkeypatch):
    def data_errada(t):
        t["bio_atleta"][0]["birth_date"] = "01/05/1990"  # formato fora do declarado

    banco = preparar(tmp_path, monkeypatch, data_errada)

    with pytest.raises(SystemExit) as saida:
        transformacao.main()

    assert saida.value.code == 1
    assert not existe_refined(banco, "bio_atleta")


def test_inteiro_que_nao_converte_encerra_sem_gravar_nada(tmp_path, monkeypatch):
    def altura_com_unidade(t):
        t["bio_atleta"][0]["height"] = "170cm"

    banco = preparar(tmp_path, monkeypatch, altura_com_unidade)

    with pytest.raises(SystemExit):
        transformacao.main()

    for tabela in transformacao.COLUNAS:
        assert not existe_refined(banco, tabela)


def test_edicao_sem_temporada_reconhecivel_encerra(tmp_path, monkeypatch):
    def edicao_estranha(t):
        t["jogos_olimpicos"][0]["edition"] = "2020 Jogos Misteriosos"

    preparar(tmp_path, monkeypatch, edicao_estranha)

    with pytest.raises(SystemExit):
        transformacao.main()


def test_temporada_sai_da_edicao_e_1906_e_verao(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    transformacao.main()

    assert consultar(banco, "SELECT ano_jogos, temporada FROM refined.jogos_olimpicos ORDER BY ano_jogos") == [
        (1906, "Summer"),
        (2020, "Summer"),
    ]


def test_espaco_a_esquerda_sai_e_na_vira_nulo(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    transformacao.main()

    assert consultar(banco, "SELECT pais_atleta FROM refined.bio_atleta") == [("Cuba",)]
    assert consultar(banco, "SELECT data_resultado, detalhe_resultado FROM refined.resultados") == [
        ("2 October 1900", None)
    ]


def test_posicao_continua_texto(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    transformacao.main()

    assert consultar(banco, "SELECT posicao FROM refined.resultado_atleta") == [("=9",)]


def test_chave_repetida_com_conteudo_diferente_encerra(tmp_path, monkeypatch):
    def mesmo_id_outro_nome(t):
        linha = dict(t["bio_atleta"][0])
        linha["name"] = "Ana Maria"  # mesmo athlete_id, conteúdo diferente
        t["bio_atleta"].append(linha)

    banco = preparar(tmp_path, monkeypatch, mesmo_id_outro_nome)

    with pytest.raises(SystemExit):
        transformacao.main()

    assert not existe_refined(banco, "bio_atleta")


def test_nulo_em_medalhas_pais_encerra(tmp_path, monkeypatch):
    def sem_ouro(t):
        t["medalhas_pais"][0]["gold"] = None  # quadro de medalhas não admite nulo

    preparar(tmp_path, monkeypatch, sem_ouro)

    with pytest.raises(SystemExit):
        transformacao.main()


def test_tabela_faltando_em_raw_encerra(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch, sem=["pais"])

    with pytest.raises(SystemExit) as saida:
        transformacao.main()

    assert saida.value.code == 1


def test_rodar_duas_vezes_da_o_mesmo_resultado(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch)

    transformacao.main()
    primeira = consultar(banco, "SELECT * FROM refined.bio_atleta")
    transformacao.main()
    segunda = consultar(banco, "SELECT * FROM refined.bio_atleta")

    assert primeira == segunda
    assert len(segunda) == 1
