"""Testes de traducao.py e da regra de tradução (item 3 da spec do dashboard).

As funções que aplicam os dicionários ficam em painel.py; os dicionários,
em traducao.py.
"""

import painel
import traducao


def test_valores_conhecidos_saem_em_portugues():
    assert traducao.TEMPORADAS["Summer"] == "Verão"
    assert traducao.TEMPORADAS["Winter"] == "Inverno"
    assert painel.pais_pt("BRA", "Brazil") == "Brasil"
    assert painel.esporte_pt("Swimming") == "Natação"


def test_termo_sem_traducao_aparece_no_original_sem_erro():
    assert painel.pais_pt("ZZZ", "Zedland") == "Zedland"  # sigla inventada, com nome da fonte
    assert painel.pais_pt("ZZZ") == "ZZZ"  # sigla inventada, sem nome: mostra a sigla
    assert painel.esporte_pt("Quidditch") == "Quidditch"
    assert painel.temporada_pt("Spring") == "Spring"


def test_lista_e_traduzida_item_a_item():
    assert painel.traduzir_lista("GDR, GER", traducao.PAISES) == "Alemanha Oriental, Alemanha"
    assert painel.traduzir_lista("Swimming, Quidditch", traducao.ESPORTES) == "Natação, Quidditch"
    assert painel.traduzir_lista(None, traducao.PAISES) == ""


def test_edicao_vira_ano_e_temporada_e_1956_hipismo_tem_rotulo_proprio():
    assert painel.rotulo_edicao("2020 Summer Olympics", 2020, "Summer") == "2020 · Verão"
    assert painel.rotulo_edicao("2022 Winter Olympics", 2022, "Winter") == "2022 · Inverno"
    assert painel.rotulo_edicao("1956 Equestrian", 1956, "Summer") == "1956 · Verão (hipismo)"


def test_dicionarios_nao_tem_traducao_vazia():
    for dicionario in (traducao.TEMPORADAS, traducao.PAISES, traducao.ESPORTES):
        assert all(valor.strip() for valor in dicionario.values())


def test_chaves_de_paises_sao_siglas_de_tres_letras_maiusculas():
    assert all(len(sigla) == 3 and sigla.isupper() for sigla in traducao.PAISES)
