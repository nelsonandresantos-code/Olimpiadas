"""Testes de painel.py (itens 1, 2, 4, 5, 6 e 7 da spec do dashboard).

Os DataFrames são inventados aqui, com as colunas dos marts; ler() roda
sobre um DuckDB em tmp_path, nunca sobre olimpiadas.duckdb.
"""

import math

import duckdb
import pandas as pd
import pytest

import painel

# ---------------------------------------------------------------- formato


def test_numero_usa_ponto_no_milhar_e_virgula_no_decimal():
    assert painel.numero(96470) == "96.470"
    assert painel.numero(1234567.891, 2) == "1.234.567,89"
    assert painel.numero(0.0665, 2) == "0,07"


def test_numero_negativo_mantem_o_sinal():
    assert painel.numero(-1234) == "-1.234"


def test_numero_vazio_vira_travessao():
    assert painel.numero(None) == "–"
    assert painel.numero(math.nan) == "–"


def test_pct_recebe_valor_na_escala_0_a_100():
    assert painel.pct(93.2) == "93,2%"
    assert painel.pct(47.84) == "47,8%"
    assert painel.pct(50, 0) == "50%"


def test_pct_vazio_vira_travessao():
    assert painel.pct(None) == "–"


# ---------------------------------------------------------------- leitura


def criar_banco(caminho, marts_existentes):
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    for nome in marts_existentes:
        con.execute(f"CREATE TABLE marts.{nome} AS SELECT * FROM range(3) t(x)")
    con.close()


def test_ler_devolve_um_dataframe_por_mart(tmp_path, monkeypatch):
    banco = tmp_path / "olimpiadas.duckdb"
    criar_banco(banco, ["a", "b"])
    monkeypatch.setattr(painel, "BANCO", banco)

    dados = painel.ler(["a", "b"])

    assert set(dados) == {"a", "b"}
    assert len(dados["a"]) == 3


def test_ler_fecha_a_conexao_e_libera_o_banco_para_escrita(tmp_path, monkeypatch):
    banco = tmp_path / "olimpiadas.duckdb"
    criar_banco(banco, ["a"])
    monkeypatch.setattr(painel, "BANCO", banco)

    painel.ler(["a"])

    # Com uma conexão read_only ainda aberta, o DuckDB recusaria abrir esta
    # para escrita ("different configuration").
    con = duckdb.connect(str(banco))
    con.execute("DROP TABLE marts.a")
    restantes = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'marts'").fetchall()
    con.close()
    assert restantes == [(0,)]


def test_ler_sem_banco_avisa_e_nao_cria_o_arquivo(tmp_path, monkeypatch):
    banco = tmp_path / "olimpiadas.duckdb"
    monkeypatch.setattr(painel, "BANCO", banco)

    with pytest.raises(painel.DadosIndisponiveis) as erro:
        painel.ler(["a"])

    assert erro.value.banco_ausente
    assert painel.COMANDO_MARTS in str(erro.value)
    assert not banco.exists()


def test_ler_lista_todos_os_marts_que_faltam(tmp_path, monkeypatch):
    banco = tmp_path / "olimpiadas.duckdb"
    criar_banco(banco, ["a"])
    monkeypatch.setattr(painel, "BANCO", banco)

    with pytest.raises(painel.DadosIndisponiveis) as erro:
        painel.ler(["a", "b", "c"])

    assert erro.value.faltando == ["b", "c"]
    assert "b, c" in str(erro.value)


# ---------------------------------------------------------------- dados inventados


def quadro_edicao():
    linhas = [
        # (edicao_id, ano, temporada, edicao, ranking, abrev, ouro, prata, bronze)
        *[(61, 2020, "Summer", "2020 Summer Olympics", r, f"P{r:02d}", 20 - r, 1, 1) for r in range(1, 12)],  # 11 países
        (61, 2020, "Summer", "2020 Summer Olympics", 12, "BRA", 7, 6, 8),  # Brasil fora do top 10
        (57, 2016, "Summer", "2016 Summer Olympics", 1, "USA", 46, 37, 38),  # edição anterior
        (31, 1956, "Summer", "1956 Equestrian", 1, "SWE", 3, 0, 2),  # edição de hipismo
        (62, 2022, "Winter", "2022 Winter Olympics", 1, "NOR", 16, 8, 13),  # Brasil sem medalha
    ]
    df = pd.DataFrame(
        linhas, columns=["edicao_id", "ano", "temporada", "edicao", "ranking_edicao", "abrev_pais", "ouro", "prata", "bronze"]
    )
    df["nome_pais"] = df["abrev_pais"]
    df["total"] = df["ouro"] + df["prata"] + df["bronze"]
    return df


