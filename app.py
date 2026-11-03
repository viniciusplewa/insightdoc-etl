import os
import re
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

# Função de Mapeamento Inteligente de Setores baseada nos Leitos
def identificar_setor(leito):
    leito_str = str(leito).strip().upper()
    
    if any(prefix in leito_str for prefix in ["OBS M", "OBS F", "EXTRA", "ESTAB", "MED"]):
        return "PA (Pronto Atendimento)"
    
    match = re.search(r'\d+', leito_str)
    if not match:
        return "Outros / Não Especificado"
    
    num = int(match.group())
    
    if 101 <= num <= 112:
        return "Semi intensiva (1 andar)"
    elif 113 <= num <= 122:
        return "Hospital dia (1 andar)"
    elif 200 <= num <= 299:
        return "Clínica Médica (2 andar)"
    elif 301 <= num <= 310:
        return "Clínica cirúrgica 1 (3 andar)"
    elif 311 <= num <= 320:
        return "Clínica cirúrgica pediátrica (3 andar)"
    elif 321 <= num <= 330:
        return "UTI 1 (3 andar)"
    elif 331 <= num <= 340:
        return "UTI 5 (3 andar)"
    elif 341 <= num <= 350:
        return "UTI Pediátrica (3 andar)"
    elif 401 <= num <= 420:
        return "Clínica cirúrgica 2 (4 andar)"
    elif 421 <= num <= 430:
        return "UTI 2 (4 andar)"
    elif 431 <= num <= 440:
        return "UTI 3 (4 andar)"
    elif 441 <= num <= 450:
        return "UTI 4 (4 andar)"
    elif 501 <= num <= 520:
        return "Clínica cirúrgica 3 (5 andar)"
    
    return "Outros / Demais Setores"

