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

# Injeção de CSS Customizado para cartões coloridos modernos
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

# Função vetorizada para mapear setores baseada nos leitos
def identificar_setor_serie(leitos_series):
    leitos_upper = leitos_series.fillna("PA").astype(str).str.strip().str.upper()
    
    setores = pd.Series("PA (Pronto Atendimento)", index=leitos_series.index)
    num_leitos = leitos_upper.str.extract(r'(\d+)', expand=False).astype(float)
    
    setores[leitos_upper.str.contains("OBS M|OBS F|EXTRA|ESTAB|MED|EX", na=False)] = "PA (Pronto Atendimento)"
    
    setores[(num_leitos >= 101) & (num_leitos <= 112)] = "Semi intensiva (1 andar)"
    setores[(num_leitos >= 113) & (num_leitos <= 122)] = "Hospital dia (1 andar)"
    setores[(num_leitos >= 200) & (num_leitos <= 299)] = "Clínica Médica (2 andar)"
    setores[(num_leitos >= 301) & (num_leitos <= 310)] = "Clínica cirúrgica 1 (3 andar)"
    setores[(num_leitos >= 311) & (num_leitos <= 320)] = "Clínica cirúrgica pediátrica (3 andar)"
    setores[(num_leitos >= 321) & (num_leitos <= 330)] = "UTI 1 (3 andar)"
    setores[(num_leitos >= 331) & (num_leitos <= 340)] = "UTI 5 (3 andar)"
    setores[(num_leitos >= 341) & (num_leitos <= 350)] = "UTI Pediátrica (3 andar)"
    setores[(num_leitos >= 401) & (num_leitos <= 420)] = "Clínica cirúrgica 2 (4 andar)"
    setores[(num_leitos >= 421) & (num_leitos <= 430)] = "UTI 2 (4 andar)"
    setores[(num_leitos >= 431) & (num_leitos <= 440)] = "UTI 3 (4 andar)"
    setores[(num_leitos >= 441) & (num_leitos <= 450)] = "UTI 4 (4 andar)"
    setores[(num_leitos >= 501) & (num_leitos <= 520)] = "Clínica cirúrgica 3 (5 andar)"
    
    return setores

# Função vetorizada para classificar o turno com base na hora
def identificar_turno_serie(horas_series):
    horas_str = horas_series.fillna("").astype(str).str.strip()
    turnos = pd.Series("Não Especificado", index=horas_series.index)
    
    match_hora = horas_str.str.extract(r'(\d{2}):(\d{2})', expand=True)
    valido = match_hora[0].notna()
    
    if valido.any():
        h_num = match_hora[0][valido].astype(int)
        m_num = match_hora[1][valido].astype(int)
        total_min = h_num * 60 + m_num
        
        diurno = (total_min >= 420) & (total_min <= 1140) # 07:00 a 19:00
        turnos[valido & diurno] = "Diurno (07:00 - 19:00)"
        turnos[valido & ~diurno] = "Noturno"
        
    return turnos

