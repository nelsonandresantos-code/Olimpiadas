# Olimpíadas: pipeline de dados e dashboard

Pipeline de dados em Python sobre o dataset público do **Olympedia**, que reúne
os Jogos Olímpicos de 1896 a 2022 (Verão e Inverno). Os seis arquivos CSV
passam por três camadas num banco DuckDB (`raw` → `refined` → `marts`) e
terminam num dashboard em Streamlit com sete indicadores: quadro de medalhas,
evolução por país, atletas mais medalhados, especialidade por esporte,
eficiência de delegações e participação feminina.

O projeto segue **spec-driven development**: cada módulo começa por uma spec
(a docstring no topo do arquivo), com regras, motivos e critérios de aceite.
O código é consequência da spec.

```
data/raw/*.csv.gz ──► raw ──► refined ──► marts ──► dashboard (Streamlit)
   6 arquivos       ingestão  transformação  SQL      app.py + painel.py
```

## Stack

| Ferramenta | Uso |
|---|---|
| Python 3.14 | linguagem |
| [uv](https://docs.astral.sh/uv/) | ambiente e dependências |
| DuckDB | banco analítico em arquivo (`olimpiadas.duckdb`) |
| pandas | leitura dos CSVs |
| Streamlit + Plotly | dashboard |
| pytest + pytest-cov | testes unitários e cobertura |

## Como rodar

Pré-requisitos: Python 3.14 e uv instalados. Os CSVs já vêm no repositório,
em `data/raw/`; o banco não (é gerado pelo pipeline).

```bash
# 1. Instalar as dependências
uv sync

# 2. Rodar o pipeline, nesta ordem
uv run python -m pipeline.ingestao        # CSV  -> schema raw
uv run python -m pipeline.transformacao   # raw  -> schema refined
uv run python -m pipeline.marts           # refined -> schema marts

# 3. Abrir o dashboard
uv run python -m streamlit run app.py
```

Cada etapa imprime uma linha por tabela, com a contagem lida do banco, e
encerra com erro claro (e o comando a rodar) se a etapa anterior não tiver
sido executada. Todas podem ser rodadas de novo sem efeito colateral: recriam
as tabelas, nunca acrescentam linhas.

Para explorar o banco no navegador com a interface do DuckDB:

```bash
uv run python ui.py    # http://localhost:4213, Ctrl+C para encerrar
```

> O DuckDB aceita um único processo escrevendo no arquivo. Feche o `ui.py`
> antes de rodar o pipeline. O dashboard não bloqueia: ele lê em modo
> somente leitura e fecha a conexão a cada leitura.

## Estrutura

```
.
├── data/raw/                  # os seis .csv.gz do Olympedia (entrada)
├── pipeline/
│   ├── db.py                  # conexão com o olimpiadas.duckdb, compartilhada
│   ├── ingestao.py            # etapa 1: CSV -> raw
│   ├── transformacao.py       # etapa 2: raw -> refined
│   └── marts.py               # etapa 3: executa SQL/Marts/*.sql -> marts
├── SQL/Marts/                 # um SELECT por indicador (01_ a 07_)
├── painel.py                  # etapa 4: leitura, cálculos, formato e gráficos
├── traducao.py                # nomes de países, esportes e temporadas em português
├── app.py                     # a página do dashboard (só layout)
├── ui.py                      # interface web do DuckDB, para exploração
├── protótipo_dashboard.html   # protótipo de layout, com dados ilustrativos
├── Specs/                     # specs escritas fora do código
├── test/                      # testes unitários
└── pyproject.toml
```

## Etapas

### 1. Ingestão (`pipeline/ingestao.py`) → schema `raw`

Carrega os seis CSVs **sem nenhuma decisão sobre o dado**: toda coluna entra
como texto, nada é convertido, descartado, deduplicado ou corrigido; campo
vazio vira nulo. É a fotografia do que chegou, para servir de comparação com
o resultado das decisões da etapa seguinte.

| Arquivo | Tabela |
|---|---|
| `world_olympedia_olympics_athlete_bio.csv.gz` | `bio_atleta` |
| `world_olympedia_olympics_athlete_event_result.csv.gz` | `resultado_atleta` |
| `world_olympedia_olympics_country.csv.gz` | `pais` |
| `world_olympedia_olympics_game.csv.gz` | `jogos_olimpicos` |
| `world_olympedia_olympics_game_medal_tally.csv.gz` | `medalhas_pais` |
| `world_olympedia_olympics_result.csv.gz` | `resultados` |

### 2. Transformação (`pipeline/transformacao.py`) → schema `refined`

Onde as decisões acontecem, todas registradas na spec do módulo:

- colunas renomeadas para português, em `snake_case`;
- tipos convertidos (datas para `DATE`, ids e contagens para `INTEGER`);
  um valor que não converte **para o pipeline**, em vez de virar nulo;
- espaços à esquerda removidos e o texto `'na'` tratado como nulo;
- coluna `temporada` (Summer/Winter) extraída da edição;
- duplicatas exatas removidas; chave repetida com conteúdo diferente para o
  pipeline e mostra as linhas em conflito.

Tudo roda numa transação: se algo falha, `refined` continua como estava.

### 3. Marts (`pipeline/marts.py` + `SQL/Marts/`) → schema `marts`

Cada arquivo `NN_nome.sql` contém um único `SELECT` e vira a tabela
`marts.nome`. A regra de negócio mora inteira no `.sql`, comentada; o Python
só executa. O schema é recriado a cada execução, numa transação única: um
SQL com erro ou um mart vazio desfaz tudo e mantém a versão anterior.

| Mart | Grão | Indicador |
|---|---|---|
| `quadro_medalhas_por_edicao` | edição × país | quadro de medalhas e ranking de cada edição |
| `quadro_medalhas_historico_pais` | temporada × país | ranking histórico somando todas as edições |
| `evolucao_medalhas_pais_ano` | temporada × ano × país | medalhas de um país ao longo do tempo |
| `atletas_mais_medalhados` | atleta | ranking por total de medalhas e por ouros |
| `especialidade_pais_esporte` | país × esporte | em que esporte cada país concentra medalhas |
| `eficiencia_conversao_pais_edicao` | edição × país | medalhas por atleta enviado |
| `participacao_feminina_edicao` | temporada × ano | percentual de mulheres entre os atletas |

Critérios comuns: ranking no critério olímpico (ouro, depois prata, depois
bronze; empate divide a posição); os Jogos Intercalados de 1906 ficam de fora
por não serem reconhecidos pelo COI.

### 4. Dashboard (`app.py` + `painel.py`)

Página única em Streamlit, com o layout do `protótipo_dashboard.html`:

- **Filtros**: temporada (padrão Verão), edição (padrão a mais recente) e país
  (padrão Brasil), mais o botão "Recarregar dados".
- **Cards**: posição no quadro, medalhas, medalhas por atleta e percentual de
  mulheres na edição.
- **Blocos**: quadro da edição, quadro histórico, evolução do país,
  participação feminina, heatmap país × esporte, atletas mais medalhados e
  eficiência (com mínimo de atletas ajustável).

`painel.py` concentra leitura, cálculos, formatação e gráficos e não importa
Streamlit, para poder ser testado sozinho; `app.py` só monta a página. Os
números saem sempre no padrão brasileiro (milhar com ponto, decimal com
vírgula), sem depender do locale da máquina, e todos os nomes aparecem em
português. A spec completa está em [`Specs/dashboard_spec.txt`](Specs/dashboard_spec.txt).

## Testes

```bash
uv run pytest --cov
```

Um arquivo por módulo em `test/`, com pytest puro. Cada teste cria um DuckDB
novo numa pasta temporária, com poucas linhas inventadas e comentadas;
**nenhum teste abre o `olimpiadas.duckdb`**, então a suíte roda em qualquer
máquina, sem o pipeline ter rodado. Os SQLs dos marts 01 e 03 são testados
sobre tabelas inventadas, verificando as regras escritas nos comentários.

A meta de cobertura é 60% do total (configurada no `pyproject.toml`); a suíte
atual tem 77 testes e cobre 97%. Ficam fora da medição `app.py` (layout,
conferido no navegador) e `ui.py`.

## Specs

| Spec | Onde está |
|---|---|
| Conexão | docstring de `pipeline/db.py` |
| Ingestão | docstring de `pipeline/ingestao.py` |
| Transformação | docstring de `pipeline/transformacao.py` |
| Marts | docstring de `pipeline/marts.py` e comentários de cada `SQL/Marts/*.sql` |
| Dashboard | `Specs/dashboard_spec.txt` e docstring de `painel.py` |
| Interface do DuckDB | docstring de `ui.py` |

## Fonte dos dados

Dataset público do [Olympedia](https://www.olympedia.org/) com atletas,
resultados, edições, países e quadro de medalhas dos Jogos Olímpicos. Os
arquivos em `data/raw/` são usados como vieram, sem edição manual.
