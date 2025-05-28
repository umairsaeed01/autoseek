# html_processor.py
from bs4 import BeautifulSoup, NavigableString

def extract_form_sections(html_content):
    """
    Parse the HTML content and extract relevant form sections as text.
    Returns a list of section text chunks.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove irrelevant elements
    for tag in soup.find_all(['script', 'style', 'noscript', 'header', 'footer', 'nav', 'aside']):
        tag.decompose()

    # Handle iframes
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        iframe_content = iframe.get('srcdoc') or iframe.get('src')
        if iframe_content:
            try:
                iframe_soup = BeautifulSoup(iframe_content, "html.parser")
                # Add iframe content to main soup
                iframe.replace_with(iframe_soup)
            except Exception as e:
                print(f"[Warning] Could not parse iframe content: {e}")

    # Handle dynamic content
    dynamic_elements = soup.find_all(['div', 'button'], attrs={'data-dynamic': True})
    for elem in dynamic_elements:
        elem['data-visible'] = 'true'
        # Add continue button specific handling
        if elem.get('data-testid') == 'continue-button':
            elem['data-visible'] = 'true'
            elem['data-clickable'] = 'true'

    sections = []

    # Find form sections via <fieldset> or <form> tags
    fieldsets = soup.find_all('fieldset')
    if fieldsets:
        # Multiple sections found
        for fs in fieldsets:
            section_text = _process_section(fs)
            if section_text:
                sections.append(section_text)
    else:
        # If no fieldsets, use the main form (if any) or body as one section
        main_form = soup.find('form')
        section_container = main_form if main_form else soup.body
        if section_container:
            section_text = _process_section(section_container)
            if section_text:
                sections.append(section_text)

    # Add continue button section if found
    continue_button = soup.find('button', attrs={'data-testid': 'continue-button'})
    if continue_button:
        continue_section = _process_section(continue_button)
        if continue_section:
            sections.append(continue_section)

    return sections

def _process_section(section_element):
    """
    Helper to extract text from a section of the form (fieldset or form).
    Returns cleaned text for that section.
    """
    # Determine section title if available
    title = ""
    # Check for aria-label or legend (for fieldset)
    if section_element.name == 'fieldset':
        if section_element.has_attr('aria-label'):
            title = section_element['aria-label']
        legend = section_element.find('legend')
        if legend:
            title = legend.get_text(strip=True) or title
    # If section has a preceding heading in the HTML, use that (for non-fieldset sections)
    if not title:
        prev_heading = section_element.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if prev_heading:
            title = prev_heading.get_text(strip=True)

    # Create a copy of the section HTML to manipulate (so we don't alter the original soup)
    section_html = str(section_element)
    sec_soup = BeautifulSoup(section_html, "html.parser")

    # Remove scripts or styles in this section if any
    for tag in sec_soup.find_all(['script', 'style', 'noscript']):
        tag.decompose()

    # Replace form inputs and controls with placeholders
    for inp in sec_soup.find_all(['input', 'textarea', 'button', 'select']):
        placeholder = ""
        tag_name = inp.name
        if tag_name == 'input':
            input_type = inp.get('type', 'text')
            if input_type == 'hidden':
                # skip hidden inputs entirely
                inp.decompose()
                continue
            placeholder = f"[INPUT: type={input_type}"
            name = inp.get('name')
            if name:
                placeholder += f", name={name}"
            # Include placeholder text if any (for text inputs)
            if inp.get('placeholder'):
                ph = inp['placeholder']
                placeholder += f", placeholder={ph}"
            if input_type in ['radio', 'checkbox']:
                # We'll rely on label text for meaning, so we may not include value unless no label
                value = inp.get('value')
                if value and value.lower() not in ["on", "off", ""]:
                    placeholder += f", value={value}"
            if input_type == 'file':
                placeholder += ", file upload"
            placeholder += "]"
        elif tag_name == 'textarea':
            placeholder = "[TEXTAREA"
            name = inp.get('name')
            if name:
                placeholder += f", name={name}"
            if inp.get('placeholder'):
                ph = inp['placeholder']
                placeholder += f", placeholder={ph}"
            placeholder += "]"
        elif tag_name == 'button':
            # Special handling for continue button
            if inp.get('data-testid') == 'continue-button':
                placeholder = "[BUTTON: Continue]"
            else:
                # Only include meaningful buttons (e.g., submit)
                btn_type = inp.get('type', 'button')
                btn_text = inp.get_text(strip=True)
                # If it's a submit or next button, include it; otherwise skip minor buttons
                if btn_type in ['submit', 'button'] and btn_text:
                    placeholder = f"[BUTTON: {btn_text}]"
                else:
                    # If no text or not a submit, skip it
                    inp.decompose()
                    continue
        elif tag_name == 'select':
            # Summarize select options
            name = inp.get('name')
            options = [opt.get_text(strip=True) for opt in inp.find_all('option')]
            options = [opt for opt in options if opt]  # remove empty texts
            opt_summary = ""
            if options:
                if len(options) > 5:
                    # Take first 3 options for preview
                    opt_summary = ", ".join(options[:3]) + f", ... (+{len(options)-3} more options)"
                else:
                    opt_summary = ", ".join(options)
            placeholder = "[SELECT"
            if name:
                placeholder += f", name={name}"
            if opt_summary:
                placeholder += f", options={opt_summary}"
            placeholder += "]"
        # Replace the element with the placeholder text node, if we set one
        if placeholder:
            inp.replace_with(NavigableString(placeholder))

    # Remove all tag attributes from remaining tags (to remove clutter like huge class names)
    for tag in sec_soup.find_all():
        if tag.name in ['input', 'textarea', 'button', 'select', 'option']:
            # these should have been handled or removed above
            continue
        # Keep label text but remove its attributes
        if tag.name == 'label':
            tag.attrs = {}
        else:
            # Remove attributes for any other tags (div, span, etc.)
            tag.attrs = {}

    # Get text content with each block separated by newline
    section_text = sec_soup.get_text(separator="\n", strip=True)
    if title:
        # Prepend the section title as a header
        section_text = title + ":\n" + section_text
    return section_text.strip()

def extract_page_sections(html_content):
    """
    Extract sections from HTML content, focusing on upload-related sections.
    Each section is truncated to avoid token limit issues.
    """
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get all form elements and their containers
        sections = []
        MAX_SECTION_LEN = 2000  # Maximum length for any section
        
        # Find all form elements
        forms = soup.find_all('form')
        for form in forms:
            # Get form's parent container
            container = form.find_parent('div', class_=lambda x: x and ('container' in x.lower() or 'section' in x.lower()))
            if container:
                section_text = container.get_text(separator=' ', strip=True)
                if len(section_text) > MAX_SECTION_LEN:
                    section_text = section_text[:MAX_SECTION_LEN] + "..."
                sections.append(section_text)
                
        # Find upload-related divs
        upload_keywords = ['resume', 'cover', 'upload', 'file', 'document']
        for div in soup.find_all('div'):
            # Check if div contains upload-related keywords
            if any(keyword in div.get_text().lower() for keyword in upload_keywords):
                section_text = div.get_text(separator=' ', strip=True)
                if len(section_text) > MAX_SECTION_LEN:
                    section_text = section_text[:MAX_SECTION_LEN] + "..."
                sections.append(section_text)
                
        # If no sections found, get main content
        if not sections:
            main = soup.find('main') or soup.find('div', role='main')
            if main:
                section_text = main.get_text(separator=' ', strip=True)
                if len(section_text) > MAX_SECTION_LEN:
                    section_text = section_text[:MAX_SECTION_LEN] + "..."
                sections.append(section_text)
                
        return sections
        
    except Exception as e:
        print(f"Error extracting page sections: {e}")
        return []