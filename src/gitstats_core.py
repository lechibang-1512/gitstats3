"""
Gitstats3 - Git repository statistics generator.

This module provides comprehensive git repository analysis and HTML report generation.
This is the main entry point that imports from the modular src/ package.
"""

import sys

# Version check
if sys.version_info < (3, 6):
    print("Python 3.6 or higher is required for gitstats", file=sys.stderr)
    sys.exit(1)

# Re-export core components for backward compatibility
from .gitstats_config import conf, get_config, GitStatsConfig
from .gitstats_helpers import (
    ON_LINUX, WEEKDAYS,
    getkeyssortedbyvalues, getkeyssortedbyvaluekey,
    getstatsummarycounts, should_include_file
)
from .gitstats_gitcommands import (
    getpipeoutput, getpipeoutput_list,
    get_default_branch, get_first_parent_flag,
    getlogrange, getcommitrange,
    is_git_repository, getversion, getgitversion,
    get_exectime_external
)
from .gitstats_tabledata import TableDataGenerator
from .gitstats_oopmetrics import OOPMetricsAnalyzer, format_oop_report
from .gitstats_sortable import get_sortable_js

# Import extracted core classes
from .gitstats_datacollector import DataCollector
from .gitstats_gitdatacollector import GitDataCollector
from .gitstats_htmlreport import ReportCreator, HTMLReportCreator, html_linkify, html_header
from .gitstats_repository import (
    _is_bare_repository,
    discover_repositories,
    _discover_repositories_concurrent
)
from .gitstats_cli import usage, GitStats


# Module-level functions that depend on imported utilities
import os
import re
import time

# Set locale for consistent git output
os.environ['LC_ALL'] = 'C'

# Timing variables for performance tracking
exectime_internal = 0.0
time_start = time.time()


def get_output_format():
    """Return output format description."""
    return "HTML tables (no charts)"


def getnumoffilesfromrev(time_rev):
    """Get number of files changed in commit (filtered by allowed extensions)."""
    time_val, rev = time_rev
    if conf['filter_by_extensions']:
        try:
            all_files_output = getpipeoutput(['git ls-tree -r --name-only "%s"' % rev])
            if not all_files_output:
                return (int(time_val), rev, 0)
            all_files = all_files_output.split('\n')
            filtered_files = [f for f in all_files if f.strip() and should_include_file(f.split('/')[-1])]
            return (int(time_val), rev, len(filtered_files))
        except (ValueError, IndexError) as e:
            if conf['debug']:
                print(f'Warning: Failed to get file count for rev {rev}: {e}')
            return (int(time_val), rev, 0)
    else:
        try:
            output = getpipeoutput(['git ls-tree -r --name-only "%s"' % rev, 'wc -l'])
            if not output or not output.strip():
                return (int(time_val), rev, 0)
            count = int(output.split('\n')[0].strip())
            return (int(time_val), rev, count)
        except (ValueError, IndexError) as e:
            if conf['debug']:
                print(f'Warning: Failed to get file count for rev {rev}: {e}')
            return (int(time_val), rev, 0)


def getnumoflinesinblob(ext_blob):
    """Get number of lines in blob."""
    ext, blob_id = ext_blob
    try:
        output = getpipeoutput(['git cat-file blob %s' % blob_id, 'wc -l'])
        if not output or not output.strip():
            return (ext, blob_id, 0)
        count = int(output.split()[0])
        return (ext, blob_id, count)
    except (ValueError, IndexError) as e:
        if conf['debug']:
            print(f'Warning: Failed to get line count for blob {blob_id}: {e}')
        return (ext, blob_id, 0)


def analyzesloc(ext_blob):
    """
    Analyze source lines of code vs comments vs blank lines in a blob.
    Returns (ext, blob_id, total_lines, source_lines, comment_lines, blank_lines).
    """
    ext, blob_id = ext_blob
    content = getpipeoutput(['git cat-file blob %s' % blob_id])

    total_lines = 0
    source_lines = 0
    comment_lines = 0
    blank_lines = 0

    # Define comment patterns for different file types
    comment_patterns = {
        '.py': [r'^\s*#', r'^\s*"""', r"^\s*'''"],
        '.js': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
        '.ts': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
        '.java': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
        '.cpp': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
        '.c': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
        '.h': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
        '.css': [r'^\s*/\*', r'^\s*\*'],
        '.html': [r'^\s*<!--', r'^\s*<!\-\-'],
        '.xml': [r'^\s*<!--', r'^\s*<!\-\-'],
        '.sh': [r'^\s*#'],
        '.rb': [r'^\s*#'],
        '.pl': [r'^\s*#'],
        '.php': [r'^\s*//', r'^\s*/\*', r'^\s*\*', r'^\s*#'],
    }

    patterns = comment_patterns.get(ext, [])

    for line in content.split('\n'):
        total_lines += 1
        line_stripped = line.strip()

        if not line_stripped:
            blank_lines += 1
        elif any(re.match(pattern, line) for pattern in patterns):
            comment_lines += 1
        else:
            source_lines += 1

    return (ext, blob_id, total_lines, source_lines, comment_lines, blank_lines)


# Main entry point
if __name__ == '__main__':
    try:
        g = GitStats()
        g.run(sys.argv[1:])
    except KeyboardInterrupt:
        print('\nInterrupted by user')
        sys.exit(1)
    except KeyError as e:
        print(f'FATAL: Configuration error: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'FATAL: Unexpected error: {e}')
        if conf.get('debug', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)
