
import streamlit as st
import pandas as pd
import openai
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import logging
from openai import OpenAI, APIError
from summarize_analyses import summarize_lesson_analyses, format_lesson_insights_for_output, format_executive_summary_table_data


# ENSURE set_page_config IS THE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="Learning Platform Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

# Configure logging globally
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
#load_dotenv() # No load_dotenv() for Streamlit Cloud
DB_URL = os.environ.get("DB_URL") # Use os.environ.get() for Streamlit Cloud Secrets

engine = create_engine(DB_URL)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY


def main():
    st.title("Learning Platform Analytics Dashboard")
    st.write(f"Streamlit version: **{st.__version__}**")
    # Create DB engine inside main()
    engine = create_engine(DB_URL)

    # Sidebar Menu
    menu = ["Metrics Dashboard", "User Leaderboard", "Content Analysis", "Analysis Summary", "Curriculum Overview"]
    choice = st.sidebar.selectbox("Navigation", menu)

    if choice == "Metrics Dashboard":
        display_metrics_dashboard(engine)
    elif choice == "User Leaderboard":
        display_user_leaderboard(engine)
    elif choice == "Content Analysis":
        display_content_analysis(engine)
    elif choice == "Analysis Summary":
        display_analysis_summary()
    elif choice == "Curriculum Overview":
        display_curriculum_overview(engine)


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

    # Time Range Selector
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
            (SELECT COUNT(DISTINCT user_id) FROM users WHERE created_at >= :start_time) as new_users
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
        total_user_messages = lesson_messages + universal_chat_messages
        total_time_learning = format_time(total_time_learning_minutes) # Format total time

        col1, col2, col3, col4, col5 = st.columns(5) # Added one more column
        col1.metric("Completed Sessions", completed_sessions)
        col2.metric("In-Progress Sessions", in_progress_sessions)
        col3.metric("Lesson Messages", lesson_messages)
        col4.metric("Universal Chat Messages", universal_chat_messages)
        col5.metric("Total Time Learning", total_time_learning) # New metric - Total Time Learning
        st.metric("Total User Messages", total_user_messages) # Moved Total User Messages below columns
        st.metric("New Users", new_users)

    else:
        st.error("Failed to fetch daily metrics.")

    overall_query = text("""
        SELECT
          (SELECT COUNT(*) FROM users) AS total_users,
          (SELECT COUNT(DISTINCT lesson_id) FROM lesson_sessions WHERE status='completed') AS total_completed_lessons,
          (SELECT COUNT(*) FROM lessons) AS total_lessons
    """)
    try:
        with engine.connect() as conn:
            overall_result = conn.execute(overall_query).fetchone()

        if overall_result:
            total_users = overall_result[0] if overall_result else 0
            total_completed_lessons = overall_result[1] if overall_result else 0
            total_lessons = overall_result[2] if overall_result else 0
            completion_rate = 0
            if total_lessons > 0:
                completion_rate = (total_completed_lessons / total_lessons) * 100

            st.subheader("Overall Progress")
            colA, colB, colC = st.columns(3)
            colA.metric("Total Active Users", total_users)
            colB.metric("Completed Lessons", total_completed_lessons)
            colC.metric("Completion Rate", f"{completion_rate:.2f}%")
        else:
            st.error("Failed to fetch overall progress metrics.")
    except Exception as e:
        logger.error(f"Error fetching overall metrics: {e}")
        st.error(f"Error fetching overall metrics data. Please check logs for details.")

    # --- Daily Active Users Chart ---
    daily_users_query = text("""
        SELECT DATE(ls.updated_at) as activity_date, COUNT(DISTINCT ls.user_id) as daily_active_users
        FROM lesson_sessions ls
        WHERE ls.updated_at >= :start_time
        GROUP BY activity_date
        ORDER BY activity_date
    """)
    try:
        with engine.connect() as conn:
            daily_users_df = pd.read_sql_query(daily_users_query, conn, params={"start_time": start_time})
            if not daily_users_df.empty:
                daily_users_df['activity_date'] = pd.to_datetime(daily_users_df['activity_date']).dt.strftime('%Y-%m-%d') # Format date
                daily_users_df.set_index('activity_date', inplace=True)
                st.subheader("Daily Active Users")
                st.line_chart(daily_users_df)
            else:
                st.info("No user activity data available for the selected time range to display Daily Active Users chart.")
    except Exception as e:
        logger.error(f"Error fetching daily active users data: {e}")
        st.error("Error fetching data for Daily Active Users chart.")


    # --- Daily Messages Chart (Bar Chart) ---
    daily_messages_query = text("""
        SELECT DATE(msg_time) as message_date, COUNT(*) as daily_messages
        FROM (
            SELECT lsm.created_at as msg_time FROM lesson_session_messages lsm
            UNION ALL
            SELECT cm.created_at as msg_time FROM conversation_messages cm WHERE cm.message_role = 'user'
        ) as all_messages
        WHERE msg_time >= :start_time
        GROUP BY message_date
        ORDER BY message_date
    """)
    try:
        with engine.connect() as conn:
            daily_messages_df = pd.read_sql_query(daily_messages_query, conn, params={"start_time": start_time})
            if not daily_messages_df.empty:
                daily_messages_df['message_date'] = pd.to_datetime(daily_messages_df['message_date']).dt.strftime('%Y-%m-%d') # Format date
                daily_messages_df.set_index('message_date', inplace=True)
                st.subheader("Daily Total Messages (User)")
                st.bar_chart(daily_messages_df) # Changed to bar_chart
            else:
                st.info("No message data available for the selected time range to display Daily Messages chart.")

    except Exception as e:
        logger.error(f"Error fetching daily messages data: {e}")
        st.error("Error fetching data for Daily Messages chart.")

    # --- Cumulative New Users Chart ---
    cumulative_new_users_query = text("""
        SELECT DATE(created_at) as signup_date, COUNT(DISTINCT user_id) as new_users_count
        FROM users
        WHERE created_at <= NOW() -- Consider all signups up to now
        GROUP BY signup_date
        ORDER BY signup_date
    """)
    try:
        with engine.connect() as conn:
            cumulative_new_users_df = pd.read_sql_query(cumulative_new_users_query, conn)
            if not cumulative_new_users_df.empty:
                cumulative_new_users_df['signup_date'] = pd.to_datetime(cumulative_new_users_df['signup_date']).dt.strftime('%Y-%m-%d') # Format date
                cumulative_new_users_df.set_index('signup_date', inplace=True)
                cumulative_new_users_df['cumulative_users'] = cumulative_new_users_df['new_users_count'].cumsum() # Calculate cumulative sum
                st.subheader("Cumulative New Users Over Time")
                st.line_chart(cumulative_new_users_df[['cumulative_users']]) # Chart cumulative users
            else:
                st.info("No new user signup data available to display Cumulative New Users chart.")
    except Exception as e:
        logger.error(f"Error fetching cumulative new users data: {e}")
        st.error("Error fetching data for Cumulative New Users chart.")


    lesson_breakdown_query = text("""
    SELECT
      l.title,
      l.lesson_id,
      COUNT(DISTINCT ls.user_id) FILTER (WHERE ls.status='completed') AS users_completed,
      COUNT(DISTINCT ls.user_id) FILTER (WHERE ls.status='in_progress') AS users_in_progress,
      COUNT(DISTINCT ls.user_id) AS total_users_started
    FROM lessons l
    LEFT JOIN lesson_sessions ls ON l.lesson_id = ls.lesson_id
    GROUP BY l.lesson_id, l.title
    ORDER BY users_completed DESC
""")

    try:
        with engine.connect() as conn:
            lesson_df = pd.read_sql_query(lesson_breakdown_query, conn)

        if not lesson_df.empty:
            lesson_df['completion_rate'] = (lesson_df['users_completed'] / lesson_df['total_users_started'] * 100).fillna(0).round(0).astype(int)
            lesson_df = lesson_df.sort_values(by='users_completed', ascending=False)

            st.subheader("Analyze Lessons") # Subheader for buttons

            analysis_results = {} # Dictionary to store analysis output per lesson

            for index, lesson_row in lesson_df.iterrows(): # Iterate through lesson rows
                lesson_title = lesson_row['title']
                lesson_id = str(lesson_row['lesson_id'])

                col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 2]) # Adjust column widths as needed for layout
                with col1:
                    st.write(f"**{lesson_title}**") # Lesson title in first column
                with col2:
                    st.write(f"Completed: {lesson_row['users_completed']}")
                with col3:
                    st.write(f"In Progress: {lesson_row['users_in_progress']}")
                with col4:
                    st.write(f"Rate: {lesson_row['completion_rate']}%")
                with col5:
                    with st.expander(f"Analysis Options - Lesson: {lesson_title}", expanded=False): # Expander for each lesson
                        analyze_ai_responses = st.checkbox("Include AI Responses in Analysis", value=True, key=f"ai_checkbox_{lesson_id}_expander") # Checkbox INSIDE expander

                        if st.button("Analyze", key=f"analyze_button_{lesson_id}_expander"): # Analyze button INSIDE expander
                            analysis_output = analyze_lesson_content(engine, lesson_id, lesson_title, analyze_ai_responses=analyze_ai_responses) # Pass analyze_ai_responses

                            if analysis_output: # Check if analysis output is not None (success)
                                st.subheader(f"Concept Analysis for Lesson: '{lesson_title}'") # Subheader for each lesson analysis - placed INSIDE expander now
                                st.write(analysis_output) # Display analysis output within expander - FULL WIDTH

                                messages_df = get_lesson_messages_for_concept_analysis(engine, lesson_id=lesson_id, include_ai_responses=analyze_ai_responses) # Re-fetch messages
                                if not messages_df.empty:
                                    sample_size = 500
                                    sample_df = messages_df.head(sample_size)
                                    st.subheader(f"Message Activity Timeline (Sample - {min(sample_size, len(messages_df))} messages):") # Subheader inside expander
                                    timeline_df = sample_df.set_index('created_at')
                                    timeline_df['count'] = 1
                                    daily_counts = timeline_df['count'].resample('D').sum()
                                    st.line_chart(daily_counts)

                                    st.subheader(f"Lesson Message Content (Sample - {min(sample_size, len(messages_df))} messages - User and AI):") # Subheader inside expander
                                    st.dataframe(sample_df[['created_at', 'role', 'content']])
                            else:
                                st.error("Analysis failed. Check logs for details.") # Error message within expander


        else:
            st.info("No lesson progress data available yet.")

    except Exception as e:
        logger.error(f"Error fetching lesson breakdown for content analysis: {e}")
        st.error("Error fetching lesson data for content analysis.")



