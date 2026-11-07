"""Etapa 4: leitura, cálculos, formatação e gráficos do dashboard.

A página é app.py (uv run streamlit run app.py). Este módulo não importa
streamlit: tudo aqui é testável sem subir a página.

1. LEITURA
   ler(nomes) -> dict nome -> DataFrame. Para cada nome, só
   SELECT * FROM marts.<nome>. Nenhuma outra SQL, em nenhum arquivo.
   Caminho do banco resolvido a partir da localização deste arquivo, nunca
   do diretório corrente. Conexão read_only, aberta e fechada dentro de ler().
   Por quê: conexão aberta segura o arquivo, e o pipeline.marts não consegue
   gravar com o painel de pé. Caminho relativo ao diretório corrente faria o
   painel não achar o banco quando rodado de outra pasta.

2. CÁLCULOS
   Permitidos aqui (groupby, contagem, pivot, merge, contas entre colunas),
   cada um numa função com nome que diga o que calcula. app.py não faz
   contas: só chama funções deste módulo e monta a página.
   Por quê: as regras de negócio do painel ficam num lugar só, testável sem
   streamlit; app.py é só layout.

3. TRADUÇÃO
   Tudo que aparece na tela fica em português, pelos dicionários de
   traducao.py (TEMPORADAS, PAISES por abrev_pais, ESPORTES).
   Edição é exibida como "<ano> · <temporada>" (ex.: "2020 · Verão");
   "1956 Equestrian" é "1956 · Verão (hipismo)". Colunas com listas
   (paises, esportes, temporadas em atletas_mais_medalhados) são traduzidas
   item a item. Termo sem tradução aparece no original, sem erro.
   Por quê: os marts vêm em inglês da fonte; traduzir na exibição não altera
   o dado, e um termo esquecido não pode derrubar a página.

4. LAYOUT (app.py), na ordem do protótipo protótipo_dashboard.html
   Filtros numa linha no topo (Temporada, Edição, País) com o botão
   "Recarregar dados". Quatro cards: posição no quadro, medalhas
   (ouro/prata/bronze abaixo), medalhas por atleta (nº de atletas abaixo) e
   mulheres na edição. Sem linha do país no quadro da edição: posição e
   medalhas mostram "Sem medalhas nesta edição". Sem linha em eficiência:
   medalhas por atleta mostra "Não participou".
   Blocos:
     Quadro da edição       top 10 por ranking_edicao + país selecionado se
                            estiver fora; barra ouro/prata/bronze por linha
     Quadro histórico       barras empilhadas, ranking_geral <= 10
     Evolução do país       linha: total por ano
     Participação feminina  área: percentual_mulheres por ano; tracejado em
                            50% rotulado "paridade"
     Especialidade          heatmap de percentual_do_pais: país selecionado +
                            9 primeiros do histórico da temporada; 8 esportes
                            de maior total entre eles + "Outros"
     Atletas                top 10 dos que têm medalha na temporada, posição
                            recalculada (total, ouro, prata; empate divide)
     Eficiência             top 10 por medalhas_por_atleta com atletas >=
                            mínimo (1 a 100, padrão 20); país em destaque
   O mart de especialidade não tem temporada: os percentuais somam verão e
   inverno, e a legenda do bloco diz isso.
   Por quê: cada bloco diz de onde vem e o que filtra; nada fica para
   adivinhar a partir do protótipo.

5. FORMATO
   pct(valor, casas=1) -> "47,8%" (valor na escala 0–100);
   numero(valor, casas=0) -> "96.470"; posicao(n) -> "12º".
   Milhar com ponto, decimal com vírgula, sempre. None ou NaN -> "–".
   Sem locale do sistema.
   Por quê: o resultado não pode depender da máquina de quem roda.
   Uma função por gráfico, recebendo o DataFrame já filtrado e devolvendo a
   figura plotly.

6. FILTROS
   Temporada: Verão / Inverno, padrão Verão. Edição: as da temporada, da
   mais recente para a mais antiga, padrão a mais recente; trocar a
   temporada volta para a mais recente. País: todos de
   eficiencia_conversao_pais_edicao, em ordem alfabética do nome em
   português, padrão Brasil (BRA).
   Por quê: o painel abre mostrando o caso mais recente do país de quem usa.

7. CACHE E ERRO
   ler() envolvida por st.cache_data em app.py; "Recarregar dados" limpa o
   cache e recarrega. Sem olimpiadas.duckdb ou faltando mart da lista:
   st.error com quais e o comando "uv run python -m pipeline.marts",
   st.stop(), sem traceback.
   Por quê: um painel que quebra com traceback não diz o que fazer.

ACEITE
   1. Ao abrir: Verão, "2020 · Verão", Brasil; cards 12º, 21 (7/6/8),
      0,07 por atleta (316 atletas), 47,8% de mulheres.
   2. pct(93.2) == "93,2%"; numero(96470) == "96.470";
      numero(1234567.891, 2) == "1.234.567,89"; numero(-1234) == "-1.234";
      posicao(12) == "12º"; numero(None) == "–"; com locale pt_BR e en_US.
   3. painel e traducao importam sem streamlit; única SQL fora de pipeline/
      é SELECT * FROM marts.<nome>; todo abrev_pais e esporte dos marts
      tem tradução.
   4. Com o app aberto, pipeline.marts roda sem erro de lock, e
      "Recarregar dados" mostra os dados novos.
   5. Sem banco ou sem mart: st.error sem traceback. Inverno + Brasil:
      "Sem medalhas nesta edição" e o resto da página carrega.
"""

