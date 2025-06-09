import os
from openai import OpenAI
from dotenv import load_dotenv
from bs4 import BeautifulSoup # Import BeautifulSoup for HTML parsing

# Load environment variables from .env file
load_dotenv()

# This script attempts to interact with the OpenAI LLM API.
# It is designed to demonstrate potential errors that can occur
# when programmatically interacting with an LLM, such as:
# - Missing or incorrect API key
# - Invalid request format (e.g., missing required parameters)
# - API limits or other service-side errors
# It also demonstrates handling large inputs by extracting relevant information.

def interact_with_openai_llm():
    """
    Attempts to send a request to the OpenAI Chat Completions endpoint.
    This function will use the API key loaded from the .env file.
    It will extract relevant information from an HTML file before sending.
    """
    # Get API key from environment variables
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please make sure you have a .env file with OPENAI_API_KEY=your_api_key")
        return

    try:
        # Initialize the OpenAI client
        client = OpenAI(api_key=api_key)

        # Define the path to the HTML file
        html_file_path = "screenshots/application_step1.html"

        # Read the content of the HTML file
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except FileNotFoundError:
            print(f"Error: HTML file not found at {html_file_path}")
            return
        except Exception as e:
            print(f"Error reading HTML file: {e}")
            return

        # Parse the HTML content and extract relevant information
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract job title and company
        job_title_element = soup.select_one('h1._15uaf0e0._1li239b4z._15gbqyr0._15gbqyrl.ni6qyg4._15gbqyrp._15gbqyr21')
        company_name_element = soup.select_one('span._15uaf0e0._1li239b4z._15gbqyr0._15gbqyr1._15gbqyr21.ni6qyg4._15gbqyrd')

        job_title_text = job_title_element.get_text(strip=True) if job_title_element else 'N/A'
        company_name_text = company_name_element.get_text(strip=True) if company_name_element else 'N/A'
        job_info = f"Applying for: {job_title_text} at {company_name_text}\n\n"

        # Extract personal details
        personal_details_heading_element = soup.select_one('h3._15uaf0e0._1li239b4z._15gbqyr0._15gbqyrl.ni6qyg4._15gbqyrs._15gbqyr21')
        personal_details_text = 'N/A'
        if personal_details_heading_element:
            details_div_element = personal_details_heading_element.find_next_sibling('div')
            if details_div_element:
                personal_details_text = details_div_element.get_text(separator='\n', strip=True)
        
        personal_info = f"Personal Details:\n{personal_details_text}\n\n"

        # Extract resume information
        resume_heading_element = soup.find('h3', string='Resumé')
        resume_info_text = "Resumé:\n"
        if resume_heading_element:
            fieldset_element = resume_heading_element.find_next_sibling('fieldset')
            if fieldset_element:
                selected_resume_label_element = fieldset_element.select_one('input[name="resume-method"]:checked + div label')
                selected_resume_name_element = fieldset_element.select_one('select option[selected]')

                if selected_resume_label_element:
                    resume_info_text += f"- Option selected: {selected_resume_label_element.get_text(strip=True)}\n"
                
                if selected_resume_name_element:
                     resume_info_text += f"- Selected resumé: {selected_resume_name_element.get_text(strip=True)}\n"
                elif not selected_resume_label_element: # If no label and no selected name, then likely no resume selected/uploaded
                     resume_info_text += "- No resumé selected or uploaded.\n"
            else:
                resume_info_text += "Resumé fieldset not found.\n"
        else:
            resume_info_text += "Resumé section heading not found.\n"
        resume_info_text += "\n"


        # Extract cover letter information
        cover_letter_heading_element = soup.find('h3', string='Cover letter')
        cover_letter_info_text = "Cover letter:\n"
        if cover_letter_heading_element:
            fieldset_element = cover_letter_heading_element.find_next_sibling('fieldset')
            if fieldset_element:
                selected_cover_letter_label_element = fieldset_element.select_one('input[name="coverLetter-method"]:checked + div label')
                cover_letter_text_area_element = fieldset_element.select_one('textarea')

                if selected_cover_letter_label_element:
                    cover_letter_info_text += f"- Option selected: {selected_cover_letter_label_element.get_text(strip=True)}\n"
                
                if cover_letter_text_area_element and cover_letter_text_area_element.get_text(strip=True):
                    cover_letter_info_text += f"- Cover letter content:\n{cover_letter_text_area_element.get_text(strip=True)}\n"
                elif not selected_cover_letter_label_element: # If no label and no text area content
                    cover_letter_info_text += "- No cover letter content found or option selected.\n"
            else:
                cover_letter_info_text += "Cover letter fieldset not found.\n"
        else:
            cover_letter_info_text += "Cover letter section heading not found.\n"
        cover_letter_info_text += "\n"

        # Combine extracted information
        extracted_info = job_info + personal_info + resume_info_text + cover_letter_info_text

        # Define the prompt and model
        model = "gpt-3.5-turbo" # Or another suitable model
        messages = [
            {"role": "system", "content": "Analyze the following extracted information from a job application page and summarize the key details about the applicant, the job, and the documents being submitted."},
            {"role": "user", "content": extracted_info}
        ]
        # Adjust max_tokens as needed for a summary of the extracted information
        max_tokens = 500

        print(f"Attempting to call OpenAI LLM API using model: {model}")
        print(f"Analyzing extracted information from: {html_file_path}")
        print("--- Extracted Information ---")
        print(extracted_info)
        print("-----------------------------")


        # Make the API call
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens
        )

        # ——— GPT-3.5-turbo usage logging ———
        try:
            usage = response.usage
            pt = usage.prompt_tokens
            ct = usage.completion_tokens
            tt = usage.total_tokens
            ir, orate = (0.03, 0.06) if model.startswith("gpt-4") else (0.0015, 0.002)
            ic = pt * ir / 1000
            oc = ct * orate / 1000
            tc = ic + oc
            print(f"[{model} usage] prompt={pt}, completion={ct}, total={tt} tokens;"
                  f" cost_input=${ic:.4f}, cost_output=${oc:.4f}, cost_total=${tc:.4f}")
        except Exception:
            print(f"[{model} usage] ⚠️ failed to read response.usage")
        # ———————————————————————

        # Print the response
        print("\nOpenAI API analysis successful:")
        print(response.choices[0].message.content)

    except Exception as e:
        # Catch any exceptions during the API call
        print("\nAn error occurred while interacting with the OpenAI LLM API:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {e}")


if __name__ == "__main__":
    interact_with_openai_llm()