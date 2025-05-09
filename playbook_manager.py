# playbook_manager.py
import os
import json

PLAYBOOK_DIR = "playbooks"

def load_playbook(form_key):
    """
    Load a playbook (JSON) for the given form key (e.g., domain).
    Returns the playbook data (dict or list) or None if not found.
    """
    ensure_playbook_dir()
    filename = _key_to_filename(form_key)
    filepath = os.path.join(PLAYBOOK_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"[Playbook] Loaded existing playbook for '{form_key}' from {filepath}")
            return data
        except Exception as e:
            print(f"[Playbook] Error loading playbook {filepath}: {e}")
            return None
    else:
        print(f"[Playbook] No playbook found for '{form_key}'")
        return None

def save_playbook(form_key, playbook_data):
    """
    Save the playbook data (dict or list) to a JSON file identified by form_key.
    """
    ensure_playbook_dir()
    filename = _key_to_filename(form_key)
    filepath = os.path.join(PLAYBOOK_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(playbook_data, f, indent=2)
        print(f"[Playbook] Saved playbook for '{form_key}' to {filepath}")
    except Exception as e:
        print(f"[Playbook] Failed to save playbook for '{form_key}': {e}")

def ensure_playbook_dir():
    """Ensure the playbook directory exists."""
    os.makedirs(PLAYBOOK_DIR, exist_ok=True)

def _key_to_filename(form_key):
    """
    Sanitize and convert a form_key (like a domain) to a filename.
    For example, 'www.seek.com.au' -> 'www_seek_com_au.json'
    """
    # Basic sanitization: replace dots with underscores and add .json extension
    filename = form_key.replace(".", "_") + ".json"
    # Further sanitization could be added if needed (e.g., handling spaces, special chars)
    return filename

# Example usage (if standalone test):
if __name__ == "__main__":
    # This is a placeholder example. In a real scenario, you would get playbook_data
    # from llm_agent.generate_playbook.
    sample_playbook = {
      "actions": [
        {
          "action": "click",
          "target": "input#resume-method-:r1:_0",
          "description": "Select 'Upload a resumé' option"
        },
        {
          "action": "upload",
          "target": "input#resume-fileFile",
          "value": "/path/to/UserResume.pdf",
          "description": "Upload resume file"
        }
      ]
    }
    sample_key = "www.example.com"

    print(f"Attempting to load playbook for '{sample_key}'...")
    loaded_playbook = load_playbook(sample_key)

    if loaded_playbook is None:
        print(f"No playbook found, saving sample playbook for '{sample_key}'...")
        save_playbook(sample_key, sample_playbook)
        print(f"Attempting to load playbook for '{sample_key}' again...")
        loaded_playbook_after_save = load_playbook(sample_key)
        print("Loaded playbook after save:", json.dumps(loaded_playbook_after_save, indent=2))
    else:
        print("Loaded existing playbook:", json.dumps(loaded_playbook, indent=2))