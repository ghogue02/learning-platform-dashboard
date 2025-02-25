import streamlit as st
import pandas as pd
import openai
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import logging
from openai import OpenAI, APIError
from summarize_analyses import summarize_lesson_analyses, format_lesson_insights_for_output, format_executive_summary_table_data
import json
from airtable import Airtable
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Learning Platform Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.environ.get("DB_URL")
# engine = create_engine(DB_URL) # Moved inside functions
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# --- Airtable Configuration ---
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_KEY = os.getenv("AIRTABLE_BASE_KEY")
AIRTABLE_TABLE_NAME = "fellows"
AIRTABLE_VIEW_NAME = "Leaderboard Test" # ADDED: View Name

airtable = Airtable(AIRTABLE_BASE_KEY, AIRTABLE_TABLE_NAME, api_key=AIRTABLE_API_KEY)

# --- Static Folder Configuration ---
STATIC_FOLDER = os.path.join(os.getcwd(), "data") # Path to your 'data' directory
print(f"DEBUG: Static Folder Path: {STATIC_FOLDER}") # DEBUG PRINT - Check path
# -----------------------------------------------------


def main():
    st.title("Learning Platform Analytics Dashboard")
    st.write(f"Streamlit version: **{st.__version__}**")
    engine = create_engine(DB_URL) # Create engine here

    # --- Apply Basic Dark Theme using CSS ---
    st.markdown(
        """
        <style>
            body {
                color: white;
                background-color: #1E1E1E; /* Dark background color */
            }
            .stDataFrame th, .stDataFrame td {
                color: white !important; /* Ensure table text is white */
                border-color: #333 !important; /* Darker border color for table */
            }
            .stApp {
                background-color: #1E1E1E;
            }
            .css-1egvi7u { /* Streamlit elements background (e.g., sidebar) */
                background-color: #282828;
            }
            .css-ke7b8c { /* Streamlit widget text color */
                color: white;
            }
            .css-1adrpw7 { /* Metric value color */
                color: white !important;
            }
            .css-1bb5s3u { /* Metric label color */
                color: #ddd; /* Slightly lighter text for labels */
            }
            /* --- More Specific CSS for profile pictures --- */
            .stDataFrame tr > td:nth-child(1) img { /* Target images in the FIRST column's td */
                width: 60px !important; /* Increased width */
                height: 60px !important; /* Increased height */
                border-radius: 50%; /* Optional: Keep circular shape */
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # --- End Dark Theme CSS ---

    menu = ["Metrics Dashboard", "Users", "Content Analysis", "Analysis Summary", "Curriculum Overview", "Mock Interviews"]
    choice = st.sidebar.selectbox("Navigation", menu)

    if choice == "Metrics Dashboard":
        display_metrics_dashboard(engine)
        engine.dispose()
    elif choice == "Users":
        display_user_leaderboard(engine)
        engine.dispose()
    elif choice == "Content Analysis":
        display_content_analysis(engine)
        engine.dispose()
    elif choice == "Analysis Summary":
        display_analysis_summary() # No engine needed
    elif choice == "Curriculum Overview":
        display_curriculum_overview(engine)
        engine.dispose()
    elif choice == "Mock Interviews":
        display_mock_interviews(engine)
        engine.dispose()

def display_mock_interviews(engine):
    st.header("Mock Interview Analytics")
    st.write("Exploring mock interview data.")

    st.subheader("Key Metrics")
    col1, col2 = st.columns(2)

    total_interviews_query = text("SELECT COUNT(*) FROM interview_sessions")
    try:
        with engine.connect() as conn:
            total_interviews = conn.execute(total_interviews_query).scalar()
    except Exception as e:
        logger.error(f"Error fetching total mock interview count: {e}")
        total_interviews = "Error"
    col1.metric("Total Mock Interviews", total_interviews)

    avg_feedback_query = text("SELECT AVG(CASE WHEN overall_feedback::TEXT ~ '^\\d+(\\.\\d+)?$' THEN overall_feedback::NUMERIC ELSE NULL END) FROM interview_sessions")
    try:
        with engine.connect() as conn:
            avg_feedback_result = conn.execute(avg_feedback_query).scalar()
            avg_feedback = round(avg_feedback_result, 2) if avg_feedback_result else "N/A"
    except Exception as e:
        logger.error(f"Error fetching average feedback: {e}")
        avg_feedback = "Error"
    col2.metric("Average Feedback Score", avg_feedback)

    st.subheader("Recent Interview Sessions")
    recent_interviews_df = fetch_recent_interview_data(engine) # Moved table display to separate function
    display_recent_interviews_table(recent_interviews_df)


@st.cache_data(ttl=120) # Cache recent interviews data for 2 minutes
def fetch_recent_interview_data(_engine):
    recent_interviews_query = text("""
        SELECT
            isess.int_session_id,
            u.first_name,
            u.last_name,
            isess.overall_feedback,
            isess.created_at
        FROM interview_sessions isess
        JOIN users u ON isess.user_id = u.user_id
        ORDER BY isess.created_at DESC
        LIMIT 10
    """)
    try:
        with _engine.connect() as conn: # Use '_engine' here as well
            recent_interviews_df = pd.read_sql_query(recent_interviews_query, conn)
            return recent_interviews_df
    except Exception as e:
        logger.error(f"Error fetching recent mock interview sessions: {e}")
        st.error("Error fetching recent mock interview session data.")
        return pd.DataFrame()


def display_recent_interviews_table(recent_interviews_df):
    if not recent_interviews_df.empty:
        recent_interviews_df.rename(columns={
            'int_session_id': 'Session ID',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'overall_feedback': 'Feedback JSON',
            'created_at': 'Interview Date'
        }, inplace=True)

        def extract_interview_score(feedback_json_dict):
            logger.info(f"Type of feedback_json_str before parsing: {type(feedback_json_dict)}")
            try:
                return feedback_json_dict.get('interviewScore')
            except (AttributeError, TypeError) as e:
                logger.error(f"Error extracting interviewScore from dict: {e}. Data: {feedback_json_dict}")
                return None

        recent_interviews_df['Interview Score'] = recent_interviews_df['Feedback JSON'].apply(extract_interview_score)

        def extract_interview_feedback_text(feedback_json_dict):
            return feedback_json_dict.get('interviewFeedback')

        recent_interviews_df['Formatted Feedback'] = recent_interviews_df['Feedback JSON'].apply(extract_interview_feedback_text)

        st.dataframe(recent_interviews_df[['Session ID', 'First Name', 'Last Name', 'Interview Score', 'Formatted Feedback', 'Interview Date']], height=500)
    else:
        st.info("No mock interview session data available yet for recent sessions.")


def display_curriculum_overview(engine):
    st.header("Curriculum Overview")
    st.subheader("Time Spent Learning per Unit & Lesson")
    st.write("This section shows the average and total time users have spent learning in each unit and lesson.")

    time_spent_query = text("""
        SELECT
            u.title AS unit_title,
            l.title AS lesson_title,
            SUM(CASE
                WHEN EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60 > 120 THEN 120
                ELSE EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60
            END) as total_time_minutes,
            AVG(CASE
                WHEN EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60 > 120 THEN 120
                ELSE EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60
            END) as avg_time_minutes,
            COUNT(DISTINCT ls.session_id) as session_count
        FROM lesson_sessions ls
        JOIN lessons l ON ls.lesson_id = l.lesson_id
        JOIN units u ON l.unit_id = u.unit_id
        WHERE ls.status = 'completed' -- Consider only completed sessions for time spent
        GROUP BY u.title, l.title
        ORDER BY u.title, l.title
    """)

    try:
        with engine.connect() as conn:
            time_spent_df = pd.read_sql_query(time_spent_query, conn)

        if not time_spent_df.empty:
            time_spent_df['total_time_learning'] = time_spent_df['total_time_minutes'].apply(format_time)
            time_spent_df['avg_time_learning'] = time_spent_df['avg_time_minutes'].apply(format_time)
            st.dataframe(time_spent_df[['unit_title', 'lesson_title', 'total_time_learning', 'avg_time_learning', 'session_count']], height=800)
        else:
            st.info("No lesson session data available yet to calculate time spent learning.")

    except Exception as e:
        logger.error(f"Error fetching time spent learning data: {e}")
        st.error("Error fetching data for Time Spent Learning analysis.")


def display_metrics_dashboard(engine):
    st.header("Learning Platform Metrics")
    st.write("Note: 'User Messages' counts are separated into 'Lesson Messages' and 'Universal Chat Messages'. 'Universal Chat Messages' count is approximated and may not be perfectly accurate without a clear distinction in the database.")

    time_ranges = {
        "Last 24 Hours": 1,
        "Last 7 Days": 7,
        "Last 30 Days": 30
    }
    selected_range = st.selectbox("Select Time Range", list(time_ranges.keys()))
    days_back = time_ranges[selected_range]
    start_time = datetime.now() - timedelta(days=days_back)
    st.write(f"Showing data since: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    query = text("""
       SELECT
            (SELECT COUNT(DISTINCT session_id) FROM lesson_sessions ls WHERE ls.status = 'completed' AND (created_at >= :start_time OR ls.updated_at >= :start_time)) as completed_sessions,
            (SELECT COUNT(DISTINCT session_id) FROM lesson_sessions ls WHERE ls.status = 'in_progress' AND (created_at >= :start_time OR updated_at >= :start_time)) as in_progress_sessions,
            -- Calculate total time spent learning in minutes for the time range
            (SELECT COALESCE(SUM(CASE WHEN EXTRACT(EPOCH FROM (ls_time.updated_at - ls_time.created_at)) / 60 > 120 THEN 120 ELSE EXTRACT(EPOCH FROM (ls_time.updated_at - ls_time.created_at)) / 60 END), 0)
             FROM lesson_sessions ls_time WHERE ls_time.status = 'completed' AND (ls_time.created_at >= :start_time OR ls_time.updated_at >= :start_time)) as total_time_learning_minutes,
            -- Count lesson messages from lesson_session_messages for the time range
            (SELECT COUNT(*) FROM lesson_session_messages lsm INNER JOIN lesson_sessions ls_sub ON lsm.session_id = ls_sub.session_id WHERE (ls_sub.created_at >= :start_time OR ls_sub.updated_at >= :start_time)) as lesson_messages,
            -- Count universal chat messages from conversation_messages for the time range (APPROXIMATION)
            (SELECT COUNT(*) FROM conversation_messages cm WHERE cm.message_role = 'user' AND cm.created_at >= :start_time) as universal_chat_messages,
            (SELECT COUNT(DISTINCT user_id) FROM users WHERE created_at >= :start_time) as new_users,
            -- Count mock interviews for the selected time range
            (SELECT COUNT(*) FROM interview_sessions isess WHERE isess.created_at >= :start_time) as mock_interviews_count
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"start_time": start_time}).fetchone()
    except Exception as e:
        logger.error(f"Error executing metrics query: {e}")
        result = None

    if result:
        completed_sessions = result[0] if result else 0
        in_progress_sessions = result[1] if result else 0
        total_time_learning_minutes = result[2] if result else 0
        lesson_messages = result[3] if result else 0
        universal_chat_messages = result[4] if result else 0
        new_users = result[5] if result else 0
        mock_interviews_count = result[6] if result else 0
        total_user_messages = lesson_messages + universal_chat_messages
        total_time_learning = format_time(total_time_learning_minutes)


        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Completed Sessions", completed_sessions)
        col2.metric("In-Progress Sessions", in_progress_sessions)
        col3.metric("Lesson Messages", lesson_messages)
        col4.metric("Universal Chat Messages", universal_chat_messages)

        # Display Total User Messages and Total Time Spent Learning side-by-side
        col5, col6 = st.columns(2)
        col5.metric("Total User Messages", total_user_messages)
        col6.metric("Total Time Learning", total_time_learning)

        st.metric("New Users", new_users)
        st.metric("Mock Interviews", mock_interviews_count)


        # --- Cumulative Charts ---
        st.subheader("Cumulative Metrics Over Time")

        # Cumulative Total User Messages
        st.write("**Cumulative User Messages**")  # Added header
        messages_query = text("""
            SELECT
                DATE(lsm.created_at) as date,
                COUNT(*) as message_count
            FROM lesson_session_messages lsm
            INNER JOIN lesson_sessions ls ON lsm.session_id = ls.session_id
            WHERE (ls.created_at >= :start_time OR ls.updated_at >= :start_time)
            GROUP BY DATE(lsm.created_at)
            UNION ALL
            SELECT
                DATE(cm.created_at) as date,
                COUNT(*) as message_count
            FROM conversation_messages cm
            WHERE cm.message_role = 'user' AND cm.created_at >= :start_time
            GROUP BY DATE(cm.created_at)
            ORDER BY date
        """)

        try:
            with engine.connect() as conn:
                messages_df = pd.read_sql_query(messages_query, conn, params={"start_time": start_time})
                # Group by date and sum the message_count *after* the UNION
                messages_df = messages_df.groupby('date')['message_count'].sum().reset_index()
                messages_df['cumulative_messages'] = messages_df['message_count'].cumsum()
                st.line_chart(messages_df, x='date', y='cumulative_messages')
        except Exception as e:
            logger.error(f"Error fetching cumulative messages data: {e}")
            st.error("Failed to load cumulative messages chart.")

        # Cumulative Total Users
        st.write("**Cumulative New Users**")  # Added header
        users_query = text("""
            SELECT
                DATE(created_at) as date,
                COUNT(DISTINCT user_id) as user_count
            FROM users
            WHERE created_at >= :start_time
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
        """)
        try:
            with engine.connect() as conn:
                users_df = pd.read_sql_query(users_query, conn, params={"start_time": start_time})
                users_df['cumulative_users'] = users_df['user_count'].cumsum()
                st.line_chart(users_df, x='date', y='cumulative_users')
        except Exception as e:
            logger.error(f"Error fetching cumulative users data: {e}")
            st.error("Failed to load cumulative users chart.")

        # Cumulative Total Time Spent Learning
        st.write("**Cumulative Time Spent (Hours)**")  # Added header
        time_query = text("""
            SELECT
                DATE(ls.created_at) as date,
                SUM(CASE
                    WHEN EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60 > 120 THEN 120
                    ELSE EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60
                END) as time_spent_minutes
            FROM lesson_sessions ls
            WHERE ls.status = 'completed' AND (ls.created_at >= :start_time OR ls.updated_at >= :start_time)
            GROUP BY DATE(ls.created_at)
            ORDER BY DATE(ls.created_at)
        """)
        try:
            with engine.connect() as conn:
                time_df = pd.read_sql_query(time_query, conn, params={"start_time": start_time})
                time_df['cumulative_time_minutes'] = time_df['time_spent_minutes'].cumsum()
                # Convert cumulative minutes to hours
                time_df['cumulative_time_hours'] = time_df['cumulative_time_minutes'] / 60
                st.line_chart(time_df, x='date', y='cumulative_time_hours')
        except Exception as e:
            logger.error(f"Error fetching cumulative time spent data: {e}")
            st.error("Failed to load cumulative time spent chart.")


    else:
        st.error("Failed to fetch daily metrics.")