import html
import math
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from traducao import ESPORTES, PAISES, TEMPORADAS

BANCO = Path(__file__).resolve().parent / "olimpiadas.duckdb"

MARTS = [
    "quadro_medalhas_por_edicao",
    "quadro_medalhas_historico_pais",
    "evolucao_medalhas_pais_ano",
    "atletas_mais_medalhados",
    "especialidade_pais_esporte",
    "eficiencia_conversao_pais_edicao",
    "participacao_feminina_edicao",
]

COMANDO_MARTS = "uv run python -m pipeline.marts"

# Cores do protótipo.
OURO, PRATA, BRONZE = "#d4a017", "#9e9e9e", "#b0703c"
DESTAQUE, SECUNDARIA = "#2a78d6", "#9ec5f4"
CORES_MEDALHA = {"Ouro": OURO, "Prata": PRATA, "Bronze": BRONZE}


# ---------------------------------------------------------------- leitura

@dataclass
class DadosIndisponiveis(Exception):
    banco_ausente: bool = False
    faltando: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.banco_ausente:
            motivo = f"Banco não encontrado: {BANCO.name}."
        else:
            motivo = "Marts faltando: " + ", ".join(self.faltando) + "."
        return f"{motivo} Rode: {COMANDO_MARTS}"


def ler(nomes: list[str]) -> dict[str, pd.DataFrame]:
    # O arquivo é checado antes: connect criaria um banco vazio se não fosse
    # read_only, e com read_only o erro do DuckDB não diz o que fazer.
    if not BANCO.is_file():
        raise DadosIndisponiveis(banco_ausente=True)
    dados, faltando = {}, []
    con = duckdb.connect(str(BANCO), read_only=True)
    try:
        for nome in nomes:
            # Um mart ausente é descoberto pelo próprio SELECT, sem consultar o
            # catálogo: a spec só permite SELECT * FROM marts.<nome>.
            try:
                dados[nome] = con.execute(f"SELECT * FROM marts.{nome}").df()
            except duckdb.CatalogException:
                faltando.append(nome)
    finally:
        con.close()
    if faltando:
        raise DadosIndisponiveis(faltando=faltando)
    return dados


# ---------------------------------------------------------------- formato

def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor)) or valor is pd.NA


def numero(valor, casas: int = 0) -> str:
    if _vazio(valor):
        return "–"
    # Formata no padrão americano e troca os separadores: independe de locale.
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def pct(valor, casas: int = 1) -> str:
    return "–" if _vazio(valor) else numero(valor, casas) + "%"


def posicao(n) -> str:
    return "–" if _vazio(n) else f"{int(n)}º"


# ---------------------------------------------------------------- tradução

def temporada_pt(temporada: str) -> str:
    return TEMPORADAS.get(temporada, temporada)


def pais_pt(abrev: str, original: str | None = None) -> str:
    return PAISES.get(abrev, original or abrev)