# Função de processamento otimizada
def processar_relatorio_limpeza(uploaded_file, nome_origem):
    nome_arquivo = uploaded_file.name.lower()
    
    try:
        if nome_arquivo.endswith('.csv'):
            try:
                df_raw = pd.read_csv(uploaded_file, encoding='utf-8', sep=None, engine='python', dtype=str, nrows=300000)
            except Exception:
                uploaded_file.seek(0)
                df_raw = pd.read_csv(uploaded_file, encoding='latin1', sep=None, engine='python', dtype=str, nrows=300000)
        else:
            df_raw = pd.read_excel(uploaded_file, sheet_name=0, dtype=str, engine="openpyxl")
    except Exception as e:
        st.error(f"Erro ao ler o arquivo {uploaded_file.name}: {e}")
        return pd.DataFrame()
    
    df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
    
    col_sol = next((c for c in df_raw.columns if any(k in c for k in ["SOLICITA", "COD", "ID", "REGISTRO"])), df_raw.columns[0])
    col_leito = next((c for c in df_raw.columns if any(k in c for k in ["LEITO", "QUARTO", "LOCAL", "AMBIENTE"])), None)
    col_tipo = next((c for c in df_raw.columns if any(k in c for k in ["TIPO", "LIMPEZA"])), None)

    solicitacao = df_raw[col_sol].fillna("").astype(str).str.strip()
    
    hora = pd.Series("", index=df_raw.index)
    candidatas_hora = [c for c in df_raw.columns if any(k in c for k in ["HORA", "DATA", "EMISSAO"])]
    
    for col in candidatas_hora:
        amostra = df_raw[col].fillna("").astype(str).str.strip()
        if amostra.str.contains(r'\d{2}:\d{2}', na=False).any():
            hora = amostra.str.extract(r'(\d{2}:\d{2})', expand=False).fillna("")
            break
            
    if (hora == "").all():
        for col in df_raw.columns[:15]:
            amostra = df_raw[col].fillna("").astype(str).str.strip()
            if amostra.head(100).str.contains(r'\d{2}:\d{2}', na=False).any():
                hora = amostra.str.extract(r'(\d{2}:\d{2})', expand=False).fillna("")
                break

    leito = pd.Series("PA", index=df_raw.index)
    if col_leito and col_leito in df_raw.columns:
        leito = df_raw[col_leito].fillna("PA").astype(str).str.strip()
        leito = leito.replace("", "PA")
    else:
        for col in df_raw.columns[:15]:
            amostra = df_raw[col].fillna("").astype(str).str.upper()
            if amostra.head(100).str.contains("ESTAB|OBS|EXTRA|ISO|OBES|MED", na=False).any():
                leito = df_raw[col].fillna("PA").astype(str).str.strip()
                break

    tipo_limpeza = pd.Series("TERMINAL DE LEITO", index=df_raw.index)
    if col_tipo and col_tipo in df_raw.columns:
        val_tipo = df_raw[col_tipo].fillna("").astype(str).str.upper()
        tipo_limpeza = val_tipo.apply(lambda x: "CONCORRENTE" if "CONCORRENTE" in x else "TERMINAL DE LEITO")
    else:
        for col in df_raw.columns[:15]:
            amostra = df_raw[col].fillna("").astype(str).str.upper()
            if amostra.head(100).str.contains("CONCORRENTE|TERMINAL", na=False).any():
                val_tipo = df_raw[col].fillna("").astype(str).str.upper()
                tipo_limpeza = val_tipo.apply(lambda x: "CONCORRENTE" if "CONCORRENTE" in x else "TERMINAL DE LEITO")
                break

    funcionario_protegido = pd.Series("🔒 [LGPD Ocultado]", index=df_raw.index)

    df_final = pd.DataFrame({
        "Origem / Período": nome_origem,
        "Solicitação": solicitacao,
        "Hora": hora,
        "Turno": identificar_turno_serie(hora),
        "Leito": leito,
        "Tipo de Limpeza": tipo_limpeza,
        "Funcionário / Paciente": funcionario_protegido,
        "Unidade de Internação": identificar_setor_serie(leito),
    })

    df_final = df_final[df_final["Solicitação"] != ""].copy()
    return df_final

# Main Title & Header
st.title("🏥 InsightDoc-ETL: Gestão Hospitalar & Comparador de Limpezas")
st.markdown("---")

st.header("Análise Comparativa de Relatórios de Quartos")
st.markdown(
    "Faça o upload de **uma ou duas planilhas** para realizar análises isoladas ou uma **comparação lado a lado** "
    "com total segurança (LGPD Ativada)."
)

col_up1, col_up2 = st.columns(2)
with col_up1:
    arquivo_1 = st.file_uploader("📂 Enviar 1ª Planilha (Ex: Período A)", type=["xlsx", "xls", "csv"], key="file1")
with col_up2:
    arquivo_2 = st.file_uploader("📂 Enviar 2ª Planilha (Opcional - Ex: Período B)", type=["xlsx", "xls", "csv"], key="file2")

dfs_combinados = []

if arquivo_1 is not None:
    with st.spinner("A processar a 1ª planilha..."):
        df1 = processar_relatorio_limpeza(arquivo_1, "Planilha 1 (A)")
        if not df1.empty:
            dfs_combinados.append(df1)

if arquivo_2 is not None:
    with st.spinner("A processar a 2ª planilha..."):
        df2 = processar_relatorio_limpeza(arquivo_2, "Planilha 2 (B)")
        if not df2.empty:
            dfs_combinados.append(df2)

