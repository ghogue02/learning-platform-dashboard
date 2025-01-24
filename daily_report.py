import os
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DB_URL = os.getenv("DB_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def get_new_data():
    """
    Connects to the Postgres database and retrieves rows created/updated
    in the last 24 hours (where possible).
    We'll store them in a dictionary keyed by table name.
    """
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    yesterday = datetime.now() - timedelta(days=1)
    data_map = {}

    # conversation_messages
    cursor.execute("""
        SELECT message_id, user_id, thread_id,
               LEFT(content, 100) AS content_snippet,
               created_at
        FROM conversation_messages
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """, (yesterday,))
    data_map['conversation_messages'] = cursor.fetchall()

    # lesson_session_messages
    cursor.execute("""
        SELECT message_id, session_id,
               role,
               LEFT(content, 100) AS content_snippet,
               created_at
        FROM lesson_session_messages
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """, (yesterday,))
    data_map['lesson_session_messages'] = cursor.fetchall()

    # lesson_sessions (has created_at and updated_at)
    cursor.execute("""
        SELECT session_id, user_id, lesson_id,
               status, lab_status,
               created_at, updated_at
        FROM lesson_sessions
        WHERE created_at >= %s
           OR updated_at >= %s
        ORDER BY updated_at DESC
    """, (yesterday, yesterday))
    data_map['lesson_sessions'] = cursor.fetchall()

    # lessons (has created_at and updated_at)
    cursor.execute("""
        SELECT lesson_id, path, title,
               LEFT(content, 100) AS content_snippet,
               created_at, updated_at
        FROM lessons
        WHERE created_at >= %s
           OR updated_at >= %s
        ORDER BY updated_at DESC
    """, (yesterday, yesterday))
    data_map['lessons'] = cursor.fetchall()

    # submissions (only created_at)
    cursor.execute("""
        SELECT submission_id, user_id, lesson_id, unit_id,
               LEFT(lab_url, 100) AS lab_url_snippet,
               type, LEFT(ai_feedback, 100) AS ai_feedback_snippet,
               grade, created_at
        FROM submissions
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """, (yesterday,))
    data_map['submissions'] = cursor.fetchall()

    # threads (created_at, updated_at)
    cursor.execute("""
        SELECT thread_id, user_id, title,
               created_at, updated_at
        FROM threads
        WHERE created_at >= %s
           OR updated_at >= %s
        ORDER BY updated_at DESC
    """, (yesterday, yesterday))
    data_map['threads'] = cursor.fetchall()

    # units (created_at, updated_at)
    cursor.execute("""
        SELECT unit_id, title,
               LEFT(description, 100) AS description_snippet,
               created_at, updated_at
        FROM units
        WHERE created_at >= %s
           OR updated_at >= %s
        ORDER BY updated_at DESC
    """, (yesterday, yesterday))
    data_map['units'] = cursor.fetchall()

    # user_progress (completed_at)
    cursor.execute("""
        SELECT progress_id, user_id, lesson_id, unit_id,
               is_unlocked, is_completed, completed_at
        FROM user_progress
        WHERE completed_at >= %s
          AND completed_at IS NOT NULL
        ORDER BY completed_at DESC
    """, (yesterday,))
    data_map['user_progress'] = cursor.fetchall()

    # users (only created_at)
    cursor.execute("""
        SELECT user_id, first_name, last_name, email,
               created_at
        FROM users
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """, (yesterday,))
    data_map['users'] = cursor.fetchall()

    cursor.close()
    conn.close()
    return data_map

def generate_summary(data_map):
    """
    Builds a text summary of new/updated rows from each table,
    then sends it to OpenAI for a summarized bullet-point report.
    """
    overview_str = "Daily Database Updates (last 24 hours):\n\n"
    no_changes = True

    for table_name, rows in data_map.items():
        if rows:
            no_changes = False
            overview_str += f"Table: {table_name}\n"
            overview_str += f"Number of new/updated rows: {len(rows)}\n"
            for row in rows[:5]:  # show up to 5 as a preview
                overview_str += f"  Row preview: {row}\n"
            overview_str += "...\n\n"

    if no_changes:
        overview_str = "No new or updated rows in the last 24 hours."

    prompt = f"""
    You are a data analysis assistant. Below are database changes from the last 24 hours
    across multiple tables. Summarize the important points, trends, or anomalies in bullet points.
    
    Data overview:
    {overview_str}
    """

    response = client.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=[
            {"role": "system", "content": "You are an expert data analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

def main():
    data_map = get_new_data()
    summary = generate_summary(data_map)
    print("---------- DAILY REPORT ----------")
    print(summary)

if __name__ == "__main__":
    main()