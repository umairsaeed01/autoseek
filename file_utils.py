# file_utils.py
import os
import re

def slugify_title(title):
    """
    Convert a job title into a slug suitable for filenames.
    e.g. "Software Engineer (AI/ML)" -> "Software-Engineer-AI-ML"
    """
    if not title:
        return ""
    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^A-Za-z0-9]+', '-', title)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    # Limit length if necessary (optional, to avoid extremely long names)
    if len(slug) > 100:
        slug = slug[:100]
    return slug

def ensure_dir(path):
    """Create the directory (and parent dirs) if it doesn't exist."""
    os.makedirs(path, exist_ok=True)

def get_unique_filename(dir_path, base_name, extension):
    """
    Generate a unique file path in dir_path for base_name with the given extension.
    Avoids overwriting by adding suffix.
    """
    # Start with no suffix
    file_name = f"{base_name}.{extension}"
    file_path = os.path.join(dir_path, file_name)
    counter = 1
    # Increment suffix until a free name is found
    while os.path.exists(file_path):
        file_name = f"{base_name}_{counter}.{extension}"
        file_path = os.path.join(dir_path, file_name)
        counter += 1
    return file_path