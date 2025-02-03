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
import json


st.set_page_config(
    page_title="Learning Platform Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.environ.get("DB_URL")
engine = create_engine(DB_URL)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


def main():
    st.title("Learning Platform Analytics Dashboard")
    st.write(f"Streamlit version: **{st.__version__}**")
    engine = create_engine(DB_URL)

    menu = ["Metrics Dashboard", "User Leaderboard", "Content Analysis", "Analysis Summary", "Curriculum Overview", "Mock Interviews"]
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
    elif choice == "Mock Interviews":
        display_mock_interviews(engine)


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


    # --- Recent Mock Interview Sessions Table ---
    st.subheader("Recent Interview Sessions")
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
        with engine.connect() as conn:
            recent_interviews_df = pd.read_sql_query(recent_interviews_query, conn)
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

    except Exception as e:
        logger.error(f"Error fetching recent mock interview sessions: {e}")
        st.error("Error fetching recent mock interview session data.")


    # --- Feedback Analysis Section --- --- REMOVED ENTIRE FEEDBACK ANALYSIS SECTION ---
    # st.subheader("Feedback Analysis")

    # time_ranges_charts = {
    #     "Last 7 Days": 7,
    #     "Last 30 Days": 30,
    #     "Last 90 Days": 90,
    #     "All Time": 999999
    # }
    # selected_range_charts = st.selectbox("Select Time Range for Feedback Charts", list(time_ranges_charts.keys()), key="feedback_time_range_selector")
    # days_back_charts = time_ranges_charts[selected_range_charts]
    # start_time_charts = datetime.now() - timedelta(days=days_back_charts) if selected_range_charts != "All Time" else datetime(1970, 1, 1)

    # feedback_trend_query = text("""
    #     SELECT DATE(created_at) as interview_date, AVG(CASE WHEN overall_feedback::TEXT ~ '^\\d+(\\.\\d+)?$' THEN overall_feedback::NUMERIC ELSE NULL END) as avg_feedback
    #     FROM interview_sessions
    #     WHERE overall_feedback IS NOT NULL AND created_at >= :start_time
    #     GROUP BY interview_date
    #     ORDER BY interview_date
    # """)
    # try:
    #     with engine.connect() as conn:
    #         feedback_trend_df = pd.read_sql_query(feedback_trend_query, conn, params={"start_time": start_time_charts})
    #         if not feedback_trend_df.empty:
    #             feedback_trend_df.rename(columns={'interview_date': 'Interview Date', 'avg_feedback': 'Average Feedback Score'}, inplace=True)
    #             feedback_trend_df.set_index('Interview Date', inplace=True)
    #             st.line_chart(feedback_trend_df, y="Average Feedback Score", height=300, use_container_width=True)
    #         else:
    #             st.info("No numeric feedback data available to display Feedback Score Trend chart for the selected time range.")
    #     except Exception as e:
    #         logger.error(f"Error fetching feedback trend data: {e}")
    #         st.error("Error fetching data for Feedback Score Trend chart.")

    # feedback_distribution_query = text("""
    #     SELECT overall_feedback, COUNT(*) as count
    #     FROM interview_sessions
    #     WHERE overall_feedback IS NOT NULL AND created_at >= :start_time
    #     GROUP BY overall_feedback
    #     ORDER BY overall_feedback
    # """)
    # try:
    #     with engine.connect() as conn:
    #         feedback_distribution_df = pd.read_sql_query(feedback_distribution_query, conn, params={"start_time": start_time_charts})
    #         if not feedback_distribution_df.empty:
    #             feedback_distribution_df.rename(columns={'overall_feedback': 'Feedback Category', 'count': 'Number of Interviews'}, inplace=True)
    #             feedback_distribution_df.set_index('Feedback Category', inplace=True)
    #             st.bar_chart(feedback_distribution_df, height=300, use_container_width=True)
    #         else:
    #             st.info("No feedback data available to display Feedback Distribution chart for the selected time range.")
    #     except Exception as e:
    #         logger.error(f"Error fetching feedback distribution data: {e}")
    #         st.error("Error fetching data for Feedback Distribution chart.")


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

        st.metric("Total User Messages", total_user_messages)
        st.metric("New Users", new_users)
        st.metric("Mock Interviews", mock_interviews_count)

    else:
        st.error("Failed to fetch daily metrics.")

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
                daily_users_df['activity_date'] = pd.to_datetime(daily_users_df['activity_date']).dt.strftime('%Y-%m-%d')
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
                daily_messages_df['message_date'] = pd.to_datetime(daily_messages_df['message_date']).dt.strftime('%Y-%m-%d')
                daily_messages_df.set_index('message_date', inplace=True)
                st.subheader("Daily Total Messages (User)")
                st.bar_chart(daily_messages_df)
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
                cumulative_new_users_df['signup_date'] = pd.to_datetime(cumulative_new_users_df['signup_date']).dt.strftime('%Y-%m-%d')
                cumulative_new_users_df.set_index('signup_date', inplace=True)
                cumulative_new_users_df['cumulative_users'] = cumulative_new_users_df['new_users_count'].cumsum()
                st.subheader("Cumulative New Users Over Time")
                st.line_chart(cumulative_new_users_df[['cumulative_users']])
            else:
                st.info("No new user signup data available to display Cumulative New Users chart.")
    except Exception as e:
        logger.error(f"Error fetching cumulative new users data: {e}")
        st.error("Error fetching data for Cumulative New Users chart.")

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
    st.table(summary_df.set_index('Challenge')[['Description', 'Example', 'Severity Level', 'Actionable Recommendation']].rename(columns={'Severity Level': 'Weight'}))


def display_lesson_insights_table(lesson_insights_table_data):
    insights_df = pd.DataFrame(lesson_insights_table_data)
    st.table(insights_df.set_index('Lesson Title')[['Opportunity Insights', 'Severity Level']].rename(columns={'Severity Level': 'Weight'}))


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


if __name__ == "__main__":
    main()