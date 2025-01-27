import streamlit as st
import pandas as pd

st.write(f"Streamlit version: **{st.__version__}**") # Keep version display for確認

data = {'Challenge': ['Challenge 1', 'Challenge 2'],
        'Description': ['Description for challenge 1', 'Description for challenge 2'],
        'Example': ['Example 1', 'Example 2'],
        'Severity Level': ['High', 'Medium'],
        'Actionable Recommendation': ['Recommendation 1', 'Recommendation 2']}
df = pd.DataFrame(data)

st.dataframe(df.set_index('Challenge'),
             column_config={
                 "Description": st.column_config.Column(width="large", label="Description"),
                 "Example": st.column_config.Column(width="medium"),
                 "Severity Level": st.column_config.Column(width="small"),
                 "Actionable Recommendation": st.column_config.Column(width="large", label="Recommendation")
             },
             hide_index=False,
             height=200)

st.write("Basic DataFrame displayed with column_config")