def eficiencia():
    return pd.DataFrame(
        [
            # (edicao_id, abrev, nome, atletas, total, medalhas_por_atleta)
            (61, "BRA", "Brazil", 316, 21, 0.0665),
            (61, "JAM", "Jamaica", 58, 9, 0.155),
            (61, "SMR", "San Marino", 5, 3, 0.6),  # delegação minúscula: some com mínimo 20
            (61, "AUT", "Austria", 75, 7, 0.093),
            (61, "AUS", "Australia", 477, 46, 0.096),
            (62, "BRA", "Brazil", 10, 0, 0.0),  # participou do inverno sem medalha
        ],
        columns=["edicao_id", "abrev_pais", "nome_pais", "atletas", "total", "medalhas_por_atleta"],
    )


def participacao():
    return pd.DataFrame(
        [("Summer", 2016, 45.0, 5000, 6100), ("Summer", 2020, 47.84, 5539, 6040), ("Winter", 2022, 44.8, 1277, 1571)],
        columns=["temporada", "ano", "percentual_mulheres", "mulheres", "homens"],
    )


def dados():
    return {
        "quadro_medalhas_por_edicao": quadro_edicao(),
        "eficiencia_conversao_pais_edicao": eficiencia(),
        "participacao_feminina_edicao": participacao(),
    }


# ---------------------------------------------------------------- filtros e cards


def test_edicoes_vem_da_mais_recente_para_a_mais_antiga_com_rotulo_em_portugues():
    edicoes = painel.opcoes_edicao(quadro_edicao(), "Summer")

    assert list(edicoes.values()) == ["2020 · Verão", "2016 · Verão", "1956 · Verão (hipismo)"]


def test_paises_em_ordem_alfabetica_do_nome_em_portugues_ignorando_acento():
    paises = painel.opcoes_pais(eficiencia())

    # Austrália, Áustria, Brasil, Jamaica, San Marino
    assert list(paises) == ["AUS", "AUT", "BRA", "JAM", "SMR"]
    assert paises["BRA"] == "Brasil"


def test_cards_do_brasil_em_2020():
    cards = painel.cards(dados(), 61, "BRA")

    assert [c.valor for c in cards] == ["12º", "21", "0,07", "47,8%"]
    assert cards[1].detalhe == "7 ouros · 6 pratas · 8 bronzes"


def test_cards_pais_sem_medalha_na_edicao_mostra_aviso():
    cards = painel.cards(dados(), 62, "BRA")

    assert cards[0].valor == cards[1].valor == "Sem medalhas nesta edição"
    assert cards[2].valor == "0,00"


def test_cards_pais_que_nao_participou():
    cards = painel.cards(dados(), 62, "JAM")

    assert cards[2].valor == "Não participou"


# ---------------------------------------------------------------- recortes


def test_quadro_da_edicao_tem_top_10_e_o_pais_selecionado_no_fim():
    recorte = painel.recorte_quadro_edicao(quadro_edicao(), 61, "BRA")

    assert list(recorte["ranking_edicao"]) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]
    assert recorte.iloc[-1]["abrev_pais"] == "BRA"
    assert recorte.iloc[-1]["fora_do_topo"]


def test_quadro_da_edicao_nao_repete_pais_que_ja_esta_no_top_10():
    recorte = painel.recorte_quadro_edicao(quadro_edicao(), 61, "P03")

    assert len(recorte) == 10


def test_eficiencia_respeita_o_minimo_de_atletas_e_ordena_pela_razao():
    recorte = painel.recorte_eficiencia(eficiencia(), 61, 20)

    assert list(recorte["abrev_pais"]) == ["JAM", "AUS", "AUT", "BRA"]


def test_atletas_posicao_recalculada_dentro_da_temporada_com_empate():
    atletas = pd.DataFrame(
        [
            ("Ana", "BRA", "Swimming", "Summer", 3, 0, 0),
            ("Bia", "USA", "Athletics", "Summer, Winter", 2, 1, 0),  # vale nas duas temporadas
            ("Caio", "GDR, GER", "Rowing", "Summer", 2, 1, 0),  # empate total com Bia
            ("Davi", "NOR", "Biathlon", "Winter", 9, 0, 0),  # só inverno: fora do filtro de verão
            ("Eva", "FRA", "Fencing", "Summer", 1, 0, 0),
        ],
        columns=["nome_atleta", "paises", "esportes", "temporadas", "ouro", "prata", "bronze"],
    )
    atletas["total"] = atletas["ouro"] + atletas["prata"] + atletas["bronze"]

    recorte = painel.recorte_atletas(atletas, "Summer")

    assert list(zip(recorte["nome_atleta"], recorte["posicao"])) == [("Ana", 1), ("Bia", 2), ("Caio", 2), ("Eva", 4)]
    assert recorte.set_index("nome_atleta").loc["Caio", "paises_pt"] == "Alemanha Oriental, Alemanha"


