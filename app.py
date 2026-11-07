"""Dashboard dos Jogos Olímpicos. A spec está no topo de painel.py.

Execução:
    uv run streamlit run app.py

Este arquivo só monta a página: leitura, contas, tradução e gráficos ficam
em painel.py.
"""

import streamlit as st

import painel

st.set_page_config(page_title="Olimpíadas", page_icon="🏅", layout="wide")


@st.cache_data(show_spinner="Lendo os marts…")
def carregar() -> dict:
    return painel.ler(painel.MARTS)


try:
    dados = carregar()
except painel.DadosIndisponiveis as erro:
    st.error(str(erro))
    st.stop()


def _voltar_para_ultima_edicao() -> None:
    # Trocar a temporada descarta a edição escolhida: o selectbox volta para
    # a mais recente da nova temporada.
    st.session_state.pop("edicao", None)


st.title("Olimpíadas: painel de indicadores")
st.caption("Medalhas, atletas e participação nos Jogos Olímpicos, a partir do schema marts do olimpiadas.duckdb.")

# ---------------------------------------------------------------- filtros
col_temp, col_ed, col_pais, col_botao = st.columns([1.2, 1.4, 2, 1], vertical_alignment="bottom")
with col_temp:
    temporada = st.radio(
        "Temporada", ["Summer", "Winter"], format_func=painel.temporada_pt,
        horizontal=True, key="temporada", on_change=_voltar_para_ultima_edicao,
    )
edicoes = painel.opcoes_edicao(dados["quadro_medalhas_por_edicao"], temporada)
with col_ed:
    edicao_id = st.selectbox("Edição", list(edicoes), format_func=edicoes.get, key="edicao")
paises = painel.opcoes_pais(dados["eficiencia_conversao_pais_edicao"])
lista_paises = list(paises)
with col_pais:
    pais = st.selectbox(
        "País", lista_paises, format_func=lambda a: f"{a} · {paises[a]}",
        index=lista_paises.index("BRA") if "BRA" in paises else 0, key="pais",
    )
with col_botao:
    if st.button("Recarregar dados", width="stretch"):
        st.cache_data.clear()
        st.rerun()

nome_pais = paises[pais]
rotulo_edicao = edicoes[edicao_id]
nome_temporada = painel.temporada_pt(temporada)

# ---------------------------------------------------------------- cards
for coluna, card in zip(st.columns(4), painel.cards(dados, edicao_id, pais)):
    with coluna, st.container(border=True):
        st.metric(card.rotulo, card.valor)
        st.caption(card.detalhe or " ")

GRAFICO = {"displayModeBar": False}


def fonte(mart: str) -> None:
    st.caption(f"Fonte: `marts.{mart}`")


# ---------------------------------------------------------------- quadros
esq, dir = st.columns([7, 5])
with esq, st.container(border=True):
    st.subheader("Quadro de medalhas da edição", divider=False)
    st.caption(f"{rotulo_edicao}. Ordem olímpica: ouro, depois prata, depois bronze.")
    recorte = painel.recorte_quadro_edicao(dados["quadro_medalhas_por_edicao"], edicao_id, pais)
    st.html(painel.tabela_quadro_edicao(recorte, pais))
    fonte("quadro_medalhas_por_edicao")
with dir, st.container(border=True):
    st.subheader("Quadro histórico: 10 maiores")
    st.caption(f"Soma de todas as edições de {nome_temporada}. Países históricos (URS, GDR, FRG…) contam separados, como no quadro oficial.")
    recorte = painel.recorte_historico(dados["quadro_medalhas_historico_pais"], temporada)
    st.plotly_chart(painel.grafico_historico(recorte), config=GRAFICO)
    fonte("quadro_medalhas_historico_pais")

# ---------------------------------------------------------------- séries
esq, dir = st.columns(2)
with esq, st.container(border=True):
    st.subheader(f"Evolução de medalhas: {nome_pais}")
    st.caption(f"Total de medalhas por ano nos Jogos de {nome_temporada}. Ano com participação e sem medalha aparece como zero.")
    recorte = painel.recorte_evolucao(dados["evolucao_medalhas_pais_ano"], temporada, pais)
    if recorte.empty:
        st.info(f"{nome_pais} não tem participação registrada nos Jogos de {nome_temporada}.")
    else:
        st.plotly_chart(painel.grafico_evolucao(recorte), config=GRAFICO)
    fonte("evolucao_medalhas_pais_ano")
with dir, st.container(border=True):
    st.subheader("Participação feminina")
    st.caption(f"Percentual de mulheres entre os atletas de cada edição de {nome_temporada}.")
    recorte = painel.recorte_participacao(dados["participacao_feminina_edicao"], temporada)
    st.plotly_chart(painel.grafico_participacao(recorte), config=GRAFICO)
    fonte("participacao_feminina_edicao")

# ---------------------------------------------------------------- especialidade
with st.container(border=True):
    st.subheader("Em que esporte cada país concentra suas medalhas")
    st.caption(
        f"Percentual das medalhas do país que vêm de cada esporte. Linhas: {nome_pais} e os 9 primeiros "
        f"do quadro histórico de {nome_temporada}. Os percentuais somam Verão e Inverno, porque o mart "
        "não separa temporada. Célula vazia: nenhuma medalha."
    )
    matriz = painel.matriz_especialidade(
        dados["especialidade_pais_esporte"], dados["quadro_medalhas_historico_pais"], temporada, pais
    )
    st.plotly_chart(painel.grafico_especialidade(matriz), config=GRAFICO)
    fonte("especialidade_pais_esporte")

# ---------------------------------------------------------------- atletas e eficiência
esq, dir = st.columns(2)
with esq, st.container(border=True):
    st.subheader("Atletas mais medalhados")
    st.caption(f"Top 10 entre os atletas com medalha nos Jogos de {nome_temporada}, todas as edições.")
    recorte = painel.recorte_atletas(dados["atletas_mais_medalhados"], temporada)
    st.html(painel.tabela_atletas(recorte))
    fonte("atletas_mais_medalhados")
with dir, st.container(border=True):
    st.subheader("Eficiência: medalhas por atleta")
    st.caption(f"{rotulo_edicao}. Delegações pequenas distorcem a razão, por isso há um mínimo de atletas.")
    minimo = st.slider("Mín. de atletas", min_value=1, max_value=100, value=20, key="minimo")
    recorte = painel.recorte_eficiencia(dados["eficiencia_conversao_pais_edicao"], edicao_id, minimo)
    if recorte.empty:
        st.info("Nenhum país com esse mínimo de atletas nesta edição.")
    else:
        st.plotly_chart(painel.grafico_eficiencia(recorte, pais), config=GRAFICO)
    fonte("eficiencia_conversao_pais_edicao")