def esporte_pt(esporte: str) -> str:
    return ESPORTES.get(esporte, esporte)


def traduzir_lista(texto: str, dicionario: dict[str, str]) -> str:
    if _vazio(texto):
        return ""
    return ", ".join(dicionario.get(item.strip(), item.strip()) for item in texto.split(","))


def rotulo_edicao(edicao: str, ano: int, temporada: str) -> str:
    rotulo = f"{ano} · {temporada_pt(temporada)}"
    return rotulo + " (hipismo)" if "Equestrian" in edicao else rotulo


def _chave_alfabetica(texto: str) -> str:
    # Ordem alfabética sem locale: "Áustria" fica entre "Austrália" e "Azerbaijão".
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.casefold()


# ---------------------------------------------------------------- filtros

def opcoes_edicao(quadro: pd.DataFrame, temporada: str) -> dict[int, str]:
    """edicao_id -> rótulo, da edição mais recente para a mais antiga."""
    edicoes = (
        quadro[quadro["temporada"] == temporada][["edicao_id", "edicao", "ano", "temporada"]]
        .drop_duplicates("edicao_id")
        .sort_values(["ano", "edicao_id"], ascending=False)
    )
    return {
        int(r.edicao_id): rotulo_edicao(r.edicao, r.ano, r.temporada) for r in edicoes.itertuples()
    }


def opcoes_pais(eficiencia: pd.DataFrame) -> dict[str, str]:
    """abrev_pais -> nome em português, em ordem alfabética do nome."""
    paises = eficiencia[["abrev_pais", "nome_pais"]].drop_duplicates("abrev_pais")
    nomes = {r.abrev_pais: pais_pt(r.abrev_pais, r.nome_pais) for r in paises.itertuples()}
    return dict(sorted(nomes.items(), key=lambda par: _chave_alfabetica(par[1])))


# ---------------------------------------------------------------- cards

@dataclass
class Card:
    rotulo: str
    valor: str
    detalhe: str


def cards(dados: dict[str, pd.DataFrame], edicao_id: int, pais: str) -> list[Card]:
    quadro = dados["quadro_medalhas_por_edicao"]
    da_edicao = quadro[quadro["edicao_id"] == edicao_id]
    linha_quadro = da_edicao[da_edicao["abrev_pais"] == pais]

    eficiencia = dados["eficiencia_conversao_pais_edicao"]
    linha_efic = eficiencia[(eficiencia["edicao_id"] == edicao_id) & (eficiencia["abrev_pais"] == pais)]

    # participação feminina é por temporada e ano (1956 soma as duas edições de verão).
    ano, temporada = da_edicao[["ano", "temporada"]].iloc[0]
    participacao = dados["participacao_feminina_edicao"]
    linha_fem = participacao[(participacao["ano"] == ano) & (participacao["temporada"] == temporada)]

    sem_medalha = "Sem medalhas nesta edição"
    if linha_quadro.empty:
        card_posicao = Card("Posição no quadro", sem_medalha, "")
        card_medalhas = Card("Medalhas", sem_medalha, "")
    else:
        q = linha_quadro.iloc[0]
        card_posicao = Card("Posição no quadro", posicao(q["ranking_edicao"]), f"entre {numero(len(da_edicao))} países medalhistas")
        card_medalhas = Card(
            "Medalhas",
            numero(q["total"]),
            f"{numero(q['ouro'])} ouros · {numero(q['prata'])} pratas · {numero(q['bronze'])} bronzes",
        )

    if linha_efic.empty:
        card_efic = Card("Medalhas por atleta", "Não participou", "")
    else:
        e = linha_efic.iloc[0]
        card_efic = Card("Medalhas por atleta", numero(e["medalhas_por_atleta"], 2), f"{numero(e['atletas'])} atletas enviados")

    if linha_fem.empty:
        card_fem = Card("Mulheres na edição", "–", "")
    else:
        f = linha_fem.iloc[0]
        card_fem = Card("Mulheres na edição", pct(f["percentual_mulheres"]), f"{numero(f['mulheres'])} de {numero(f['mulheres'] + f['homens'])} atletas")

    return [card_posicao, card_medalhas, card_efic, card_fem]


# ---------------------------------------------------------------- recortes

