"""Testes de pipeline/marts.py (itens 1 a 4 e ACEITE) e das regras de
SQL/Marts/01_quadro_medalhas_por_edicao.sql e 03_evolucao_medalhas_pais_ano.sql.

O executor roda sobre uma pasta de .sql escrita pelo teste em tmp_path; os
SQLs do projeto rodam sobre tabelas refined inventadas.
"""

import io
import sys
from pathlib import Path

import duckdb
import pytest

from pipeline import db, marts, transformacao

PASTA_SQL_PROJETO = Path(__file__).resolve().parent.parent / "SQL" / "Marts"


# ---------------------------------------------------------------- apoio do executor

def preparar(tmp_path, monkeypatch, arquivos, refined_completo=True):
    """Banco com refined (tabelas vazias) e pasta de marts com `arquivos`."""
    banco = tmp_path / "olimpiadas.duckdb"
    con = duckdb.connect(str(banco))
    con.execute("CREATE SCHEMA refined")
    tabelas = list(transformacao.COLUNAS)
    if not refined_completo:
        tabelas = tabelas[1:]  # falta a primeira (bio_atleta)
    for tabela in tabelas:
        con.execute(f"CREATE TABLE refined.{tabela} (x INTEGER)")
    con.close()

    pasta = tmp_path / "marts_sql"
    pasta.mkdir()
    for nome, sql in arquivos.items():
        (pasta / nome).write_text(sql, encoding="utf-8")
    monkeypatch.setattr(db, "_RAIZ", tmp_path)
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta)
    return banco, pasta


def capturar_saida(monkeypatch):
    # TextIOWrapper, e não StringIO: main() chama sys.stdout.reconfigure.
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", write_through=True)
    monkeypatch.setattr(sys, "stdout", saida)
    return lambda: saida.buffer.getvalue().decode("utf-8")


def rodar(monkeypatch):
    texto = capturar_saida(monkeypatch)
    marts.main()
    return texto()


def rodar_e_parar(monkeypatch):
    texto = capturar_saida(monkeypatch)
    with pytest.raises(SystemExit) as fim:
        marts.main()
    assert fim.value.code == 1
    return texto()


def tabelas_marts(banco):
    con = duckdb.connect(str(banco), read_only=True)
    try:
        nomes = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts' ORDER BY 1"
        ).fetchall()
        return {n: con.execute(f"SELECT count(*) FROM marts.{n}").fetchall()[0][0] for (n,) in nomes}
    finally:
        con.close()


# ---------------------------------------------------------------- executor

def test_arquivo_com_select_1_vira_tabela_com_uma_linha(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"00_teste.sql": "SELECT 1 AS x"})

    saida = rodar(monkeypatch)

    assert tabelas_marts(banco) == {"teste": 1}
    assert "✓ marts.teste" in saida


def test_ponto_e_virgula_e_espacos_no_final_sao_tolerados(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"01_a.sql": "-- comentário no topo\nSELECT 1 AS x;\n\n  "})

    rodar(monkeypatch)

    assert tabelas_marts(banco) == {"a": 1}


def test_arquivo_apagado_faz_o_mart_sumir_na_execucao_seguinte(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"00_teste.sql": "SELECT 1 AS x", "01_fica.sql": "SELECT 2 AS y"})
    rodar(monkeypatch)

    (pasta / "00_teste.sql").unlink()
    rodar(monkeypatch)

    assert tabelas_marts(banco) == {"fica": 1}


def test_saida_tem_milhar_com_ponto_e_linha_de_total(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch, {"01_grande.sql": "SELECT * FROM range(1234)", "02_um.sql": "SELECT 1 AS x"})

    saida = rodar(monkeypatch)

    assert "1.234 linhas" in saida
    assert saida.strip().splitlines()[-1] == "2 marts, 1.235 linhas no total"


def test_rodar_duas_vezes_imprime_a_mesma_coisa(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch, {"01_a.sql": "SELECT 1 AS x", "02_b.sql": "SELECT * FROM range(5)"})

    assert rodar(monkeypatch) == rodar(monkeypatch)


