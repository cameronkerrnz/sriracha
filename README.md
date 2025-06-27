# README.md

# Project Title

Brief description of the project.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Experiments](#experiments)
- [Contributing](#contributing)
- [License](#license)

## Installation

Instructions for installing the project dependencies.

```bash
git clone https://github.com/yourusername/yourproject.git
cd yourproject
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Instructions for using the project.

```bash
source .venv/bin/activate
python -m yourmodule
```

## Experiments

To run the Milestone 1 experiment (indexing MBOX files from a Google Takeout zip):

```bash
cd experiments
source ../.venv/bin/activate
python index_mbox_from_zip.py
```

- The script will extract all `.mbox` files from the zip archive and index them in memory using Whoosh.
- The index is persisted to disk in `experiments/whoosh-index/`
- Update the `ZIP_PATH` variable in `index_mbox_from_zip.py` if your archive is in a different location.

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