def recorte_quadro_edicao(quadro: pd.DataFrame, edicao_id: int, pais: str) -> pd.DataFrame:
    """Top 10 da edição + a linha do país selecionado, se estiver fora do top 10."""
    da_edicao = quadro[quadro["edicao_id"] == edicao_id].sort_values(
        ["ranking_edicao", "ouro", "prata", "bronze", "abrev_pais"], ascending=[True, False, False, False, True]
    )
    topo = da_edicao[da_edicao["ranking_edicao"] <= 10]
    extra = da_edicao[(da_edicao["abrev_pais"] == pais) & (da_edicao["ranking_edicao"] > 10)]
    recorte = pd.concat([topo, extra])
    recorte = recorte.assign(fora_do_topo=recorte["ranking_edicao"] > 10)
    return recorte


def recorte_historico(historico: pd.DataFrame, temporada: str) -> pd.DataFrame:
    return historico[(historico["temporada"] == temporada) & (historico["ranking_geral"] <= 10)].sort_values(
        ["ranking_geral", "abrev_pais"]
    )


def recorte_evolucao(evolucao: pd.DataFrame, temporada: str, pais: str) -> pd.DataFrame:
    return evolucao[(evolucao["temporada"] == temporada) & (evolucao["abrev_pais"] == pais)].sort_values("ano")


def recorte_participacao(participacao: pd.DataFrame, temporada: str) -> pd.DataFrame:
    return participacao[participacao["temporada"] == temporada].sort_values("ano")


def matriz_especialidade(
    especialidade: pd.DataFrame, historico: pd.DataFrame, temporada: str, pais: str
) -> pd.DataFrame:
    """Linhas: país selecionado + 9 primeiros do histórico da temporada.
    Colunas: 8 esportes de maior total entre essas linhas + "Outros".
    Valor: percentual_do_pais; NaN onde o país não tem medalha no esporte."""
    ordem = historico[historico["temporada"] == temporada].sort_values(["ranking_geral", "abrev_pais"])
    outros_paises = [p for p in ordem["abrev_pais"] if p != pais][:9]
    linhas = [pais, *outros_paises]

    recorte = especialidade[especialidade["abrev_pais"].isin(linhas)]
    top_esportes = (
        recorte.groupby("esporte")["total"].sum().sort_values(ascending=False).head(8).index.tolist()
    )
    matriz = (
        recorte[recorte["esporte"].isin(top_esportes)]
        .pivot(index="abrev_pais", columns="esporte", values="percentual_do_pais")
        .reindex(index=linhas, columns=top_esportes)
    )
    # "Outros" só existe para país com alguma medalha; sem medalha a linha
    # fica vazia, e não "100% em Outros".
    com_medalha = set(recorte["abrev_pais"])
    matriz["Outros"] = [
        100 - matriz.loc[p, top_esportes].fillna(0).sum() if p in com_medalha else float("nan") for p in linhas
    ]
    matriz.index = [pais_pt(p) for p in matriz.index]
    matriz.columns = [esporte_pt(c) if c != "Outros" else c for c in matriz.columns]
    return matriz


def recorte_atletas(atletas: pd.DataFrame, temporada: str) -> pd.DataFrame:
    """Top 10 dos atletas com medalha na temporada, posição recalculada no filtro."""
    na_temporada = atletas[atletas["temporadas"].str.split(", ").apply(lambda ts: temporada in ts)].copy()
    # total, depois ouro, depois prata, numa chave só: RANK com empate dividindo a posição.
    chave = na_temporada["total"] * 1_000_000 + na_temporada["ouro"] * 1_000 + na_temporada["prata"]
    na_temporada["posicao"] = chave.rank(method="min", ascending=False).astype(int)
    topo = na_temporada[na_temporada["posicao"] <= 10].sort_values(["posicao", "nome_atleta"])
    return topo.assign(
        paises_pt=topo["paises"].apply(lambda t: traduzir_lista(t, PAISES)),
        esportes_pt=topo["esportes"].apply(lambda t: traduzir_lista(t, ESPORTES)),
    )


def recorte_eficiencia(eficiencia: pd.DataFrame, edicao_id: int, minimo: int) -> pd.DataFrame:
    return (
        eficiencia[(eficiencia["edicao_id"] == edicao_id) & (eficiencia["atletas"] >= minimo)]
        .sort_values(["medalhas_por_atleta", "abrev_pais"], ascending=[False, True])
        .head(10)
    )


