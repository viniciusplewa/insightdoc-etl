import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# Add src directories to module path
from rag.llm_chain import generate_rag_response

# Page configuration
st.set_page_config(
    page_title="InsightDoc-ETL | Hospital Analytics & RAG",
    page_icon="📊",
    layout="wide"
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

# Main Title & Header
st.title("🏥 InsightDoc-ETL: Operational Analytics & AI Assistant")
st.markdown("---")

# Navigation Tabs
tab1, tab2 = st.tabs(["📊 Executive KPIs & Analytics", "🤖 AI Document Assistant (RAG)"])

# ---------------------------------------------------------
# TAB 1: EXECUTIVE DASHBOARD
# ---------------------------------------------------------
with tab1:
    st.header("Hospital Service Orders Performance Dashboard")
    
    df = load_data()
    
    if df is None:
        st.warning("⚠️ Database not found! Please run `python src/etl/transform.py` to populate data.")
    else:
        # High Level Metric Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Service Orders", f"{len(df):,}")
        col2.metric("Total Estimated Cost", f"${df['estimated_cost'].sum():,.2f}")
        col3.metric("Avg Resolution Time", f"{df['duration_hours'].mean():.2f} hrs")
        col4.metric("Urgent Tickets", f"{len(df[df['priority'] == 'URGENT'])}")
        
        st.markdown("---")
        
        # Interactive Charts Grid
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Total Costs by Department")
            cost_by_dept = df.groupby('department')['estimated_cost'].sum().reset_index()
            fig_cost = px.bar(
                cost_by_dept, 
                x='department', 
                y='estimated_cost',
                color='department',
                text_auto='.2s',
                title="Total Operational Spend per Department ($)"
            )
            st.plotly_chart(fig_cost, use_container_width=True)
            
        with c2:
            st.subheader("Service Orders by Priority Level")
            priority_counts = df['priority'].value_index if hasattr(df['priority'], 'value_index') else df['priority'].value_counts().reset_index()
            priority_counts.columns = ['priority', 'count']
            fig_pie = px.pie(
                priority_counts, 
                names='priority', 
                values='count',
                color='priority',
                title="Tickets Distribution by Priority"
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Detailed Transformed Data Table")
        st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: RAG CHAT ASSISTANT
# ---------------------------------------------------------
with tab2:
    st.header("Interactive RAG Audit Query System")
    st.caption("Ask questions about internal audit reports, equipment maintenance, and facility guidelines.")
    
    # Initialize Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am your AI operational analyst. Ask me anything about the hospital's internal audit reports!"}
        ]
        
    # Render previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # User Input
    if prompt := st.chat_input("Ex: What were the audit findings for Pediatrics or ICU Adult?"):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Generate RAG response
        with st.chat_message("assistant"):
            with st.spinner("Searching vector database & analyzing documents..."):
                response = generate_rag_response(prompt)
                st.markdown(response)
                
        st.session_state.messages.append({"role": "assistant", "content": response})