def display_analysis_summary():
    st.header("Overall Lesson Analysis Summary")
    st.write("This section provides a summary of the weekly lesson content analysis, highlighting key challenges and actionable recommendations for curriculum improvement.")

    summary_report, lesson_insights_table_data, executive_summary_table_data, lesson_analyses_data = summarize_lesson_analyses()

    if summary_report:
        with st.spinner("Generating analysis summary..."):
            formatted_output_markdown, lesson_insights_table_data = format_lesson_insights_for_output(lesson_analyses_data, summary_report)

            st.subheader("Part 1: Executive Summary - Top Curriculum Improvement Priorities")

            if executive_summary_table_data:
                display_executive_summary_table(executive_summary_table_data)
            else:
                st.warning("No Executive Summary data available.")

            if lesson_insights_table_data:
                with st.expander("Part 2: Lesson-Specific Opportunity Insights for Coaches (Click to Expand)", expanded=False):
                    st.write("Detailed, lesson-specific insights and actionable suggestions for coaches. Expand to view.")
                    display_lesson_insights_table(lesson_insights_table_data)
    else:
        st.info("No lesson analysis files found to summarize. Run weekly analysis script to generate the summary.")


def display_executive_summary_table(summary_table_data):
    summary_df = pd.DataFrame(summary_table_data)
    summary_df = summary_df.head(5)
    columns_to_display = ['Description', 'Example', 'Severity Level']
    if 'ActionableRecommendation' in summary_df.columns:
        columns_to_display.append('ActionableRecommendation')
    elif 'Actionable Recommendation' in summary_df.columns: # Check for space
        columns_to_display.append('Actionable Recommendation') # Use with space if exists
    else:
        logger.warning("Column 'ActionableRecommendation' or 'Actionable Recommendation' not found in executive summary data.")

    st.table(summary_df.set_index('Challenge')[columns_to_display].rename(columns={'Severity Level': 'Weight'}))


