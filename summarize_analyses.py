import pandas as pd
import openai
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI, APIError

# Configure logging globally
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # We only need OPENAI_API_KEY for summarization
openai.api_key = OPENAI_API_KEY


def summarize_lesson_analyses(analysis_dir="lesson_analyses", model="gpt-4o-mini"):
    """
    Reads lesson analysis files, summarizes them using GPT, and provides prioritized recommendations.
    Returns a tuple: (summary_markdown, lesson_insights_table_data, executive_summary_table_data).
    Returns None, None, None in case of error or no data.
    """
    combined_analysis_text = ""
    lesson_analyses_data = []
    executive_summary_table_data = [] # Initialize executive_summary_table_data

    # Read and combine analysis from each file
    for filename in os.listdir(analysis_dir):
        if filename.startswith("lesson_analysis_lesson_") and filename.endswith(".txt"):
            filepath = os.path.join(analysis_dir, filename)
            try:
                with open(filepath, "r") as f:
                    analysis_content = f.read()
                    lesson_title_line = analysis_content.split('\n')[0]
                    lesson_title = lesson_title_line.split("'")[1] if "'" in lesson_title_line else filename
                    lesson_analyses_data.append({"title": lesson_title, "analysis": analysis_content})
                    combined_analysis_text += f"\n\n---START LESSON ANALYSIS: {lesson_title}---\n{analysis_content}"
            except Exception as e:
                logger.error(f"Error reading analysis file {filename}: {e}")
                continue

    if not combined_analysis_text:
        logger.info("No lesson analysis files found to summarize.")
        return None, None, None # Return None for all three values if no data

    prompt = f"""
    You are an expert learning and curriculum designer, providing **highly concise and actionable** insights to improve a coding education platform. Analyze the following lesson concept analyses. 
    ... (rest of the prompt is the same) ...
    """

    logger.info("Generating overall analysis summary using GPT...")
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        summary_output = response.choices[0].message.content
        formatted_output_markdown, executive_summary_table_data = format_executive_summary_table_data(overall_summary=summary_output) # Get table data for Part 1
        formatted_output_markdown_part2, lesson_insights_table_data = format_lesson_insights_for_output(lesson_analyses_data, "") # overall_summary not needed for Part 2

        return formatted_output_markdown, lesson_insights_table_data, executive_summary_table_data # Return all three

    except Exception as e:
        logger.error(f"Error during overall analysis summarization with OpenAI: {e}")
        return None, None, None # Return None for all three values in case of error


def format_executive_summary_table_data(overall_summary):
    """Formats executive summary into table data and returns Markdown for Part 1."""
    output_text_part1 = "### Part 1: Executive Summary - Top Curriculum Improvement Priorities\n\n" # Markdown for Part 1

    summary_table_data = [] # Initialize table data

    # --- Parse overall_summary to extract data for the table ---
    summary_lines = overall_summary.split('\n')
    challenge = None
    description = None
    example = None
    severity_level = None
    recommendation = None
    
    for line in summary_lines:
        line = line.strip()
        if line.startswith("### "):
            challenge = line[4:].strip()
        elif line.startswith("- **Description:**"):
            description = line[len("- **Description:**"):].strip()
        elif line.startswith("- **Example:**"):
            example = line[len("- **Example:**"):].strip()
        elif line.startswith("- **Severity Level:**"):
            severity_level = line[len("- **Severity Level:**"):].strip()
        elif line.startswith("- **Actionable Recommendation:**"):
            recommendation = line[len("- **Actionable Recommendation:**"):].strip()
            if challenge and description and severity_level and recommendation:
                summary_table_data.append({
                    "Challenge": challenge,
                    "Description": description,
                    "Example": example,
                    "Severity Level": severity_level,
                    "Actionable Recommendation": recommendation
                })
                challenge = None
                description = None
                example = None
                severity_level = None
                recommendation = None

    # Format Part 1 as Markdown text (no table here, table will be created in Streamlit)
    output_text_part1 += "# Curriculum Improvement Report\n" # Top level heading
    output_text_part1 += "## Part 1: CONCISE Executive Summary - Top 3 Curriculum Improvement Priorities\n\n" # Sub-heading

    if summary_table_data:
        for row in summary_table_data: # Iterate through table data and format as Markdown
            output_text_part1 += f"### {row['Challenge']}\n"
            output_text_part1 += f"- **Description:** {row['Description']}\n"
            output_text_part1 += f"- **Example:** {row['Example']}\n"
            output_text_part1 += f"- **Severity Level:** {row['Severity Level']}\n"
            output_text_part1 += f"- **Actionable Recommendation:** {row['Actionable Recommendation']}\n\n"
    else:
        output_text_part1 += "No Executive Summary data available.\n" # Handle no data case

    return output_text_part1, summary_table_data # Return Markdown for Part 1 and table data


def format_lesson_insights_for_output(lesson_analyses_data, overall_summary): # overall_summary not used here now
    """Formats lesson-specific insights for Markdown output. Returns table data."""
    output_text = "" # No Markdown output in this function anymore - only table data returned
    lesson_insights_table_data = []

    # ... (rest of the format_lesson_insights_for_output function is the same as before) ...
    # (Iterate through lesson_analyses_data, extract insights, populate lesson_insights_table_data list)

    return output_text, lesson_insights_table_data # Returns empty Markdown output and table data for Part 2


if __name__ == "__main__":
    logger.info("Summarization script started.")
    overall_summary, lesson_analyses_data = summarize_lesson_analyses()

    if overall_summary and lesson_analyses_data:
        formatted_output_markdown, lesson_insights_table_data, executive_summary_table_data = format_lesson_insights_for_output(lesson_analyses_data, overall_summary) # Get all three return values
        filepath_markdown = "overall_analysis_summary.md"

        try:
            with open(filepath_markdown, "w") as f_md:
                f_md.write(formatted_output_markdown)
            logger.info(f"Overall analysis summary (Markdown) saved to: {filepath_markdown}")
        except Exception as e:
            logger.error(f"Error saving overall analysis summary to file: {e}")
    else:
        logger.error("Failed to generate overall analysis summary.")

    logger.info("Summarization script finished.")