# ---------------------------------------------------------------- gráficos

def _layout(fig: go.Figure, altura: int) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=10, t=10, b=0),
        separators=",.",  # decimal vírgula, milhar ponto nos eixos e hovers
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title_text=""),
        hoverlabel=dict(namelength=-1),
    )
    return fig


def grafico_historico(df: pd.DataFrame) -> go.Figure:
    dados = df.assign(pais=[pais_pt(a, n) for a, n in zip(df["abrev_pais"], df["nome_pais"])]).rename(
        columns={"ouro": "Ouro", "prata": "Prata", "bronze": "Bronze"}
    )
    fig = px.bar(
        dados, y="pais", x=["Ouro", "Prata", "Bronze"], orientation="h",
        color_discrete_map=CORES_MEDALHA, custom_data=["total"],
    )
    fig.update_traces(hovertemplate="%{y}<br>%{fullData.name}: %{x:,.0f}<br>Total: %{customdata[0]:,.0f}<extra></extra>")
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(dados["pais"])[::-1])
    fig.update_xaxes(title=None)
    for pais, total in zip(dados["pais"], dados["total"]):
        fig.add_annotation(x=total, y=pais, text=numero(total), showarrow=False, xanchor="left", xshift=6)
    return _layout(fig, 360)


def grafico_evolucao(df: pd.DataFrame) -> go.Figure:
    fig = px.line(df, x="ano", y="total", markers=True)
    fig.update_traces(line_color=DESTAQUE, hovertemplate="%{x}<br>Medalhas: %{y:,.0f}<extra></extra>")
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None, rangemode="tozero")
    if not df.empty:
        ultimo = df.iloc[-1]
        fig.add_annotation(x=ultimo["ano"], y=ultimo["total"], text=numero(ultimo["total"]), showarrow=False, yshift=14)
    return _layout(fig, 300)


def grafico_participacao(df: pd.DataFrame) -> go.Figure:
    fig = px.area(df, x="ano", y="percentual_mulheres")
    fig.update_traces(line_color=DESTAQUE, hovertemplate="%{x}<br>Mulheres: %{y:,.1f}%<extra></extra>")
    fig.add_hline(y=50, line_dash="dash", line_width=1, annotation_text="paridade", annotation_position="top left")
    topo = max(60, math.ceil(df["percentual_mulheres"].max() / 10) * 10) if not df.empty else 60
    fig.update_yaxes(title=None, range=[0, topo], ticksuffix="%")
    fig.update_xaxes(title=None)
    return _layout(fig, 300)


def grafico_especialidade(matriz: pd.DataFrame) -> go.Figure:
    texto = matriz.map(lambda v: "" if _vazio(v) else pct(v, 0))
    fig = px.imshow(matriz, color_continuous_scale="Blues", zmin=0, zmax=100, aspect="auto")
    fig.update_traces(
        text=texto.values, texttemplate="%{text}", xgap=2, ygap=2,
        hovertemplate="%{y} · %{x}<br>%{z:,.0f}% das medalhas do país<extra></extra>",
    )
    fig.update_xaxes(title=None, side="top")
    fig.update_yaxes(title=None)
    fig.update_layout(coloraxis_colorbar=dict(title="", ticksuffix="%"))
    return _layout(fig, 420)


def grafico_eficiencia(df: pd.DataFrame, pais: str) -> go.Figure:
    dados = df.assign(
        pais=[pais_pt(a, n) for a, n in zip(df["abrev_pais"], df["nome_pais"])],
        cor=["destaque" if a == pais else "demais" for a in df["abrev_pais"]],
        rotulo=[numero(v, 2) for v in df["medalhas_por_atleta"]],
    )
    fig = px.bar(
        dados, y="pais", x="medalhas_por_atleta", orientation="h", color="cor", text="rotulo",
        color_discrete_map={"destaque": DESTAQUE, "demais": SECUNDARIA},
        custom_data=["total", "atletas"],
    )
    fig.update_traces(
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Medalhas por atleta: %{x:,.3f}<br>%{customdata[0]:,.0f} medalhas / %{customdata[1]:,.0f} atletas<extra></extra>",
    )
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(dados["pais"])[::-1])
    fig.update_xaxes(title=None)
    fig.update_layout(showlegend=False)
    return _layout(fig, 360)