def display_lesson_insights_table(lesson_insights_table_data):
    insights_df = pd.DataFrame(lesson_insights_table_data)
    st.table(insights_df.set_index('Lesson Title')[['Opportunity Insights', 'Severity Level']].rename(columns={'Severity Level': 'Weight'}))


def display_user_leaderboard(engine):
    st.header("Users")
    st.write("Note: 'Universal Chat Messages' count is approximated and may not be perfectly accurate without a clear distinction in the database.")

    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["Leaderboard View", "Detailed User View", "Daily Activity"])
    
    with tab1:
        # --- Filtering and Search Options ---
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            time_ranges = {
                "All Time": 999999,
                "Last 7 Days": 7,
                "Last 30 Days": 30
            }
            selected_range = st.selectbox("Time Range", list(time_ranges.keys()))
            days_back = time_ranges[selected_range]

        with col2:
            sort_options = {
                "Lessons Completed": "lessons_completed",
                "Time Spent Learning": "time_spent_minutes",
                "Recent Activity": "last_activity_time",
                "Engagement (Messages)": "total_messages"
            }
            sort_by = st.selectbox("Sort By", list(sort_options.keys()))
            sort_column = sort_options[sort_by]
            
        with col3:
            search_term = st.text_input("Search Users", placeholder="Enter name...")
        
        # --- Pagination Controls ---
        col4, col5 = st.columns([3, 1])
        with col4:
            page_size_options = [10, 20, 50, 100]
            page_size = st.select_slider("Users per page", options=page_size_options, value=20)
        
        with col5:
            show_inactive = st.checkbox("Include Inactive", value=False)

        if selected_range == "All Time":
            start_time = datetime(1970, 1, 1)
        else:
            start_time = datetime.now() - timedelta(days=days_back)

        # --- Enhanced SQL Query with Additional Metrics ---
        leaderboard_query = text("""
            WITH user_metrics AS (
                SELECT
                    u.user_id,
                    u.first_name,
                    u.last_name,
                    u.email,
                    u.created_at as user_created_at,
                    COUNT(DISTINCT ls.lesson_id) AS lessons_completed,
                    -- Calculate total lessons available for completion percentage
                    (SELECT COUNT(*) FROM lessons) as total_lessons,
                    COALESCE(SUM(
                        CASE
                            WHEN EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60 > 120 THEN 120
                            ELSE EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60
                        END
                    ), 0) as time_spent_minutes,
                    -- Count lesson messages
                    (SELECT COUNT(*) FROM lesson_session_messages lsm
                     INNER JOIN lesson_sessions ls_sub ON lsm.session_id = ls_sub.session_id
                     WHERE ls_sub.user_id = u.user_id AND (ls_sub.created_at >= :start_time OR ls_sub.updated_at >= :start_time)) as lesson_messages,
                    -- Count universal chat messages
                    (SELECT COUNT(*) FROM conversation_messages cm
                     WHERE cm.user_id = u.user_id AND cm.message_role = 'user' AND cm.created_at >= :start_time) as universal_chat_messages,
                    -- Last activity time
                    MAX(ls.updated_at) as last_activity_time,
                    -- Calculate active days (streak potential)
                    (SELECT COUNT(DISTINCT DATE(activity_time))
                     FROM (
                         SELECT ls_days.updated_at as activity_time FROM lesson_sessions ls_days
                         WHERE ls_days.user_id = u.user_id AND ls_days.updated_at >= :start_time
                         UNION ALL
                         SELECT cm_days.created_at FROM conversation_messages cm_days
                         WHERE cm_days.user_id = u.user_id AND cm_days.created_at >= :start_time
                     ) as activity_dates) as active_days,
                    -- Calculate submissions
                    (SELECT COUNT(*) FROM submissions s WHERE s.user_id = u.user_id AND s.created_at >= :start_time) as submissions_count
                FROM users u
                LEFT JOIN lesson_sessions ls ON u.user_id = ls.user_id AND ls.status = 'completed' AND ls.updated_at >= :start_time
                GROUP BY u.user_id, u.first_name, u.last_name, u.email, u.created_at
            )
            SELECT
                user_id,
                first_name,
                last_name,
                email,
                user_created_at,
                lessons_completed,
                total_lessons,
                CASE
                    WHEN total_lessons > 0 THEN (lessons_completed::float / total_lessons) * 100
                    ELSE 0
                END as completion_percentage,
                time_spent_minutes,
                lesson_messages,
                universal_chat_messages,
                (lesson_messages + universal_chat_messages) as total_messages,
                last_activity_time,
                active_days,
                submissions_count,
                CASE
                    WHEN last_activity_time >= NOW() - INTERVAL '1 day' THEN true
                    ELSE false
                END as active_today
            FROM user_metrics
            WHERE 1=1
                AND (first_name ILIKE :search_term OR last_name ILIKE :search_term OR :search_term = '')
                AND (last_activity_time IS NOT NULL OR :show_inactive = true)
            ORDER BY
                CASE WHEN :sort_column = 'lessons_completed' THEN lessons_completed END DESC,
                CASE WHEN :sort_column = 'time_spent_minutes' THEN time_spent_minutes END DESC,
                CASE WHEN :sort_column = 'last_activity_time' THEN last_activity_time END DESC,
                CASE WHEN :sort_column = 'total_messages' THEN (lesson_messages + universal_chat_messages) END DESC
        """)

        try:
            # Get total count for pagination
            count_query = text("""
                SELECT COUNT(*) FROM users u
                WHERE (:search_term = '' OR u.first_name ILIKE :search_term OR u.last_name ILIKE :search_term)
            """)
            
            with engine.connect() as conn:
                total_users = conn.execute(count_query, {"search_term": f"%{search_term}%"}).scalar()
                
                # Calculate total pages
                total_pages = (total_users + page_size - 1) // page_size
                
                # Add page selector
                col_pages_left, col_pages_right = st.columns([3, 1])
                with col_pages_left:
                    st.write(f"Showing {min(total_users, page_size)} of {total_users} users")
                
                with col_pages_right:
                    page_number = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=1, step=1)
                
                # Calculate offset
                offset = (page_number - 1) * page_size
                
                # Add pagination to query
                paginated_query = text(f"{leaderboard_query.text} LIMIT :page_size OFFSET :offset")
                
                # Execute query with all parameters
                df_leaderboard = pd.read_sql_query(
                    paginated_query,
                    conn,
                    params={
                        "start_time": start_time,
                        "search_term": f"%{search_term}%",
                        "sort_column": sort_column,
                        "show_inactive": show_inactive,
                        "page_size": page_size,
                        "offset": offset
                    }
                )

                # --- Fetch Profile Pictures from Airtable ---
                airtable_data = fetch_airtable_fellow_data()
                df_leaderboard = merge_airtable_pictures(df_leaderboard, airtable_data)

                # --- Format columns for display ---
                df_leaderboard['time_spent_learning'] = df_leaderboard['time_spent_minutes'].apply(format_time)
                df_leaderboard['time_since_last_activity'] = df_leaderboard['last_activity_time'].apply(format_time_since_activity)
                
                # --- Add visual progress bar ---
                df_leaderboard['progress_bar'] = df_leaderboard['completion_percentage'].apply(
                    lambda x: create_progress_bar(x)
                )
                
                # --- Add streak indicator ---
                df_leaderboard['streak_indicator'] = df_leaderboard.apply(
                    lambda row: '🔥' if row['active_today'] else '⚪', axis=1
                )

                # --- Reorder and select columns for display ---
                ordered_columns = [
                    'profile_picture',
                    'streak_indicator',
                    'first_name',
                    'last_name',
                    'lessons_completed',
                    'progress_bar',
                    'time_spent_learning',
                    'active_days',
                    'total_messages',
                    'submissions_count',
                    'time_since_last_activity'
                ]
                df_leaderboard_ordered = df_leaderboard[ordered_columns]

                # --- Apply Styling to the ORDERED DataFrame ---
                styled_leaderboard = df_leaderboard_ordered.style.apply(style_top_3_and_stripes, axis=None)

                st.dataframe(
                    styled_leaderboard,
                    column_config={
                        "profile_picture": st.column_config.ImageColumn("Portrait"),
                        "streak_indicator": st.column_config.Column("Streak"),
                        "first_name": "First Name",
                        "last_name": "Last Name",
                        "lessons_completed": "Lessons 🎓",
                        "progress_bar": st.column_config.ProgressColumn(
                            "Curriculum Progress",
                            help="Percentage of total curriculum completed",
                            format="%d%%",
                            min_value=0,
                            max_value=100
                        ),
                        "time_spent_learning": "Time Learning ⏱️",
                        "active_days": "Active Days",
                        "total_messages": "Total Messages 💬",
                        "submissions_count": "Submissions",
                        "time_since_last_activity": "Last Activity"
                    },
                    height=600,
                    hide_index=True
                )
                
                # --- Add summary metrics ---
                st.subheader("Cohort Summary")
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    avg_completion = df_leaderboard['completion_percentage'].mean()
                    st.metric("Avg. Completion", f"{avg_completion:.1f}%")
                
                with metric_col2:
                    avg_time = df_leaderboard['time_spent_minutes'].mean()
                    st.metric("Avg. Learning Time", format_time(avg_time))
                
                with metric_col3:
                    active_users = df_leaderboard['active_today'].sum()
                    st.metric("Active Today", f"{active_users} users")
                
                with metric_col4:
                    avg_messages = df_leaderboard['total_messages'].mean()
                    st.metric("Avg. Messages", f"{avg_messages:.1f}")

        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            st.error(f"Failed to load leaderboard data: {e}")
    
    with tab2:
        st.subheader("Detailed User Analysis")
        
        # User selector
        with engine.connect() as conn:
            users_query = text("""
                SELECT user_id, first_name, last_name
                FROM users
                ORDER BY first_name, last_name
            """)
            users_df = pd.read_sql_query(users_query, conn)
            users_df['full_name'] = users_df['first_name'] + ' ' + users_df['last_name']
            
            selected_user_name = st.selectbox(
                "Select User",
                options=users_df['full_name'].tolist(),
                index=0
            )
            
            # Convert numpy.int64 to Python int to avoid adaptation issues
            selected_user_id = int(users_df[users_df['full_name'] == selected_user_name]['user_id'].iloc[0])
            
            # Get detailed user data
            user_detail_query = text("""
                WITH user_activity AS (
                    SELECT
                        DATE(activity_time) as activity_date
                    FROM (
                        SELECT updated_at as activity_time FROM lesson_sessions
                        WHERE user_id = :user_id
                        UNION ALL
                        SELECT created_at FROM conversation_messages
                        WHERE user_id = :user_id AND message_role = 'user'
                    ) as all_activity
                    GROUP BY DATE(activity_time)
                    ORDER BY DATE(activity_time)
                ),
                daily_lessons AS (
                    SELECT
                        DATE(updated_at) as completion_date,
                        COUNT(DISTINCT lesson_id) as lessons_completed
                    FROM lesson_sessions
                    WHERE user_id = :user_id AND status = 'completed'
                    GROUP BY DATE(updated_at)
                ),
                daily_messages AS (
                    SELECT
                        DATE(created_at) as message_date,
                        COUNT(*) as message_count
                    FROM conversation_messages
                    WHERE user_id = :user_id AND message_role = 'user'
                    GROUP BY DATE(created_at)
                ),
                user_units AS (
                    SELECT
                        u.title as unit_title,
                        COUNT(DISTINCT l.lesson_id) as total_unit_lessons,
                        COUNT(DISTINCT CASE WHEN ls.status = 'completed' THEN l.lesson_id END) as completed_unit_lessons
                    FROM units u
                    JOIN lessons l ON u.unit_id = l.unit_id
                    LEFT JOIN lesson_sessions ls ON l.lesson_id = ls.lesson_id AND ls.user_id = :user_id
                    GROUP BY u.unit_id, u.title
                    ORDER BY u.unit_id
                )
                SELECT
                    u.first_name,
                    u.last_name,
                    u.email,
                    u.created_at as join_date,
                    COUNT(DISTINCT ua.activity_date) as active_days,
                    COUNT(DISTINCT ls.lesson_id) as total_lessons_completed,
                    SUM(CASE WHEN ls.status = 'completed' THEN
                        EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60
                        ELSE 0 END) as total_time_minutes,
                    (SELECT COUNT(*) FROM conversation_messages cm
                     WHERE cm.user_id = u.user_id AND cm.message_role = 'user') as total_messages,
                    (SELECT COUNT(*) FROM submissions s WHERE s.user_id = u.user_id) as total_submissions,
                    (SELECT string_agg(unit_title || ': ' ||
                        completed_unit_lessons || '/' || total_unit_lessons ||
                        ' (' || ((completed_unit_lessons::float/total_unit_lessons)*100)::int || '%)',
                        E'\n')
                     FROM user_units) as unit_progress,
                    (SELECT json_agg(json_build_object(
                        'date', activity_date,
                        'lessons', COALESCE(dl.lessons_completed, 0),
                        'messages', COALESCE(dm.message_count, 0)
                    ) ORDER BY activity_date DESC)
                     FROM user_activity ua
                     LEFT JOIN daily_lessons dl ON ua.activity_date = dl.completion_date
                     LEFT JOIN daily_messages dm ON ua.activity_date = dm.message_date
                     LIMIT 30) as recent_activity
                FROM users u
                LEFT JOIN user_activity ua ON 1=1
                LEFT JOIN lesson_sessions ls ON u.user_id = ls.user_id
                WHERE u.user_id = :user_id
                GROUP BY u.user_id, u.first_name, u.last_name, u.email, u.created_at
            """)
            
            user_detail = conn.execute(user_detail_query, {"user_id": selected_user_id}).fetchone()
            
            if user_detail:
                # Display user profile
                user_col1, user_col2 = st.columns([1, 3])
                
                with user_col1:
                    # Get profile picture
                    airtable_data = fetch_airtable_fellow_data()
                    user_name = f"{user_detail[0]} {user_detail[1]}"
                    profile_pic = None
                    
                    for fellow in airtable_data:
                        if fellow.get('Name') == user_name:
                            profile_pic = fellow.get('profile_picture_url')
                            break
                    
                    if profile_pic:
                        st.image(profile_pic, width=150)
                    else:
                        st.info("No profile picture available")
                
                with user_col2:
                    st.subheader(f"{user_detail[0]} {user_detail[1]}")
                    st.write(f"Email: {user_detail[2]}")
                    st.write(f"Joined: {user_detail[3].strftime('%Y-%m-%d')}")
                    st.write(f"Active Days: {user_detail[4]}")
                    
                    # Progress metrics
                    progress_cols = st.columns(4)
                    progress_cols[0].metric("Lessons Completed", user_detail[5])
                    progress_cols[1].metric("Time Learning", format_time(user_detail[6]))
                    progress_cols[2].metric("Total Messages", user_detail[7])
                    progress_cols[3].metric("Submissions", user_detail[8])
                
                # Unit progress
                st.subheader("Unit Progress")
                unit_progress = user_detail[9].split('\n') if user_detail[9] else []
                for unit in unit_progress:
                    unit_name, progress = unit.split(': ', 1)
                    st.write(f"**{unit_name}**: {progress}")
                
                # Recent activity
                st.subheader("Recent Activity")
                if user_detail[10]:
                    recent_activity = pd.DataFrame(user_detail[10])
                    
                    # Create activity chart
                    activity_chart = pd.DataFrame(recent_activity)
                    activity_chart['date'] = pd.to_datetime(activity_chart['date'])
                    activity_chart = activity_chart.sort_values('date')
                    
                    # Plot activity
                    st.line_chart(
                        activity_chart.set_index('date')[['lessons', 'messages']]
                    )
                    
                    # Show activity table
                    activity_table = activity_chart.copy()
                    activity_table['date'] = activity_table['date'].dt.strftime('%Y-%m-%d')
                    st.dataframe(
                        activity_table[['date', 'lessons', 'messages']].head(10),
                        hide_index=True
                    )
                else:
                    st.info("No recent activity data available")
            else:
                st.error("Failed to load user details")
    
    with tab3:
        st.subheader("Daily User Activity")
        st.write("This view shows which users were active on each day.")
        
        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            days_to_show = st.slider("Number of days to display", min_value=7, max_value=30, value=14, step=1)
        
        with col2:
            end_date = st.date_input("End date", value=datetime.now().date())
        
        start_date = end_date - timedelta(days=days_to_show-1)
        
        # Generate date range in Python
        date_range = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days_to_show)]
        date_range.reverse()  # Most recent dates first
        
        # Query to get user activity for each day
        try:
            # Create a DataFrame to store all activity data
            all_activity_data = []
            
            for date_str in date_range:
                # Query for this specific date
                day_query = text("""
                    WITH user_activity AS (
                        SELECT DISTINCT
                            user_id
                        FROM (
                            -- Lesson sessions activity
                            SELECT
                                user_id
                            FROM lesson_sessions
                            WHERE DATE(updated_at) = :activity_date
                            UNION
                            -- Chat messages activity
                            SELECT
                                user_id
                            FROM conversation_messages
                            WHERE message_role = 'user' AND DATE(created_at) = :activity_date
                        ) all_activity
                    ),
                    users_info AS (
                        SELECT
                            user_id,
                            first_name || ' ' || last_name AS full_name
                        FROM users
                    )
                    SELECT
                        ui.full_name
                    FROM user_activity ua
                    JOIN users_info ui ON ua.user_id = ui.user_id
                    ORDER BY ui.full_name
                """)
                
                with engine.connect() as conn:
                    # Execute query for this date
                    active_users_df = pd.read_sql_query(
                        day_query,
                        conn,
                        params={"activity_date": date_str}
                    )
                    
                    # Get the list of active users for this date
                    active_users = active_users_df['full_name'].tolist() if not active_users_df.empty else []
                    
                    # Add to our activity data
                    all_activity_data.append({
                        'activity_date': date_str,
                        'active_users': active_users,
                        'user_count': len(active_users)
                    })
            
            # Convert to DataFrame
            activity_df = pd.DataFrame(all_activity_data)
                
            # Process and display the activity data
            if activity_df is not None and not activity_df.empty:
                # Format the data for display
                activity_df['day_of_week'] = pd.to_datetime(activity_df['activity_date']).dt.strftime('%a')
                activity_df['formatted_date'] = pd.to_datetime(activity_df['activity_date']).dt.strftime('%b %d')
                activity_df['date_display'] = activity_df['formatted_date'] + ' (' + activity_df['day_of_week'] + ')'
                
                # Create a heatmap-style display
                st.subheader("Activity Overview")
                
                # Display metrics
                metrics_cols = st.columns(3)
                
                # Calculate metrics
                all_users = set()
                for users in activity_df['active_users']:
                    all_users.update(users)
                total_active_users = len(all_users)
                
                avg_daily_users = activity_df['user_count'].mean()
                
                if not activity_df['user_count'].empty:
                    most_active_idx = activity_df['user_count'].idxmax()
                    most_active_day = activity_df.iloc[most_active_idx]
                    most_active_display = f"{most_active_day['formatted_date']} ({most_active_day['user_count']} users)"
                else:
                    most_active_display = "None"
                
                metrics_cols[0].metric("Total Active Users", total_active_users)
                metrics_cols[1].metric("Avg. Daily Users", f"{avg_daily_users:.1f}")
                metrics_cols[2].metric("Most Active Day", most_active_display)
                
                # Create the daily activity display
                st.subheader("Daily User Activity")
                
                # Display each day with its active users
                for _, row in activity_df.iterrows():
                    date_col, users_col = st.columns([1, 3])
                    
                    with date_col:
                        st.markdown(f"### {row['date_display']}")
                        st.metric("Active Users", row['user_count'])
                    
                    with users_col:
                        if row['active_users'] and len(row['active_users']) > 0:
                            # Create a more visual representation with user badges
                            html_users = ""
                            for user in row['active_users']:
                                html_users += f"""
                                <span style="
                                    display: inline-block;
                                    padding: 5px 10px;
                                    margin: 3px;
                                    background-color: #2C3E50;
                                    border-radius: 15px;
                                    color: white;
                                    font-size: 0.9em;
                                ">{user}</span>
                                """
                            st.markdown(html_users, unsafe_allow_html=True)
                        else:
                            st.write("No active users")
                    
                    st.markdown("---")
            else:
                st.info("No activity data found for the selected date range.")
        except Exception as e:
            logger.error(f"Error fetching daily activity data: {e}")
            st.error(f"Failed to load daily activity data: {e}")

