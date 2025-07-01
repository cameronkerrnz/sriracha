# Sriracha - Makes Takeout Better

Sriracha is a fast desktop email viewer for large mbox archives. It is designed for power users, researchers, and anyone who needs to search, filter, and explore large email collections efficiently.

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
git clone https://github.com/cameronkerrnz/sriracha.git
cd sriracha
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

To run the app from source:

```bash
source .venv/bin/activate
python src/sriracha_gui.py
```

## Building the App

To build a standalone app (macOS):

```bash
pyinstaller packaging/sriracha_gui.spec
```


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

## Developer Prerequisites

- Python 3.13 (recommended)
- [ImageMagick](https://imagemagick.org/) (required for generating Windows .ico icons from PNG)
    - On macOS: `brew install imagemagick`
    - On Linux: `sudo apt install imagemagick`
    - On Windows: Download from the official site and add to PATH
- (macOS only) Xcode command line tools (for iconutil and sips)
- (Linux only) AppImage tools if you want to build AppImage packages

See `.vscode/tasks.json` for platform-specific build and icon generation tasks.