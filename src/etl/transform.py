import pandas as pd
import sqlite3
import os
from extract import generate_raw_data

def clean_and_transform():
    """
    Cleans raw data, handles missing values, standardizes text fields,
    and loads the transformed dataset into a SQLite database.
    """
    # 1. Load raw data
    if not os.path.exists('data_raw.csv'):
        df = generate_raw_data()
    else:
        df = pd.read_csv('data_raw.csv')
        
    print(f"📊 Raw records loaded: {len(df)}")
    
    # 2. Handle missing values (fill missing costs with category median)
    median_cost = df['estimated_cost'].median()
    df['estimated_cost'] = df['estimated_cost'].fillna(median_cost)
    
    # 3. Text standardization
    df['department'] = df['department'].astype(str).str.title().str.strip()
    df['service_type'] = df['service_type'].astype(str).str.strip()
    df['priority'] = df['priority'].astype(str).str.upper().str.strip()
    
    # 4. Date conversion and feature engineering
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['year_month'] = df['created_at'].dt.to_period('M').astype(str)
    
    # 5. KPI Metrics (convert minutes to hours)
    df['duration_hours'] = (df['duration_minutes'] / 60).round(2)
    
    # 6. Load to SQLite Database
    conn = sqlite3.connect('database.db')
    df.to_sql('service_orders', conn, if_exists='replace', index=False)
    conn.close()
    
    print("✅ Cleaned data successfully loaded into 'service_orders' table in SQLite!")
    print("\n--- Sample Transformed Data ---")
    print(df.head(3))

if __name__ == "__main__":
    clean_and_transform()