# Helper function to create a visual progress bar
def create_progress_bar(percentage):
    return percentage

# --- ADD DISPLAY_CONTENT_ANALYSIS FUNCTION HERE ---
def display_content_analysis(engine):
    st.header("Content Analysis")
    st.write("This section allows you to analyze the content of specific lessons to understand user engagement and comprehension.")

    lessons_query = text("SELECT lesson_id, title FROM lessons ORDER BY unit_id, title") # Removed lesson_order, ordering by title instead
    try:
        with engine.connect() as conn:
            lessons_df = pd.read_sql_query(lessons_query, conn)
    except Exception as e:
        logger.error(f"Error fetching lessons for content analysis: {e}")
        st.error("Error fetching lesson list for content analysis.")
        return

    if lessons_df.empty:
        st.info("No lessons found in the database.")
        return

    lesson_titles = lessons_df['title'].tolist()
    lesson_titles.insert(0, "<Select a Lesson>") # Add placeholder option
    selected_lesson_title = st.selectbox("Select Lesson to Analyze", lesson_titles)

    if selected_lesson_title != "<Select a Lesson>":
        # CONVERT TO PYTHON INTEGER HERE
        selected_lesson_id = int(lessons_df[lessons_df['title'] == selected_lesson_title]['lesson_id'].iloc[0])
        st.subheader(f"Analysis for Lesson: '{selected_lesson_title}' (Lesson ID: {selected_lesson_id})")

        analysis_type = st.selectbox("Analysis Type", ["Concept Understanding Analysis", "Keyword Analysis (Deprecated)"])

        if analysis_type == "Concept Understanding Analysis":
            analyze_ai_responses = st.checkbox("Include AI Responses in Analysis", value=False) # Added checkbox for AI responses
            if st.button("Run Concept Analysis"):
                lesson_analysis_result = analyze_lesson_content(engine, selected_lesson_id, selected_lesson_title, analyze_ai_responses=analyze_ai_responses) # Pass analyze_ai_responses
                if lesson_analysis_result:
                    st.write("### Concept Understanding Analysis Results:")
                    st.write(lesson_analysis_result)
                else:
                    st.error("Failed to perform concept analysis. Check logs for errors.")

        elif analysis_type == "Keyword Analysis (Deprecated)":
            st.warning("Keyword Analysis is deprecated and may not provide insightful results. Consider using Concept Understanding Analysis instead.")
            if st.button("Run Keyword Analysis"):
                messages_df_keywords = get_lesson_messages_for_concept_analysis(engine, lesson_id=selected_lesson_id) # Re-use function for keyword analysis too for now
                if not messages_df_keywords.empty:
                    keyword_analysis_result = analyze_keywords_with_percent(messages_df_keywords)
                    st.write("### Keyword Analysis Results:")
                    st.write(keyword_analysis_result)
                else:
                    st.info("No user messages found for this lesson to perform keyword analysis.")