def test_erro_de_sintaxe_para_mostra_o_arquivo_e_deixa_marts_como_estava(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"01_bom.sql": "SELECT 1 AS x"})
    rodar(monkeypatch)
    antes = tabelas_marts(banco)
    (pasta / "02_quebrado.sql").write_text("SELEC 1", encoding="utf-8")

    saida = rodar_e_parar(monkeypatch)

    assert "02_quebrado.sql" in saida
    assert tabelas_marts(banco) == antes


def test_mart_vazio_encerra_e_deixa_marts_como_estava(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"01_bom.sql": "SELECT 1 AS x"})
    rodar(monkeypatch)
    antes = tabelas_marts(banco)
    # JOIN que não casa: zero linhas
    (pasta / "02_vazio.sql").write_text("SELECT 1 AS x WHERE false", encoding="utf-8")

    saida = rodar_e_parar(monkeypatch)

    assert "marts.vazio" in saida
    assert tabelas_marts(banco) == antes


def test_arquivo_sem_prefixo_para_antes_de_executar_qualquer_sql(tmp_path, monkeypatch):
    # 01_bom.sql seria executado primeiro se a checagem não viesse antes
    banco, _ = preparar(tmp_path, monkeypatch, {"01_bom.sql": "SELECT 1 AS x", "teste.sql": "SELECT 1 AS x"})

    saida = rodar_e_parar(monkeypatch)

    assert "teste.sql" in saida
    assert tabelas_marts(banco) == {}


def test_dois_arquivos_com_o_mesmo_nome_de_tabela_param_antes_de_executar(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"01_igual.sql": "SELECT 1 AS x", "02_igual.sql": "SELECT 2 AS x"})

    saida = rodar_e_parar(monkeypatch)

    assert "01_igual.sql" in saida and "02_igual.sql" in saida
    assert tabelas_marts(banco) == {}


def test_pasta_sem_nenhum_sql_encerra(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch, {})

    saida = rodar_e_parar(monkeypatch)

    assert "Nenhum arquivo .sql" in saida


def test_refined_incompleto_encerra_e_manda_rodar_a_transformacao(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"01_a.sql": "SELECT 1 AS x"}, refined_completo=False)

    saida = rodar_e_parar(monkeypatch)

    assert "bio_atleta" in saida
    assert "uv run python -m pipeline.transformacao" in saida
    assert tabelas_marts(banco) == {}


# ---------------------------------------------------------------- SQL 01 e 03

def executar_sql_do_projeto(tmp_path, arquivo, preparo):
    con = duckdb.connect(str(tmp_path / "sql.duckdb"))
    con.execute("CREATE SCHEMA refined")
    con.execute(preparo)
    try:
        return con.execute((PASTA_SQL_PROJETO / arquivo).read_text(encoding="utf-8")).df()
    finally:
        con.close()


MEDALHAS_PAIS = """
CREATE TABLE refined.medalhas_pais (
    ano INTEGER, edicao VARCHAR, edicao_id INTEGER, pais_medalha VARCHAR,
    abrev_pais_medalha VARCHAR, medalha_ouro INTEGER, medalha_prata INTEGER,
    medalha_bronze INTEGER, total_medalha INTEGER, temporada VARCHAR
);
"""


def quadro_por_edicao(tmp_path):
    preparo = MEDALHAS_PAIS + """
    INSERT INTO refined.medalhas_pais VALUES
        -- menos medalhas, mais ouros: fica à frente de BBB
        (2020, '2020 Summer Olympics', 61, 'Aland',  'AAA', 2, 0, 0,  2, 'Summer'),
        -- mais medalhas no total, um ouro só
        (2020, '2020 Summer Olympics', 61, 'Bland',  'BBB', 1, 5, 5, 11, 'Summer'),
        -- CCC e DDD: empate total em ouro, prata e bronze
        (2020, '2020 Summer Olympics', 61, 'Cland',  'CCC', 1, 1, 1,  3, 'Summer'),
        (2020, '2020 Summer Olympics', 61, 'Dland',  'DDD', 1, 1, 1,  3, 'Summer'),
        -- logo depois do empate: RANK pula uma posição
        (2020, '2020 Summer Olympics', 61, 'Eland',  'EEE', 0, 3, 0,  3, 'Summer'),
        -- 1906: Jogos Intercalados, não reconhecidos pelo COI
        (1906, '1906 Intercalated Games', 5, 'Fland', 'FFF', 9, 9, 9, 27, 'Summer');
    """
    return executar_sql_do_projeto(tmp_path, "01_quadro_medalhas_por_edicao.sql", preparo)


