import pandas as pd
from gitscore.db.database import engine

df = pd.read_sql("SELECT * FROM profile_features", engine,)
print(df.head())
print(df.shape)
print(df.dtypes)
print(df.isna().sum())