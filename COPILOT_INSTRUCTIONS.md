# Self-Maintenance Instructions for GitHub Copilot

1. Always update `requirements.txt` whenever a new Python package is added, removed, or upgraded in the project. Ensure it reflects all runtime dependencies required for the project to run and is kept in sync with the actual environment.

2. When adding, removing, or changing project features, document these changes in `README.md`. This includes:
   - Project setup instructions (e.g., how to create and activate the virtual environment, install dependencies, and run the application)
   - Usage instructions for new features or scripts
   - Any changes to the project structure or workflow

3. If a new dependency is required for a feature, add it to `requirements.txt` before or at the same time as the code change.

4. If a new script, module, or major feature is added, update `README.md` to describe its purpose and usage.

5. When removing a dependency or feature, ensure both `requirements.txt` and `README.md` are updated to reflect the removal.

6. Always check that both files are up to date before considering a feature or fix complete.

7. If the user expresses a preference for a specific format or content in either file, follow that preference for all future changes.
