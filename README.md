# Desktop Picnic

Peruse a MBOX mail archive, such as from a Google Take-out. Search, tag and export
messages to find messages that matter. Data is indexed, so searching is fast. Data
can be stored on a file-server; no infrastructure needed.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Building the App](#building-the-app)
- [Experiments](#experiments)
- [Contributing](#contributing)
- [License](#license)

## Installation

Install dependencies in a virtual environment:

```bash
git clone https://github.com/yourusername/desktop-picnic.git
cd desktop-picnic
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

To run the app from source:

```bash
source .venv/bin/activate
python desktop_picnic_gui.py
```

## Building the App

To package Desktop Picnic as a standalone macOS app using PyInstaller:

- Make sure you have activated your virtual environment and installed requirements.
- Run the VS Code task **Build Desktop Picnic App** (from the Command Palette: `Tasks: Run Task`).
- Or, from the terminal:

```bash
pyinstaller --windowed desktop_picnic_gui.spec
```

The built app will appear in `dist/Desktop Picnic.app` (or as an executable in `dist/desktop_picnic_gui` for onefile mode).

## Experiments

To run the Milestone 1 experiment (indexing MBOX files from a Google Takeout zip):

```bash
cd experiments
source ../.venv/bin/activate
python index_mbox.py
```

- The script will extract all `.mbox` files from the zip archive and index them in memory using Whoosh.
- The index is persisted to disk in `experiments/whoosh-index/`
- Update the `ZIP_PATH` variable in `index_mbox.py` if your archive is in a different location.

## Contributing

Instructions for contributing to the project.

1. Fork the repository
2. Create a new branch (`git checkout -b feature-branch`)
3. Make your changes
4. Commit your changes (`git commit -am 'Add new feature'`)
5. Push to the branch (`git push origin feature-branch`)
6. Create a new Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.