def test_quadro_ordena_por_ouro_antes_do_total(tmp_path):
    df = quadro_por_edicao(tmp_path)
    ranking = dict(zip(df["abrev_pais"], df["ranking_edicao"]))

    assert ranking["AAA"] == 1
    assert ranking["BBB"] == 2


def test_quadro_empate_total_divide_a_posicao_e_a_seguinte_e_pulada(tmp_path):
    df = quadro_por_edicao(tmp_path)
    ranking = dict(zip(df["abrev_pais"], df["ranking_edicao"]))

    assert ranking["CCC"] == ranking["DDD"] == 3
    assert ranking["EEE"] == 5


def test_quadro_deixa_1906_de_fora(tmp_path):
    df = quadro_por_edicao(tmp_path)

    assert "FFF" not in set(df["abrev_pais"])
    assert set(df["ano"]) == {2020}


def evolucao(tmp_path):
    preparo = MEDALHAS_PAIS + """
    CREATE TABLE refined.jogos_olimpicos (id_jogos INTEGER, ano_jogos INTEGER, temporada VARCHAR);
    INSERT INTO refined.jogos_olimpicos VALUES
        (61, 2020, 'Summer'),
        (10, 1956, 'Summer'),  -- Melbourne
        (11, 1956, 'Summer'),  -- provas hípicas em Estocolmo: mesma temporada e ano
        (62, 2022, 'Winter'),
        (5,  1906, 'Summer');  -- Intercalados

    CREATE TABLE refined.resultado_atleta (edicao_id INTEGER, abrev_pais_atleta VARCHAR);
    INSERT INTO refined.resultado_atleta VALUES
        (61, 'BRA'), (61, 'BRA'),  -- dois atletas do Brasil: uma participação só
        (61, 'NEP'),               -- Nepal participou e não ganhou medalha
        (5,  'BRA');               -- participação em 1906: fica de fora

    INSERT INTO refined.medalhas_pais VALUES
        (2020, '2020 Summer Olympics', 61, 'Brazil', 'BRA', 7, 6, 8, 21, 'Summer'),
        (1956, '1956 Summer Olympics', 10, 'Sweden', 'SWE', 1, 0, 0,  1, 'Summer'),
        (1956, '1956 Equestrian',      11, 'Sweden', 'SWE', 2, 1, 0,  3, 'Summer'),
        (1906, '1906 Intercalated Games', 5, 'Brazil', 'BRA', 1, 0, 0, 1, 'Summer');

    -- nome de quem nunca ganhou medalha vem de pais
    CREATE TABLE refined.pais (abrev_pais VARCHAR, nome_pais VARCHAR);
    INSERT INTO refined.pais VALUES ('NEP', 'Nepal'), ('BRA', 'Brazil'), ('SWE', 'Sweden');
    """
    return executar_sql_do_projeto(tmp_path, "03_evolucao_medalhas_pais_ano.sql", preparo)


def linha(df, pais, ano):
    selecao = df[(df["abrev_pais"] == pais) & (df["ano"] == ano)]
    assert len(selecao) == 1
    return selecao.iloc[0]


def test_evolucao_ano_com_participacao_e_sem_medalha_aparece_com_zero(tmp_path):
    nepal = linha(evolucao(tmp_path), "NEP", 2020)

    assert (nepal["ouro"], nepal["prata"], nepal["bronze"], nepal["total"]) == (0, 0, 0, 0)
    assert nepal["nome_pais"] == "Nepal"


def test_evolucao_soma_as_duas_edicoes_de_1956(tmp_path):
    suecia = linha(evolucao(tmp_path), "SWE", 1956)

    assert (suecia["ouro"], suecia["prata"], suecia["total"]) == (3, 1, 4)


def test_evolucao_varios_atletas_nao_multiplicam_as_medalhas_do_pais(tmp_path):
    brasil = linha(evolucao(tmp_path), "BRA", 2020)

    assert brasil["total"] == 21


def test_evolucao_deixa_1906_de_fora_e_nao_inventa_ano_sem_participacao(tmp_path):
    df = evolucao(tmp_path)

    assert 1906 not in set(df["ano"])
    assert df[(df["abrev_pais"] == "BRA") & (df["temporada"] == "Winter")].empty
