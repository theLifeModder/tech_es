import shutil
import subprocess
import sys

def open_editor(file_path):
    """Verifies physical VS Code host configurations and binds active instances."""
    editor_binary = shutil.which("code")
    
    if not editor_binary:
        print("Error: Visual Studio Code execution binary ('code') could not be detected on this host system path.", file=sys.stderr)
        sys.exit(1)
        
    subprocess.run([editor_binary, "-r", file_path])
