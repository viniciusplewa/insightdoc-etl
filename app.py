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
    
    if any(p in leito_str for p in ["OBS M", "OBS F", "EXTRA", "ESTAB", "MED", "EX"]):
        return "PA (Pronto Atendimento)"
    
    match = re.search(r'\d+', leito_str)
    if not match:
        return "PA (Pronto Atendimento)"
    
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
    
    return "PA (Pronto Atendimento)"

# Função para classificar o turno com base na hora (07:00 às 19:00 = Diurno, restante = Noturno)
def identificar_turno(hora_str):
    if not hora_str or ":" not in str(hora_str):
        return "Não Especificado"
    try:
        partes = str(hora_str).strip().split(":")
        hora_num = int(partes[0])
        minuto_num = int(partes[1])
        
        total_minutos = hora_num * 60 + minuto_num
        inicio_diurno = 7 * 60   # 07:00
        fim_diurno = 19 * 60     # 19:00
        
        if inicio_diurno <= total_minutos <= fim_diurno:
            return "Diurno (07:00 - 19:00)"
        else:
            return "Noturno"
    except Exception:
        return "Não Especificado"

# Função para processar o relatório de forma segura (LGPD Compliance)
def processar_relatorio_limpeza(uploaded_file):
    df_raw = pd.read_excel(uploaded_file, sheet_name=0)
    registros = []

    for _, row in df_raw.iterrows():
        primeira_col = row.iloc[0]
        if pd.notna(primeira_col) and str(primeira_col).strip().isdigit():
            row_vals = [str(x).strip() for x in row.values if pd.notna(x) and str(x).strip() != "nan"]
            
            solicitacao = str(row.iloc[0]).strip()
            
            # Hora
            hora = ""
            for val in row_vals:
                if re.match(r'^\d{2}:\d{2}$', val):
                    hora = val
                    break
            if not hora and len(row.values) > 23 and pd.notna(row.iloc[23]):
                hora = str(row.iloc[23]).strip()

            # Leito
            leito = ""
            for val in row_vals:
                val_upper = val.upper()
                if any(p in val_upper for p in ["ESTAB", "OBS", "EXTRA", "ISO", "OBES", "MED", "EX"]) or re.match(r'^\d{3}\s*[A-D]?$', val_upper):
                    leito = val
                    break
            if not leito and len(row.values) > 25 and pd.notna(row.iloc[25]):
                leito = str(row.iloc[25]).strip()
            if not leito:
                leito = "PA"

            # Tipo de Limpeza
            tipo_limpeza = "TERMINAL DE LEITO"
            for val in row_vals:
                val_upper = val.upper()
                if "CONCORRENTE" in val_upper:
                    tipo_limpeza = "CONCORRENTE"
                    break
                elif "TERMINAL" in val_upper:
                    tipo_limpeza = "TERMINAL DE LEITO"
                    break

            # Funcionário
            funcionario = ""
            if len(row.values) > 36 and pd.notna(row.iloc[36]):
                funcionario = str(row.iloc[36]).strip()
            else:
                for val in reversed(row_vals):
                    val_upper = val.upper()
                    if val_upper not in [tipo_limpeza.upper(), leito.upper(), hora, solicitacao] and not val.isdigit() and len(val) > 3:
                        funcionario = val
                        break

            setor_mapeado = identificar_setor(leito)
            turno_mapeado = identificar_turno(hora)

            registros.append({
                "Solicitação": solicitacao,
                "Hora": hora,
                "Turno": turno_mapeado,
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
        "os dados em tempo real com total segurança (dados de pacientes e atendimentos ocultados)."
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
                st.info("🔒 **LGPD Ativada:** Nomes de pacientes e números de atendimento foram excluídos do processamento para garantir total sigilo.")

                # Filtros
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    unidades_disponiveis = ["Todas"] + list(df_limpeza["Unidade de Internação"].unique())
                    unidade_filtro = st.selectbox("Filtrar por Unidade de Internação", unidades_disponiveis)
                with col_f2:
                    tipos_disponiveis = ["Todos"] + list(df_limpeza["Tipo de Limpeza"].unique())
                    tipo_filtro = st.selectbox("Filtrar por Tipo de Limpeza", tipos_disponiveis)
                with col_f3:
                    turnos_disponiveis = ["Todos"] + list(df_limpeza["Turno"].unique())
                    turno_filtro = st.selectbox("Filtrar por Turno", turnos_disponiveis)

                # Aplicando filtros
                df_filtrado = df_limpeza.copy()
                if unidade_filtro != "Todas":
                    df_filtrado = df_filtrado[df_filtrado["Unidade de Internação"] == unidade_filtro]
                if tipo_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["Tipo de Limpeza"] == tipo_filtro]
                if turno_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["Turno"] == turno_filtro]

                m1, m2, m3 = st.columns(3)
                m1.metric("Total de Limpezas Filtradas", len(df_filtrado))
                m2.metric("Limpezas Terminais", len(df_filtrado[df_filtrado["Tipo de Limpeza"].str.contains("TERMINAL", case=False, na=False)]))
                m3.metric("Limpezas Concorrentes", len(df_filtrado[df_filtrado["Tipo de Limpeza"].str.contains("CONCORRENTE", case=False, na=False)]))

                st.markdown("---")

                # Gráficos maiores e com a legenda lateral ativada
                g1, g2 = st.columns(2)
                with g1:
                    st.subheader("Distribuição por Tipo de Limpeza")
                    tipo_counts = df_filtrado["Tipo de Limpeza"].value_counts().reset_index()
                    tipo_counts.columns = ["Tipo de Limpeza", "Quantidade"]
                    fig_tipo = px.pie(
                        tipo_counts,
                        names="Tipo de Limpeza",
                        values="Quantidade",
                        title="Proporção de Limpezas",
                        color_discrete_sequence=["#FF5733", "#3357FF"]
                    )
                    fig_tipo.update_layout(
                        height=480,
                        font=dict(size=14),
                        legend=dict(font=dict(size=14)),
                        title_font=dict(size=16)
                    )
                    st.plotly_chart(fig_tipo, use_container_width=True)

                with g2:
                    st.subheader("Limpezas por Unidade de Internação")
                    unidade_counts = df_filtrado["Unidade de Internação"].value_counts().reset_index()
                    unidade_counts.columns = ["Unidade", "Quantidade"]
                    fig_unidade = px.bar(
                        unidade_counts,
                        x="Unidade",
                        y="Quantidade",
                        text_auto=True,
                        title="Volume por Unidade",
                        color="Unidade",
                        color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    # Legenda lateral ativada e dimensionada adequadamente
                    fig_unidade.update_layout(
                        height=500,
                        font=dict(size=13),
                        xaxis=dict(showticklabels=False, title="Unidades de Internação"), # Oculta os nomes longos no eixo X para dar lugar à legenda lateral limpa
                        yaxis=dict(tickfont=dict(size=13), title_font=dict(size=14)),
                        title_font=dict(size=16),
                        legend=dict(title=dict(text="<b>Unidades</b>"), font=dict(size=12), orientation="v"),
                        showlegend=True
                    )
                    st.plotly_chart(fig_unidade, use_container_width=True)

                st.subheader("Tabela Detalhada de Limpezas (Segura)")
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

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
            fig_cost.update_layout(height=450, font=dict(size=13))
            st.plotly_chart(fig_cost, use_container_width=True)
        with c2:
            st.subheader("Service Orders by Priority Level")
            priority_counts = df["priority"].value_counts().reset_index()
            priority_counts.columns = ["priority", "count"]
            fig_pie = px.pie(priority_counts, names="priority", values="count", color="priority", title="Tickets Distribution by Priority")
            fig_pie.update_layout(height=450, font=dict(size=13))
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Detailed Transformed Data Table")
        st.dataframe(df, use_container_width=True, hide_index=True)

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
