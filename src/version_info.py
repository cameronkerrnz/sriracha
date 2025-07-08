import os
import subprocess

def get_version_info():
    version = None
    version_file = os.path.join(os.path.dirname(__file__), '..', 'VERSION')
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            version = f.read().strip()
    except Exception:
        version = 'unknown'
    # Try to get git commit hash
    try:
        git_dir = os.path.join(os.path.dirname(__file__), '..')
        commit = subprocess.check_output(
            ['git', '-C', git_dir, 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
    except Exception:
        commit = None
    if commit:
        return f"{version} (git {commit})"
    else:
        return version
