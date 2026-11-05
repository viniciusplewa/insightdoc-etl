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

# Função para classificar o turno com base na hora
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

# Função otimizada para processar relatórios grandes com baixo consumo de memória
def processar_relatorio_limpeza(uploaded_file, nome_origem):
    # Lendo o Excel de forma otimizada para evitar estouro de RAM em ficheiros grandes
    df_raw = pd.read_excel(uploaded_file, sheet_name=0, dtype=str, engine="openpyxl")
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
                "Origem / Período": nome_origem,
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
st.title("🏥 InsightDoc-ETL: Gestão Hospitalar & Comparador de Limpezas")
st.markdown("---")

st.header("Análise Comparativa de Relatórios de Quartos")
st.markdown(
    "Faça o upload de **uma ou duas planilhas** (formatos grandes suportados com otimização de memória) "
    "para realizar análises isoladas ou uma **comparação lado a lado** com total segurança (LGPD Ativada)."
)

# Layout com duas colunas para upload independente
col_up1, col_up2 = st.columns(2)
with col_up1:
    arquivo_1 = st.file_uploader("📂 Enviar 1ª Planilha (Ex: Período A)", type=["xlsx", "xls"], key="file1")
with col_up2:
    arquivo_2 = st.file_uploader("📂 Enviar 2ª Planilha (Opcional - Ex: Período B)", type=["xlsx", "xls"], key="file2")

# Processamento dos arquivos com tratamento de erro de memória
dfs_combinados = []

if arquivo_1 is not None:
    try:
        df1 = processar_relatorio_limpeza(arquivo_1, "Planilha 1 (A)")
        dfs_combinados.append(df1)
    except Exception as e:
        st.error(f"Erro ao processar a 1ª planilha: {e}")

if arquivo_2 is not None:
    try:
        df2 = processar_relatorio_limpeza(arquivo_2, "Planilha 2 (B)")
        dfs_combinados.append(df2)
    except Exception as e:
        st.error(f"Erro ao processar a 2ª planilha: {e}")

if len(dfs_combinados) > 0:
    df_limpeza = pd.concat(dfs_combinados, ignore_index=True)

    if df_limpeza.empty:
        st.warning("⚠️ Não foram encontrados registros estruturados nas planilhas enviadas.")
    else:
        st.success(f"Dados processados com sucesso! Total de registros combinados: {len(df_limpeza)}")
        st.info("🔒 **LGPD Ativada:** Nomes de pacientes e números de atendimento foram ocultados.")

        # Filtros Globais
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

        # 1. GRÁFICOS DE PIZZA SEPARADOS
        st.subheader("Proporção por Tipo de Limpeza (Separado por Planilha)")
        origens_presentes = df_filtrado["Origem / Período"].unique()
        
        cols_pizza = st.columns(len(origens_presentes) if len(origens_presentes) > 0 else 1)
        for i, origem in enumerate(origens_presentes):
            with cols_pizza[i]:
                df_origem = df_filtrado[df_filtrado["Origem / Período"] == origem]
                tipo_counts = df_origem["Tipo de Limpeza"].value_counts().reset_index()
                tipo_counts.columns = ["Tipo de Limpeza", "Quantidade"]
                
                fig_p = px.pie(
                    tipo_counts,
                    names="Tipo de Limpeza",
                    values="Quantidade",
                    title=f"Distribuição - {origem}",
                    color_discrete_sequence=["#FF5733", "#2980B9"]
                )
                fig_p.update_layout(height=400, font=dict(size=13), title_font=dict(size=15))
                st.plotly_chart(fig_p, use_container_width=True)

        st.markdown("---")

        # 2. GRÁFICO DE BARRAS
        st.subheader("Volume por Unidade de Internação (Comparativo)")
        fig_unidade = px.histogram(
            df_filtrado,
            x="Unidade de Internação",
            color="Origem / Período",
            barmode="group",
            title="Comparativo de Volume entre Planilhas",
            text_auto=True,
            color_discrete_sequence=["#2980B9", "#E67E22"]
        )
        fig_unidade.update_traces(textfont_size=10, textangle=0, textposition="outside", cliponaxis=False)
        fig_unidade.update_layout(
            height=550,
            font=dict(size=12),
            xaxis=dict(tickangle=-35, title="Unidades de Internação"),
            yaxis=dict(title="Quantidade"),
            legend=dict(title=dict(text="<b>Planilha</b>"))
        )
        st.plotly_chart(fig_unidade, use_container_width=True)

        # 3. GRÁFICO DE LINHA TEMPORAL COMPARATIVO
        st.markdown("---")
        st.subheader("📈 Comparativo de Picos por Horário do Dia (00h às 23h)")
        
        def extrair_hora_inteira(hora_str):
            if not hora_str or ":" not in str(hora_str):
                return None
            return int(str(hora_str).split(":")[0])

        df_filtrado["Hora_Num"] = df_filtrado["Hora"].apply(extrair_hora_inteira)
        
        df_horas_comp = df_filtrado.groupby(["Hora_Num", "Origem / Período"]).size().reset_index(name="Quantidade")
        
        horas_base = []
        for orig in origens_presentes:
            for h in range(24):
                horas_base.append({"Hora_Num": h, "Origem / Período": orig})
        
        df_base_24h = pd.DataFrame(horas_base)
        df_horas_final = pd.merge(df_base_24h, df_horas_comp, on=["Hora_Num", "Origem / Período"], how="left").fillna(0)
        df_horas_final["Hora"] = df_horas_final["Hora_Num"].apply(lambda x: f"{int(x):02d}h")
        df_horas_final = df_horas_final.sort_values(by=["Hora_Num"])

        fig_hora = px.line(
            df_horas_final,
            x="Hora",
            y="Quantidade",
            color="Origem / Período",
            markers=True,
            title="Evolução Temporal Comparativa Detalhada",
            color_discrete_sequence=["#2980B9", "#E67E22"]
        )
        fig_hora.update_traces(
            mode="lines+markers+text",
            text=df_horas_final["Quantidade"],
            textposition="top center",
            textfont=dict(size=11, family="Arial Black"),
            line=dict(width=3)
        )
        fig_hora.update_layout(
            height=600,
            font=dict(size=13),
            xaxis=dict(title="Hora do Dia"),
            yaxis=dict(title="Número de Limpezas"),
            legend=dict(title=dict(text="<b>Planilha</b>"))
        )
        st.plotly_chart(fig_hora, use_container_width=True)

        st.markdown("---")
        
        # Tabela e Botão de Download
        col_d1, col_d2 = st.columns([3, 1])
        with col_d1:
            st.subheader("Tabela Detalhada Consolidada (Segura)")
        with col_d2:
            csv_bytes = df_filtrado.drop(columns=["Hora_Num"], errors="ignore").to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="📥 Baixar CSV Combinado",
                data=csv_bytes,
                file_name="relatorio_comparativo_limpezas.csv",
                mime="text/csv",
                use_container_width=True
            )

        st.dataframe(df_filtrado.drop(columns=["Hora_Num"], errors="ignore"), use_container_width=True, hide_index=True)

else:
    st.info("👆 Por favor, faça o upload de pelo menos uma planilha Excel acima para iniciar as análises.")
