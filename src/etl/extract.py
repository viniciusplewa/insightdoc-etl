import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_raw_data(num_records=200):
    """
    Simulates raw data extraction of service orders / tickets from an operational system.
    Introduces deliberate inconsistencies (null values, mixed casing) to mimic 
    a real-world environment requiring data cleaning.
    """
    np.random.seed(42)
    
    departments = ['ICU Adult', 'Emergency Room', 'Surgical Center', 'Pediatrics', 'Outpatient Clinic']
    service_types = ['Preventive Maintenance', 'Advanced Sanitation', 'Equipment Repair', 'Technical Inspection']
    priorities = ['Low', 'Medium', 'High', 'URGENT']
    
    start_date = datetime(2026, 1, 1)
    
    data = []
    for i in range(1, num_records + 1):
        order_id = f"OS-{1000 + i}"
        department = np.random.choice(departments)
        service = np.random.choice(service_types)
        priority = np.random.choice(priorities)
        
        # Simulate timestamps over past months
        created_at = start_date + timedelta(days=int(np.random.randint(0, 180)), hours=int(np.random.randint(0, 23)))
        duration_minutes = int(np.random.randint(15, 300))
        
        # Introduce inconsistent casing
        if np.random.rand() < 0.05:
            department = department.lower()
        
        estimated_cost = round(float(np.random.uniform(50.0, 1200.0)), 2)
        
        # Introduce occasional missing values
        if np.random.rand() < 0.03:
            estimated_cost = None
            
        data.append({
            'order_id': order_id,
            'department': department,
            'service_type': service,
            'priority': priority,
            'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_minutes': duration_minutes,
            'estimated_cost': estimated_cost
        })
        
    df = pd.DataFrame(data)
    
    # Save raw dataset to simulate source file
    df.to_csv('data_raw.csv', index=False)
    print("✅ Raw data extracted and saved to 'data_raw.csv'.")
    return df

if __name__ == "__main__":
    generate_raw_data()