# Função para processar o relatório (.xlsx) com as colunas corretas
def processar_relatorio_limpeza(uploaded_file):
    df_raw = pd.read_excel(uploaded_file, sheet_name=0)
    registros = []

    for _, row in df_raw.iterrows():
        primeira_col = row.iloc[0]
        if pd.notna(primeira_col) and str(primeira_col).strip().isdigit():
            solicitacao = str(row.iloc[0])
            atendimento = str(row.iloc[8]) if len(row) > 8 and pd.notna(row.iloc[8]) else ""
            hora = str(row.iloc[23]) if len(row) > 23 and pd.notna(row.iloc[23]) else ""
            leito = str(row.iloc[25]) if len(row) > 25 and pd.notna(row.iloc[25]) else ""
            tipo_limpeza = str(row.iloc[29]) if len(row) > 29 and pd.notna(row.iloc[29]) else ""
            funcionario = str(row.iloc[36]) if len(row) > 36 and pd.notna(row.iloc[36]) else ""
            
            setor_mapeado = identificar_setor(leito)

            registros.append({
                "Solicitação": solicitacao,
                "Atendimento": atendimento,
                "Hora": hora,
                "Leito": leito,
                "Tipo de Limpeza": tipo_limpeza,
                "Funcionário": funcionario,
                "Unidade de Internação": setor_mapeado,
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
        "Faça o upload do relatório Excel **`R_HISTORICO_QUARTOS`** para analisar "
        "os dados em tempo real com total segurança (dados de pacientes ocultados)."
    )

    arquivo_limpeza = st.file_uploader(
        "Enviar Planilha de Histórico de Quartos (.xls / .xlsx)",
        type=["xls", "xlsx"],
    )

    if arquivo_limpeza is not None:
        try:
            df_limpeza = processar_relatorio_limpeza(arquivo_limpeza)

            if df_limpeza.empty:
                st.warning("⚠️ Não foram encontrados registros estruturados na planilha enviada.")
            else:
                st.success(f"Planilha processada com sucesso! Total de registros: {len(df_limpeza)}")
                st.info("🔒 **LGPD Ativada:** Nomes de pacientes foram excluídos do processamento para garantir total sigilo.")

                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    unidades_disponiveis = ["Todas"] + list(df_limpeza["Unidade de Internação"].unique())
                    unidade_filtro = st.selectbox("Filtrar por Unidade de Internação", unidades_disponiveis)
                with col_f2:
                    tipos_disponiveis = ["Todos"] + list(df_limpeza["Tipo de Limpeza"].unique())
                    tipo_filtro = st.selectbox("Filtrar por Tipo de Limpeza", tipos_disponiveis)

                df_filtrado = df_limpeza.copy()
                if unidade_filtro != "Todas":
                    df_filtrado = df_filtrado[df_filtrado["Unidade de Internação"] == unidade_filtro]
                if tipo_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["Tipo de Limpeza"] == tipo_filtro]

                m1, m2, m3 = st.columns(3)
                m1.metric("Total de Limpezas Filtradas", len(df_filtrado))
                m2.metric("Limpezas Terminais", len(df_filtrado[df_filtrado["Tipo de Limpeza"].str.contains("TERMINAL", case=False, na=False)]))
                m3.metric("Limpezas Concorrentes", len(df_filtrado[df_filtrado["Tipo de Limpeza"].str.contains("CONCORRENTE", case=False, na=False)]))

                st.markdown("---")

                g1, g2 = st.columns(2)
                with g1:
                    st.subheader("Distribuição por Tipo de Limpeza")
                    tipo_counts = df_filtrado["Tipo de Limpeza"].value_counts().reset_index()
                    tipo_counts.columns = ["Tipo de Limpeza", "Quantidade"]
                    fig_tipo = px.pie(tipo_counts, names="Tipo de Limpeza", values="Quantidade", title="Proporção de Limpezas")
                    st.plotly_chart(fig_tipo, use_container_width=True)

                with g2:
                    st.subheader("Limpezas por Unidade de Internação")
                    unidade_counts = df_filtrado["Unidade de Internação"].value_counts().reset_index()
                    unidade_counts.columns = ["Unidade", "Quantidade"]
                    fig_unidade = px.bar(unidade_counts, x="Unidade", y="Quantidade", text_auto=True, title="Volume por Unidade")
                    st.plotly_chart(fig_unidade, use_container_width=True)

                st.subheader("Tabela Detalhada de Limpezas")
                st.dataframe(df_filtrado, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao processar o arquivo de limpeza: {e}")
    else:
        st.info("👆 Por favor, faça o upload da planilha Excel para gerar os gráficos e análises operacionais.")

# ---------------------------------------------------------
# TAB 2: EXECUTIVE DASHBOARD
# ---------------------------------------------------------
with tab2:
    st.header("Hospital Service Orders Performance Dashboard")
    df = load_data()
    if df is None:
        st.warning("⚠️ Database not found!")
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
            cost_by_dept = df.groupby("department")["estimated_cost"].sum().reset_index()
            fig_cost = px.bar(cost_by_dept, x="department", y="estimated_cost", color="department", text_auto=".2s", title="Total Operational Spend per Department ($)")
            st.plotly_chart(fig_cost, use_container_width=True)
        with c2:
            st.subheader("Service Orders by Priority Level")
            priority_counts = df["priority"].value_counts().reset_index()
            priority_counts.columns = ["priority", "count"]
            fig_pie = px.pie(priority_counts, names="priority", values="count", color="priority", title="Tickets Distribution by Priority")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Detailed Transformed Data Table")
        st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: RAG CHAT ASSISTANT
# ---------------------------------------------------------
with tab3:
    st.header("Interactive RAG Audit Query System")
    st.caption("Ask questions about internal audit reports, equipment maintenance, and facility guidelines.")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hello! I am your AI operational analyst. Ask me anything about the hospital's internal audit reports!"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ex: What were the audit findings for Pediatrics or ICU Adult?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching vector database & analyzing documents..."):
                response = generate_rag_response(prompt)
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
