import pandas as pd
import openai
import os
from datetime import datetime, timedelta
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
    Reads lesson analysis files, summarizes them using GPT, and provides prioritized recommendations,
    returning the summary in Markdown format and lesson insights data.
    """
    combined_analysis_text = ""
    lesson_analyses_data = []  # List to store lesson analysis data

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
        return None, None

    prompt = f"""
    You are an expert learning and curriculum designer, providing **highly concise and actionable** insights to improve a coding education platform. Analyze the following lesson concept analyses. 

    Produce a report in Markdown format with two parts:

    **Part 1: CONCISE Executive Summary - Top 3 Curriculum Improvement Priorities (MAXIMUM)**

    * Identify the **TOP 3 MOST CRITICAL RECURRING CHALLENGES** or areas of student struggle across lessons. Focus on the **most fundamental and impactful concepts**.
    * For EACH challenge, provide:
        *   **Very Concise Description** (1-2 sentences MAX).
        *   **Illustrative Example** (quote or brief description, if strong examples are available).
        *   **Severity Level (High/Medium/Low)**.
        *   **ONE KEY Actionable Recommendation** for curriculum improvement. Focus on the *most impactful* action.

    **Part 2: PRIORITIZED Lesson-Specific Opportunity Insights for Coaches (Concise & Actionable)**

    * For EACH lesson with significant student struggles, provide **up to 3 HIGH-QUALITY, CONCISE, and ACTIONABLE "Opportunity Insights for Coaches"**.  
    * **Prioritize insights that are supported by *multiple* student messages or clear patterns of struggle** within the lesson analysis.  Exclude insights that are based on very few data points or seem less significant.
    * Format each insight as a bullet point: "**[Area of Struggle]:** [Concise, actionable suggestion for coaches]."

    **Formatting Requirements:** 
    * Use Markdown for headings, bolding, lists. 
    * Aim for a *brief, highly focused, and actionable* report.

    Lesson Concept Analyses:
    {combined_analysis_text}

    ---END LESSON ANALYSES---
    """

    logger.info("Generating overall analysis summary using GPT...")
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        summary_output = response.choices[0].message.content
        return summary_output, lesson_analyses_data

    except Exception as e:
        logger.error(f"Error during overall analysis summarization with OpenAI: {e}")
        return None, None


def format_lesson_insights_for_output(lesson_analyses_data, overall_summary):
    """Formats lesson-specific insights for Markdown output. Returns table data, not Streamlit table."""
    output_text = "## Overall Learning Platform Content Analysis Summary and Recommendations\n\n"
    output_text += "### Part 1: Executive Summary - Top Curriculum Improvement Priorities\n\n"
    output_text += overall_summary + "\n\n"

    output_text += "### Part 2: **Concise** Lesson-Specific Opportunity Insights for Coaches\n\n" # Corrected subheader

    lesson_insights_table_data = [] # List to store data for table

    for lesson_data in lesson_analyses_data:
        lesson_title = lesson_data["title"]
        analysis_content = lesson_data["analysis"]

        output_text += f"**Lesson Title:** {lesson_title}\n"

        struggles_section_start = analysis_content.find("### 1. Concepts or Topics Students are **Struggling** to Understand:")
        if struggles_section_start == -1:
            struggles_section_start = analysis_content.find("Concepts or Topics Students are **Struggling**")

        understanding_section_start = analysis_content.find("### 2. Concepts or Topics Students Seem to **Understand Well**:")

        if struggles_section_start != -1 and understanding_section_start != -1:
            struggles_text = analysis_content[struggles_section_start:understanding_section_start].strip()
            struggles_insights = []
            for line in struggles_text.split('\n'):
                line = line.strip()
                if line.startswith("- ") and "Struggling" not in line and "Concepts or Topics" not in line:
                    insight_text = line[2:].strip()
                    if insight_text:
                        # Prioritize and shorten insights for table - select top 2 concise insights
                        top_insights = struggles_insights[:2] # Get max top 2 insights - adjust as needed
                        concise_insights = ["- " + insight[:80] + "..." if len(insight) > 80 else "- " + insight for insight in top_insights] # Shorten insights, limit to ~80 chars
                        lesson_insights_table_data.append({"Lesson Title": lesson_title, "Opportunity Insights": "\n".join(concise_insights)}) # Add to table data


    return output_text, lesson_insights_table_data # Return both Markdown output and table data


if __name__ == "__main__":
    # No more Streamlit code here
    logger.info("Summarization script started.")
    overall_summary, lesson_insights_table_data = summarize_lesson_analyses() # Get both summary and table data

    if overall_summary:
        formatted_output_markdown, _ = format_lesson_insights_for_output(lesson_analyses_data, overall_summary) # Corrected argument order!
        filepath_markdown = "overall_analysis_summary.md" # Define filepath

        try:
            with open(filepath_markdown, "w") as f_md: # Open file for writing
                f_md.write(formatted_output_markdown) # Save Markdown content to file
            logger.info(f"Overall analysis summary (Markdown) saved to: {filepath_markdown}") # Log success

        except Exception as e:
            logger.error(f"Error saving overall analysis summary to file: {e}") # Log error if saving fails
    else:
        logger.error("Failed to generate overall analysis summary.")

    logger.info("Summarization script finished.")