def display_analysis_summary():
    st.header("Overall Lesson Analysis Summary")
    st.write("This section provides a summary of the weekly lesson content analysis, highlighting key challenges and actionable recommendations for curriculum improvement.")

    summary_report, lesson_insights_table_data, executive_summary_table_data, lesson_analyses_data = summarize_lesson_analyses() # Get all four return values

    if summary_report:
        with st.spinner("Generating analysis summary..."):
            formatted_output_markdown, lesson_insights_table_data = format_lesson_insights_for_output(lesson_analyses_data, summary_report) # Pass lesson_analyses_data

            st.subheader("Part 1: Executive Summary - Top Curriculum Improvement Priorities")

            # --- ADD THIS DEBUG STATEMENT ---
            #st.write("Debug: executive_summary_table_data:", executive_summary_table_data)
            # --- END DEBUG STATEMENT ---

            if executive_summary_table_data: # Check if executive_summary_table_data is not empty
                display_executive_summary_table(executive_summary_table_data) # Display Executive Summary as table
            else:
                st.warning("No Executive Summary data available.") # Warning if no table data

            if lesson_insights_table_data:
                with st.expander("Part 2: Lesson-Specific Opportunity Insights for Coaches (Click to Expand)", expanded=False):
                    st.write("Detailed, lesson-specific insights and actionable suggestions for coaches. Expand to view.")
                    display_lesson_insights_table(lesson_insights_table_data)
    else:
        st.info("No lesson analysis files found to summarize. Run weekly analysis script to generate the summary.")



