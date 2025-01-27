import pandas as pd
import openai
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import logging
from openai import OpenAI, APIError  # Correct import for APIError

# Configure logging globally
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DB_URL = os.getenv("DB_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY


def analyze_lesson_content(engine, lesson_id, lesson_title, sample_size=500, retry_count=0, max_retries=3, analyze_ai_responses=False): # Added analyze_ai_responses to params
    messages_df = get_lesson_messages_for_concept_analysis(engine, lesson_id=lesson_id, include_ai_responses=analyze_ai_responses) # Use passed analyze_ai_responses

    if not messages_df.empty:
        current_sample_size = min(sample_size, len(messages_df)) # Use current_sample_size
        logger.info(f"Analyzing a sample of the {current_sample_size} most recent messages from Lesson: '{lesson_title}' (including AI responses: {analyze_ai_responses})")
        sample_df = messages_df.head(current_sample_size)

        try:
            analysis = analyze_concept_understanding(sample_df, lesson_title=lesson_title, model="gpt-4o-mini", sample_size=current_sample_size) # Pass sample_size
            return analysis # Return analysis output

        except APIError as e: # Catch OpenAI API errors - using corrected import
            if e.code == 'context_length_exceeded' and retry_count < max_retries and current_sample_size > 100: # Check for token limit and retry conditions
                reduced_sample_size = max(100, current_sample_size // 2) # Reduce sample size, but keep at least 100
                logger.warning(f"Token limit exceeded for lesson '{lesson_title}'. Reducing sample size to {reduced_sample_size} and retrying analysis...") # Log warning about retry
                return analyze_lesson_content(engine, lesson_id, lesson_title, sample_size=reduced_sample_size, retry_count=retry_count + 1, max_retries=max_retries, analyze_ai_responses=analyze_ai_responses) # Recursive call with reduced sample size - pass analyze_ai_responses
            else:
                logger.error(f"OpenAI API error during concept analysis for lesson '{lesson_title}': Error code: {e.code} - {e.json_body}") # Log full error details
                return None # Return None in case of error

        except Exception as e: # Catch generic exceptions too, although APIError is handled specifically in analyze_lesson_content
            logger.error(f"Unexpected error during concept analysis for lesson '{lesson_title}': {e}") # Log unexpected errors
            return None # Return None in case of error

    else:
        logger.info(f"No lesson messages found for Lesson: '{lesson_title}'. Skipping analysis.")
        return None # Return None if no messages found


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


def run_lesson_analysis(engine, lesson_id, lesson_title):
    """Runs content analysis for a single lesson and saves the output to a file."""
    logger.info(f"Starting analysis for lesson: {lesson_title} (ID: {lesson_id})")
    analysis_output = analyze_lesson_content(engine, lesson_id, lesson_title, analyze_ai_responses=True) # Include AI responses for cron job

    if analysis_output:
        # Create 'lesson_analyses' directory if it doesn't exist
        os.makedirs("lesson_analyses", exist_ok=True)
        filepath = os.path.join("lesson_analyses", f"lesson_analysis_lesson_{lesson_id}_{lesson_title.replace(' ', '_')}.txt") # Create file path
        try:
            with open(filepath, "w") as f:
                f.write(f"Analysis for Lesson: '{lesson_title}' (Lesson ID: {lesson_id})\n\n")
                f.write(analysis_output)
            logger.info(f"Analysis saved to: {filepath}")
            return filepath # Return filepath if successful
        except Exception as e:
            logger.error(f"Error saving analysis output to file: {e}")
            return None # Return None if saving failed
    else:
        logger.error(f"Analysis failed for lesson: {lesson_title} (ID: {lesson_id})")
        return None # Return None if analysis failed


if __name__ == "__main__":
    engine = create_engine(DB_URL) # Create database engine

    try:
        with engine.connect() as connection:
            lessons_query = text("""
                SELECT l.lesson_id, l.title
                FROM lessons l
                INNER JOIN lesson_sessions ls ON l.lesson_id = ls.lesson_id
                GROUP BY l.lesson_id, l.title
                HAVING COUNT(DISTINCT ls.session_id) > 0
            """) # Query to get lesson IDs and titles for lessons with sessions
            lessons_result = connection.execute(lessons_query)
            lessons = lessons_result.fetchall()

            if lessons:
                logger.info(f"Found {len(lessons)} lessons with user data to analyze.")
                for lesson in lessons:
                    lesson_id, lesson_title = lesson
                    run_lesson_analysis(engine, lesson_id, lesson_title)
            else:
                logger.info("No lessons with user data found in the database. Skipping analysis.")

    except Exception as e:
        logger.error(f"Error during lesson analysis execution: {e}")
    finally:
        engine.dispose() # Dispose of the engine connection pool

    logger.info("Weekly lesson analysis script finished.")