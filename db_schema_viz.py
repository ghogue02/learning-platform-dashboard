import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
import graphviz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables (for DB_URL)
load_dotenv()
DB_URL = os.getenv("DB_URL")

def generate_schema_diagram():
    """Generates and saves a database schema diagram with larger size and fonts as a PNG file."""
    engine = None  # Initialize engine outside the try block
    try:
        engine = create_engine(DB_URL) # Create SQLAlchemy engine
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        dot = graphviz.Digraph('database_schema', comment='Database Schema', engine='dot')

        # --- Graph-level attributes to increase size and DPI ---
        dot.attr(rankdir='TB',  # Top-to-bottom layout (TB) - experiment with 'LR' for left-to-right
                 dpi='300',     # Increase DPI for higher resolution
                 size='10,10')  # Initial size of the graph in inches (adjust as needed)


        dot.attr('node', shape='box', fontsize='12', fontname='Arial') # Increased node fontsize
        dot.attr('edge', fontsize='10', fontname='Arial') # Increased edge fontsize


        for table_name in table_names:
            columns = inspector.get_columns(table_name)
            # Start building HTML-like label for table node
            label = f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">\n<TR><TD><B>{table_name}</B></TD></TR>' # Table name as header

            for column in columns:
                column_name = column['name']
                column_type = str(column['type']) # Get column type as string
                label += f'\n<TR><TD ALIGN="LEFT">{column_name}<BR/><FONT POINT-SIZE="10">{column_type}</FONT></TD></TR>' # Increased column type font size

            label += '\n</TABLE>>' # Close HTML-like table
            dot.node(table_name, label) # Use HTML-like label for node

        for table_name in table_names:
            foreign_keys = inspector.get_foreign_keys(table_name)
            for fk in foreign_keys:
                referred_table = fk['referred_table']
                constrained_columns = ", ".join(fk['constrained_columns'])
                referred_columns = ", ".join(fk['referred_columns'])
                label = f"{constrained_columns} -> {referred_columns}"
                dot.edge(table_name, referred_table, label=label)

        diagram_path = "database_schema_diagram_large_font.png" # Changed output filename
        dot.render(diagram_path[:-4], format='png', view=False) # Render to PNG, don't open viewer

        print(f"Detailed database schema diagram (larger size and fonts) generated and saved to: {diagram_path}") # User feedback

    except Exception as e:
        logger.error(f"Error generating detailed database schema visualization (large font): {e}")
        print(f"Error generating detailed database schema visualization (large font). Check logs for details. Error: {e}") # User feedback with error

    finally:
        if engine:
            engine.dispose() # Dispose of the engine connection pool


if __name__ == "__main__":
    generate_schema_diagram()