def display_executive_summary_table(summary_table_data):
    """Displays the Executive Summary in a Streamlit DataFrame table."""
    summary_df = pd.DataFrame(summary_table_data)

    # Limit to the first 5 rows if there are more
    summary_df = summary_df.head(5)

    st.table(summary_df.set_index('Challenge')[['Description', 'Example', 'Severity Level', 'Actionable Recommendation']].rename(columns={'Severity Level': 'Weight'})) # Use st.table, set index, select and rename columns


def display_lesson_insights_table(lesson_insights_table_data):
    """Displays lesson-specific opportunity insights in a Streamlit Table."""
    insights_df = pd.DataFrame(lesson_insights_table_data)
    st.table(insights_df.set_index('Lesson Title')[['Opportunity Insights', 'Severity Level']].rename(columns={'Severity Level': 'Weight'})) # Use st.table, set index, select and rename columns


def display_user_leaderboard(engine):
    st.header("User Leaderboard")
    st.write("Note: 'Universal Chat Messages' count is approximated and may not be perfectly accurate without a clear distinction in the database.")

    time_ranges = {
        "All Time": 999999,
        "Last 7 Days": 7,
        "Last 30 Days": 30
    }
    selected_range = st.selectbox("Time Range for Completions", list(time_ranges.keys()))
    days_back = time_ranges[selected_range]

    if selected_range == "All Time":
        start_time = datetime(1970, 1, 1)
    else:
        start_time = datetime.now() - timedelta(days=days_back)

    leaderboard_query = text("""
        SELECT
            u.first_name,
            u.last_name,
            COUNT(DISTINCT ls.lesson_id) AS lessons_completed,
            COALESCE(SUM(
                CASE
                    WHEN EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60 > 120 THEN 120
                    ELSE EXTRACT(EPOCH FROM (ls.updated_at - ls.created_at)) / 60
                END
            ), 0) as time_spent_minutes,
            -- Count lesson messages from lesson_session_messages for each user
            (SELECT COUNT(*) FROM lesson_session_messages lsm
             INNER JOIN lesson_sessions ls_sub ON lsm.session_id = ls_sub.session_id
             WHERE ls_sub.user_id = u.user_id AND (ls_sub.created_at >= :start_time OR ls_sub.updated_at >= :start_time)) as lesson_messages,
            -- Count universal chat messages from conversation_messages for each user
            (SELECT COUNT(*) FROM conversation_messages cm
             WHERE cm.user_id = u.user_id AND cm.message_role = 'user' AND cm.created_at >= :start_time) as universal_chat_messages,
            MAX(ls.updated_at) as last_activity_time,
            COUNT(DISTINCT ls.session_id) FILTER (WHERE ls.updated_at >= :start_time) AS active_sessions_count
        FROM users u
        LEFT JOIN lesson_sessions ls ON u.user_id = ls.user_id AND ls.status = 'completed' AND ls.updated_at >= :start_time
        GROUP BY u.user_id, u.first_name, u.last_name
        ORDER BY lessons_completed DESC
        LIMIT 20
    """)

    try:
        with engine.connect() as conn:
            df_leaderboard = pd.read_sql_query(leaderboard_query, conn, params={"start_time": start_time})

        df_leaderboard['time_spent_learning'] = df_leaderboard['time_spent_minutes'].apply(format_time)
        df_leaderboard['time_since_last_activity'] = df_leaderboard['last_activity_time'].apply(format_time_since_activity)

        st.dataframe(df_leaderboard[['first_name', 'last_name', 'lessons_completed', 'time_spent_learning', 'lesson_messages', 'universal_chat_messages', 'active_sessions_count', 'time_since_last_activity']], height=800)

    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        st.error("Failed to load leaderboard data.")


def analyze_lesson_content(engine, lesson_id, lesson_title, sample_size=500, retry_count=0, max_retries=3, analyze_ai_responses=False): # Added analyze_ai_responses to params
    messages_df = get_lesson_messages_for_concept_analysis(engine, lesson_id=lesson_id, include_ai_responses=analyze_ai_responses) # Use passed analyze_ai_responses

    if not messages_df.empty:
        current_sample_size = min(sample_size, len(messages_df)) # Use current_sample_size
        st.info(f"Analyzing a sample of the {current_sample_size} most recent messages from Lesson: '{lesson_title}' (including AI responses: {analyze_ai_responses})")
        sample_df = messages_df.head(current_sample_size)

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


if __name__ == "__main__":
    main()
