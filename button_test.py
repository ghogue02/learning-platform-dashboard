import streamlit as st
import pandas as pd

st.write(f"Streamlit version (test app): {st.__version__}") # Verify version in test app too

data = {'col1': ['A', 'B', 'C'], 'col2': [1, 2, 3]}
df = pd.DataFrame(data)

def button_function(row):
    st.write(f"Button clicked for row: {row}")

df["Button Column"] = "" # Just to create the column

st.dataframe(
    df,
    column_config={
        "Button Column": st.column_config.ButtonColumn(
            "Click Me",
            on_click=button_function,
            args=(df.index,), # Pass index as arg
            kwargs={},
            width="small"
        )
    }
)