def analyze_lesson_content(engine, lesson_id, lesson_title, sample_size=500, retry_count=0, max_retries=3, analyze_ai_responses=False): # Added analyze_ai_responses to params
    messages_df = get_lesson_messages_for_concept_analysis(engine, lesson_id=lesson_id, include_ai_responses=analyze_ai_responses) # Use passed analyze_ai_responses

    if not messages_df.empty:
        current_sample_size = min(sample_size, len(messages_df)) # Use current_sample_size
        st.info(f"Analyzing a sample of the {current_sample_size} most recent messages from Lesson: '{lesson_title}' (including AI Responses: {analyze_ai_responses})")
        sample_df = messages_df.head(sample_size)

        with st.spinner(f"Analyzing lesson conversations for '{lesson_title}' ..."):
            try:
                analysis = analyze_concept_understanding(sample_df, lesson_title=lesson_title, model="gpt-4o-mini", sample_size=current_sample_size) # Pass sample_size
                return analysis # Return analysis output

            except APIError as e: # Catch OpenAI API errors - using corrected import
                if e.code == 'context_length_exceeded' and retry_count < max_retries and current_sample_size > 100: # Check for token limit and retry conditions
                    reduced_sample_size = max(100, current_sample_size // 2) # Reduce sample size, but keep at least 100
                    st.warning(f"Token limit exceeded. Reducing sample size to {reduced_sample_size} and retrying analysis...") # Inform user about retry
                    return analyze_lesson_content(engine, lesson_id, lesson_title, sample_size=reduced_sample_size, retry_count=retry_count + 1, max_retries=max_retries, analyze_ai_responses=analyze_ai_responses) # Recursive call with reduced sample size - pass analyze_ai_responses
                else:
                    logger.error(f"OpenAI API error during concept analysis: Error code: {e.code} - {e.json_body}") # Log full error details
                    st.error(f"Error analyzing messages. Please try again later. OpenAI API Error: {e.code}") # Display user-friendly error
                    return None # Return None in case of error

            except Exception as e: # Catch generic exceptions too, although APIError is handled specifically in analyze_lesson_content
                logger.error(f"Unexpected error during concept analysis: {e}") # Log unexpected errors
                st.error(f"An unexpected error occurred during analysis. Please check logs for details.") # User-friendly error for unexpected issues
                return None # Return None in case of error


def get_lesson_messages_for_concept_analysis(engine, lesson_id, include_ai_responses=False):
    try:
        query = text("""
            SELECT lsm.role, lsm.content, lsm.created_at
            FROM lesson_session_messages lsm
            INNER JOIN lesson_sessions ls ON lsm.session_id = ls.session_id
            WHERE ls.lesson_id = :lesson_id
            ORDER BY lsm.created_at DESC
        """)
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"lesson_id": lesson_id})
        if not include_ai_responses:
            df = df[df['role'] == 'user']
        return df
    except Exception as e:
        logger.error(f"Error fetching lesson messages for concept analysis: {e}")
        return pd.DataFrame()


