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
    Returns a tuple: (summary_markdown, lesson_insights_table_data, executive_summary_table_data, lesson_analyses_data).
    Returns None, None, None, None in case of error or no data.
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
        return None, None, None, None # Return None for all four values if no data

    prompt = f"""
    You are an expert learning and curriculum designer, providing **highly concise and actionable** insights to improve a coding education platform. Analyze the following lesson concept analyses.
    Identify:
    1.  **Top 3 Key Challenges**: Identify the top 3 most significant, recurring challenges or areas of difficulty students are facing across all lessons, based on the combined lesson analyses. Focus on actionable curriculum improvements to address these.
    2.  **Lesson-Specific Opportunity Insights for Coaches**: For each lesson, extract 2-3 key insights that coaches can use to better support students in those specific lessons. These should be very specific and actionable for coaches.

    Format your output as follows:

    Part 1: Executive Summary - Top Curriculum Improvement Priorities

    ### [Key Challenge 1]
    - **Description:** [Concise description of the challenge]
    - **Example:** [Brief example illustrating the challenge]
    - **Severity Level:** [High/Medium/Low]
    - **Actionable Recommendation:** [Specific, actionable recommendation to address this challenge in the curriculum]

    ### [Key Challenge 2]
    - **Description:** [Concise description of the challenge]
    - **Example:** [Brief example illustrating the challenge]
    - **Severity Level:** [High/Medium/Low]
    - **Actionable Recommendation:** [Specific, actionable recommendation to address this challenge in the curriculum]

    ### [Key Challenge 3]
    - **Description:** [Concise description of the challenge]
    - **Example:** [Brief example illustrating the challenge]
    - **Severity Level:** [High/Medium/Low]
    - **Actionable Recommendation:** [Specific, actionable recommendation to address this challenge in the curriculum]


    Part 2: PRIORITIZED Lesson-Specific Opportunity Insights for Coaches

    **Lesson Title:** [Lesson Title 1]
    - **Opportunity Insights:** [Bulleted list of 2-3 actionable insights for coaches for this lesson]

    **Lesson Title:** [Lesson Title 2]
    - **Opportunity Insights:** [Bulleted list of 2-3 actionable insights for coaches for this lesson]

    ... (and so on for each lesson)


    Combined Lesson Analyses:
    {combined_analysis_text}
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

        return formatted_output_markdown, lesson_insights_table_data, executive_summary_table_data, lesson_analyses_data # Return all four values

    except Exception as e:
        logger.error(f"Error during overall analysis summarization with OpenAI: {e}")
        return None, None, None, None # Return None for all four values in case of error


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

    if lesson_analyses_data:
        output_text += "### Part 2: PRIORITIZED Lesson-Specific Opportunity Insights for Coaches\n\n" # Markdown for Part 2
        output_text += "These insights are designed to be concise and immediately actionable for coaches, enhancing their support to students in specific lessons.\n\n"

        for lesson_analysis in lesson_analyses_data:
            lesson_title = lesson_analysis['title']
            analysis_lines = lesson_analysis['analysis'].split('\n')
            insights = []
            collect_insights = False

            for line in analysis_lines:
                if "Concepts or Topics Students are **Struggling** to Understand:" in line:
                    collect_insights = True
                    continue
                elif "Concepts or Topics Students Seem to **Understand Well**:" in line:
                    collect_insights = False
                    break # Stop collecting after struggles, before good understanding for conciseness
                elif collect_insights and line.strip() and not line.startswith("Examples:"): # Capture insights, not examples
                    insight = line.strip().replace('- ', '').replace('* ', '') # Clean up insight formatting
                    if insight: # Only add non-empty insights
                        insights.append(insight)

            if insights:
                lesson_insights_table_data.append({
                    "Lesson Title": lesson_title,
                    "Opportunity Insights": "\n".join([f"- {insight}" for insight in insights[:3]]) # Take only first 3 insights and format as bullet points
                })
                output_text += f"**Lesson Title:** {lesson_title}\n"
                output_text += "- **Opportunity Insights:**\n"
                for insight in insights[:3]: # Output only the first 3 insights in markdown
                    output_text += f"  - {insight}\n"
                output_text += "\n"
    else:
        output_text += "No lesson-specific insights available.\n" # Handle no data case

    return output_text, lesson_insights_table_data # Returns empty Markdown output and table data for Part 2


if __name__ == "__main__":
    logger.info("Summarization script started.")
    overall_summary_markdown, lesson_insights_table_data, executive_summary_table_data, lesson_analyses_data = summarize_lesson_analyses() # Capture lesson_analyses_data

    if overall_summary_markdown and lesson_insights_table_data and executive_summary_table_data and lesson_analyses_data: # Check lesson_analyses_data too
        filepath_markdown = "overall_analysis_summary.md"

        try:
            with open(filepath_markdown, "w") as f_md:
                f_md.write(overall_summary_markdown)
            logger.info(f"Overall analysis summary (Markdown) saved to: {filepath_markdown}")
        except Exception as e:
            logger.error(f"Error saving overall analysis summary to file: {e}")
    else:
        logger.error("Failed to generate overall analysis summary.")

    logger.info("Summarization script finished.")