if len(dfs_combinados) > 0:
    df_limpeza = pd.concat(dfs_combinados, ignore_index=True)

    if df_limpeza.empty:
        st.warning("⚠️ Não foram encontrados registros estruturados nas planilhas enviadas.")
    else:
        st.success(f"Dados processados com sucesso! Total de registros combinados: {len(df_limpeza):,}".replace(",", "."))
        st.info("🔒 **LGPD Ativada:** Nomes de pacientes e dados confidenciais foram totalmente ocultados.")

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

        df_filtrado = df_limpeza.copy()
        if unidade_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Unidade de Internação"] == unidade_filtro]
        if tipo_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Tipo de Limpeza"] == tipo_filtro]
        if turno_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Turno"] == turno_filtro]

        # 1. MÉTRICAS COLORIDAS E COMPARATIVO DE DIFERENÇAS
        st.markdown("### 📊 Métricas por Planilha & Comparativo")
        origens_presentes = df_filtrado["Origem / Período"].unique()
        
        valores_metricas = {}

        cols_met = st.columns(len(origens_presentes) if len(origens_presentes) > 0 else 1)
        for i, orig in enumerate(origens_presentes):
            df_orig = df_filtrado[df_filtrado["Origem / Período"] == orig]
            tot = len(df_orig)
            term = len(df_orig[df_orig["Tipo de Limpeza"].str.contains("TERMINAL", case=False, na=False)])
            conc = len(df_orig[df_orig["Tipo de Limpeza"].str.contains("CONCORRENTE", case=False, na=False)])
            
            valores_metricas[orig] = {"Total": tot, "Terminais": term, "Concorrentes": conc}
            
            css_class = "metric-card-1" if i == 0 else "metric-card-2"
            
            with cols_met[i]:
                st.markdown(f"**📌 {orig}**")
                st.markdown(f"""
                <div class="{css_class}">
                    <div style="display: flex; justify-content: space-between;">
                        <div><span style="font-size: 13px; color: #555;">Total</span><br><b style="font-size: 24px;">{tot:,}</b></div>
                        <div><span style="font-size: 13px; color: #555;">Terminais</span><br><b style="font-size: 24px;">{term:,}</b></div>
                        <div><span style="font-size: 13px; color: #555;">Concorrentes</span><br><b style="font-size: 24px;">{conc:,}</b></div>
                    </div>
                </div>
                """.replace(",", "."), unsafe_allow_html=True)

        # Se houver duas planilhas, exibe o cartão de diferença com formatação segura
        if len(origens_presentes) == 2:
            p1, p2 = origens_presentes[0], origens_presentes[1]
            m1, m2 = valores_metricas[p1], valores_metricas[p2]
            
            diff_tot = m2["Total"] - m1["Total"]
            pct_tot = (diff_tot / m1["Total"] * 100) if m1["Total"] > 0 else 0
            
            diff_term = m2["Terminais"] - m1["Terminais"]
            pct_term = (diff_term / m1["Terminais"] * 100) if m1["Terminais"] > 0 else 0
            
            diff_conc = m2["Concorrentes"] - m1["Concorrentes"]
            pct_conc = (diff_conc / m1["Concorrentes"] * 100) if m1["Concorrentes"] > 0 else 0
            
            sinal_tot = "+" if diff_tot > 0 else ""
            sinal_term = "+" if diff_term > 0 else ""
            sinal_conc = "+" if diff_conc > 0 else ""
            
            sinal_pct_tot = "+" if pct_tot > 0 else ""
            sinal_pct_term = "+" if pct_term > 0 else ""
            sinal_pct_conc = "+" if pct_conc > 0 else ""

            st.markdown(f"""
            <div style="background-color: #f8f9fa; padding: 14px; border-radius: 10px; border: 1px solid #ddd; margin-top: 12px;">
                <b style="color: #333;">📈 Diferença ({p2} vs {p1}):</b>
                <div style="display: flex; justify-content: space-around; margin-top: 8px; font-size: 14px;">
                    <div><b>Total:</b> {sinal_tot}{diff_tot:,} ({sinal_pct_tot}{pct_tot:.2f}%)</div>
                    <div><b>Terminais:</b> {sinal_term}{diff_term:,} ({sinal_pct_term}{pct_term:.2f}%)</div>
                    <div><b>Concorrentes:</b> {sinal_conc}{diff_conc:,} ({sinal_pct_conc}{pct_conc:.2f}%)</div>
                </div>
            </div>
            """.replace(",", "."), unsafe_allow_html=True)

        st.markdown("---")

        # 2. GRÁFICOS DE PIZZA SEPARADOS
        st.subheader("Proporção por Tipo de Limpeza (Separado por Planilha)")
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

        # 3. GRÁFICO DE BARRAS
        st.subheader("Volume por Unidade de Internação (Comparativo)")
        ordem_unidades = df_filtrado.groupby("Unidade de Internação").size().sort_values(ascending=False).index.tolist()

        fig_unidade = px.histogram(
            df_filtrado,
            x="Unidade de Internação",
            color="Origem / Período",
            barmode="group",
            title="Comparativo de Volume entre Planilhas",
            text_auto=True,
            category_orders={"Unidade de Internação": ordem_unidades},
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

        # 4. GRÁFICO DE LINHA TEMPORAL COMPARATIVO
        st.markdown("---")
        st.subheader("📈 Comparativo de Picos por Horário do Dia (00h às 23h)")
        
        def extrair_hora_inteira(hora_str):
            if not hora_str or ":" not in str(hora_str):
                return None
            try:
                return int(str(hora_str).split(":")[0])
            except Exception:
                return None

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
        
        text_positions = []
        for _, row in df_horas_final.iterrows():
            if row["Origem / Período"] != origens_presentes[0]:
                text_positions.append("bottom center")
            else:
                text_positions.append("top center")

        fig_hora.update_traces(
            mode="lines+markers+text",
            text=df_horas_final["Quantidade"],
            textposition=text_positions,
            textfont=dict(size=10, family="Arial Black"),
            line=dict(width=3)
        )
        fig_hora.update_layout(
            height=650,
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
    st.info("👆 Por favor, faça o upload de pelo menos uma planilha (Excel ou CSV) acima para iniciar as análises.")