def analyze_concept_understanding(df, lesson_title, model="gpt-4o-mini", sample_size=None):
    if df.empty:
        return "No messages found for analysis in this lesson."

    messages_text = "\n".join(f"{i+1}) {row['content']} (Role: {row['role']})"
                            for i, row in df.iterrows())

    prompt = f"""
    Analyze student messages from the lesson titled: "{lesson_title}".  {f"A sample of {sample_size} messages was analyzed due to potential token limits." if sample_size else ""}

    Identify:
    1. Concepts or topics students are **struggling** to understand in this lesson, based on their questions and messages.
    2. Concepts or topics students seem to **understand well** or grasp easily in this lesson, evidenced by their messages showing understanding or successful application.
    3. Provide specific examples or quotes from the messages to illustrate both struggles and areas of good understanding, if possible.
    4. Summarize the main areas of struggle and understanding for this lesson.

    Messages (sample):
    {messages_text}
    """

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e: # Catch generic exceptions too, although APIError is handled specifically in analyze_lesson_content
        logger.error(f"OpenAI API error during concept analysis: {e}")
        raise # Re-raise the exception to be caught in analyze_lesson_content for retry logic


def analyze_keywords_with_percent(df, model="gpt-4o-mini"): # Keep this for potential future use
    if df.empty:
        return "No messages found in the selected timeframe."

    messages_text = "\n".join(f"{i+1}) {row['content']}"
                            for i, row in df.iterrows())

    prompt = f"""
    Analyze these lesson messages (sample):
    1. Identify main topics/themes
    2. Estimate percentage for each theme
    3. Note any patterns

    Messages:
    {messages_text}
    """

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "Error analyzing messages. Please try again later."


