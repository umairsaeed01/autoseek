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