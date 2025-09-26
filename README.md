# gitstats3

**gitstats3** is a git history statistics generator, ported from Python 2 to Python 3.

This project analyzes and visualizes statistics from git repositories (commit activity, author contributions, file changes, and more) and produces an HTML report with charts and detail pages.


**Highlights**

- Generates detailed HTML reports from a git repository
- Produces charts (PNG) and raw data files for further processing
- Supports analyzing one repository or scanning a folder tree for many repositories (multi-repo)
- Lightweight; single-file script with a small set of Python dependencies


**Table of Contents**

- Getting Started
- Installation
- Quick Start (single-repo)
- Multi-Repository Analysis
- CLI Reference (complete)
- Configuration Options (defaults)
- Troubleshooting
- Development & Tests


## Getting Started

### Prerequisites

- Python 3.8+ (or a recent Python 3)
- `git` available on PATH
- Optional but recommended: `gnuplot` (for generating PNG charts)

Python dependencies are listed in `requirements.txt` and include:

- `matplotlib` (>=3.7.0)
- `psutil`


Install them with:

```bash
python -m pip install -r requirements.txt
```


## Installation

Clone the repository and change into the project directory:

```bash
git clone https://github.com/lechibang-1512/gitstats3.git
cd gitstats3
```

You can run the main script directly with `python gitstats.py`.


## Quick Start (single repository)

To analyze a single git repository and create a report:

```bash
python gitstats.py /path/to/your/repo /path/to/output
```

This will:
- Collect repository history and statistics
- Generate an `index.html` report and detail pages in `/path/to/output`
- Produce PNG charts (if `gnuplot` / matplotlib is available)


Common flags:

- `--verbose` show progress and executed commands
- `--debug` show detailed debug traces (implies `--verbose`)
- `-c key=value` override a configuration option (see Configuration Options below)

Example with extra verbosity and worker processes:

```bash
python gitstats.py /path/to/your/repo /path/to/output --verbose -c processes=4
```


## Multi-Repository Analysis

`gitstats3` can scan a folder tree and generate reports for each Git repository it finds. The `--multi-repo` option recursively searches the provided folder (default max depth: 3) and produces individual reports under the output folder.

Usage:

```bash
python gitstats.py --multi-repo /path/to/repos/folder /path/to/output
```

Behavior:
- Recursively scans the folder for git repositories (default max depth: 3)
- Creates a subfolder for each repository named `<reponame>_report` and writes the report there
- Produces a summary index under the base output path linking to each individual report

You can tune scanning via configuration flags (use `-c key=value`):

- `multi_repo_max_depth` (default: 3) — maximum directory depth to scan
- `multi_repo_include_patterns` — comma-separated glob patterns to include
- `multi_repo_exclude_patterns` — comma-separated glob patterns to exclude
- `multi_repo_parallel` (default: False) — process repos in parallel (experimental)
- `multi_repo_max_workers` (default: 4) — number of workers when parallel processing is enabled
- `multi_repo_timeout` (default: 3600) — timeout (seconds) per repository
- `multi_repo_cleanup_on_error` (default: True) — remove partial output on error

Examples:

```bash
# Increase scan depth
python gitstats.py -c multi_repo_max_depth=5 --multi-repo /path/to/repos /path/to/output

# Only include directories matching patterns
python gitstats.py -c multi_repo_include_patterns=proj*,app* --multi-repo /path/to/repos /path/to/output

# Exclude directories (in addition to default exclusions like node_modules)
python gitstats.py -c multi_repo_exclude_patterns=temp*,backup* --multi-repo /path/to/repos /path/to/output
```


## CLI Reference (complete)

Usage patterns:

- Single repo mode:
	```bash
	python gitstats.py [options] <gitpath> <outputpath>
	```

- Multi-repo mode:
	```bash
	python gitstats.py [options] --multi-repo <scan-folder> <outputpath>
	```

Options:

- `-c key=value` — Override a single configuration option at runtime. Examples:
	- `-c processes=4`
	- `-c multi_repo_max_depth=5`

- `--debug` — Enable debug output (implies `--verbose`)
- `--verbose` — Enable verbose logging/progress output
- `--multi-repo` — Scan a folder recursively for git repositories and generate reports for each
- `-h, --help` — Show help text

Notes:
- For multi-repo scanning the script now always scans recursively (no separate `--multi-repo-recursive` option).
- Use `-c` to control multi-repo tuning values (depth, include/exclude patterns, parallelism).


## Configuration Options (defaults)

You can set configuration values with the `-c key=value` option. The following defaults are defined in the script's `conf` dictionary and can be overridden at runtime:

- `max_domains`: 10
- `max_ext_length`: 10
- `style`: `gitstats.css`
- `max_authors`: 20
- `authors_top`: 5
- `commit_begin`: `` (empty)
- `commit_end`: `HEAD`
- `linear_linestats`: 1
- `project_name`: `` (empty)
- `processes`: 8
- `start_date`: `` (empty)
- `debug`: False
- `verbose`: False

Branch scanning defaults:

- `scan_default_branch_only`: True — Only analyze commits from the default branch (main/master/develop). Set to `false` to include all branches.

Multi-repo specific defaults:

- `multi_repo_max_depth`: 3
- `multi_repo_include_patterns`: None
- `multi_repo_exclude_patterns`: None
- `multi_repo_parallel`: False
- `multi_repo_max_workers`: 4
- `multi_repo_timeout`: 3600
- `multi_repo_cleanup_on_error`: True

Examples:

```bash
# Run analysis starting from a specific date
python gitstats.py -c start_date=2024-01-01 /path/to/repo /path/to/output

# Limit number of worker processes
python gitstats.py -c processes=2 /path/to/repo /path/to/output

# Scan all branches instead of just the default branch
python gitstats.py -c scan_default_branch_only=false /path/to/repo /path/to/output
```


## Troubleshooting

- If charts are missing, ensure `matplotlib` is available in your Python environment.
- If you see permission errors, confirm read access to the repository and write access to the output folder.
- Use `--debug` to see the git/gnuplot commands executed; this helps reproduce and fix issues.
- If `--multi-repo` finds no repositories, try increasing `multi_repo_max_depth`.


## Development & Tests

- The script is a single-file implementation (`gitstats.py`) and can be extended by editing that file.
- To run basic operations locally (recommended in a virtualenv):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gitstats.py /path/to/repo /path/to/output
```


## Contributing

Contributions are welcome. Suggested improvements:

- Add unit tests for the CLI and multi-repo scanning behavior
- Improve parallel multi-repo processing and add a progress indicator
- Add a `gitstats` console script entry point to install as a CLI tool


---

For details about code structure and internals, inspect `gitstats.py` directly — the core `conf` dictionary, the multi-repo discovery functions, and `GitDataCollector` / `HTMLReportCreator` are implemented there.

