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
```

This will analyze the git repository and generate an HTML report in the output directory.

## License

This project is a fork of [hoxu/gitstats](https://github.com/hoxu/gitstats). Please refer to the original project for licensing details.

## Acknowledgements

- Original author: [hoxu/gitstats](https://github.com/hoxu/gitstats)
- Ported to Python 3 by [lechibang-1512](https://github.com/lechibang-1512)
