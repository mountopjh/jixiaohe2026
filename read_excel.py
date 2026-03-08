import pandas as pd

try:
    df = pd.read_excel('bank2025.2/bin-list-data2025.2 - 副本.xlsx', dtype=str, nrows=5)
    print("COLUMNS:")
    print(df.columns.tolist())
    print("DATA:")
    print(df.head())
except Exception as e:
    print(e)
