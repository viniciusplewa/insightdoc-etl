import os
import re
import pandas as pd
import plotly.express as px
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="InsightDoc-ETL | Hospital Analytics & Limpezas",
    page_icon="🏥",
    layout="wide",
)

# Injeção de CSS Customizado para UI/UX moderna
st.markdown(
    """
    <style>
    .stMetric {
        background-color: #fdfefe;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #e1e4e8;
    }
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

            # Gráficos Principais (Distribuição e Unidades)
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
                fig_unidade.update_layout(
                    height=500,
                    font=dict(size=13),
                    xaxis=dict(showticklabels=False, title="Unidades de Internação"),
                    yaxis=dict(tickfont=dict(size=13), title_font=dict(size=14)),
                    title_font=dict(size=16),
                    legend=dict(title=dict(text="<b>Unidades</b>"), font=dict(size=12), orientation="v"),
                    showlegend=True
                )
                st.plotly_chart(fig_unidade, use_container_width=True)

            # Gráfico de Picos por Horário limpo, elegante e com números fixos visíveis
            st.markdown("---")
            st.subheader("📈 Picos de Solicitações por Horário do Dia")
            
            def extrair_hora_inteira(hora_str):
                if not hora_str or ":" not in str(hora_str):
                    return "Desconhecido"
                return str(hora_str).split(":")[0] + "h"

            df_filtrado["Hora_Cheia"] = df_filtrado["Hora"].apply(extrair_hora_inteira)
            hora_counts = df_filtrado["Hora_Cheia"].value_counts().reset_index()
            hora_counts.columns = ["Hora", "Quantidade"]
            hora_counts = hora_counts.sort_values(by="Hora")

            fig_hora = px.line(
                hora_counts,
                x="Hora",
                y="Quantidade",
                markers=True,
                title="Evolução do Volume de Limpezas ao Longo do Dia",
                color_discrete_sequence=["#2980B9"] # Azul profissional elegante
            )
            # Torna os números visíveis permanentemente em cima dos pontos e destaca os marcadores
            fig_hora.update_traces(
                mode="lines+markers+text",
                text=hora_counts["Quantidade"],
                textposition="top center",
                textfont=dict(size=13, color="#1B4F72", family="Arial Black"),
                line=dict(width=3)
            )
            fig_hora.update_layout(
                height=450,
                font=dict(size=13),
                xaxis=dict(title="Hora do Dia", tickfont=dict(size=12)),
                yaxis=dict(title="Número de Limpezas", tickfont=dict(size=12)),
                title_font=dict(size=16),
                showlegend=False
            )
            st.plotly_chart(fig_hora, use_container_width=True)

            st.markdown("---")
            
            # Botão de Download com codificação corrigida para o Excel abrir com acentos perfeitos
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                st.subheader("Tabela Detalhada de Limpezas (Segura)")
            with col_d2:
                # utf-8-sig resolve o problema de acentuação corrompida (ex: Solicitação / Funcionário) no Excel do Windows
                csv_bytes = df_filtrado.drop(columns=["Hora_Cheia"], errors="ignore").to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    label="📥 Baixar CSV Corrigido",
                    data=csv_bytes,
                    file_name="relatorio_limpezas_hospitalares.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            st.dataframe(df_filtrado.drop(columns=["Hora_Cheia"], errors="ignore"), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Erro ao processar o arquivo de limpeza: {e}")
else:
    st.info("👆 Por favor, faça o upload da planilha Excel para gerar os gráficos e análises operacionais.")
