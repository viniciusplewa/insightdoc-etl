import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ---------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="InsightDoc-ETL | Hospital Analytics & Limpezas",
    page_icon="🏥",
    layout="wide",
)

st.markdown(
    """
    <style>
    .metric-card-1 {
        background-color: #f0f7fd;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border-left: 6px solid #2980B9;
    }
    .metric-card-2 {
        background-color: #fdf5ec;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border-left: 6px solid #E67E22;
    }
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Funções auxiliares de leitura e identificação
# ---------------------------------------------------------------------
def normalizar_texto(valor):
    """Remove acentos e espaços extras para comparar rótulos."""
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto)


def encontrar_coluna(colunas, termos):
    """Encontra uma coluna pelo nome, sem depender de maiúsculas/minúsculas."""
    for coluna in colunas:
        nome = normalizar_texto(coluna)
        if any(termo in nome for termo in termos):
            return coluna
    return None


def identificar_setor_serie(leitos_series):
    """
    Classificação de reserva pelo número do leito.
    É usada somente quando a planilha não informa a Unidade de Internação.
    """
    leitos = leitos_series.fillna("").astype(str).str.strip().str.upper()
    numeros = leitos.str.extract(r"(\d+)", expand=False)
    numeros = pd.to_numeric(numeros, errors="coerce")

    setores = pd.Series("PA (Pronto Atendimento)", index=leitos_series.index, dtype="object")
    setores.loc[(numeros >= 101) & (numeros <= 112)] = "Semi intensiva (1 andar)"
    setores.loc[(numeros >= 113) & (numeros <= 122)] = "Hospital dia (1 andar)"
    setores.loc[(numeros >= 200) & (numeros <= 299)] = "Clínica Médica (2 andar)"
    setores.loc[(numeros >= 301) & (numeros <= 310)] = "Clínica cirúrgica 1 (3 andar)"
    setores.loc[(numeros >= 311) & (numeros <= 320)] = "Clínica cirúrgica pediátrica (3 andar)"
    setores.loc[(numeros >= 321) & (numeros <= 330)] = "UTI 1 (3 andar)"
    setores.loc[(numeros >= 331) & (numeros <= 340)] = "UTI 5 (3 andar)"
    setores.loc[(numeros >= 341) & (numeros <= 350)] = "UTI Pediátrica (3 andar)"
    setores.loc[(numeros >= 401) & (numeros <= 420)] = "Clínica cirúrgica 2 (4 andar)"
    setores.loc[(numeros >= 421) & (numeros <= 430)] = "UTI 2 (4 andar)"
    setores.loc[(numeros >= 431) & (numeros <= 440)] = "UTI 3 (4 andar)"
    setores.loc[(numeros >= 441) & (numeros <= 450)] = "UTI 4 (4 andar)"
    setores.loc[(numeros >= 501) & (numeros <= 520)] = "Clínica cirúrgica 3 (5 andar)"
    return setores


def extrair_horas_por_linha(df_raw, coluna_hora=None):
    """
    Procura o horário em cada registro.
    Isso permite ler planilhas que juntam blocos com colunas em posições diferentes.
    """
    padrao_hora = r"(?<!\d)((?:[01]?\d|2[0-3]):[0-5]\d)(?!\d)"
    horas = pd.Series("", index=df_raw.index, dtype="object")

    colunas_busca = []
    if coluna_hora and coluna_hora in df_raw.columns:
        colunas_busca.append(coluna_hora)
    colunas_busca.extend(c for c in df_raw.columns if c not in colunas_busca)

    for coluna in colunas_busca:
        extraida = (
            df_raw[coluna]
            .fillna("")
            .astype(str)
            .str.extract(padrao_hora, expand=False)
            .fillna("")
        )
        horas = horas.mask(horas.eq(""), extraida)

    return horas


def extrair_tipo_limpeza_por_linha(df_raw):
    """
    Identifica o tipo em qualquer coluna da linha.
    O CSV de referência contém blocos em que o campo Tipo de Limpeza muda
    de posição; por isso, não se pode interromper a busca na primeira coluna.
    """
    tipo = pd.Series("", index=df_raw.index, dtype="object")
    posicao_tipo = pd.Series(-1, index=df_raw.index, dtype="int64")

    for posicao, coluna in enumerate(df_raw.columns):
        valores = df_raw[coluna].fillna("").astype(str).str.upper().str.strip()
        valores = valores.str.replace(r"\s+", " ", regex=True)

        concorrente = valores.str.contains(r"\bCONCORRENTE\b", regex=True, na=False)
        terminal_quarto = (
            valores.str.contains(r"\bTERMINAL\b", regex=True, na=False)
            & valores.str.contains(r"\bQUART", regex=True, na=False)
        )
        terminal_leito = valores.str.contains(r"\bTERMINAL\b", regex=True, na=False) & ~terminal_quarto
        pontual = valores.str.contains(r"\bPONTUAL\b", regex=True, na=False)

        # Uma linha recebe somente a primeira classificação reconhecida.
        for mascara, classificacao in (
            (concorrente, "CONCORRENTE"),
            (terminal_quarto, "TERMINAL DE QUARTO"),
            (terminal_leito, "TERMINAL DE LEITO"),
            (pontual, "LIMPEZA PONTUAL"),
        ):
            aplicar = tipo.eq("") & mascara
            tipo.loc[aplicar] = classificacao
            posicao_tipo.loc[aplicar] = posicao

    tipo = tipo.mask(tipo.eq(""), "Não Identificado")
    return tipo, posicao_tipo


def extrair_proximo_valor(df_raw, posicoes_ancora, linhas_validas):
    """Retorna o primeiro campo preenchido à direita de uma coluna-âncora."""
    matriz = df_raw.fillna("").astype(str).to_numpy()
    resultado = [""] * len(df_raw)

    for i in linhas_validas:
        posicao = int(posicoes_ancora.iloc[i])
        if posicao < 0:
            continue
        for j in range(posicao + 1, matriz.shape[1]):
            valor = matriz[i, j].strip()
            if valor and valor.lower() != "nan":
                resultado[i] = valor
                break

    return pd.Series(resultado, index=df_raw.index, dtype="object")


def extrair_unidade_do_relatorio(df_raw):
    """
    O relatório pode trazer a unidade em uma linha de cabeçalho
    ('Unidade de Internação :'). A unidade é propagada até o próximo cabeçalho.
    """
    marcadores = pd.Series(False, index=df_raw.index)
    for coluna in df_raw.columns:
        texto = df_raw[coluna].fillna("").astype(str).apply(normalizar_texto)
        marcadores |= texto.str.contains("UNIDADE DE INTERNACAO", regex=False)

    unidades_cabecalho = pd.Series("", index=df_raw.index, dtype="object")
    matriz = df_raw.fillna("").astype(str).to_numpy()

    for i in marcadores[marcadores].index:
        linha = matriz[df_raw.index.get_loc(i)]
        pos_marcador = next(
            (j for j, valor in enumerate(linha)
             if "UNIDADE DE INTERNACAO" in normalizar_texto(valor)),
            -1,
        )
        if pos_marcador >= 0:
            valor_unidade = next(
                (
                    valor.strip()
                    for valor in linha[pos_marcador + 1:]
                    if valor.strip() and valor.strip().lower() != "nan"
                ),
                "",
            )
            if valor_unidade:
                unidades_cabecalho.loc[i] = valor_unidade

    return unidades_cabecalho.replace("", pd.NA).ffill()


def processar_relatorio_limpeza(uploaded_file, nome_origem):
    """Lê CSV/Excel e normaliza os registros sem depender de posições fixas."""
    nome_arquivo = uploaded_file.name.lower()

    try:
        if nome_arquivo.endswith(".csv"):
            df_raw = None
            erros = []
            for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
                try:
                    uploaded_file.seek(0)
                    df_raw = pd.read_csv(
                        uploaded_file,
                        encoding=encoding,
                        sep=None,
                        engine="python",
                        dtype=str,
                        nrows=300000,
                    )
                    break
                except Exception as erro:
                    erros.append(str(erro))
            if df_raw is None:
                raise ValueError("Não foi possível identificar a codificação do CSV.")
        else:
            uploaded_file.seek(0)
            df_raw = pd.read_excel(uploaded_file, sheet_name=0, dtype=str)

    except Exception as erro:
        st.error(f"Erro ao ler o arquivo {uploaded_file.name}: {erro}")
        return pd.DataFrame()

    if df_raw.empty or len(df_raw.columns) == 0:
        st.warning(f"O arquivo {uploaded_file.name} está vazio.")
        return pd.DataFrame()

    df_raw.columns = [str(coluna).strip() for coluna in df_raw.columns]

    # Solicitação: usa o cabeçalho quando disponível; caso contrário, primeira coluna.
    col_solicitacao = encontrar_coluna(df_raw.columns, ["SOLICITA", "REGISTRO"])
    if col_solicitacao is None:
        col_solicitacao = df_raw.columns[0]

    solicitacao = (
        df_raw[col_solicitacao]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\.0+$", "", regex=True)
    )
    linhas_validas_mask = solicitacao.str.fullmatch(r"\d+", na=False)
    linhas_validas = list(linhas_validas_mask[linhas_validas_mask].index)

    if not linhas_validas:
        st.warning(f"Nenhuma solicitação numérica foi encontrada em {uploaded_file.name}.")
        return pd.DataFrame()

    # Tipo de limpeza: procura o valor na linha inteira, pois o CSV alterna layouts.
    tipo_limpeza, pos_tipo = extrair_tipo_limpeza_por_linha(df_raw)

    # Hora: primeiro tenta a coluna nomeada e depois todas as outras colunas.
    col_hora = encontrar_coluna(df_raw.columns, ["HORA"])
    hora = extrair_horas_por_linha(df_raw, col_hora)

    # Leito: no relatório de referência, o leito é o primeiro campo após a hora.
    pos_hora = pd.Series(-1, index=df_raw.index, dtype="int64")
    padrao_hora = re.compile(r"(?<!\d)((?:[01]?\d|2[0-3]):[0-5]\d)(?!\d)")
    matriz = df_raw.fillna("").astype(str).to_numpy()
    for i in linhas_validas:
        for j, valor in enumerate(matriz[i]):
            if padrao_hora.search(valor):
                pos_hora.iloc[i] = j
                break

    leito = extrair_proximo_valor(df_raw, pos_hora, linhas_validas)
    col_leito = encontrar_coluna(df_raw.columns, ["LEITO"])
    if col_leito:
        valor_nomeado = df_raw[col_leito].fillna("").astype(str).str.strip()
        # Quando a coluna Leito está preenchida, ela é mais confiável que a posição.
        # No CSV de referência, os blocos deslocados ficam vazios nessa coluna;
        # nesses casos, usamos o valor encontrado após o horário.
        leito = valor_nomeado.mask(valor_nomeado.eq(""), leito)
    leito = leito.replace(["nan", "NAN", "NaN"], "")

    # Colaborador: é o primeiro campo preenchido depois do tipo de limpeza.
    colaborador = extrair_proximo_valor(df_raw, pos_tipo, linhas_validas)
    col_funcionario = encontrar_coluna(
        df_raw.columns,
        ["FUNCIONARIO", "COLABORADOR", "EXECUTANTE", "RESPONSAVEL", "OPERADOR"],
    )
    if col_funcionario:
        valor_nomeado = df_raw[col_funcionario].fillna("").astype(str).str.strip()
        colaborador = valor_nomeado.mask(valor_nomeado.eq(""), colaborador)
    colaborador = colaborador.replace(["nan", "NAN", "NaN", ""], "Não Informado")

    # Unidade real do cabeçalho do relatório; se não existir, usa a classificação pelo leito.
    unidade = extrair_unidade_do_relatorio(df_raw)
    col_unidade = encontrar_coluna(df_raw.columns, ["UNIDADE DE INTERNACAO", "SETOR"])
    if col_unidade:
        unidade_coluna = df_raw[col_unidade].fillna("").astype(str).str.strip()
        unidade = unidade_coluna.mask(unidade_coluna.eq(""), unidade)
    setor_por_leito = identificar_setor_serie(leito)
    unidade = unidade.fillna("").astype(str).str.strip()
    unidade = unidade.mask(unidade.eq(""), setor_por_leito)
    unidade = unidade.replace("", "Não Informado")

    resultado = pd.DataFrame(
        {
            "Origem / Período": nome_origem,
            "Solicitação": solicitacao,
            "Hora": hora,
            "Turno": identificar_turno_serie(hora),
            "Leito": leito.replace("", "Não Informado"),
            "Tipo de Limpeza": tipo_limpeza,
            "Colaborador": colaborador,
            "Unidade de Internação": unidade,
        },
        index=df_raw.index,
    )

    resultado = resultado.loc[linhas_validas_mask].copy()
    return resultado.reset_index(drop=True)


def identificar_turno_serie(horas_series):
    """Diurno das 07:00 às 19:00; demais horários são noturnos."""
    horas = horas_series.fillna("").astype(str).str.strip()
    turnos = pd.Series("Não Especificado", index=horas_series.index, dtype="object")

    match = horas.str.extract(r"^(\d{1,2}):(\d{2})", expand=True)
    valido = match[0].notna() & match[1].notna()

    if valido.any():
        hora_num = pd.to_numeric(match.loc[valido, 0], errors="coerce")
        minuto_num = pd.to_numeric(match.loc[valido, 1], errors="coerce")
        total_minutos = hora_num * 60 + minuto_num
        diurno = (total_minutos >= 7 * 60) & (total_minutos <= 19 * 60)
        turnos.loc[diurno[diurno].index] = "Diurno (07:00 - 19:00)"
        turnos.loc[diurno[~diurno].index] = "Noturno"

    return turnos


def formatar_numero(valor):
    return f"{int(valor):,}".replace(",", ".")


def formatar_diferenca(valor):
    sinal = "+" if valor > 0 else ""
    return f"{sinal}{formatar_numero(valor)}"


# ---------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------
st.title("InsightDoc-ETL: Gestão Hospitalar & Comparador de Limpezas")
st.markdown("---")
st.header("Análise Comparativa de Relatórios de Quartos")
st.markdown(
    "Envie uma ou duas planilhas para analisar os registros separadamente "
    "ou comparar os períodos lado a lado."
)

col_up1, col_up2 = st.columns(2)
with col_up1:
    arquivo_1 = st.file_uploader(
        "Enviar 1ª Planilha (Ex.: Período A)",
        type=["xlsx", "xls", "csv"],
        key="file1",
    )
with col_up2:
    arquivo_2 = st.file_uploader(
        "Enviar 2ª Planilha (Opcional - Ex.: Período B)",
        type=["xlsx", "xls", "csv"],
        key="file2",
    )

dfs_combinados = []

if arquivo_1 is not None:
    with st.spinner("Processando a 1ª planilha..."):
        df1 = processar_relatorio_limpeza(arquivo_1, "Planilha 1 (A)")
        if not df1.empty:
            dfs_combinados.append(df1)

if arquivo_2 is not None:
    with st.spinner("Processando a 2ª planilha..."):
        df2 = processar_relatorio_limpeza(arquivo_2, "Planilha 2 (B)")
        if not df2.empty:
            dfs_combinados.append(df2)

if not dfs_combinados:
    st.info("Envie pelo menos uma planilha (Excel ou CSV) para iniciar as análises.")
else:
    df_limpeza = pd.concat(dfs_combinados, ignore_index=True)

    st.success(
        f"Dados processados: {formatar_numero(len(df_limpeza))} registros válidos."
    )

    nao_identificados = int(
        df_limpeza["Tipo de Limpeza"].eq("Não Identificado").sum()
    )
    if nao_identificados:
        st.warning(
            f"{formatar_numero(nao_identificados)} registros não tiveram o tipo "
            "de limpeza reconhecido. Eles aparecem como 'Não Identificado' "
            "em vez de serem classificados incorretamente como terminais."
        )

    # Os filtros partem sempre da base completa e são combinados entre si.
    st.subheader("Filtros")
    col_f1, col_f2, col_f3 = st.columns(3)

    unidades_disponiveis = sorted(
        df_limpeza["Unidade de Internação"].dropna().astype(str).unique().tolist()
    )
    tipos_preferidos = [
        "CONCORRENTE",
        "TERMINAL DE LEITO",
        "TERMINAL DE QUARTO",
        "LIMPEZA PONTUAL",
        "Não Identificado",
    ]
    tipos_presentes = df_limpeza["Tipo de Limpeza"].dropna().unique().tolist()
    tipos_disponiveis = [t for t in tipos_preferidos if t in tipos_presentes]
    tipos_disponiveis += sorted(t for t in tipos_presentes if t not in tipos_disponiveis)

    turnos_preferidos = [
        "Diurno (07:00 - 19:00)",
        "Noturno",
        "Não Especificado",
    ]
    turnos_presentes = df_limpeza["Turno"].dropna().unique().tolist()
    turnos_disponiveis = [t for t in turnos_preferidos if t in turnos_presentes]
    turnos_disponiveis += sorted(t for t in turnos_presentes if t not in turnos_disponiveis)

    with col_f1:
        unidade_filtro = st.selectbox(
            "Unidade de Internação",
            ["Todas"] + unidades_disponiveis,
            key="filtro_unidade",
        )
    with col_f2:
        tipo_filtro = st.selectbox(
            "Tipo de Limpeza",
            ["Todos"] + tipos_disponiveis,
            key="filtro_tipo",
        )
    with col_f3:
        turno_filtro = st.selectbox(
            "Turno",
            ["Todos"] + turnos_disponiveis,
            key="filtro_turno",
        )

    df_filtrado = df_limpeza.copy()
    if unidade_filtro != "Todas":
        df_filtrado = df_filtrado[
            df_filtrado["Unidade de Internação"] == unidade_filtro
        ]
    if tipo_filtro != "Todos":
        df_filtrado = df_filtrado[
            df_filtrado["Tipo de Limpeza"] == tipo_filtro
        ]
    if turno_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Turno"] == turno_filtro]

    st.caption(
        f"Exibindo {formatar_numero(len(df_filtrado))} de "
        f"{formatar_numero(len(df_limpeza))} registros. "
        "Os filtros de unidade, tipo e turno são aplicados em conjunto."
    )
    st.markdown("---")

    origens_presentes = df_limpeza["Origem / Período"].drop_duplicates().tolist()

    # -----------------------------------------------------------------
    # Métricas por planilha
    # -----------------------------------------------------------------
    st.markdown("### Métricas por Planilha & Comparativo")
    valores_metricas = {}
    cols_met = st.columns(max(1, len(origens_presentes)))

    for i, origem in enumerate(origens_presentes):
        df_origem = df_filtrado[df_filtrado["Origem / Período"] == origem]
        total = len(df_origem)
        terminais = int(
            df_origem["Tipo de Limpeza"].str.startswith("TERMINAL", na=False).sum()
        )
        concorrentes = int(
            df_origem["Tipo de Limpeza"].eq("CONCORRENTE").sum()
        )
        valores_metricas[origem] = {
            "Total": total,
            "Terminais": terminais,
            "Concorrentes": concorrentes,
        }

        classe = "metric-card-1" if i == 0 else "metric-card-2"
        with cols_met[i]:
            st.markdown(f"**{origem}**")
            st.markdown(
                f"""
                <div class="{classe}">
                    <div style="display:flex; justify-content:space-between; gap:8px;">
                        <div><span style="font-size:13px;color:#555;">Total</span><br>
                            <b style="font-size:23px;">{formatar_numero(total)}</b></div>
                        <div><span style="font-size:13px;color:#555;">Terminais</span><br>
                            <b style="font-size:23px;">{formatar_numero(terminais)}</b></div>
                        <div><span style="font-size:13px;color:#555;">Concorrentes</span><br>
                            <b style="font-size:23px;">{formatar_numero(concorrentes)}</b></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if len(origens_presentes) == 2:
        origem_a, origem_b = origens_presentes
        met_a = valores_metricas[origem_a]
        met_b = valores_metricas[origem_b]

        itens_diferenca = []
        for chave, rotulo in (
            ("Total", "Total"),
            ("Terminais", "Terminais"),
            ("Concorrentes", "Concorrentes"),
        ):
            diferenca = met_b[chave] - met_a[chave]
            base = met_a[chave]
            percentual = (diferenca / base * 100) if base else None
            percentual_txt = f" ({percentual:+.1f}%)" if percentual is not None else " (base zero)"
            itens_diferenca.append(
                f"<div><b>{rotulo}:</b> {formatar_diferenca(diferenca)}{percentual_txt}</div>"
            )

        st.markdown(
            f"""
            <div style="background-color:#f8f9fa;padding:14px;border-radius:10px;
                        border:1px solid #ddd;margin-top:12px;">
                <b>Diferença ({origem_b} vs. {origem_a}):</b>
                <div style="display:flex;justify-content:space-around;gap:12px;
                            flex-wrap:wrap;margin-top:8px;font-size:14px;">
                    {''.join(itens_diferenca)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    if df_filtrado.empty:
        st.warning(
            "Nenhum registro corresponde à combinação de filtros selecionada. "
            "Altere um ou mais filtros para visualizar os gráficos."
        )
    else:
        # -------------------------------------------------------------
        # Gráfico de pizza por tipo de limpeza e por planilha
        # -------------------------------------------------------------
        st.subheader("Proporção por Tipo de Limpeza (separado por planilha)")
        cols_pizza = st.columns(max(1, len(origens_presentes)))

        for i, origem in enumerate(origens_presentes):
            with cols_pizza[i]:
                df_origem = df_filtrado[
                    df_filtrado["Origem / Período"] == origem
                ]
                if df_origem.empty:
                    st.info(f"Sem registros para {origem} com esses filtros.")
                    continue

                tipo_counts = (
                    df_origem["Tipo de Limpeza"]
                    .value_counts()
                    .rename_axis("Tipo de Limpeza")
                    .reset_index(name="Quantidade")
                )
                fig_pizza = px.pie(
                    tipo_counts,
                    names="Tipo de Limpeza",
                    values="Quantidade",
                    title=f"Distribuição - {origem}",
                    color_discrete_sequence=["#2980B9", "#E67E22", "#27AE60", "#8E44AD"],
                )
                fig_pizza.update_layout(height=400, font=dict(size=13))
                st.plotly_chart(fig_pizza, use_container_width=True)

        st.markdown("---")

        # -------------------------------------------------------------
        # Gráfico de barras por unidade
        # -------------------------------------------------------------
        st.subheader("Volume por Unidade de Internação (comparativo)")
        col_ord1, _ = st.columns([2, 4])
        with col_ord1:
            criterio_ordenacao = st.selectbox(
                "Ordenar unidades por:",
                [
                    "Maior Diferença Absoluta (Planilhas)",
                    "Maior Volume Geral",
                ],
                key="criterio_ordenacao",
            )

        contagem_unidades = (
            df_filtrado.groupby(
                ["Unidade de Internação", "Origem / Período"],
                as_index=False,
            )
            .size()
            .rename(columns={"size": "Quantidade"})
        )

        pivot_unidades = contagem_unidades.pivot(
            index="Unidade de Internação",
            columns="Origem / Período",
            values="Quantidade",
        ).fillna(0)
        pivot_unidades = pivot_unidades.reindex(
            columns=origens_presentes, fill_value=0
        )

        if len(origens_presentes) == 2:
            origem_a, origem_b = origens_presentes
            diferencas = pivot_unidades[origem_b] - pivot_unidades[origem_a]
            if criterio_ordenacao == "Maior Diferença Absoluta (Planilhas)":
                ordem_unidades = diferencas.abs().sort_values(ascending=False).index.tolist()
            else:
                ordem_unidades = (
                    pivot_unidades.sum(axis=1).sort_values(ascending=False).index.tolist()
                )
        else:
            ordem_unidades = (
                pivot_unidades.sum(axis=1).sort_values(ascending=False).index.tolist()
            )

        fig_unidade = px.bar(
            contagem_unidades,
            x="Unidade de Internação",
            y="Quantidade",
            color="Origem / Período",
            barmode="group",
            title=f"Comparativo ordenado por: {criterio_ordenacao}",
            text="Quantidade",
            category_orders={"Unidade de Internação": ordem_unidades},
            color_discrete_sequence=["#2980B9", "#E67E22"],
        )
        fig_unidade.update_traces(
            textposition="outside",
            cliponaxis=False,
            texttemplate="%{text:,.0f}",
        )
        maior_valor = (
            float(contagem_unidades["Quantidade"].max())
            if not contagem_unidades.empty
            else 1
        )
        fig_unidade.update_yaxes(range=[0, max(1, maior_valor * 1.25)])
        fig_unidade.update_layout(
            height=650,
            font=dict(size=12),
            xaxis=dict(tickangle=-35, title="Unidades de Internação"),
            yaxis=dict(title="Quantidade de limpezas"),
            legend=dict(title=dict(text="Planilha")),
        )

        if len(origens_presentes) == 2:
            for unidade in ordem_unidades:
                valor_a = float(pivot_unidades.loc[unidade, origem_a])
                valor_b = float(pivot_unidades.loc[unidade, origem_b])
                diferenca = int(valor_b - valor_a)
                maximo = max(valor_a, valor_b)
                percentual = (
                    (diferenca / valor_a * 100) if valor_a else None
                )
                percentual_texto = (
                    f"{percentual:+.1f}%" if percentual is not None else "base zero"
                )
                sinal = "+" if diferenca > 0 else ""
                texto = f"Δ {sinal}{diferenca} ({percentual_texto})"
                fig_unidade.add_annotation(
                    x=unidade,
                    y=maximo + maior_valor * 0.08,
                    text=texto,
                    showarrow=False,
                    font=dict(size=10, color="#333"),
                )

        st.plotly_chart(fig_unidade, use_container_width=True)

        st.markdown("---")

        # -------------------------------------------------------------
        # Gráfico de horário (usa somente registros com hora reconhecida)
        # -------------------------------------------------------------
        st.subheader("Comparativo de Limpezas por Horário (00h às 23h)")
        df_horarios = df_filtrado.copy()
        df_horarios["Hora_Num"] = pd.to_numeric(
            df_horarios["Hora"].astype(str).str.extract(r"^(\d{1,2})", expand=False),
            errors="coerce",
        )
        df_horarios = df_horarios[df_horarios["Hora_Num"].between(0, 23)]

        if df_horarios.empty:
            st.info("Não há horários válidos nos registros que passaram pelos filtros.")
        else:
            contagem_horas = (
                df_horarios.groupby(
                    ["Hora_Num", "Origem / Período"]
                )
                .size()
                .rename("Quantidade")
                .reset_index()
            )
            fig_hora = go.Figure()

            for origem in origens_presentes:
                serie = (
                    contagem_horas[contagem_horas["Origem / Período"] == origem]
                    .set_index("Hora_Num")["Quantidade"]
                    .reindex(range(24), fill_value=0)
                )
                fig_hora.add_trace(
                    go.Scatter(
                        x=[f"{h:02d}h" for h in range(24)],
                        y=serie.values,
                        name=origem,
                        mode="lines+markers",
                        line=dict(width=3),
                        marker=dict(size=6),
                    )
                )

            fig_hora.update_layout(
                height=550,
                font=dict(size=13),
                xaxis=dict(title="Hora do dia"),
                yaxis=dict(title="Número de limpezas"),
                legend=dict(title=dict(text="Planilha")),
                hovermode="x unified",
            )
            st.plotly_chart(fig_hora, use_container_width=True)

    st.markdown("---")

    # -----------------------------------------------------------------
    # Tabela detalhada e download
    # -----------------------------------------------------------------
    st.subheader("Tabela Detalhada Consolidada")
    csv_bytes = df_filtrado.to_csv(
        index=False, encoding="utf-8-sig"
    ).encode("utf-8-sig")
    st.download_button(
        label="Baixar CSV combinado",
        data=csv_bytes,
        file_name="relatorio_comparativo_limpezas.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