def test_especialidade_outros_completa_100_e_pais_sem_medalha_fica_vazio():
    historico = pd.DataFrame(
        [("Summer", 1, "USA"), ("Summer", 2, "KEN")], columns=["temporada", "ranking_geral", "abrev_pais"]
    )
    especialidade = pd.DataFrame(
        [
            ("USA", "Swimming", 40, 40.0),
            ("USA", "Athletics", 30, 30.0),
            ("USA", "Rowing", 30, 30.0),
            ("KEN", "Athletics", 96, 96.0),
            ("KEN", "Boxing", 4, 4.0),
        ],
        columns=["abrev_pais", "esporte", "total", "percentual_do_pais"],
    )

    matriz = painel.matriz_especialidade(especialidade, historico, "Summer", "NEP")  # Nepal: nenhuma medalha

    assert list(matriz.index) == ["Nepal", "Estados Unidos", "Quênia"]
    assert list(matriz.columns) == ["Atletismo", "Natação", "Remo", "Boxe", "Outros"]
    assert matriz.loc["Estados Unidos", "Outros"] == 0
    assert matriz.loc["Quênia", "Outros"] == 0
    assert matriz.loc["Nepal"].isna().all()


# ---------------------------------------------------------------- gráficos: um ponto por linha


def test_grafico_historico_tem_uma_barra_por_pais_em_cada_medalha():
    df = pd.DataFrame(
        [("USA", "United States", 10, 5, 3, 18), ("BRA", "Brazil", 2, 1, 1, 4), ("XYZ", "Xland", 0, 0, 1, 1)],
        columns=["abrev_pais", "nome_pais", "ouro", "prata", "bronze", "total"],
    )

    fig = painel.grafico_historico(df)

    assert [t.name for t in fig.data] == ["Ouro", "Prata", "Bronze"]
    assert all(len(t.y) == len(df) for t in fig.data)


def test_grafico_evolucao_tem_um_ponto_por_ano():
    df = pd.DataFrame({"ano": [2012, 2016, 2020], "total": [17, 19, 21]})

    fig = painel.grafico_evolucao(df)

    assert len(fig.data[0].x) == len(df)


def test_grafico_participacao_tem_um_ponto_por_edicao_e_linha_de_paridade():
    df = participacao()[participacao()["temporada"] == "Summer"]

    fig = painel.grafico_participacao(df)

    assert len(fig.data[0].x) == len(df)
    assert fig.layout.shapes[0].y0 == 50


def test_grafico_eficiencia_tem_uma_barra_por_pais_e_destaca_o_selecionado():
    df = painel.recorte_eficiencia(eficiencia(), 61, 1)

    fig = painel.grafico_eficiencia(df, "BRA")

    assert sum(len(t.y) for t in fig.data) == len(df)
    destaque = [t for t in fig.data if t.marker.color == painel.DESTAQUE]
    assert list(destaque[0].y) == ["Brasil"]


def test_grafico_especialidade_tem_uma_celula_por_pais_e_esporte():
    matriz = pd.DataFrame({"Natação": [40.0, math.nan], "Outros": [60.0, 100.0]}, index=["EUA", "Quênia"])

    fig = painel.grafico_especialidade(matriz)

    assert len(fig.data[0].z) == 2
    assert len(fig.data[0].z[0]) == 2
    assert fig.data[0].text[1][0] == ""  # célula sem medalha fica sem texto


# ---------------------------------------------------------------- tabelas


def test_tabela_do_quadro_marca_o_pais_selecionado_e_o_separador():
    recorte = painel.recorte_quadro_edicao(quadro_edicao(), 61, "BRA")

    html = painel.tabela_quadro_edicao(recorte, "BRA")

    assert html.count("<tr class=\"sel\">") == 1
    assert "⋯" in html


def test_tabela_de_atletas_escapa_html_do_nome():
    df = pd.DataFrame(
        [(1, "<b>Ana</b>", "Brasil", "Natação", 1, 0, 0, 1)],
        columns=["posicao", "nome_atleta", "paises_pt", "esportes_pt", "ouro", "prata", "bronze", "total"],
    )

    html = painel.tabela_atletas(df)

    assert "&lt;b&gt;Ana&lt;/b&gt;" in html
    assert "<b>Ana</b>" not in html
