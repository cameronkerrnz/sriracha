import os
import subprocess

try:
    from _baked_version import VERSION as BAKED_VERSION, GIT_COMMIT as BAKED_COMMIT
except ImportError:
    BAKED_VERSION = None
    BAKED_COMMIT = None

def get_version_info():
    # Prefer baked-in version info if available
    if BAKED_VERSION and BAKED_COMMIT:
        return f"{BAKED_VERSION} (git {BAKED_COMMIT})"
    elif BAKED_VERSION:
        return BAKED_VERSION
    # Fallback to dynamic detection
    version = None
    version_file = os.path.join(os.path.dirname(__file__), '..', 'VERSION')
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            version = f.read().strip()
    except Exception:
        version = 'unknown'
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
