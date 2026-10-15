import shutil
import subprocess
import sys

def open_editor(file_path):
    """Open a file in the running VS Code instance, or report a missing CLI."""
    editor_binary = shutil.which("code")
    
    if not editor_binary:
        print("Error: Visual Studio Code execution binary ('code') could not be detected on this host system path.", file=sys.stderr)
        sys.exit(1)
        
    subprocess.run([editor_binary, "-r", file_path])
