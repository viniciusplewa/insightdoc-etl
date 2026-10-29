import os
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# Tenta importar o módulo de RAG se existir
try:
  from rag.llm_chain import generate_rag_response
except ImportError:

  def generate_rag_response(prompt):
    return "Módulo RAG não carregado neste ambiente."


# Page configuration
st.set_page_config(
    page_title="InsightDoc-ETL | Hospital Analytics & Limpezas",
    page_icon="🏥",
    layout="wide",
)


# Database loader helper
@st.cache_data
def load_data():
  db_path = os.path.join(os.path.dirname(__file__), "etl/database.db")
  if not os.path.exists(db_path):
    return None
  conn = sqlite3.connect(db_path)
  df = pd.read_sql("SELECT * FROM service_orders", conn)
  conn.close()
  return df


# Função para processar o relatório de histórico de quartos / limpezas
def processar_relatorio_limpeza(uploaded_file):
  df_raw = pd.read_excel(uploaded_file, sheet_name=0)

  # Lógica de varredura para extrair Unidade de Internação e os dados das limpezas
  registros = []
  unidade_atual = "Não especificada"

  for i, row in df_raw.iterrows():
    row_str = str(row.values)
    # Identifica linha de Unidade de Internação
    if "Unidade de Internação" in row_str:
      # Procura o valor preenchido na linha
      for val in row.values:
        if (
            pd.notna(val)
            and val != "Unidade de Internação :"
            and isinstance(val, str)
        ):
          unidade_atual = val.strip()
          break

    # Identifica linha de registro de limpeza (ex: número de solicitação válido)
    primeira_col = row.iloc[0]
    if pd.notna(primeira_col) and str(primeira_col).strip().isdigit():
      registros.append({
          "Solicitação": str(row.iloc[0]),
          "Atendimento": str(row.iloc[7]) if len(row) > 7 else "",
          "Paciente": str(row.iloc[12]) if len(row) > 12 else "",
          "Hora": str(row.iloc[22]) if len(row) > 22 else "",
          "Leito": str(row.iloc[24]) if len(row) > 24 else "",
          "Tipo de Limpeza": str(row.iloc[28]) if len(row) > 28 else "",
          "Funcionário": str(row.iloc[31]) if len(row) > 31 else "",
          "Unidade de Internação": unidade_atual,
      })

  return pd.DataFrame(registros)


# Main Title & Header
st.title("🏥 InsightDoc-ETL: Gestão Hospitalar & Limpezas")
st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3 = st.tabs([
    "🧼 Limpezas (Terminais & Concorrentes)",
    "📊 Executive KPIs & Analytics",
    "🤖 AI Document Assistant (RAG)",
])

