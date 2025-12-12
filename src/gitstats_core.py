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
    getstatsummarycounts, should_include_file,
    get_output_format,
    exectime_internal, time_start
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




from .gitstats_analyzers import getnumoffilesfromrev, getnumoflinesinblob, analyzesloc



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
