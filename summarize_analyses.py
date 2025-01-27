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
    returning the summary in Markdown format.
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
    You are an expert learning and curriculum designer for a coding education platform. Analyze these lesson concept analyses (separated by '---START LESSON ANALYSIS---'). 

    Produce a report in Markdown format with two parts:

    **Part 1: Executive Summary of Top Curriculum Improvement Priorities**

    * Identify the **TOP 3-5 KEY RECURRING CHALLENGES** or areas of struggle across lessons. Focus on fundamental concepts.
    * For each challenge, include: Description, Example (if available), **Severity Level (High/Medium/Low)**, and **Actionable Recommendations** for curriculum improvement.

    **Part 2: Detailed Lesson-Specific Opportunity Insights for Coaches**

    * For EACH lesson, provide a concise bulleted list of "Opportunity Insights for Coaches." 
    * Each insight should clearly state a student struggle and a coaching suggestion. 
    * Aim for 1-3 insights per lesson.

    Analyses:
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
    """Formats lesson-specific insights for Markdown output."""
    output_text = "## Overall Learning Platform Content Analysis Summary and Recommendations\n\n"
    output_text += "### Part 1: Executive Summary - Top Curriculum Improvement Priorities\n\n"
    output_text += overall_summary + "\n\n"

    output_text += "### Part 2: Detailed Lesson-Specific Opportunity Insights for Coaches\n\n"
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
                        struggles_insights.append(insight_text)

            if struggles_insights:
                output_text += "#### Opportunity Insights for Coaches:\n"
                for insight in struggles_insights:
                    output_text += f"- {insight}\n"
            else:
                output_text += "- No specific student struggles identified in the analysis for this lesson.\n"
        else:
            output_text += "- No student struggles data found in the analysis for this lesson. Review full analysis file for details.\n"

        output_text += "\n"

    return output_text


if __name__ == "__main__":
    summary_report, lesson_analyses_data = summarize_lesson_analyses()

    if summary_report:
        formatted_output_markdown = format_lesson_insights_for_output(lesson_analyses_data, summary_report)
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