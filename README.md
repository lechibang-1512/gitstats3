# gitstats3

**gitstats3** is a git history statistics generator, ported from Python 2 to Python 3.

This project allows you to analyze and visualize various statistics from a git repository, such as commit activity, author contributions, and more. It is a fork of the original [gitstats](https://github.com/hoxu/gitstats) project, updated to work with modern Python environments.

## Features

- Generates detailed statistics and graphs from git repositories
- Analyzes commit history, author contribution, file changes, and more
- Output is visual and easy to share

## Getting Started

### Prerequisites

- Python 3.x
- Git (installed and available in your system path)

### Installation

Clone the repository:

```sh
git clone https://github.com/lechibang-1512/gitstats3.git
cd gitstats3
```

Install required dependencies (if any):

```sh
pip install -r requirements.txt
```

### Usage

To generate statistics for a git repository:

```sh
python gitstats <path-to-git-repo> <output-directory>
```

Example:

```sh
python gitstats /path/to/your/repo /path/to/output
To generate statistics for a git repository:

```sh
python gitstats <path-to-git-repo> <output-directory>
```

Common options:

- `--debug`: print detailed command traces and timings (useful for diagnosing issues).
- `--verbose`: show progress and executed git/gnuplot commands.
- `--processes N`: run N worker processes when collecting data (default depends on your machine).

Example:

```sh
python gitstats /path/to/your/repo /path/to/output --verbose --processes 4
```

This will analyze the git repository and generate an HTML report (and optional PDF) in the output directory.

Required system dependencies and notes:

- **Python 3.x**: the script targets modern Python 3.
- **Git**: required for reading repository history.
- **gnuplot**: used to render charts. If not installed, `.dat` and `.plot` files will still be produced but PNG graphs won't be generated.
- **fpdf** (Python package): used to create a summary PDF. You may see deprecation warnings from older fpdf APIs; the PDF is still created successfully, but updating `fpdf` usage can remove warnings.

Install Python dependencies (if provided):

```sh
pip install -r requirements.txt
```

On Debian/Ubuntu you can install system deps with:

```sh
sudo apt-get update && sudo apt-get install git gnuplot
```

Generated output (example files written to the output directory):

- `index.html`: main HTML report with links to charts and pages.
- `authors.html`, `lines.html`, `files.html`, `tags.html`, `activity.html`: detail pages for each statistic.
- `*.dat`, `*.plot`: raw data and gnuplot scripts used to generate images.
- `*.png`: chart images produced by `gnuplot` (if available).
- `gitstats_*.pdf`: optional PDF summary produced via `fpdf`.

Troubleshooting tips:

- If charts are missing, confirm `gnuplot` is installed and available in your `PATH`.
- If the script fails with permission errors, ensure you have read access to the git repository and write access to the output directory.
- Use `--debug` to see the exact git and gnuplot commands being executed; this helps reproduce and fix issues.
- If you see fpdf deprecation warnings, the PDF is likely still generated. Consider upgrading the `fpdf` package or updating the PDF-generation code to use the current API.