def format_time(minutes):
    hours = int(minutes // 60)
    minutes_rem = int(minutes % 60)
    if hours > 0:
        return f"{hours} hours {minutes_rem} minutes"
    else:
        return f"{minutes_rem} minutes"


def format_time_since_activity(last_activity_time):
    if pd.isnull(last_activity_time):
        return "No activity"
    time_diff = datetime.now() - last_activity_time
    days = time_diff.days
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    if days > 0:
        return f"{days} days ago"
    elif hours > 0:
        return f"{hours} hours ago"
    elif minutes > 0:
        return f"{minutes} minutes ago"
    else:
        return "Just now"

# --- Airtable Functions ---
@st.cache_data(ttl=3600)  # Cache Airtable data for 1 hour
def fetch_airtable_fellow_data():
    """Fetches Fellow data including profile pictures from Airtable."""
    try:
        all_records = airtable.get_all(view=AIRTABLE_VIEW_NAME) # Changed view name to use variable
        fellow_data = []
        for record in all_records:
            fields = record['fields']
            picture_url = None
            if 'Portrait' in fields and fields['Portrait']:
                picture_url = fields['Portrait'][0]['url'] if fields['Portrait'][0]['url'] else None
            fellow_data.append({
                'first_name': fields.get('First Name'),
                'last_name': fields.get('LastName'),
                'profile_picture_url': picture_url,
                'Name': fields.get('Name') # Fetch combined "Name" field from Airtable
            })
        return fellow_data
    except Exception as e:
        logger.error(f"Error fetching data from Airtable: {e}")
        return []

def merge_airtable_pictures(leaderboard_df, airtable_fellow_data):
    """Merges Airtable profile picture URLs into the leaderboard DataFrame."""
    profile_pictures = {}
    for fellow in airtable_fellow_data:
        name_key = fellow['Name'] # Use combined "Name" from Airtable as key
        if name_key:
            profile_pictures[name_key] = fellow['profile_picture_url']

    profile_pictures_list = []
    for index, row in leaderboard_df.iterrows():
        combined_name = f"{row['first_name']} {row['last_name']}" # Create combined name from database
        profile_pictures_list.append(profile_pictures.get(combined_name)) # Match against combined name

    leaderboard_df['profile_picture'] = profile_pictures_list
    return leaderboard_df


# --- Styling Function ---
def style_top_3_and_stripes(df):
    """Styles the top 3 rows with gold, silver, bronze and adds zebra striping for better readability."""
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    
    # Apply top 3 styling
    if len(df) >= 1: # Check if DataFrame has at least 1 row
        styles.iloc[0:1, :] = 'background-color: gold; color: black' # Gold for rank 1
    if len(df) >= 2: # Check if DataFrame has at least 2 rows
        styles.iloc[1:2, :] = 'background-color: silver; color: black' # Silver for rank 2
    if len(df) >= 3: # Check if DataFrame has at least 3 rows
        styles.iloc[2:3, :] = 'background-color: #CD7F32; color: white' # Bronze for rank 3
    
    # Add zebra striping for rows after top 3
    for i in range(3, len(df)):
        if i % 2 == 0:  # Even rows
            styles.iloc[i, :] = 'background-color: #2E2E2E'
    
    return styles


if __name__ == "__main__":
    main()