# ---------------------------------------------------------
# TAB 1: LIMPEZAS (TERMINAIS E CONCORRENTES)
# ---------------------------------------------------------
with tab1:
  st.header("Análise de Limpezas de Quartos (Terminais e Concorrentes)")
  st.markdown(
      "Faça o upload do relatório Excel **`R_HISTORICO_QUARTOS`** para analisar"
      " os dados em tempo real."
  )

  arquivo_limpeza = st.file_uploader(
      "Enviar Planilha de Histórico de Quartos (.xls / .xlsx)",
      type=["xls", "xlsx"],
  )

  if arquivo_limpeza is not None:
    try:
      df_limpeza = processar_relatorio_limpeza(arquivo_limpeza)

      if df_limpeza.empty:
        st.warning(
            "⚠️ Não foram encontrados registros estruturados na planilha"
            " enviada. Verifique o formato."
        )
      else:
        st.success(
            f"Planilha processada com sucesso! Total de registros:"
            f" {len(df_limpeza)}"
        )

        # Filtros rápidos
        col_f1, col_f2 = st.columns(2)
        with col_f1:
          unidades_disponiveis = [
              "Todas"
          ] + list(df_limpeza["Unidade de Internação"].unique())
          unidade_filtro = st.selectbox(
              "Filtrar por Unidade de Internação", unidades_disponiveis
          )
        with col_f2:
          tipos_disponiveis = [
              "Todos"
          ] + list(df_limpeza["Tipo de Limpeza"].unique())
          tipo_filtro = st.selectbox(
              "Filtrar por Tipo de Limpeza", tipos_disponiveis
          )

        # Aplicando filtros
        df_filtrado = df_limpeza.copy()
        if unidade_filtro != "Todas":
          df_filtrado = df_filtrado[
              df_filtrado["Unidade de Internação"] == unidade_filtro
          ]
        if tipo_filtro != "Todos":
          df_filtrado = df_filtrado[
              df_filtrado["Tipo de Limpeza"] == tipo_filtro
          ]

        # Métricas em Cards
        m1, m2, m3 = st.columns(3)
        m1.metric("Total de Limpezas Filtradas", len(df_filtrado))
        m2.metric(
            "Limpezas Terminais",
            len(
                df_filtrado[
                    df_filtrado["Tipo de Limpeza"].str.contains(
                        "TERMINAL", case=False, na=False
                    )
                ]
            ),
        )
        m3.metric(
            "Limpezas Concorrentes",
            len(
                df_filtrado[
                    df_filtrado["Tipo de Limpeza"].str.contains(
                        "CONCORRENTE", case=False, na=False
                    )
                ]
            ),
        )

        st.markdown("---")

        # Gráficos
        g1, g2 = st.columns(2)
        with g1:
          st.subheader("Distribuição por Tipo de Limpeza")
          tipo_counts = (
              df_filtrado["Tipo de Limpeza"].value_counts().reset_index()
          )
          tipo_counts.columns = ["Tipo de Limpeza", "Quantidade"]
          fig_tipo = px.pie(
              tipo_counts,
              names="Tipo de Limpeza",
              values="Quantidade",
              title="Proporção de Limpezas",
          )
          st.plotly_chart(fig_tipo, use_container_width=True)

        with g2:
          st.subheader("Limpezas por Unidade de Internação")
          unidade_counts = (
              df_filtrado["Unidade de Internação"].value_counts().reset_index()
          )
          unidade_counts.columns = ["Unidade", "Quantidade"]
          fig_unidade = px.bar(
              unidade_counts,
              x="Unidade",
              y="Quantidade",
              text_auto=True,
              title="Volume por Unidade",
          )
          st.plotly_chart(fig_unidade, use_container_width=True)

        st.subheader("Tabela Detalhada de Limpezas")
        st.dataframe(df_filtrado, use_container_width=True)

    except Exception as e:
      st.error(f"Erro ao processar o arquivo de limpeza: {e}")
  else:
    st.info(
        "👆 Por favor, faça o upload da planilha Excel para gerar os gráficos"
        " e análises."
    )

# ---------------------------------------------------------
# TAB 2: EXECUTIVE DASHBOARD
# ---------------------------------------------------------
with tab2:
  st.header("Hospital Service Orders Performance Dashboard")

  df = load_data()

  if df is None:
    st.warning(
        "⚠️ Database not found! Certifique-se de que o banco SQLite está na"
        " pasta correta."
    )
  else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Service Orders", f"{len(df):,}")
    col2.metric("Total Estimated Cost", f"${df['estimated_cost'].sum():,.2f}")
    col3.metric("Avg Resolution Time", f"{df['duration_hours'].mean():.2f} hrs")
    col4.metric("Urgent Tickets", f"{len(df[df['priority'] == 'URGENT'])}")

    st.markdown("---")

    c1, c2 = st.columns(2)

    with c1:
      st.subheader("Total Costs by Department")
      cost_by_dept = (
          df.groupby("department")["estimated_cost"].sum().reset_index()
      )
      fig_cost = px.bar(
          cost_by_dept,
          x="department",
          y="estimated_cost",
          color="department",
          text_auto=".2s",
          title="Total Operational Spend per Department ($)",
      )
      st.plotly_chart(fig_cost, use_container_width=True)

    with c2:
      st.subheader("Service Orders by Priority Level")
      priority_counts = df["priority"].value_counts().reset_index()
      priority_counts.columns = ["priority", "count"]
      fig_pie = px.pie(
          priority_counts,
          names="priority",
          values="count",
          color="priority",
          title="Tickets Distribution by Priority",
      )
      st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("Detailed Transformed Data Table")
    st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: RAG CHAT ASSISTANT
# ---------------------------------------------------------
with tab3:
  st.header("Interactive RAG Audit Query System")
  st.caption(
      "Ask questions about internal audit reports, equipment maintenance, and"
      " facility guidelines."
  )

  if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "Hello! I am your AI operational analyst. Ask me anything about the"
            " hospital's internal audit reports!"
        ),
    }]

  for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
      st.markdown(msg["content"])

  if prompt := st.chat_input(
      "Ex: What were the audit findings for Pediatrics or ICU Adult?"
  ):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
      st.markdown(prompt)

    with st.chat_message("assistant"):
      with st.spinner("Searching vector database & analyzing documents..."):
        response = generate_rag_response(prompt)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