# ---------------------------------------------------------------- tabelas

_ESTILO_TABELA = """
<style>
.tq { width:100%; border-collapse:collapse; font-size:14px; font-variant-numeric:tabular-nums; }
.tq th { text-align:left; font-weight:500; font-size:12px; opacity:.65; padding:6px; border-bottom:1px solid rgba(128,128,128,.35); }
.tq td { padding:6px; border-bottom:1px solid rgba(128,128,128,.15); vertical-align:middle; }
.tq .n { text-align:right; }
.tq .r { opacity:.6; width:28px; }
.tq .sel td { font-weight:600; }
.tq .sep td { text-align:center; opacity:.5; padding:0; border:0; }
.tq small { display:block; opacity:.6; font-size:12px; }
.tq .noc { font:600 11px ui-monospace,Consolas,monospace; background:rgba(128,128,128,.18); border-radius:4px; padding:2px 5px; margin-right:6px; }
.tq .bar { display:flex; gap:2px; height:8px; min-width:80px; }
.tq .bar b { display:block; height:100%; border-radius:2px; }
</style>
"""


def _barra(ouro: int, prata: int, bronze: int, maximo: int) -> str:
    seg = lambda v, c: f'<b style="width:{v / maximo * 100:.2f}%;background:{c}"></b>' if v else ""
    return f'<div class="bar">{seg(ouro, OURO)}{seg(prata, PRATA)}{seg(bronze, BRONZE)}</div>'


def tabela_quadro_edicao(df: pd.DataFrame, pais: str) -> str:
    maximo = max(int(df["total"].max()), 1) if not df.empty else 1
    linhas = []
    for r in df.itertuples():
        if r.fora_do_topo:
            linhas.append('<tr class="sep"><td colspan="7">⋯</td></tr>')
        classe = ' class="sel"' if r.abrev_pais == pais else ""
        linhas.append(
            f"<tr{classe}><td class='r'>{posicao(r.ranking_edicao)}</td>"
            f"<td><span class='noc'>{r.abrev_pais}</span>{html.escape(pais_pt(r.abrev_pais, r.nome_pais))}</td>"
            f"<td class='n'>{numero(r.ouro)}</td><td class='n'>{numero(r.prata)}</td>"
            f"<td class='n'>{numero(r.bronze)}</td><td class='n'><strong>{numero(r.total)}</strong></td>"
            f"<td style='width:28%'>{_barra(r.ouro, r.prata, r.bronze, maximo)}</td></tr>"
        )
    cabecalho = (
        "<tr><th>#</th><th>País</th><th class='n'>Ouro</th><th class='n'>Prata</th>"
        "<th class='n'>Bronze</th><th class='n'>Total</th><th></th></tr>"
    )
    return f"{_ESTILO_TABELA}<table class='tq'><thead>{cabecalho}</thead><tbody>{''.join(linhas)}</tbody></table>"


def tabela_atletas(df: pd.DataFrame) -> str:
    maximo = max(int(df["total"].max()), 1) if not df.empty else 1
    linhas = [
        f"<tr><td class='r'>{posicao(r.posicao)}</td>"
        f"<td>{html.escape(r.nome_atleta)}<small>{html.escape(r.paises_pt)} · {html.escape(r.esportes_pt)}</small></td>"
        f"<td class='n'>{numero(r.ouro)}</td><td class='n'>{numero(r.prata)}</td>"
        f"<td class='n'>{numero(r.bronze)}</td><td class='n'><strong>{numero(r.total)}</strong></td>"
        f"<td style='width:24%'>{_barra(r.ouro, r.prata, r.bronze, maximo)}</td></tr>"
        for r in df.itertuples()
    ]
    cabecalho = (
        "<tr><th>#</th><th>Atleta</th><th class='n'>Ouro</th><th class='n'>Prata</th>"
        "<th class='n'>Bronze</th><th class='n'>Total</th><th></th></tr>"
    )
    return f"{_ESTILO_TABELA}<table class='tq'><thead>{cabecalho}</thead><tbody>{''.join(linhas)}</tbody></table>"
