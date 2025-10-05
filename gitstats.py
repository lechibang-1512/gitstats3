import datetime
import getopt
import glob
import os
import pickle
import platform
import re
import shutil
import subprocess
import sys
import time
import zlib
from collections import defaultdict
import threading

# Import OOP Metrics Module for Distance from Main Sequence analysis
from oop_metrics import OOPMetricsAnalyzer, format_oop_report

if sys.version_info < (3, 6):
	print("Python 3.6 or higher is required for gitstats", file=sys.stderr)
	sys.exit(1)

from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import threading
import queue

os.environ['LC_ALL'] = 'C'

# Configuration for table-based output instead of charts

ON_LINUX = (platform.system() == 'Linux')
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

exectime_internal = 0.0
exectime_external = 0.0
exectime_lock = threading.Lock()  # Thread-safe lock for exectime_external updates
time_start = time.time()

class TableDataGenerator:
	"""Generates table data instead of charts for better accessibility and data readability."""
	
	def __init__(self):
		pass
	
	def read_data_file(self, data_file):
		"""Read data from a file and return as lines."""
		try:
			with open(data_file, 'r') as f:
				return [line.strip().split() for line in f if line.strip()]
		except Exception as e:
			print(f"Warning: Failed to read data file {data_file}: {e}")
			return []
	
	def generate_table_data(self, data_file, chart_type):
		"""Generate table data for the given chart type."""
		data = self.read_data_file(data_file)
		if not data:
			return []
		
		if chart_type == 'hour_of_day':
			return self._format_hour_of_day_data(data)
		elif chart_type == 'day_of_week':
			return self._format_day_of_week_data(data)
		elif chart_type == 'domains':
			return self._format_domains_data(data)
		elif chart_type == 'month_of_year':
			return self._format_month_of_year_data(data)
		elif chart_type == 'commits_by_year_month':
			return self._format_commits_by_year_month_data(data)
		elif chart_type == 'commits_by_year':
			return self._format_commits_by_year_data(data)
		elif chart_type == 'files_by_date':
			return self._format_files_by_date_data(data)
		elif chart_type == 'files_by_year':
			return self._format_files_by_year_data(data)
		elif chart_type == 'lines_of_code':
			return self._format_lines_of_code_data(data)
		elif chart_type == 'pace_of_changes':
			return self._format_pace_of_changes_data(data)
		else:
			return data
	
	def _format_hour_of_day_data(self, data):
		"""Format hour of day data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				hour = int(row[0])
				commits = int(row[1])
				formatted.append([f"{hour:02d}:00", commits])
		return formatted
	
	def _format_day_of_week_data(self, data):
		"""Format day of week data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 3:
				day_name = row[1]
				commits = int(row[2])
				formatted.append([day_name, commits])
		return formatted
	
	def _format_domains_data(self, data):
		"""Format domains data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 3:
				domain = row[0]
				commits = int(row[2])
				formatted.append([domain, commits])
		return sorted(formatted, key=lambda x: x[1], reverse=True)
	
	def _format_month_of_year_data(self, data):
		"""Format month of year data for table display."""
		month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
					   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
		formatted = []
		for row in data:
			if len(row) >= 2:
				month = int(row[0])
				commits = int(row[1])
				month_name = month_names[month - 1] if 1 <= month <= 12 else str(month)
				formatted.append([month_name, commits])
		return formatted
	
	def _format_commits_by_year_month_data(self, data):
		"""Format commits by year-month data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				year_month = row[0]
				commits = int(row[1])
				formatted.append([year_month, commits])
		return formatted
	
	def _format_commits_by_year_data(self, data):
		"""Format commits by year data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				year = int(row[0])
				commits = int(row[1])
				formatted.append([year, commits])
		return sorted(formatted, key=lambda x: x[0])
	
	def _format_files_by_date_data(self, data):
		"""Format files by date data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				try:
					date_str = row[0]
					files = int(row[1])
					# Convert timestamp to readable date if needed
					if date_str.isdigit():
						date_obj = datetime.datetime.fromtimestamp(int(date_str))
						date_str = date_obj.strftime('%Y-%m-%d')
					formatted.append([date_str, files])
				except (ValueError, OSError):
					formatted.append([row[0], int(row[1])])
		return formatted[-50:]  # Show last 50 entries
	
	def _format_files_by_year_data(self, data):
		"""Format files by year data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				year = int(row[0])
				files = int(row[1])
				formatted.append([year, files])
		return sorted(formatted, key=lambda x: x[0])
	
	def _format_lines_of_code_data(self, data):
		"""Format lines of code data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				try:
					timestamp = int(row[0])
					lines = int(row[1])
					date_obj = datetime.datetime.fromtimestamp(timestamp)
					date_str = date_obj.strftime('%Y-%m-%d')
					formatted.append([date_str, lines])
				except (ValueError, OSError):
					formatted.append([row[0], int(row[1])])
		return formatted[-50:]  # Show last 50 entries
	
	def _format_pace_of_changes_data(self, data):
		"""Format pace of changes data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				try:
					timestamp = int(row[0])
					changes = int(row[1])
					date_obj = datetime.datetime.fromtimestamp(timestamp)
					date_str = date_obj.strftime('%Y-%m-%d')
					formatted.append([date_str, changes])
				except (ValueError, OSError):
					formatted.append([row[0], int(row[1])])
		return formatted[-50:]  # Show last 50 entries

	def _format_lines_of_code_by_author_data(self, data, authors_to_plot):
		"""Format lines of code by author data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				author = row[0]
				if author in authors_to_plot:
					lines = int(row[1])
					formatted.append([author, lines])
		return formatted
	
	def _format_commits_by_author_data(self, data, authors_to_plot):
		"""Format commits by author data for table display."""
		formatted = []
		for row in data:
			if len(row) >= 2:
				author = row[0]
				if author in authors_to_plot:
					commits = int(row[1])
					formatted.append([author, commits])
		return formatted

	# Public methods that wrap the private formatting methods
	def format_hour_of_day_data(self, data_file):
		"""Public method to format hour of day data."""
		data = self.read_data_file(data_file)
		return self._format_hour_of_day_data(data)
	
	def format_day_of_week_data(self, data_file):
		"""Public method to format day of week data."""
		data = self.read_data_file(data_file)
		return self._format_day_of_week_data(data)
	
	def format_domains_data(self, data_file):
		"""Public method to format domains data."""
		data = self.read_data_file(data_file)
		return self._format_domains_data(data)
	
	def format_month_of_year_data(self, data_file):
		"""Public method to format month of year data."""
		data = self.read_data_file(data_file)
		return self._format_month_of_year_data(data)
	
	def format_commits_by_year_month_data(self, data_file):
		"""Public method to format commits by year month data."""
		data = self.read_data_file(data_file)
		return self._format_commits_by_year_month_data(data)
	
	def format_commits_by_year_data(self, data_file):
		"""Public method to format commits by year data."""
		data = self.read_data_file(data_file)
		return self._format_commits_by_year_data(data)
	
	def format_files_by_date_data(self, data_file):
		"""Public method to format files by date data."""
		data = self.read_data_file(data_file)
		return self._format_files_by_date_data(data)
	
	def format_files_by_year_data(self, data_file):
		"""Public method to format files by year data."""
		data = self.read_data_file(data_file)
		return self._format_files_by_year_data(data)
	
	def format_lines_of_code_data(self, data_file):
		"""Public method to format lines of code data."""
		data = self.read_data_file(data_file)
		return self._format_lines_of_code_data(data)
	
	def format_pace_of_changes_data(self, data_file):
		"""Public method to format pace of changes data."""
		data = self.read_data_file(data_file)
		return self._format_pace_of_changes_data(data)
	
	def format_lines_of_code_by_author_data(self, data_file, authors_to_plot):
		"""Public method to format lines of code by author data."""
		data = self.read_data_file(data_file)
		return self._format_lines_of_code_by_author_data(data, authors_to_plot)
	
	def format_commits_by_author_data(self, data_file, authors_to_plot):
		"""Public method to format commits by author data."""
		data = self.read_data_file(data_file)
		return self._format_commits_by_author_data(data, authors_to_plot)

# Data is now displayed in tables instead of charts for better accessibility

conf = {
	'max_domains': 10,
	'max_ext_length': 10,
	'style': 'gitstats.css',
	'max_authors': 20,
	'authors_top': 5,
	'commit_begin': '',
	'commit_end': 'HEAD',
	'linear_linestats': 1,
	'project_name': '',
	'processes': min(4, os.cpu_count() or 2),  # Reduced for stability
	'start_date': '',
	'debug': False,
	'verbose': False,
	'scan_default_branch_only': True,  # Only scan commits from the default branch
	# Multi-repo specific configuration
	'multi_repo_max_depth': 10,
	'multi_repo_include_patterns': None,
	'multi_repo_exclude_patterns': None,
	'multi_repo_parallel': False,  # Disabled by default for stability
	'multi_repo_max_workers': 2,  # Reduced for stability
	'multi_repo_timeout': 3600,  # 1 hour timeout per repository
	'multi_repo_cleanup_on_error': True,
	'multi_repo_fast_scan': True,  # Enable fast concurrent repository discovery
	'multi_repo_batch_size': 10,  # Process repositories in batches to manage memory
	'multi_repo_progress_interval': 5,  # Progress update interval in seconds
	# File extension filtering configuration
	'allowed_extensions': {
		'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx', '.m', '.mm',
		'.swift', '.cu', '.cuh', '.cl', '.java', '.scala', '.kt', '.go', '.rs',
		'.py', '.pyi', '.pyx', '.pxd', '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
		'.d.ts', '.lua', '.proto', '.thrift', '.asm', '.s', '.S', '.R', '.r'
	},
	'filter_by_extensions': True,  # Enable/disable extension filtering
	'calculate_mi_per_repository': True  # Enable/disable MI calculation per repository
}

def getpipeoutput(cmds, quiet = False):
	global exectime_external
	start = time.time()
	
	# Basic input validation to prevent command injection
	for cmd in cmds:
		if not isinstance(cmd, str):
			raise TypeError("Commands must be strings")
		# Check for obvious command injection attempts
		if any(dangerous in cmd for dangerous in [';', '&&', '||', '`', '$(']):
			print(f'Warning: Potentially dangerous command detected: {cmd}')
	
	if (not quiet and ON_LINUX and os.isatty(1)) or conf['verbose']:
		print('>> ' + ' | '.join(cmds), end='')
		sys.stdout.flush()
	p = subprocess.Popen(cmds[0], stdout = subprocess.PIPE, shell = True)
	processes=[p]
	for x in cmds[1:]:
		p = subprocess.Popen(x, stdin = p.stdout, stdout = subprocess.PIPE, shell = True)
		processes.append(p)
	output = p.communicate()[0]
	for p in processes:
		p.wait()
	end = time.time()
	if not quiet or conf['verbose'] or conf['debug']:
		if ON_LINUX and os.isatty(1):
			print('\r', end='')
		print('[%.5f] >> %s' % (end - start, ' | '.join(cmds)))
	if conf['debug']:
		print(f'DEBUG: Command output ({len(output)} bytes): {output[:200].decode("utf-8", errors="replace")}...')
	with exectime_lock:
		exectime_external += (end - start)
	return output.decode('utf-8', errors='replace').rstrip('\n')

def getpipeoutput_list(cmd_list, quiet = False):
	"""Execute command list without shell interpretation for safer path handling"""
	global exectime_external
	start = time.time()
	
	if (not quiet and ON_LINUX and os.isatty(1)) or conf['verbose']:
		print('>> ' + ' '.join(cmd_list), end='')
		sys.stdout.flush()
	
	try:
		p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		output, error = p.communicate()
		if p.returncode != 0:
			if not quiet:
				print(f'\nCommand failed: {" ".join(cmd_list)}')
				print(f'Error: {error.decode("utf-8", errors="replace")}')
			return ''
	except Exception as e:
		if not quiet:
			print(f'\nCommand execution failed: {e}')
		return ''
	
	end = time.time()
	if not quiet or conf['verbose'] or conf['debug']:
		if ON_LINUX and os.isatty(1):
			print('\r', end='')
		print('[%.5f] >> %s' % (end - start, ' '.join(cmd_list)))
	if conf['debug']:
		print(f'DEBUG: Command output ({len(output)} bytes): {output[:200].decode("utf-8", errors="replace")}...')
	with exectime_lock:
		exectime_external += (end - start)
	return output.decode('utf-8', errors='replace').rstrip('\n')

def get_default_branch():
	"""Get the default branch name from git configuration or detect it"""
	# First try to get the default branch from git config
	try:
		default_branch = getpipeoutput(['git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null']).strip()
		if default_branch:
			# Extract branch name from refs/remotes/origin/HEAD -> refs/remotes/origin/main
			branch = default_branch.replace('refs/remotes/origin/', '')
			if branch:
				return branch
	except Exception:
		pass
	
	# Try to get from current HEAD if in a repository
	try:
		current_branch = getpipeoutput(['git rev-parse --abbrev-ref HEAD 2>/dev/null']).strip()
		if current_branch and current_branch != 'HEAD':
			# We're on a named branch, use it
			return current_branch
	except Exception:
		pass
	
	# Try to get from git config init.defaultBranch
	try:
		default_branch = getpipeoutput(['git config --get init.defaultBranch 2>/dev/null']).strip()
		if default_branch:
			return default_branch
	except Exception:
		pass
	
	# Try common main branch names in order of preference
	main_branch_candidates = ['main', 'master', 'develop', 'development']
	
	# Get all local branches
	try:
		branches_output = getpipeoutput(['git branch 2>/dev/null'])
		if branches_output:
			local_branches = [line.strip().lstrip('* ') for line in branches_output.split('\n') if line.strip()]
			
			# Check if any of the common main branches exist
			for candidate in main_branch_candidates:
				if candidate in local_branches:
					return candidate
			
			# If none found and we have branches, use the first branch
			if local_branches:
				return local_branches[0]
	except Exception:
		pass
	
	# Fall back to master
	return 'master'

def get_first_parent_flag():
	"""Get --first-parent flag if scanning only default branch"""
	return '--first-parent' if conf['scan_default_branch_only'] else ''

def getlogrange(defaultrange = 'HEAD', end_only = True):
	commit_range = getcommitrange(defaultrange, end_only)
	if len(conf['start_date']) > 0:
		return '--since="%s" "%s"' % (conf['start_date'], commit_range)
	return commit_range

def getcommitrange(defaultrange = 'HEAD', end_only = False):
	if len(conf['commit_end']) > 0:
		if end_only or len(conf['commit_begin']) == 0:
			return conf['commit_end']
		return '%s..%s' % (conf['commit_begin'], conf['commit_end'])
	
	# If configured to scan only default branch and using default range
	if conf['scan_default_branch_only'] and defaultrange == 'HEAD':
		default_branch = get_default_branch()
		if conf['verbose']:
			print(f'Scanning only default branch: {default_branch}')
		return default_branch
	
	return defaultrange

def getkeyssortedbyvalues(d):
	return list(map(lambda el : el[1], sorted(map(lambda el : (el[1], el[0]), d.items()))))

# dict['author'] = { 'commits': 512 } - ...key(dict, 'commits')
def getkeyssortedbyvaluekey(d, key):
	return list(map(lambda el : el[1], sorted(map(lambda el : (d[el][key], el), d.keys()))))

def getstatsummarycounts(line):
	numbers = re.findall(r'\d+', line)
	if   len(numbers) == 1:
		# neither insertions nor deletions: may probably only happen for "0 files changed"
		numbers.append(0);
		numbers.append(0);
	elif len(numbers) == 2 and line.find('(+)') != -1:
		numbers.append(0);    # only insertions were printed on line
	elif len(numbers) == 2 and line.find('(-)') != -1:
		numbers.insert(1, 0); # only deletions were printed on line
	return numbers

VERSION = 0
def getversion():
	global VERSION
	if VERSION == 0:
		try:
			gitstats_repo = os.path.dirname(os.path.abspath(__file__))
			cmd = ['git', '--git-dir=%s/.git' % gitstats_repo, '--work-tree=%s' % gitstats_repo, 
				   'rev-parse', '--short', getcommitrange('HEAD').split('\n')[0]]
			VERSION = getpipeoutput_list(cmd)
		except:
			VERSION = 'unknown'
	return VERSION

def getgitversion():
	return getpipeoutput(['git --version']).split('\n')[0]

def get_output_format():
	return "HTML tables (no charts)"

def should_include_file(filename):
	"""
	Check if a file should be included in the analysis based on its extension.
	
	Args:
		filename (str): The filename to check
		
	Returns:
		bool: True if the file should be included, False otherwise
	"""
	if not conf['filter_by_extensions']:
		return True
	
	# Handle hidden files (starting with .)
	basename = os.path.basename(filename)
	if basename.startswith('.') and basename != '.':
		return False
	
	# Check if filename has an extension
	if filename.find('.') == -1:
		# No extension - include common extensionless files
		extensionless_includes = ['Makefile', 'Dockerfile', 'Rakefile', 'Gemfile', 'CMakeLists']
		return basename in extensionless_includes
	
	# Check multi-part extensions first (e.g., .d.ts, .spec.ts)
	filename_lower = filename.lower()
	for ext in conf['allowed_extensions']:
		if filename_lower.endswith(ext):
			return True
	
	return False

def getnumoffilesfromrev(time_rev):
	"""
	Get number of files changed in commit (filtered by allowed extensions)
	"""
	time, rev = time_rev
	if conf['filter_by_extensions']:
		# Get all files and filter by extension
		try:
			all_files_output = getpipeoutput(['git ls-tree -r --name-only "%s"' % rev])
			if not all_files_output:
				return (int(time), rev, 0)
			all_files = all_files_output.split('\n')
			filtered_files = []
			for file_path in all_files:
				if file_path.strip():  # Skip empty lines
					filename = file_path.split('/')[-1]
					if should_include_file(filename):
						filtered_files.append(file_path)
			return (int(time), rev, len(filtered_files))
		except (ValueError, IndexError) as e:
			if conf['debug']:
				print(f'Warning: Failed to get file count for rev {rev}: {e}')
			return (int(time), rev, 0)
	else:
		# Original behavior - count all files
		try:
			output = getpipeoutput(['git ls-tree -r --name-only "%s"' % rev, 'wc -l'])
			if not output or not output.strip():
				return (int(time), rev, 0)
			count = int(output.split('\n')[0].strip())
			return (int(time), rev, count)
		except (ValueError, IndexError) as e:
			if conf['debug']:
				print(f'Warning: Failed to get file count for rev {rev}: {e}')
			return (int(time), rev, 0)

def getnumoflinesinblob(ext_blob):
	"""
	Get number of lines in blob
	"""
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
	Analyze source lines of code vs comments vs blank lines in a blob
	Returns (ext, blob_id, total_lines, source_lines, comment_lines, blank_lines)
	"""
	ext, blob_id = ext_blob
	content = getpipeoutput(['git cat-file blob %s' % blob_id])
	
	total_lines = 0
	source_lines = 0
	comment_lines = 0
	blank_lines = 0
	
	# Define comment patterns for different file types
	comment_patterns = {
		'.py': [r'^\s*#', r'^\s*"""', r'^\s*\'\'\''],
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
	
	import re
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

def is_git_repository(path):
	"""
	Check if the given path is a valid Git repository.
	
	Args:
		path (str): Path to check
		
	Returns:
		bool: True if the path is a valid Git repository, False otherwise
	"""
	if not os.path.exists(path) or not os.path.isdir(path):
		return False
	
	# Check if .git directory exists
	git_dir = os.path.join(path, '.git')
	if os.path.exists(git_dir):
		# For regular repositories, .git should be a directory
		# For worktrees, .git might be a file pointing to the real .git directory
		if os.path.isdir(git_dir) or os.path.isfile(git_dir):
			return True
	
	# Also check if we're inside a git repository (not necessarily at the root)
	try:
		# Save current directory
		current_dir = os.getcwd()
		try:
			os.chdir(path)
			# Try to run a simple git command that works in any git repository
			result = subprocess.run(['git', 'rev-parse', '--git-dir'], 
								  capture_output=True, text=True, timeout=5)
			return result.returncode == 0
		finally:
			os.chdir(current_dir)
	except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
		return False
	
	return False

class DataCollector:
	"""Consolidated data collector for repository metrics with optimized memory usage."""
	def __init__(self):
		self.stamp_created = time.time()
		self.cache = {}
		self.total_authors = 0
		
		# Initialize OOP Metrics Analyzer for Distance from Main Sequence analysis
		self.oop_analyzer = OOPMetricsAnalyzer()
		
		# Core activity metrics - consolidated for memory efficiency
		self.activity_metrics = {
			'by_hour_of_day': defaultdict(int),
			'by_day_of_week': defaultdict(int),
			'by_month_of_year': defaultdict(int),
			'by_hour_of_week': defaultdict(lambda: defaultdict(int)),
			'by_year_week': defaultdict(int),
			'hour_of_day_busiest': 0,
			'hour_of_week_busiest': 0,
			'year_week_peak': 0
		}

		# Core repository statistics - consolidated
		self.repository_stats = {
			'total_commits': 0,
			'total_files': 0,
			'total_lines': 0,
			'total_lines_added': 0,
			'total_lines_removed': 0,
			'total_size': 0,
			'first_commit_stamp': 0,
			'last_commit_stamp': 0,
			'last_active_day': None,
			'active_days': set(),
			'repository_size_mb': 0.0
		}

		# Author data - consolidated structure
		self.authors = {}  # name -> all author metrics
		self.authors_by_commits = 0

		# Domain and timezone analysis
		self.domains = defaultdict(lambda: defaultdict(int))
		self.commits_by_timezone = defaultdict(int)

		# Temporal analysis - consolidated
		self.temporal_data = {
			'author_of_month': defaultdict(lambda: defaultdict(int)),
			'author_of_year': defaultdict(lambda: defaultdict(int)),
			'commits_by_month': defaultdict(int),
			'commits_by_year': defaultdict(int),
			'lines_added_by_month': defaultdict(int),
			'lines_added_by_year': defaultdict(int),
			'lines_removed_by_month': defaultdict(int),
			'lines_removed_by_year': defaultdict(int),
			'lines_added_by_author_by_year': defaultdict(lambda: defaultdict(int)),
			'commits_by_author_by_year': defaultdict(lambda: defaultdict(int)),
			'files_by_year': defaultdict(int),
			'files_by_stamp': {},
			'changes_by_date': {},
			'pace_of_changes': {},
			'pace_of_changes_by_month': defaultdict(int),
			'pace_of_changes_by_year': defaultdict(int)
		}

		# Recent activity tracking - consolidated
		self.recent_activity = {
			'last_30_days_commits': 0,
			'last_30_days_lines_added': 0,
			'last_30_days_lines_removed': 0,
			'last_12_months_commits': defaultdict(int),
			'last_12_months_lines_added': defaultdict(int),
			'last_12_months_lines_removed': defaultdict(int)
		}

		# Code quality and structure metrics - consolidated
		self.code_analysis = {
			# SLOC analysis
			'total_source_lines': 0,
			'total_comment_lines': 0,
			'total_blank_lines': 0,
			'sloc_by_extension': {},
			
			# File analysis
			'extensions': {},
			'file_sizes': {},
			'file_revisions': {},
			'file_types': defaultdict(int),
			'large_files': [],
			'complex_files': [],
			'hot_files': [],
			
			# Directory analysis
			'directories': defaultdict(lambda: {
				'commits': 0, 'lines_added': 0, 'lines_removed': 0, 'files': set()
			}),
			'directory_revisions': defaultdict(int)
		}

		# Enhanced project health metrics - consolidated and optimized
		self.project_health = {

			
			# Code quality metrics
			'code_quality': {
				'cyclomatic_complexity': 0,
				'maintainability_index': 0.0,
				'technical_debt_minutes': 0
			},
			
			# Team collaboration metrics
			'collaboration': {
				'bus_factor': 0,
				'knowledge_concentration': {},
				'cross_team_commits': 0
			}
		}

		# Branch analysis - consolidated
		self.branch_analysis = {
			'branches': {},
			'unmerged_branches': [],
			'main_branch': 'master'
		}

		# Team analysis - consolidated for memory efficiency
		self.team_analysis = {
			'author_collaboration': {},
			'commit_patterns': {},
			'working_patterns': {},
			'impact_analysis': {},
			'team_performance': {},
			'critical_files': set(),
			'file_impact_scores': {},
			'author_active_periods': {}
		}

		# Commit categorization
		self.commit_categories = {
			'bug_commits': [],
			'refactoring_commits': [],
			'feature_commits': []
		}

		# Tags
		self.tags = {}
		
		# Track changes by date by author
		self.changes_by_date_by_author = {}
		
		# Compatibility properties for backward compatibility
		self._setup_compatibility_properties()
	
	def _setup_compatibility_properties(self):
		"""Setup properties for backward compatibility with existing code."""
		# Map old property names to new consolidated structures
		pass  # Properties will be handled by @property decorators
	
	def get_consolidated_metrics(self):
		"""Get a comprehensive summary of all metrics in consolidated format."""
		return {
			'repository_stats': self.repository_stats,
			'activity_metrics': dict(self.activity_metrics),  # Convert defaultdicts to regular dicts
			'temporal_data': {k: (dict(v) if hasattr(v, 'items') and callable(getattr(v, 'items', None)) else v) 
							 for k, v in self.temporal_data.items()},
			'recent_activity': dict(self.recent_activity),
			'code_analysis': {k: (dict(v) if hasattr(v, 'items') and callable(getattr(v, 'items', None)) else v)
							 for k, v in self.code_analysis.items()},
			'project_health': self.project_health,
			'branch_analysis': self.branch_analysis,
			'team_analysis': self.team_analysis,
			'commit_categories': self.commit_categories,
			'authors': self.authors,
			'tags': self.tags,
			'domains': {k: dict(v) for k, v in self.domains.items()}
		}
	
	def update_memory_efficient_metrics(self, metric_type, key, value=None, increment=1):
		"""Memory-efficient metric updating with consolidated access patterns."""
		metric_maps = {
			'activity': self.activity_metrics,
			'repository': self.repository_stats, 
			'temporal': self.temporal_data,
			'recent': self.recent_activity,
			'code': self.code_analysis,
			'health': self.project_health,
			'branch': self.branch_analysis,
			'team': self.team_analysis
		}
		
		if metric_type in metric_maps:
			if value is not None:
				metric_maps[metric_type][key] = value
			else:
				metric_maps[metric_type][key] += increment
			return True
		return False
	
	def optimize_memory_usage(self):
		"""Optimize memory usage by converting defaultdicts to regular dicts and cleaning up cache."""
		# Convert defaultdicts to regular dicts to save memory
		for metric_group in [self.activity_metrics, self.temporal_data, self.recent_activity]:
			for key, value in metric_group.items():
				if hasattr(value, 'default_factory') and value.default_factory:
					metric_group[key] = dict(value)
		
		# Convert nested defaultdicts
		for key, value in self.temporal_data.items():
			if hasattr(value, 'items'):
				for subkey, subvalue in value.items():
					if hasattr(subvalue, 'default_factory') and subvalue.default_factory:
						value[subkey] = dict(subvalue)
		
		# Clean up large cache items that are no longer needed
		if 'files_in_tree' in self.cache and len(self.cache['files_in_tree']) > 10000:
			# Keep only most recent 5000 entries
			items = list(self.cache['files_in_tree'].items())
			self.cache['files_in_tree'] = dict(items[-5000:])
		
		if 'lines_in_blob' in self.cache and len(self.cache['lines_in_blob']) > 10000:
			# Keep only most recent 5000 entries  
			items = list(self.cache['lines_in_blob'].items())
			self.cache['lines_in_blob'] = dict(items[-5000:])
			
		return True
		
	# Backward compatibility properties
	@property
	def activity_by_hour_of_day(self):
		return self.activity_metrics['by_hour_of_day']
		
	@property
	def activity_by_day_of_week(self):
		return self.activity_metrics['by_day_of_week']
		
	@property
	def activity_by_month_of_year(self):
		return self.activity_metrics['by_month_of_year']
		
	@property 
	def activity_by_hour_of_week(self):
		return self.activity_metrics['by_hour_of_week']
		
	@property
	def activity_by_year_week(self):
		return self.activity_metrics['by_year_week']
		
	@property
	def activity_by_hour_of_day_busiest(self):
		return self.activity_metrics['hour_of_day_busiest']
		
	@activity_by_hour_of_day_busiest.setter
	def activity_by_hour_of_day_busiest(self, value):
		self.activity_metrics['hour_of_day_busiest'] = value
		
	@property
	def activity_by_hour_of_week_busiest(self):
		return self.activity_metrics['hour_of_week_busiest']
		
	@activity_by_hour_of_week_busiest.setter
	def activity_by_hour_of_week_busiest(self, value):
		self.activity_metrics['hour_of_week_busiest'] = value
		
	@property
	def activity_by_year_week_peak(self):
		return self.activity_metrics['year_week_peak']
		
	@activity_by_year_week_peak.setter
	def activity_by_year_week_peak(self, value):
		self.activity_metrics['year_week_peak'] = value

	# Repository stats properties
	@property
	def total_commits(self):
		return self.repository_stats['total_commits']
		
	@total_commits.setter
	def total_commits(self, value):
		self.repository_stats['total_commits'] = value
		
	@property
	def total_files(self):
		return self.repository_stats['total_files']
		
	@total_files.setter
	def total_files(self, value):
		self.repository_stats['total_files'] = value
		
	@property
	def total_lines(self):
		return self.repository_stats['total_lines']
		
	@total_lines.setter
	def total_lines(self, value):
		self.repository_stats['total_lines'] = value
		
	@property
	def total_lines_added(self):
		return self.repository_stats['total_lines_added']
		
	@total_lines_added.setter
	def total_lines_added(self, value):
		self.repository_stats['total_lines_added'] = value
		
	@property
	def total_lines_removed(self):
		return self.repository_stats['total_lines_removed']
		
	@total_lines_removed.setter
	def total_lines_removed(self, value):
		self.repository_stats['total_lines_removed'] = value
		
	@property
	def total_size(self):
		return self.repository_stats['total_size']
		
	@total_size.setter
	def total_size(self, value):
		self.repository_stats['total_size'] = value
		
	@property
	def first_commit_stamp(self):
		return self.repository_stats['first_commit_stamp']
		
	@first_commit_stamp.setter
	def first_commit_stamp(self, value):
		self.repository_stats['first_commit_stamp'] = value
		
	@property
	def last_commit_stamp(self):
		return self.repository_stats['last_commit_stamp']
		
	@last_commit_stamp.setter
	def last_commit_stamp(self, value):
		self.repository_stats['last_commit_stamp'] = value
		
	@property
	def last_active_day(self):
		return self.repository_stats['last_active_day']
		
	@last_active_day.setter
	def last_active_day(self, value):
		self.repository_stats['last_active_day'] = value
		
	@property
	def active_days(self):
		return self.repository_stats['active_days']
		
	@property
	def repository_size_mb(self):
		return self.repository_stats['repository_size_mb']
		
	@repository_size_mb.setter
	def repository_size_mb(self, value):
		self.repository_stats['repository_size_mb'] = value

	# Temporal data properties
	@property
	def author_of_month(self):
		return self.temporal_data['author_of_month']
		
	@property
	def author_of_year(self):
		return self.temporal_data['author_of_year']
		
	@property
	def commits_by_month(self):
		return self.temporal_data['commits_by_month']
		
	@property
	def commits_by_year(self):
		return self.temporal_data['commits_by_year']
		
	@property
	def lines_added_by_month(self):
		return self.temporal_data['lines_added_by_month']
		
	@property
	def lines_added_by_year(self):
		return self.temporal_data['lines_added_by_year']
		
	@property
	def lines_removed_by_month(self):
		return self.temporal_data['lines_removed_by_month']
		
	@property
	def lines_removed_by_year(self):
		return self.temporal_data['lines_removed_by_year']
		
	@property
	def lines_added_by_author_by_year(self):
		return self.temporal_data['lines_added_by_author_by_year']
		
	@property
	def commits_by_author_by_year(self):
		return self.temporal_data['commits_by_author_by_year']
		
	@property
	def files_by_year(self):
		return self.temporal_data['files_by_year']
		
	@property
	def files_by_stamp(self):
		return self.temporal_data['files_by_stamp']
		
	@property
	def changes_by_date(self):
		return self.temporal_data['changes_by_date']
		
	@property
	def pace_of_changes(self):
		return self.temporal_data['pace_of_changes']
		
	@property
	def pace_of_changes_by_month(self):
		return self.temporal_data['pace_of_changes_by_month']
		
	@property
	def pace_of_changes_by_year(self):
		return self.temporal_data['pace_of_changes_by_year']

	# Recent activity properties
	@property
	def last_30_days_commits(self):
		return self.recent_activity['last_30_days_commits']
		
	@last_30_days_commits.setter
	def last_30_days_commits(self, value):
		self.recent_activity['last_30_days_commits'] = value
		
	@property
	def last_30_days_lines_added(self):
		return self.recent_activity['last_30_days_lines_added']
		
	@last_30_days_lines_added.setter
	def last_30_days_lines_added(self, value):
		self.recent_activity['last_30_days_lines_added'] = value
		
	@property
	def last_30_days_lines_removed(self):
		return self.recent_activity['last_30_days_lines_removed']
		
	@last_30_days_lines_removed.setter
	def last_30_days_lines_removed(self, value):
		self.recent_activity['last_30_days_lines_removed'] = value
		
	@property
	def last_12_months_commits(self):
		return self.recent_activity['last_12_months_commits']
		
	@property
	def last_12_months_lines_added(self):
		return self.recent_activity['last_12_months_lines_added']
		
	@property
	def last_12_months_lines_removed(self):
		return self.recent_activity['last_12_months_lines_removed']

	# Code analysis properties
	@property
	def total_source_lines(self):
		return self.code_analysis['total_source_lines']
		
	@total_source_lines.setter
	def total_source_lines(self, value):
		self.code_analysis['total_source_lines'] = value
		
	@property
	def total_comment_lines(self):
		return self.code_analysis['total_comment_lines']
		
	@total_comment_lines.setter
	def total_comment_lines(self, value):
		self.code_analysis['total_comment_lines'] = value
		
	@property
	def total_blank_lines(self):
		return self.code_analysis['total_blank_lines']
		
	@total_blank_lines.setter
	def total_blank_lines(self, value):
		self.code_analysis['total_blank_lines'] = value
		
	@property
	def sloc_by_extension(self):
		return self.code_analysis['sloc_by_extension']
		
	@property
	def extensions(self):
		return self.code_analysis['extensions']
		
	@property
	def file_sizes(self):
		return self.code_analysis['file_sizes']
		
	@property
	def file_revisions(self):
		return self.code_analysis['file_revisions']
		
	@property
	def directories(self):
		return self.code_analysis['directories']
		
	@property
	def directory_revisions(self):
		return self.code_analysis['directory_revisions']

	# Project health properties
	@property
	def documentation_metrics(self):
		return self.project_health['documentation_quality']
		
	@property
	def code_quality_metrics(self):
		return self.project_health['code_quality']
		
	@property
	def collaboration_metrics(self):
		return self.project_health['collaboration']
		
	@property
	def file_analysis(self):
		return {
			'file_types': self.code_analysis['file_types'],
			'large_files': self.code_analysis['large_files'],
			'complex_files': self.code_analysis['complex_files'],
			'hot_files': self.code_analysis['hot_files']
		}

	# Branch analysis properties
	@property
	def branches(self):
		return self.branch_analysis['branches']
		
	@branches.setter
	def branches(self, value):
		self.branch_analysis['branches'] = value
		
	@property
	def unmerged_branches(self):
		return self.branch_analysis['unmerged_branches']
		
	@unmerged_branches.setter
	def unmerged_branches(self, value):
		self.branch_analysis['unmerged_branches'] = value
		
	@property
	def main_branch(self):
		return self.branch_analysis['main_branch']
		
	@main_branch.setter
	def main_branch(self, value):
		self.branch_analysis['main_branch'] = value

	# Team analysis properties
	@property
	def author_collaboration(self):
		return self.team_analysis['author_collaboration']
		
	@property
	def commit_patterns(self):
		return self.team_analysis['commit_patterns']
		
	@property
	def working_patterns(self):
		return self.team_analysis['working_patterns']
		
	@property
	def impact_analysis(self):
		return self.team_analysis['impact_analysis']
		
	@property
	def team_performance(self):
		return self.team_analysis['team_performance']
		
	@property
	def critical_files(self):
		return self.team_analysis['critical_files']
		
	@property
	def file_impact_scores(self):
		return self.team_analysis['file_impact_scores']
		
	@property
	def author_active_periods(self):
		return self.team_analysis['author_active_periods']

	# Commit categorization properties
	@property
	def potential_bug_commits(self):
		return self.commit_categories['bug_commits']
		
	@property
	def refactoring_commits(self):
		return self.commit_categories['refactoring_commits']
		
	@property
	def feature_commits(self):
		return self.commit_categories['feature_commits']

	##
	# This should be the main function to extract data from the repository.
	def collect(self, dir):
		self.dir = dir
		if len(conf['project_name']) == 0:
			self.projectname = os.path.basename(os.path.abspath(dir))
		else:
			self.projectname = conf['project_name']
	
	##
	# Load cacheable data
	def loadCache(self, cachefile):
		if not os.path.exists(cachefile):
			return
		print('Loading cache...')
		try:
			with open(cachefile, 'rb') as f:
				try:
					self.cache = pickle.loads(zlib.decompress(f.read()))
				except (zlib.error, pickle.PickleError) as e:
					# temporary hack to upgrade non-compressed caches
					try:
						f.seek(0)
						self.cache = pickle.load(f)
					except (pickle.PickleError, EOFError) as e2:
						print(f'Warning: Failed to load cache file {cachefile}: {e2}')
						self.cache = {}
				except Exception as e:
					print(f'Warning: Unexpected error loading cache file {cachefile}: {e}')
					self.cache = {}
		except IOError as e:
			print(f'Warning: Could not open cache file {cachefile}: {e}')
			self.cache = {}
	
	##
	# Produce any additional statistics from the extracted data.
	def refine(self):
		pass

	##
	# : get a dictionary of author
	def getAuthorInfo(self, author):
		return None
	
	def getActivityByDayOfWeek(self):
		return {}

	def getActivityByHourOfDay(self):
		return {}

	# : get a dictionary of domains
	def getDomainInfo(self, domain):
		return None

	##
	# Get a list of authors
	def getAuthors(self):
		return []
	
	def getFirstCommitDate(self):
		return datetime.datetime.now()
	
	def getLastCommitDate(self):
		return datetime.datetime.now()
	
	def getStampCreated(self):
		return self.stamp_created
	
	# Enhanced Metrics Calculation Methods - College Project Implementation
	

	
	def calculate_bus_factor(self):
		"""Calculate knowledge distribution risk (Bus Factor)"""
		if not self.authors:
			return 0
			
		# Sort authors by commit count
		author_commits = [(author, data['commits']) for author, data in self.authors.items()]
		author_commits.sort(key=lambda x: x[1], reverse=True)
		
		total_commits = sum(commits for _, commits in author_commits)
		if total_commits == 0:
			return 0
		
		# Calculate cumulative percentage
		cumulative = 0
		bus_factor = 0
		
		for author, commits in author_commits:
			cumulative += commits
			bus_factor += 1
			# If top N authors have >50% of commits, that's the bus factor
			if (cumulative / total_commits) >= 0.5:
				break
				
		return bus_factor
	
	def calculate_code_quality_score(self):
		"""Calculate overall code quality using industry standards"""
		scores = []
		
		# Complexity score (lower is better)
		if self.repository_stats['total_files'] > 0:
			avg_complexity = self.project_health['code_quality']['cyclomatic_complexity'] / self.repository_stats['total_files']
			complexity_score = max(0, 100 - (avg_complexity - 10) * 10)  # Penalize complexity > 10
			scores.append(complexity_score)
		

		
		# Team collaboration score
		bus_factor = self.calculate_bus_factor()
		collaboration_score = min(bus_factor * 25, 100)  # Higher bus factor = better
		scores.append(collaboration_score)
		
		# File organization score
		if self.repository_stats['total_files'] > 0:
			large_files_ratio = len(self.code_analysis['large_files']) / self.repository_stats['total_files']
			file_org_score = max(0, 100 - (large_files_ratio * 100))
			scores.append(file_org_score)
		
		# Calculate weighted average
		if scores:
			return sum(scores) / len(scores)
		return 0.0
	
	def analyze_file_complexity(self, filepath):
		"""Basic complexity analysis for a file"""
		try:
			with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
				content = f.read()
			
			# Simple complexity indicators
			complexity = 0
			lines = content.split('\n')
			
			for line in lines:
				line = line.strip()
				# Count control structures (basic cyclomatic complexity)
				if any(keyword in line for keyword in ['if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except', 'case ', 'switch']):
					complexity += 1

			
			return complexity
			
		except Exception:
			return 0
	
	def update_enhanced_metrics(self, filepath):
		"""Update enhanced metrics for a given file"""
		try:
			with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
				content = f.read()
				lines = content.split('\n')
			
			# File type analysis
			ext = os.path.splitext(filepath)[1].lower()
			self.code_analysis['file_types'][ext] += 1
			
			# Large files detection (>500 LOC)
			if len(lines) > 500:
				self.code_analysis['large_files'].append(filepath)
			
			# Documentation analysis
			comment_lines = 0
			for line in lines:
				line = line.strip()
				if line.startswith('#') or line.startswith('//') or line.startswith('*') or line.startswith('/*'):
					comment_lines += 1
				if '"""' in line or "'''" in line:
					comment_lines += 1
			
			# Complexity analysis
			complexity = self.analyze_file_complexity(filepath)
			self.project_health['code_quality']['cyclomatic_complexity'] += complexity
			
			if complexity > 20:  # High complexity threshold
				self.code_analysis['complex_files'].append(filepath)
			
		except Exception as e:
			pass  # Skip files that can't be read
	

	
	def getTags(self):
		return []
	
	def getTotalAuthors(self):
		return -1
	
	def getTotalCommits(self):
		return -1
		
	def getTotalFiles(self):
		return -1
	
	def getTotalLOC(self):
		return -1
	
	##
	# Save cacheable data
	def saveCache(self, cachefile):
		print('Saving cache...')
		tempfile = cachefile + '.tmp'
		try:
			# Optimize cache before saving - remove old/stale entries
			optimized_cache = self._optimizeCache()
			
			with open(tempfile, 'wb') as f:
				# Use higher compression level for better storage efficiency
				data = zlib.compress(pickle.dumps(optimized_cache), level=6)
				f.write(data)
			try:
				os.remove(cachefile)
			except OSError:
				pass
			os.rename(tempfile, cachefile)
			
			if conf['verbose']:
				cache_size_mb = os.path.getsize(cachefile) / (1024 * 1024)
				print(f'Cache saved: {cache_size_mb:.2f} MB')
				
		except IOError as e:
			print(f'Warning: Could not save cache file {cachefile}: {e}')
			# Clean up temp file if it exists
			try:
				os.remove(tempfile)
			except OSError:
				pass
	
	def _optimizeCache(self):
		"""Optimize cache by removing old or unnecessary entries."""
		if not hasattr(self, 'cache') or not self.cache:
			return {}
		
		optimized = {}
		
		# Keep essential cache entries
		for key in ['files_in_tree', 'lines_in_blob']:
			if key in self.cache:
				cache_data = self.cache[key]
				
				# For files_in_tree, keep only recent entries (limit to prevent unbounded growth)
				if key == 'files_in_tree' and len(cache_data) > 10000:
					# Keep most recent 10000 entries
					sorted_items = sorted(cache_data.items())[-10000:]
					optimized[key] = dict(sorted_items)
					if conf['verbose']:
						print(f'Optimized {key} cache: {len(cache_data)} -> {len(optimized[key])} entries')
				else:
					optimized[key] = cache_data
		
		return optimized

	def calculate_comprehensive_metrics(self, filepath):
		"""Calculate comprehensive code metrics for a file including LOC, Halstead, and McCabe metrics."""
		try:
			with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
				content = f.read()
			
			# Get file extension for language-specific analysis
			ext = os.path.splitext(filepath)[1].lower()
			
			# Calculate all metrics
			loc_metrics = self._calculate_loc_metrics(content, ext)
			halstead_metrics = self._calculate_halstead_metrics(content, ext)
			mccabe_metrics = self._calculate_mccabe_complexity(content, ext)
			maintainability_index = self._calculate_maintainability_index(loc_metrics, halstead_metrics, mccabe_metrics)
			oop_metrics = self._calculate_oop_metrics(content, ext, filepath)
			
			# Calculate OOP metrics using the dedicated analyzer for Distance from Main Sequence
			oop_distance_metrics = self.oop_analyzer.analyze_file(filepath, content, ext)
			
			return {
				'loc': loc_metrics,
				'halstead': halstead_metrics,
				'mccabe': mccabe_metrics,
				'maintainability_index': maintainability_index,
				'oop': oop_metrics,
				'oop_distance': oop_distance_metrics,  # New: Distance from Main Sequence metrics
				'filepath': filepath,
				'extension': ext
			}
			
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Failed to calculate metrics for {filepath}: {e}')
			return None

	def _calculate_loc_metrics(self, content, file_extension):
		"""Calculate Lines-of-Code metrics (LOCphy, LOCbl, LOCpro, LOCcom)."""
		lines = content.split('\n')
		
		# Initialize counters
		loc_phy = len(lines)  # Physical lines
		loc_bl = 0   # Blank lines
		loc_pro = 0  # Program lines (declarations, definitions, directives, code)
		loc_com = 0  # Comment lines
		
		# Language-specific comment patterns
		comment_patterns = self._get_comment_patterns(file_extension)
		
		import re
		in_multiline_comment = False
		
		for line in lines:
			original_line = line
			line_stripped = line.strip()
			
			# Check if line is blank
			if not line_stripped:
				loc_bl += 1
				continue
			
			# Handle multi-line comments
			if file_extension in ['.c', '.cpp', '.java', '.js', '.ts', '.css', '.h', '.hpp']:
				if '/*' in line_stripped and '*/' in line_stripped:
					# Single line /* */ comment
					loc_com += 1
					continue
				elif '/*' in line_stripped:
					in_multiline_comment = True
					loc_com += 1
					continue
				elif '*/' in line_stripped:
					in_multiline_comment = False
					loc_com += 1
					continue
				elif in_multiline_comment:
					loc_com += 1
					continue
			
			# Check for single-line comments
			is_comment = False
			for pattern in comment_patterns:
				if re.match(pattern, line_stripped):
					loc_com += 1
					is_comment = True
					break
			
			# If not a comment or blank line, it's a program line
			if not is_comment:
				# Check for mixed lines (code + comment on same line)
				has_code = True
				
				# Simple heuristic: if line starts with comment, it's a comment
				# Otherwise, it's code (even if it has trailing comments)
				for pattern in comment_patterns:
					if re.match(pattern, line_stripped):
						has_code = False
						break
				
				if has_code:
					loc_pro += 1
		
		return {
			'loc_phy': loc_phy,
			'loc_bl': loc_bl,
			'loc_pro': loc_pro,
			'loc_com': loc_com,
			'comment_ratio': (loc_com / loc_phy * 100) if loc_phy > 0 else 0.0
		}

	def _get_comment_patterns(self, file_extension):
		"""Get regex patterns for comments based on file extension."""
		patterns = {
			'.py': [r'^\s*#'],
			'.js': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.ts': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.jsx': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.tsx': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.java': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.scala': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.kt': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.cpp': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.c': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.cc': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.cxx': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.h': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.hpp': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
			'.go': [r'^\s*//'],
			'.rs': [r'^\s*//', r'^\s*///'],
			'.php': [r'^\s*//', r'^\s*/\*', r'^\s*\*', r'^\s*#'],
			'.rb': [r'^\s*#'],
			'.pl': [r'^\s*#'],
			'.sh': [r'^\s*#'],
			'.css': [r'^\s*/\*', r'^\s*\*'],
			'.html': [r'^\s*<!--'],
			'.xml': [r'^\s*<!--'],
		}
		
		return patterns.get(file_extension, [r'^\s*#', r'^\s*//', r'^\s*/\*'])

	def _calculate_halstead_metrics(self, content, file_extension):
		"""Calculate Halstead complexity metrics."""
		import re
		
		# Language-specific operators and operands patterns
		operators, operand_patterns = self._get_halstead_patterns(file_extension)
		
		# Remove comments and strings to avoid false positives
		cleaned_content = self._remove_comments_and_strings(content, file_extension)
		
		# Count operators
		n1_dict = {}  # distinct operators
		N1 = 0        # total operators
		
		for op in operators:
			# Escape special regex characters
			escaped_op = re.escape(op)
			matches = re.findall(escaped_op, cleaned_content)
			if matches:
				count = len(matches)
				n1_dict[op] = count
				N1 += count
		
		# Count operands (identifiers, numbers, strings)
		n2_dict = {}  # distinct operands
		N2 = 0        # total operands
		
		# Find all potential operands
		for pattern in operand_patterns:
			matches = re.findall(pattern, cleaned_content)
			for match in matches:
				if isinstance(match, tuple):
					match = match[0] if match[0] else match[1] if len(match) > 1 else ''
				
				if match and match not in n1_dict:  # Don't count operators as operands
					if match in n2_dict:
						n2_dict[match] += 1
					else:
						n2_dict[match] = 1
					N2 += 1
		
		# Calculate base metrics
		n1 = len(n1_dict)  # number of distinct operators
		n2 = len(n2_dict)  # number of distinct operands
		
		# Calculate derived metrics
		import math
		
		N = N1 + N2  # Program length
		n = n1 + n2  # Vocabulary
		
		if n > 0 and N > 0:
			V = N * math.log2(n)  # Program volume
		else:
			V = 0
		
		if n2 > 0 and n1 > 0:
			D = (n1 / 2) * (N2 / n2)  # Difficulty
		else:
			D = 0
		
		L = 1 / D if D > 0 else 0  # Level
		E = V * D if V > 0 and D > 0 else 0  # Effort
		T = E / 18 if E > 0 else 0  # Time (seconds)
		
		if E > 0:
			B = (E ** (2/3)) / 3000  # Estimated delivered bugs
		else:
			B = 0
		
		return {
			'n1': n1,           # distinct operators
			'n2': n2,           # distinct operands  
			'N1': N1,           # total operators
			'N2': N2,           # total operands
			'N': N,             # program length
			'n': n,             # vocabulary
			'V': V,             # program volume
			'D': D,             # difficulty
			'L': L,             # level
			'E': E,             # effort
			'T': T,             # time
			'B': B              # estimated bugs
		}

	def _get_halstead_patterns(self, file_extension):
		"""Get operators and operand patterns for Halstead metrics based on file extension."""
		
		# Common operators for most C-like languages
		common_operators = [
			# Arithmetic
			'+', '-', '*', '/', '%', '++', '--',
			# Assignment
			'=', '+=', '-=', '*=', '/=', '%=', 
			# Comparison
			'==', '!=', '<', '>', '<=', '>=',
			# Logical
			'&&', '||', '!',
			# Bitwise
			'&', '|', '^', '~', '<<', '>>',
			# Other
			'?', ':', ';', ',', '.', '->', 
			# Brackets and parentheses
			'(', ')', '[', ']', '{', '}',
		]
		
		# Common operand patterns (identifiers, numbers, strings)
		common_operand_patterns = [
			r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b',  # identifiers
			r'\b(\d+\.?\d*)\b',                # numbers
			r'"([^"]*)"',                      # double-quoted strings
			r"'([^']*)'",                      # single-quoted strings
		]
		
		if file_extension == '.py':
			operators = common_operators + [
				'and', 'or', 'not', 'in', 'is', 'lambda', 
				'if', 'elif', 'else', 'for', 'while', 'def', 'class',
				'import', 'from', 'as', 'try', 'except', 'finally',
				'with', 'yield', 'return', 'pass', 'break', 'continue'
			]
			
		elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
			operators = common_operators + [
				'function', 'var', 'let', 'const', 'if', 'else', 'for', 'while',
				'do', 'switch', 'case', 'default', 'break', 'continue',
				'return', 'try', 'catch', 'finally', 'throw', 'new', 'delete',
				'typeof', 'instanceof', 'this', '=>'
			]
			
		elif file_extension in ['.java', '.scala', '.kt']:
			operators = common_operators + [
				'class', 'interface', 'extends', 'implements', 'public', 'private',
				'protected', 'static', 'final', 'abstract', 'synchronized',
				'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
				'break', 'continue', 'return', 'try', 'catch', 'finally',
				'throw', 'throws', 'new', 'instanceof'
			]
			
		elif file_extension in ['.cpp', '.c', '.cc', '.cxx', '.h', '.hpp']:
			operators = common_operators + [
				'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
				'break', 'continue', 'return', 'goto', 'sizeof',
				'struct', 'union', 'enum', 'typedef', 'static', 'extern',
				'const', 'volatile', 'auto', 'register'
			]
			
		elif file_extension == '.go':
			operators = common_operators + [
				'func', 'var', 'const', 'type', 'struct', 'interface',
				'if', 'else', 'for', 'switch', 'case', 'default',
				'break', 'continue', 'return', 'go', 'select',
				'package', 'import', 'defer'
			]
			
		elif file_extension == '.rs':
			operators = common_operators + [
				'fn', 'let', 'mut', 'const', 'static', 'struct', 'enum', 'trait',
				'impl', 'if', 'else', 'for', 'while', 'loop', 'match',
				'break', 'continue', 'return', 'pub', 'use', 'mod'
			]
		else:
			# Default to common operators
			operators = common_operators
		
		return operators, common_operand_patterns

	def _remove_comments_and_strings(self, content, file_extension):
		"""Remove comments and string literals to avoid counting them in Halstead metrics."""
		import re
		
		if file_extension == '.py':
			# Remove Python comments and strings
			content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
			content = re.sub(r'""".*?"""', '', content, flags=re.DOTALL)
			content = re.sub(r"'''.*?'''", '', content, flags=re.DOTALL)
			content = re.sub(r'"[^"]*"', '', content)
			content = re.sub(r"'[^']*'", '', content)
			
		elif file_extension in ['.js', '.ts', '.jsx', '.tsx', '.java', '.scala', '.kt', '.cpp', '.c', '.cc', '.cxx', '.h', '.hpp', '.go', '.rs']:
			# Remove C-style comments and strings
			content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
			content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
			content = re.sub(r'"[^"]*"', '', content)
			content = re.sub(r"'[^']*'", '', content)
		
		return content

	def _calculate_mccabe_complexity(self, content, file_extension):
		"""Calculate McCabe Cyclomatic Complexity v(G).
		
		Formula: v(G) = #binaryDecision + 1
		Also: v(G) = #IFs + #LOOPs + 1
		"""
		import re
		
		# Remove comments and strings to avoid false positives
		cleaned_content = self._remove_comments_and_strings(content, file_extension)
		
		# Language-specific binary decision patterns (IF statements and LOOPS)
		if_patterns = []
		loop_patterns = []
		
		if file_extension in ['.py']:
			# Python patterns
			if_patterns = [r'\bif\b', r'\belif\b']
			loop_patterns = [r'\bwhile\b', r'\bfor\b']
		elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
			# JavaScript/TypeScript patterns  
			if_patterns = [r'\bif\b', r'\belse\s+if\b']
			loop_patterns = [r'\bwhile\b', r'\bfor\b', r'\bdo\b']
		elif file_extension in ['.java', '.scala', '.kt']:
			# Java/Scala/Kotlin patterns
			if_patterns = [r'\bif\b', r'\belse\s+if\b']
			loop_patterns = [r'\bwhile\b', r'\bfor\b', r'\bdo\b']
		elif file_extension in ['.cpp', '.c', '.cc', '.cxx', '.h', '.hpp']:
			# C/C++ patterns
			if_patterns = [r'\bif\b', r'\belse\s+if\b']
			loop_patterns = [r'\bwhile\b', r'\bfor\b', r'\bdo\b']
		elif file_extension in ['.go']:
			# Go patterns
			if_patterns = [r'\bif\b', r'\belse\s+if\b']
			loop_patterns = [r'\bfor\b']
		elif file_extension in ['.rs']:
			# Rust patterns
			if_patterns = [r'\bif\b', r'\belse\s+if\b']
			loop_patterns = [r'\bwhile\b', r'\bfor\b', r'\bloop\b']
		else:
			# Generic patterns for other languages
			if_patterns = [r'\bif\b', r'\belse\s+if\b']
			loop_patterns = [r'\bwhile\b', r'\bfor\b', r'\bdo\b']
		
		# Count IF statements
		if_count = 0
		for pattern in if_patterns:
			matches = re.findall(pattern, cleaned_content, re.IGNORECASE)
			if_count += len(matches)
		
		# Count LOOP statements  
		loop_count = 0
		for pattern in loop_patterns:
			matches = re.findall(pattern, cleaned_content, re.IGNORECASE)
			loop_count += len(matches)
		
		# Additional binary decisions: switch/case, try/catch, ternary operators, logical operators
		additional_decisions = 0
		
		# Switch/case statements
		if file_extension in ['.js', '.ts', '.jsx', '.tsx', '.java', '.scala', '.kt', '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp']:
			case_matches = re.findall(r'\bcase\b', cleaned_content, re.IGNORECASE)
			additional_decisions += len(case_matches)
		
		# Ternary operators
		ternary_matches = re.findall(r'\?.*:', cleaned_content)
		additional_decisions += len(ternary_matches)
		
		# Logical operators (each && or || creates a binary decision)
		logical_matches = re.findall(r'&&|\|\|', cleaned_content)
		additional_decisions += len(logical_matches)
		
		# Exception handling
		if file_extension in ['.py']:
			except_matches = re.findall(r'\bexcept\b', cleaned_content, re.IGNORECASE)
			additional_decisions += len(except_matches)
		elif file_extension in ['.js', '.ts', '.jsx', '.tsx', '.java', '.scala', '.kt', '.c', '.cpp', '.cc', '.cxx']:
			catch_matches = re.findall(r'\bcatch\b', cleaned_content, re.IGNORECASE)
			additional_decisions += len(catch_matches)
		
		# Total binary decisions = IFs + LOOPs + additional decisions
		binary_decisions = if_count + loop_count + additional_decisions
		
		# McCabe complexity v(G) = #binaryDecision + 1
		complexity = binary_decisions + 1
		
		# Interpret complexity level (recommendations: function ≲ 15; file ≲ 100)
		if complexity <= 15:
			interpretation = 'simple'
		elif complexity <= 25:
			interpretation = 'moderate'  
		elif complexity <= 50:
			interpretation = 'complex'
		else:
			interpretation = 'very_complex'
		
		return {
			'cyclomatic_complexity': complexity,
			'binary_decisions': binary_decisions,
			'if_count': if_count,
			'loop_count': loop_count,
			'additional_decisions': additional_decisions,
			'interpretation': interpretation
		}

	def _calculate_maintainability_index(self, loc_metrics, halstead_metrics, mccabe_metrics):
		"""Calculate Maintainability Index using LOC, Halstead, and McCabe metrics.
		
		Formula from slides:
		MIwoc = 171 - 5.2 * ln(aveV) - 0.23 * aveG - 16.2 * ln(aveLOC)
		MIcw = 50 * sin(√(2.4 * perCM))
		MI = MIwoc + MIcw
		"""
		import math
		
		try:
			# Extract required metrics - these are per module (file) averages
			ave_v = halstead_metrics['V'] if halstead_metrics['V'] > 0 else 1  # Halstead Volume per module
			ave_g = mccabe_metrics['cyclomatic_complexity']  # Cyclomatic complexity v(G) per module
			ave_loc = loc_metrics['loc_phy']  # Physical LOC per module
			per_cm = loc_metrics['comment_ratio']  # Comment ratio as percentage (0-100)
			
			# MIwoc = 171 - 5.2 * ln(aveV) - 0.23 * aveG - 16.2 * ln(aveLOC)
			mi_woc = (171 - 
					  5.2 * math.log(max(ave_v, 1)) - 
					  0.23 * ave_g - 
					  16.2 * math.log(max(ave_loc, 1)))
			
			# MIcw = 50 * sin(√(2.4 * perCM)) where perCM is percentage
			mi_cw = 50 * math.sin(math.sqrt(2.4 * per_cm)) if per_cm >= 0 else 0
			
			# MI = MIwoc + MIcw
			maintainability_index = mi_woc + mi_cw
			
			# Store raw value for analysis, but clamp for display
			raw_maintainability_index = maintainability_index
			# Normalize to 0-171 range (standard MI range)
			maintainability_index = max(0, min(171, maintainability_index))
			
			return {
				'mi': maintainability_index,
				'mi_raw': raw_maintainability_index,
				'mi_woc': mi_woc,
				'mi_cw': mi_cw,
				'interpretation': self._interpret_maintainability_index(raw_maintainability_index)
			}
			
		except (ValueError, OverflowError, ZeroDivisionError) as e:
			if conf['debug']:
				print(f'Warning: Maintainability Index calculation failed: {e}')
				print(f'  Input values - loc_metrics: {loc_metrics}')
				print(f'  Input values - halstead_metrics: {halstead_metrics}')
				print(f'  Input values - mccabe_metrics: {mccabe_metrics}')
			return {
				'mi': 0.0,
				'mi_woc': 0.0,
				'mi_cw': 0.0,
				'interpretation': 'calculation_failed'
			}

	def _interpret_maintainability_index(self, mi):
		"""Interpret Maintainability Index score."""
		if mi >= 85:
			return 'good'          # Good maintainability
		elif mi >= 65:
			return 'moderate'      # Moderate maintainability
		elif mi >= 0:
			return 'difficult'     # Difficult to maintain
		else:
			return 'critical'      # Critical/pathological case
	
	def _calculate_oop_metrics(self, content, file_extension, filepath):
		"""Calculate Object-Oriented Programming software metrics.
		
		Calculates:
		- Efferent Coupling (Ce): Number of classes this class depends on
		- Afferent Coupling (Ca): Number of classes that depend on this class  
		- Instability (I): Ce / (Ce + Ca)
		- Abstractness (A): Abstract classes / Total classes
		- Distance from Main Sequence (D): |A + I - 1|
		"""
		import re
		
		# Initialize OOP metrics
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'instability': 0.0,
			'abstractness': 0.0,
			'distance_main_sequence': 0.0,
			'inheritance_depth': 0,
			'method_count': 0,
			'attribute_count': 0
		}
		
		if not content.strip():
			return metrics
		
		try:
			# Remove comments and strings for accurate analysis
			cleaned_content = self._remove_comments_and_strings(content, file_extension)
			
			# Language-specific OOP analysis
			if file_extension in ['.java', '.scala', '.kt']:
				metrics.update(self._analyze_java_oop_metrics(cleaned_content))
			elif file_extension in ['.py', '.pyi']:
				metrics.update(self._analyze_python_oop_metrics(cleaned_content))
			elif file_extension in ['.cpp', '.cc', '.cxx', '.hpp', '.hxx', '.h']:
				metrics.update(self._analyze_cpp_oop_metrics(cleaned_content))
			elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
				metrics.update(self._analyze_javascript_oop_metrics(cleaned_content))
			elif file_extension in ['.swift']:
				metrics.update(self._analyze_swift_oop_metrics(cleaned_content))
			elif file_extension in ['.go']:
				metrics.update(self._analyze_go_oop_metrics(cleaned_content))
			elif file_extension in ['.rs']:
				metrics.update(self._analyze_rust_oop_metrics(cleaned_content))
			
			# Calculate derived metrics
			if metrics['classes_defined'] > 0:
				metrics['abstractness'] = metrics['abstract_classes'] / metrics['classes_defined']
			
			ce = metrics['efferent_coupling']
			ca = metrics['afferent_coupling'] 
			if (ce + ca) > 0:
				metrics['instability'] = ce / (ce + ca)
			
			# Distance from Main Sequence: D = |A + I - 1|
			metrics['distance_main_sequence'] = abs(metrics['abstractness'] + metrics['instability'] - 1.0)
			
			# Add overall coupling metric (sum of efferent and afferent coupling)
			metrics['coupling'] = metrics['efferent_coupling'] + metrics['afferent_coupling']
			
		except Exception as e:
			if conf['debug']:
				print(f'Warning: OOP metrics calculation failed for {filepath}: {e}')
		
		return metrics
	
	def _analyze_java_oop_metrics(self, content):
		"""Analyze OOP metrics for Java/Scala/Kotlin files."""
		import re
		
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'inheritance_depth': 0
		}
		
		# Count classes (including inner classes)
		class_patterns = [
			r'\bclass\s+\w+',
			r'\benum\s+\w+',
			r'\b@interface\s+\w+'
		]
		for pattern in class_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['classes_defined'] += len(matches)
		
		# Count abstract classes
		abstract_patterns = [
			r'\babstract\s+class\s+\w+',
			r'\babstract\s+.*\s+class\s+\w+'
		]
		for pattern in abstract_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['abstract_classes'] += len(matches)
		
		# Count interfaces
		interface_patterns = [r'\binterface\s+\w+']
		for pattern in interface_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['interfaces_defined'] += len(matches)
			metrics['abstract_classes'] += len(matches)  # Interfaces are abstract
		
		# Count methods (public, private, protected)
		method_patterns = [
			r'\b(public|private|protected|static).*\s+\w+\s*\([^)]*\)\s*\{',
			r'\b\w+\s*\([^)]*\)\s*\{'  # Basic method pattern
		]
		for pattern in method_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['method_count'] += len(matches)
		
		# Count attributes/fields
		field_patterns = [
			r'\b(public|private|protected|static)\s+[\w<>,\[\]]+\s+\w+\s*[=;]',
			r'\bprivate\s+[\w<>,\[\]]+\s+\w+',
			r'\bpublic\s+[\w<>,\[\]]+\s+\w+',
			r'\bprotected\s+[\w<>,\[\]]+\s+\w+'
		]
		for pattern in field_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['attribute_count'] += len(matches)
		
		# Estimate coupling by counting imports and new object creations
		import_matches = re.findall(r'\bimport\s+[\w.]+', content)
		new_matches = re.findall(r'\bnew\s+\w+\s*\(', content)
		metrics['efferent_coupling'] = len(set(import_matches)) + len(new_matches)
		
		return metrics
	
	def _analyze_python_oop_metrics(self, content):
		"""Analyze OOP metrics for Python files."""
		import re
		
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'inheritance_depth': 0
		}
		
		# Count classes
		class_matches = re.findall(r'^class\s+\w+.*:', content, re.MULTILINE)
		metrics['classes_defined'] = len(class_matches)
		
		# Count abstract classes (ABC or abstractmethod)
		abstract_patterns = [
			r'from\s+abc\s+import',
			r'@abstractmethod',
			r'ABC\)',
			r'class.*ABC.*:'
		]
		has_abc = any(re.search(pattern, content) for pattern in abstract_patterns)
		if has_abc and metrics['classes_defined'] > 0:
			metrics['abstract_classes'] = 1  # Conservative estimate
		
		# Count methods (def within classes)
		method_matches = re.findall(r'^\s+def\s+\w+\s*\(.*\):', content, re.MULTILINE)
		metrics['method_count'] = len(method_matches)
		
		# Count attributes (self.attribute assignments)
		attribute_matches = re.findall(r'self\.\w+\s*=', content)
		metrics['attribute_count'] = len(set(attribute_matches))
		
		# Estimate coupling by counting imports
		import_matches = re.findall(r'^(?:from\s+[\w.]+\s+)?import\s+[\w.,\s]+', content, re.MULTILINE)
		metrics['efferent_coupling'] = len(import_matches)
		
		return metrics
	
	def _analyze_cpp_oop_metrics(self, content):
		"""Analyze OOP metrics for C++ files."""
		import re
		
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'inheritance_depth': 0
		}
		
		# Count classes and structs
		class_patterns = [
			r'\bclass\s+\w+',
			r'\bstruct\s+\w+'
		]
		for pattern in class_patterns:
			matches = re.findall(pattern, content)
			metrics['classes_defined'] += len(matches)
		
		# Count abstract classes (virtual methods)
		virtual_matches = re.findall(r'virtual\s+.*\s*=\s*0\s*;', content)
		if virtual_matches:
			metrics['abstract_classes'] = 1  # Conservative estimate
		
		# Count methods (function definitions in classes)
		method_patterns = [
			r'\b\w+\s*\([^)]*\)\s*\{',
			r'\b(public|private|protected):\s*\n\s*\w+\s*\([^)]*\)'
		]
		for pattern in method_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['method_count'] += len(matches)
		
		# Count attributes (member variables)
		member_patterns = [
			r'\b(public|private|protected):\s*\n\s*[\w<>,\*&\[\]]+\s+\w+\s*;',
			r'^\s*[\w<>,\*&\[\]]+\s+\w+\s*;', 
		]
		for pattern in member_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['attribute_count'] += len(matches)
		
		# Estimate coupling by counting includes
		include_matches = re.findall(r'#include\s*[<"][\w./]+[>"]', content)
		metrics['efferent_coupling'] = len(include_matches)
		
		return metrics
	
	def _analyze_javascript_oop_metrics(self, content):
		"""Analyze OOP metrics for JavaScript/TypeScript files.""" 
		import re
		
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'inheritance_depth': 0
		}
		
		# Count classes
		class_matches = re.findall(r'\bclass\s+\w+', content)
		metrics['classes_defined'] = len(class_matches)
		
		# Count interfaces (TypeScript)
		interface_matches = re.findall(r'\binterface\s+\w+', content)
		metrics['interfaces_defined'] = len(interface_matches)
		metrics['abstract_classes'] += len(interface_matches)
		
		# Count abstract classes (TypeScript)
		abstract_matches = re.findall(r'\babstract\s+class\s+\w+', content)
		metrics['abstract_classes'] += len(abstract_matches)
		
		# Count methods
		method_patterns = [
			r'\b\w+\s*\([^)]*\)\s*\{',
			r'\b\w+:\s*\([^)]*\)\s*=>'
		]
		for pattern in method_patterns:
			matches = re.findall(pattern, content)
			metrics['method_count'] += len(matches)
		
		# Count properties/attributes
		property_patterns = [
			r'this\.\w+\s*=',
			r'\b\w+:\s*[\w\[\]<>]+\s*[;,]'
		]
		for pattern in property_patterns:
			matches = re.findall(pattern, content)
			metrics['attribute_count'] += len(matches)
		
		# Estimate coupling by counting imports/requires
		import_patterns = [
			r'import\s+.*\s+from\s+["\'][\w./]+["\']',
			r'require\s*\(["\'][\w./]+["\']\)'
		]
		for pattern in import_patterns:
			matches = re.findall(pattern, content)
			metrics['efferent_coupling'] += len(matches)
		
		return metrics
	
	def _analyze_swift_oop_metrics(self, content):
		"""Analyze OOP metrics for Swift files."""
		import re
		
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'inheritance_depth': 0
		}
		
		# Count classes and structs
		class_patterns = [
			r'\bclass\s+\w+',
			r'\bstruct\s+\w+'
		]
		for pattern in class_patterns:
			matches = re.findall(pattern, content)
			metrics['classes_defined'] += len(matches)
		
		# Count protocols (Swift's interfaces)
		protocol_matches = re.findall(r'\bprotocol\s+\w+', content)
		metrics['interfaces_defined'] = len(protocol_matches)
		metrics['abstract_classes'] += len(protocol_matches)
		
		# Count methods/functions
		method_matches = re.findall(r'\bfunc\s+\w+\s*\(', content)
		metrics['method_count'] = len(method_matches)
		
		# Count properties
		property_patterns = [
			r'\bvar\s+\w+\s*:',
			r'\blet\s+\w+\s*:'
		]
		for pattern in property_patterns:
			matches = re.findall(pattern, content)
			metrics['attribute_count'] += len(matches)
		
		# Estimate coupling by counting imports
		import_matches = re.findall(r'\bimport\s+\w+', content)
		metrics['efferent_coupling'] = len(import_matches)
		
		return metrics
	
	def _analyze_go_oop_metrics(self, content):
		"""Analyze OOP-like metrics for Go files."""
		import re
		
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'inheritance_depth': 0
		}
		
		# Count structs (Go's equivalent to classes)
		struct_matches = re.findall(r'\btype\s+\w+\s+struct\s*\{', content)
		metrics['classes_defined'] = len(struct_matches)
		
		# Count interfaces
		interface_matches = re.findall(r'\btype\s+\w+\s+interface\s*\{', content)
		metrics['interfaces_defined'] = len(interface_matches)
		metrics['abstract_classes'] = len(interface_matches)
		
		# Count methods (functions with receivers)
		method_matches = re.findall(r'\bfunc\s*\([^)]*\)\s*\w+\s*\(', content)
		metrics['method_count'] = len(method_matches)
		
		# Count struct fields
		# This is a simple approximation - count field-like declarations in structs
		field_matches = re.findall(r'^\s*\w+\s+[\w\[\]\*]+\s*$', content, re.MULTILINE)
		metrics['attribute_count'] = len(field_matches)
		
		# Estimate coupling by counting imports
		import_matches = re.findall(r'\bimport\s+["\w/.-]+', content)
		metrics['efferent_coupling'] = len(import_matches)
		
		return metrics
	
	def _analyze_rust_oop_metrics(self, content):
		"""Analyze OOP-like metrics for Rust files."""
		import re
		
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'inheritance_depth': 0
		}
		
		# Count structs and enums (Rust's data types)
		struct_matches = re.findall(r'\bstruct\s+\w+', content)
		enum_matches = re.findall(r'\benum\s+\w+', content)
		metrics['classes_defined'] = len(struct_matches) + len(enum_matches)
		
		# Count traits (Rust's interfaces)
		trait_matches = re.findall(r'\btrait\s+\w+', content)
		metrics['interfaces_defined'] = len(trait_matches)
		metrics['abstract_classes'] = len(trait_matches)
		
		# Count impl methods
		method_matches = re.findall(r'\bfn\s+\w+\s*\(', content)
		metrics['method_count'] = len(method_matches)
		
		# Count struct fields (simplified)
		field_matches = re.findall(r'^\s*\w+\s*:\s*[\w<>,\[\]]+\s*,?', content, re.MULTILINE)
		metrics['attribute_count'] = len(field_matches)
		
		# Estimate coupling by counting use statements
		use_matches = re.findall(r'\buse\s+[\w:]+', content)
		extern_matches = re.findall(r'\bextern\s+crate\s+\w+', content)
		metrics['efferent_coupling'] = len(use_matches) + len(extern_matches)
		
		return metrics
	
	def get_repository_files_for_mi(self, repository_path=None):
		"""Get all files from repository that match allowed extensions for MI calculation.
		
		Args:
			repository_path: Path to repository (if None, uses current working directory)
		
		Returns:
			list: List of file paths that match allowed extensions
		"""
		if repository_path:
			original_cwd = os.getcwd()
			try:
				os.chdir(repository_path)
			except OSError as e:
				print(f'Warning: Could not change to repository path {repository_path}: {e}')
				return []
		
		try:
			files_output = getpipeoutput(['git ls-files'])
			if not files_output.strip():
				print(f'    No files found in repository: {repository_path or os.getcwd()}')
				return []
			
			source_files = []
			print(f'  📁 Scanning repository: {repository_path or os.getcwd()}')
			print('  🔍 Files matching allowed extensions:')
			
			for filepath in files_output.strip().split('\n'):
				if filepath.strip():
					filename = filepath.split('/')[-1]
					if should_include_file(filename):
						full_path = os.path.join(os.getcwd(), filepath)
						if os.path.exists(full_path):
							source_files.append(filepath)
							# Output the found files to CLI as requested
							ext = os.path.splitext(filename)[1] or 'no-ext'
							print(f'      ✓ {filepath} ({ext})')
			
			print(f'  📊 Found {len(source_files)} files for MI analysis')
			return source_files
			
		except Exception as e:
			print(f'Warning: Failed to get repository files: {e}')
			return []
		finally:
			if repository_path:
				try:
					os.chdir(original_cwd)
				except OSError:
					pass
	
	def calculate_mi_for_repository(self, repository_path=None):
		"""Calculate MI for all matching files in a specific repository.
		
		Args:
			repository_path: Path to repository (if None, uses current working directory)
			
		Returns:
			dict: MI analysis results for the repository
		"""
		print('\n🧮 Calculating Maintainability Index (MI) for repository...')
		
		if repository_path:
			original_cwd = os.getcwd()
			try:
				os.chdir(repository_path)
				print(f'  📁 Repository: {repository_path}')
			except OSError as e:
				print(f'Error: Could not access repository {repository_path}: {e}')
				return None
		
		try:
			# Get all source files for this repository
			source_files = self.get_repository_files_for_mi(repository_path)
			
			if not source_files:
				print('    ⚠️  No source files found with allowed extensions')
				return {
					'repository_path': repository_path or os.getcwd(),
					'files_analyzed': 0,
					'mi_results': [],
					'summary': 'No files found'
				}
			
			# Calculate MI for each file
			mi_results = []
			successful_calculations = 0
			
			print(f'\n  🔬 Calculating MI for {len(source_files)} files...')
			
			for i, filepath in enumerate(source_files):
				try:
					metrics = self.calculate_comprehensive_metrics(filepath)
					if metrics and 'maintainability_index' in metrics:
						mi_data = metrics['maintainability_index']
						file_result = {
							'filepath': filepath,
							'extension': metrics.get('extension', ''),
							'mi_score': mi_data['mi'],
							'mi_raw': mi_data['mi_raw'],
							'interpretation': mi_data['interpretation'],
							'loc_phy': metrics['loc']['loc_phy'],
							'complexity': metrics['mccabe']['cyclomatic_complexity']
						}
						mi_results.append(file_result)
						successful_calculations += 1
						
						# Output MI result to CLI
						print(f'      📄 {filepath}: MI = {mi_data["mi"]:.1f} ({mi_data["interpretation"]})')
				
				except Exception as e:
					if conf['debug']:
						print(f'      ⚠️  Failed to calculate MI for {filepath}: {e}')
			
			# Calculate summary statistics
			if mi_results:
				mi_scores = [result['mi_score'] for result in mi_results]
				avg_mi = sum(mi_scores) / len(mi_scores)
				
				# Count by interpretation
				interpretation_counts = {}
				for result in mi_results:
					interp = result['interpretation']
					interpretation_counts[interp] = interpretation_counts.get(interp, 0) + 1
				
				print(f'\n  📊 MI Analysis Summary:')
				print(f'      Files analyzed: {len(mi_results)}')
				print(f'      Average MI: {avg_mi:.1f}')
				print(f'      Distribution:')
				for interp, count in interpretation_counts.items():
					print(f'        - {interp}: {count} files')
				
				return {
					'repository_path': repository_path or os.getcwd(),
					'files_analyzed': len(mi_results),
					'successful_calculations': successful_calculations,
					'mi_results': mi_results,
					'summary': {
						'average_mi': avg_mi,
						'distribution': interpretation_counts,
						'total_files': len(source_files),
						'calculated_files': len(mi_results)
					}
				}
			else:
				print('    ⚠️  No successful MI calculations')
				return {
					'repository_path': repository_path or os.getcwd(),
					'files_analyzed': 0,
					'mi_results': [],
					'summary': 'No successful calculations'
				}
				
		except Exception as e:
			print(f'Error during MI calculation: {e}')
			return None
		finally:
			if repository_path:
				try:
					os.chdir(original_cwd)
				except OSError:
					pass
	
	def calculate_mccabe_for_repository(self, repository_path=None):
		"""Calculate McCabe complexity metrics for all files in the repository."""
		print('🔄 Calculating McCabe Complexity for repository...')
		print(f'  📁 Repository: {repository_path or os.getcwd()}')
		
		original_cwd = os.getcwd()
		
		try:
			source_files = self.get_repository_files_for_mi(repository_path)
			
			if not source_files:
				print('    ⚠️  No source files found for McCabe analysis')
				return None
			
			print(f'  📊 Found {len(source_files)} files for McCabe analysis')
			print(f'  🔬 Calculating complexity for {len(source_files)} files...')
			
			complexity_results = []
			
			for filepath in source_files:
				try:
					full_filepath = os.path.join(repository_path or os.getcwd(), filepath)
					with open(full_filepath, 'r', encoding='utf-8', errors='ignore') as f:
						content = f.read()
					
					ext = os.path.splitext(filepath)[1].lower()
					mccabe_metrics = self._calculate_mccabe_complexity(content, ext)
					complexity = mccabe_metrics['cyclomatic_complexity']
					
					# Categorize complexity
					if complexity <= 5:
						category = 'simple'
					elif complexity <= 10:
						category = 'moderate'
					elif complexity <= 20:
						category = 'complex'
					else:
						category = 'very_complex'
					
					result = {
						'filepath': filepath,
						'complexity': complexity,
						'category': category
					}
					complexity_results.append(result)
					
					print(f'      📄 {filepath}: Complexity = {complexity} ({category})')
					
				except Exception as e:
					print(f'      ❌ Error analyzing {filepath}: {e}')
			
			if complexity_results:
				# Calculate summary statistics
				complexities = [r['complexity'] for r in complexity_results]
				avg_complexity = sum(complexities) / len(complexities)
				max_complexity = max(complexities)
				
				# Count by category
				simple_files = len([r for r in complexity_results if r['category'] == 'simple'])
				moderate_files = len([r for r in complexity_results if r['category'] == 'moderate'])
				complex_files = len([r for r in complexity_results if r['category'] == 'complex'])
				very_complex_files = len([r for r in complexity_results if r['category'] == 'very_complex'])
				
				print(f'\n  📊 McCabe Complexity Analysis Summary:')
				print(f'      Files analyzed: {len(complexity_results)}')
				print(f'      Average complexity: {avg_complexity:.1f}')
				print(f'      Maximum complexity: {max_complexity}')
				print(f'      Distribution:')
				print(f'        - Simple (≤5): {simple_files} files')
				print(f'        - Moderate (6-10): {moderate_files} files') 
				print(f'        - Complex (11-20): {complex_files} files')
				print(f'        - Very Complex (>20): {very_complex_files} files')
				
				# Show all files by complexity (highest first)
				print('\n  === Files by McCabe Complexity (Highest First) ===')
				sorted_results = sorted(complexity_results, key=lambda x: x['complexity'], reverse=True)
				for result in sorted_results:  # Show all files
					if result['complexity'] > 20:
						print(f'    🚨 {result["filepath"]} (Complexity: {result["complexity"]}) - Very Complex')
					elif result['complexity'] > 10:
						print(f'    ⚠️  {result["filepath"]} (Complexity: {result["complexity"]}) - Complex')
					elif result['complexity'] > 5:
						print(f'    � {result["filepath"]} (Complexity: {result["complexity"]}) - Moderate')
					else:
						print(f'    ✅ {result["filepath"]} (Complexity: {result["complexity"]}) - Simple')
				
				print('✓ McCabe complexity calculation completed')
				return {
					'repository_path': repository_path or os.getcwd(),
					'files_analyzed': len(complexity_results),
					'results': complexity_results,
					'summary': {
						'average_complexity': avg_complexity,
						'max_complexity': max_complexity,
						'simple_files': simple_files,
						'moderate_files': moderate_files,
						'complex_files': complex_files,
						'very_complex_files': very_complex_files
					}
				}
			else:
				print('    ⚠️  No successful McCabe calculations')
				return None
				
		except Exception as e:
			print(f'Error during McCabe calculation: {e}')
			return None
		finally:
			if repository_path:
				try:
					os.chdir(original_cwd)
				except OSError:
					pass

	def calculate_halstead_for_repository(self, repository_path=None):
		"""Calculate Halstead metrics for all files in the repository."""
		print('🧮 Calculating Halstead Metrics for repository...')
		print(f'  📁 Repository: {repository_path or os.getcwd()}')
		
		original_cwd = os.getcwd()
		
		try:
			source_files = self.get_repository_files_for_mi(repository_path)
			
			if not source_files:
				print('    ⚠️  No source files found for Halstead analysis')
				return None
			
			print(f'  📊 Found {len(source_files)} files for Halstead analysis')
			print(f'  🔬 Calculating metrics for {len(source_files)} files...')
			
			halstead_results = []
			
			for filepath in source_files:
				try:
					full_filepath = os.path.join(repository_path or os.getcwd(), filepath)
					with open(full_filepath, 'r', encoding='utf-8', errors='ignore') as f:
						content = f.read()
					
					ext = os.path.splitext(filepath)[1].lower()
					halstead_metrics = self._calculate_halstead_metrics(content, ext)
					
					result = {
						'filepath': filepath,
						'volume': halstead_metrics['V'],
						'difficulty': halstead_metrics['D'],
						'effort': halstead_metrics['E'],
						'bugs': halstead_metrics['B'],
						'time': halstead_metrics['T']
					}
					halstead_results.append(result)
					
					print(f'      📄 {filepath}: Volume={halstead_metrics["V"]:.1f}, Difficulty={halstead_metrics["D"]:.1f}, Effort={halstead_metrics["E"]:.1f}')
					
				except Exception as e:
					print(f'      ❌ Error analyzing {filepath}: {e}')
			
			if halstead_results:
				# Calculate summary statistics
				volumes = [r['volume'] for r in halstead_results]
				difficulties = [r['difficulty'] for r in halstead_results]
				efforts = [r['effort'] for r in halstead_results]
				bugs = [r['bugs'] for r in halstead_results]
				
				avg_volume = sum(volumes) / len(volumes)
				avg_difficulty = sum(difficulties) / len(difficulties)
				avg_effort = sum(efforts) / len(efforts)
				total_bugs = sum(bugs)
				
				print(f'\n  📊 Halstead Metrics Analysis Summary:')
				print(f'      Files analyzed: {len(halstead_results)}')
				print(f'      Average volume: {avg_volume:.1f}')
				print(f'      Average difficulty: {avg_difficulty:.1f}')
				print(f'      Average effort: {avg_effort:.1f}')
				print(f'      Estimated total bugs: {total_bugs:.2f}')
				
				# Show all files by effort (highest first)
				print('\n  === Files by Halstead Effort (Highest First) ===')
				sorted_results = sorted(halstead_results, key=lambda x: x['effort'], reverse=True)
				for result in sorted_results:  # Show all files
					print(f'    📄 {result["filepath"]} (Effort: {result["effort"]:.1f}, Bugs: {result["bugs"]:.2f})')
				
				print('✓ Halstead metrics calculation completed')
				return {
					'repository_path': repository_path or os.getcwd(),
					'files_analyzed': len(halstead_results),
					'results': halstead_results,
					'summary': {
						'average_volume': avg_volume,
						'average_difficulty': avg_difficulty,
						'average_effort': avg_effort,
						'total_estimated_bugs': total_bugs
					}
				}
			else:
				print('    ⚠️  No successful Halstead calculations')
				return None
				
		except Exception as e:
			print(f'Error during Halstead calculation: {e}')
			return None
		finally:
			if repository_path:
				try:
					os.chdir(original_cwd)
				except OSError:
					pass

	def calculate_oop_for_repository(self, repository_path=None):
		"""Calculate OOP metrics for all files in the repository."""
		print('🏗️ Calculating OOP Metrics for repository...')
		print(f'  📁 Repository: {repository_path or os.getcwd()}')
		
		original_cwd = os.getcwd()
		
		try:
			source_files = self.get_repository_files_for_mi(repository_path)
			
			if not source_files:
				print('    ⚠️  No source files found for OOP analysis')
				return None
			
			print(f'  📊 Found {len(source_files)} files for OOP analysis')
			print(f'  🔬 Calculating metrics for {len(source_files)} files...')
			
			oop_results = []
			
			for filepath in source_files:
				try:
					full_filepath = os.path.join(repository_path or os.getcwd(), filepath)
					with open(full_filepath, 'r', encoding='utf-8', errors='ignore') as f:
						content = f.read()
					
					ext = os.path.splitext(filepath)[1].lower()
					oop_metrics = self._calculate_oop_metrics(content, ext, full_filepath)
					
					result = {
						'filepath': filepath,
						'classes': oop_metrics['classes_defined'],
						'abstract_classes': oop_metrics['abstract_classes'],
						'interfaces': oop_metrics['interfaces_defined'],
						'methods': oop_metrics['method_count'],
						'attributes': oop_metrics['attribute_count'],
						'inheritance_depth': oop_metrics['inheritance_depth'],
						'coupling': oop_metrics['coupling']
					}
					oop_results.append(result)
					
					if oop_metrics['classes_defined'] > 0:
						print(f'      📄 {filepath}: Classes={oop_metrics["classes_defined"]}, Methods={oop_metrics["method_count"]}, Coupling={oop_metrics["coupling"]:.1f}')
					else:
						print(f'      📄 {filepath}: No OOP constructs found')
					
				except Exception as e:
					print(f'      ❌ Error analyzing {filepath}: {e}')
			
			if oop_results:
				# Calculate summary statistics
				total_classes = sum(r['classes'] for r in oop_results)
				total_methods = sum(r['methods'] for r in oop_results)
				total_attributes = sum(r['attributes'] for r in oop_results)
				files_with_oop = len([r for r in oop_results if r['classes'] > 0])
				
				avg_coupling = sum(r['coupling'] for r in oop_results if r['coupling'] > 0)
				if files_with_oop > 0:
					avg_coupling = avg_coupling / files_with_oop
				else:
					avg_coupling = 0
				
				print(f'\n  📊 OOP Metrics Analysis Summary:')
				print(f'      Files analyzed: {len(oop_results)}')
				print(f'      Files with OOP constructs: {files_with_oop}')
				print(f'      Total classes: {total_classes}')
				print(f'      Total methods: {total_methods}')
				print(f'      Total attributes: {total_attributes}')
				print(f'      Average coupling: {avg_coupling:.1f}')
				
				# Show all files with OOP constructs by coupling (highest first)
				if files_with_oop > 0:
					print('\n  === Files with OOP Constructs (by Coupling) ===')
					sorted_results = sorted([r for r in oop_results if r['coupling'] > 0], 
											key=lambda x: x['coupling'], reverse=True)
					for result in sorted_results:  # Show all files with OOP
						print(f'    📄 {result["filepath"]} (Classes: {result["classes"]}, Methods: {result["methods"]}, Coupling: {result["coupling"]:.1f})')
				
				print('✓ OOP metrics calculation completed')
				return {
					'repository_path': repository_path or os.getcwd(),
					'files_analyzed': len(oop_results),
					'results': oop_results,
					'summary': {
						'total_classes': total_classes,
						'total_methods': total_methods,
						'total_attributes': total_attributes,
						'files_with_oop': files_with_oop,
						'average_coupling': avg_coupling
					}
				}
			else:
				print('    ⚠️  No successful OOP calculations')
				return None
				
		except Exception as e:
			print(f'Error during OOP calculation: {e}')
			return None
		finally:
			if repository_path:
				try:
					os.chdir(original_cwd)
				except OSError:
					pass
	
	def _calculate_comprehensive_project_metrics(self, repository_path=None):
		"""Calculate comprehensive code quality metrics for the entire project."""
		print('  Analyzing source files for comprehensive metrics...')
		
		# Get all source files using the new method - use the target repository path
		source_files = self.get_repository_files_for_mi(repository_path)
		
		if not source_files:
			print('    No source files found with allowed extensions')
			return
		
		print(f'    Processing {len(source_files)} source files...')
		
		try:
			# Initialize storage for per-file metrics (no aggregation)
			file_metrics_list = []
			
			# Initialize aggregate metrics (keeping only what's needed for summaries)
			project_totals = {
				'files_analyzed': 0,
				'files_by_maintainability': {
					'good': 0,
					'moderate': 0,
					'difficult': 0,
					'critical': 0
				},
				'mi_file_details': {
					'good': [],
					'moderate': [],
					'difficult': [],
					'critical': []
				},
				'files_with_oop': 0
			}
			
			# Analyze each file
			for i, filepath in enumerate(source_files):
				if i % 50 == 0 and i > 0:
					print(f'    Processed {i}/{len(source_files)} files...')
				
				try:
					# Use full path since we're not in the repository directory
					full_filepath = os.path.join(repository_path, filepath)
					metrics = self.calculate_comprehensive_metrics(full_filepath)
					if not metrics:
						continue
					
					# Store complete file metrics without aggregation
					file_metric_entry = {
						'filepath': filepath,
						'extension': metrics['extension'],
						'loc': metrics['loc'],
						'halstead': metrics['halstead'],
						'mccabe': metrics['mccabe'],
						'maintainability_index': metrics['maintainability_index'],
						'oop': metrics['oop']
					}
					file_metrics_list.append(file_metric_entry)
					
					# Only track maintainability categories for summaries
					mi = metrics['maintainability_index']
					mi_category = mi['interpretation']
					project_totals['files_by_maintainability'][mi_category] += 1
					
					# Store detailed file information for MI analysis
					file_info = {
						'filepath': filepath,
						'mi_score': mi['mi'],
						'mi_raw': mi['mi_raw'],
						'extension': metrics['extension'],
						'loc': metrics['loc']['loc_phy'],
						'complexity': metrics['mccabe']['cyclomatic_complexity']
					}
					project_totals['mi_file_details'][mi_category].append(file_info)
					
					# Count files that have OOP constructs
					oop = metrics['oop']
					if (oop['classes_defined'] > 0 or oop['interfaces_defined'] > 0 or 
						oop['method_count'] > 0 or oop['attribute_count'] > 0):
						project_totals['files_with_oop'] += 1
					
					project_totals['files_analyzed'] += 1
					
				except Exception as e:
					if conf['debug']:
						print(f'    Warning: Failed to analyze {filepath}: {e}')
					continue
		
			# Calculate averages and store results
			if project_totals['files_analyzed'] > 0:
				files_count = project_totals['files_analyzed']
				
				# Store comprehensive metrics in project health
				if 'comprehensive_metrics' not in self.project_health:
					self.project_health['comprehensive_metrics'] = {}
				
				cm = self.project_health['comprehensive_metrics']
				
				# Store individual file metrics (no aggregation)
				cm['file_metrics'] = file_metrics_list
				cm['files_analyzed'] = files_count
				
				# Store only maintainability categories for summary
				cm['maintainability_summary'] = {
					'good_files': project_totals['files_by_maintainability']['good'],
					'moderate_files': project_totals['files_by_maintainability']['moderate'],
					'difficult_files': project_totals['files_by_maintainability']['difficult'],
					'critical_files': project_totals['files_by_maintainability']['critical'],
					'files_analyzed': files_count,
					'file_details': project_totals['mi_file_details']
				}
				
				# Store only OOP file count summary
				cm['oop_summary'] = {
					'files_with_oop': project_totals['files_with_oop'],
					'files_analyzed': files_count
				}
				
				print(f'    Completed comprehensive analysis of {files_count} files')
				print(f'    Stored individual file metrics (no aggregation)')
				
				# Print detailed MI analysis
				mi_summary = cm['maintainability_summary']
				print('\n  === Maintainability Index Analysis by Category ===')
				print(f'    📈 Good Files (MI ≥ 85):       {mi_summary["good_files"]:4d} files')
				print(f'    📊 Moderate Files (65 ≤ MI < 85): {mi_summary["moderate_files"]:4d} files') 
				print(f'    📉 Difficult Files (0 ≤ MI < 65): {mi_summary["difficult_files"]:4d} files')
				print(f'    ⚠️  Critical Files (MI < 0):    {mi_summary["critical_files"]:4d} files')
				print(f'    📁 Total Files Analyzed:       {files_count:4d} files')
				
				# Show most problematic files if any exist
				file_details = mi_summary['file_details']
				if file_details['critical'] or file_details['difficult']:
					print('\n  === Files Requiring Attention ===')
					
					# Show critical files (MI < 0)
					if file_details['critical']:
						print('    🚨 Critical Files (MI < 0):')
						critical_files = sorted(file_details['critical'], key=lambda x: x['mi_raw'])
						for file_info in critical_files:  # Show all critical files
							print(f'      {file_info["filepath"]} (MI: {file_info["mi_raw"]:.1f}, LOC: {file_info["loc"]}, Complexity: {file_info["complexity"]})')
					
					# Show worst difficult files (0 ≤ MI < 65)
					if file_details['difficult']:
						print('    ⚠️  Difficult Files (0 ≤ MI < 65):')
						difficult_files = sorted(file_details['difficult'], key=lambda x: x['mi_raw'])
						for file_info in difficult_files:  # Show all difficult files
							print(f'      {file_info["filepath"]} (MI: {file_info["mi_raw"]:.1f}, LOC: {file_info["loc"]}, Complexity: {file_info["complexity"]})')
				
				# Show best maintained files if any exist
				if file_details['good']:
					print('\n  === Well-Maintained Files ===')
					good_files = sorted(file_details['good'], key=lambda x: x['mi_raw'], reverse=True)
					for file_info in good_files:  # Show all good files
						print(f'    ✅ {file_info["filepath"]} (MI: {file_info["mi_raw"]:.1f}, LOC: {file_info["loc"]}, Complexity: {file_info["complexity"]})')
				
				# Show extension-based MI analysis
				print('  === Maintainability Index by File Extension ===')
				extension_stats = {}
				
				# Collect stats by extension
				for category in ['good', 'moderate', 'difficult', 'critical']:
					for file_info in file_details[category]:
						ext = file_info['extension']
						if ext not in extension_stats:
							extension_stats[ext] = {
								'good': 0, 'moderate': 0, 'difficult': 0, 'critical': 0,
								'total': 0, 'sum_mi': 0.0
							}
						extension_stats[ext][category] += 1
						extension_stats[ext]['total'] += 1
						extension_stats[ext]['sum_mi'] += file_info['mi_raw']
				
				# Display extension statistics
				if extension_stats:
					for ext in sorted(extension_stats.keys()):
						stats = extension_stats[ext]
						avg_mi = stats['sum_mi'] / stats['total'] if stats['total'] > 0 else 0.0
						print(f'    {ext:8s}: {stats["total"]:3d} files (avg MI: {avg_mi:6.1f}) | ' +
							  f'Good: {stats["good"]:2d}, Moderate: {stats["moderate"]:2d}, ' +
							  f'Difficult: {stats["difficult"]:2d}, Critical: {stats["critical"]:2d}')
				
				print()  # Add spacing after MI analysis
			else:
				print('    No files could be analyzed for comprehensive metrics')
				
		except Exception as e:
			if conf['debug']:
				print(f'    Error in comprehensive metrics calculation: {e}')
			


class GitDataCollector(DataCollector):
	def collect(self, dir):
		DataCollector.collect(self, dir)
		
		# Store the repository path for later use in comprehensive metrics
		self.repository_path = dir
		
		# Print information about branch scanning
		if conf['scan_default_branch_only']:
			default_branch = get_default_branch()
			print(f'Branch scanning: ONLY scanning default branch ({default_branch})')
		else:
			print('Branch scanning: Scanning ALL branches (default behavior)')
		
		# Print information about extension filtering
		if conf['filter_by_extensions']:
			print(f'File extension filtering is ENABLED. Only analyzing files with these extensions:')
			extensions_list = sorted(list(conf['allowed_extensions']))
			print(f'  {", ".join(extensions_list)}')
		else:
			print('File extension filtering is DISABLED. Analyzing all file types.')

		first_parent_flag = get_first_parent_flag()
		self.total_authors += int(getpipeoutput(['git shortlog -s %s %s' % (first_parent_flag, getlogrange()), 'wc -l']))
		#self.total_lines = int(getoutput('git-ls-files -z |xargs -0 cat |wc -l'))

		# Clear tags for each repository to avoid multirepo contamination
		if not hasattr(self, '_first_repo'):
			self._first_repo = True
		else:
			# For subsequent repos, clear tags to avoid mixing
			self.tags = {}

		# tags
		lines = getpipeoutput(['git show-ref --tags']).split('\n')
		for line in lines:
			if len(line) == 0:
				continue
			(hash, tag) = line.split(' ')

			tag = tag.replace('refs/tags/', '')
			output = getpipeoutput(['git log "%s" --pretty=format:"%%at %%aN" -n 1' % hash])
			if len(output) > 0:
				parts = output.split(' ')
				stamp = 0
				try:
					stamp = int(parts[0])
				except ValueError:
					stamp = 0
				self.tags[tag] = { 'stamp': stamp, 'hash' : hash, 'date' : datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d'), 'commits': 0, 'authors': {} }

		# collect info on tags, starting from latest
		tags_sorted_by_date_desc = list(map(lambda el : el[1], reversed(sorted(map(lambda el : (el[1]['date'], el[0]), self.tags.items())))))
		prev = None
		for tag in reversed(tags_sorted_by_date_desc):
			cmd = 'git shortlog -s "%s"' % tag
			if prev != None:
				cmd += ' "^%s"' % prev
			output = getpipeoutput([cmd])
			if len(output) == 0:
				continue
			prev = tag
			for line in output.split('\n'):
				parts = re.split(r'\s+', line, maxsplit=2)
				commits = int(parts[1])
				author = parts[2]
				self.tags[tag]['commits'] += commits
				self.tags[tag]['authors'][author] = commits

		# Collect revision statistics
		# Outputs "<stamp> <date> <time> <timezone> <author> '<' <mail> '>'"
		first_parent_flag = get_first_parent_flag()
		lines = getpipeoutput(['git rev-list %s --pretty=format:"%%at %%ai %%aN <%%aE>" %s' % (first_parent_flag, getlogrange('HEAD')), 'grep -v ^commit']).split('\n')
		for line in lines:
			parts = line.split(' ', 4)
			author = ''
			try:
				stamp = int(parts[0])
			except ValueError:
				stamp = 0
			timezone = parts[3]
			author, mail = parts[4].split('<', 1)
			author = author.rstrip()
			mail = mail.rstrip('>')
			domain = '?'
			if mail.find('@') != -1:
				domain = mail.rsplit('@', 1)[1]
			date = datetime.datetime.fromtimestamp(float(stamp))

			# First and last commit stamp (may be in any order because of cherry-picking and patches)
			if stamp > self.repository_stats['last_commit_stamp']:
				self.repository_stats['last_commit_stamp'] = stamp
			if self.repository_stats['first_commit_stamp'] == 0 or stamp < self.repository_stats['first_commit_stamp']:
				self.repository_stats['first_commit_stamp'] = stamp

			# activity
			# hour
			hour = date.hour
			self.activity_metrics['by_hour_of_day'][hour] += 1
			# most active hour?
			if self.activity_metrics['by_hour_of_day'][hour] > self.activity_metrics['hour_of_day_busiest']:
				self.activity_metrics['hour_of_day_busiest'] = self.activity_metrics['by_hour_of_day'][hour]

			# day of week
			day = date.weekday()
			self.activity_metrics['by_day_of_week'][day] += 1

			# domain stats
			if domain not in self.domains:
				self.domains[domain] = defaultdict(int)
			# commits
			self.domains[domain]['commits'] += 1

			# hour of week  
			self.activity_metrics['by_hour_of_week'][day][hour] += 1
			# most active hour?
			if self.activity_metrics['by_hour_of_week'][day][hour] > self.activity_metrics['hour_of_week_busiest']:
				self.activity_metrics['hour_of_week_busiest'] = self.activity_metrics['by_hour_of_week'][day][hour]

			# month of year
			month = date.month
			self.activity_metrics['by_month_of_year'][month] += 1

			# yearly/weekly activity
			yyw = date.strftime('%Y-%W')
			self.activity_metrics['by_year_week'][yyw] += 1
			if self.activity_metrics['year_week_peak'] < self.activity_metrics['by_year_week'][yyw]:
				self.activity_metrics['year_week_peak'] = self.activity_metrics['by_year_week'][yyw]

			# author stats
			if author not in self.authors:
				self.authors[author] = { 'lines_added' : 0, 'lines_removed' : 0, 'commits' : 0}
			# commits, note again that commits may be in any date order because of cherry-picking and patches
			if 'last_commit_stamp' not in self.authors[author]:
				self.authors[author]['last_commit_stamp'] = stamp
			if stamp > self.authors[author]['last_commit_stamp']:
				self.authors[author]['last_commit_stamp'] = stamp
			if 'first_commit_stamp' not in self.authors[author]:
				self.authors[author]['first_commit_stamp'] = stamp
			if stamp < self.authors[author]['first_commit_stamp']:
				self.authors[author]['first_commit_stamp'] = stamp

			# author of the month/year
			yymm = date.strftime('%Y-%m')
			self.temporal_data['author_of_month'][yymm][author] += 1
			self.temporal_data['commits_by_month'][yymm] += 1

			yy = date.year
			self.temporal_data['author_of_year'][yy][author] += 1
			self.temporal_data['commits_by_year'][yy] += 1

			# authors: active days
			yymmdd = date.strftime('%Y-%m-%d')
			if 'last_active_day' not in self.authors[author]:
				self.authors[author]['last_active_day'] = yymmdd
				self.authors[author]['active_days'] = set([yymmdd])
			elif yymmdd != self.authors[author]['last_active_day']:
				self.authors[author]['last_active_day'] = yymmdd
				self.authors[author]['active_days'].add(yymmdd)

			# project: active days
			if yymmdd != self.repository_stats['last_active_day']:
				self.repository_stats['last_active_day'] = yymmdd
				self.repository_stats['active_days'].add(yymmdd)

			# timezone
			self.commits_by_timezone[timezone] += 1

		# outputs "<stamp> <files>" for each revision
		first_parent_flag = get_first_parent_flag()
		revlines = getpipeoutput(['git rev-list %s --pretty=format:"%%at %%T" %s' % (first_parent_flag, getlogrange('HEAD')), 'grep -v ^commit']).strip().split('\n')
		lines = []
		revs_to_read = []
		time_rev_count = []
		#Look up rev in cache and take info from cache if found
		#If not append rev to list of rev to read from repo
		for revline in revlines:
			time, rev = revline.split(' ')
			#if cache empty then add time and rev to list of new rev's
			#otherwise try to read needed info from cache
			if 'files_in_tree' not in self.cache:
				revs_to_read.append((time,rev))
				continue
			if rev in self.cache['files_in_tree']:
				lines.append('%d %d' % (int(time), self.cache['files_in_tree'][rev]))
			else:
				revs_to_read.append((time,rev))

		#Read revisions from repo
		if revs_to_read:
			# Use optimized multiprocessing with better resource management
			worker_count = min(len(revs_to_read), conf['processes'])
			if conf['verbose']:
				print(f'Processing {len(revs_to_read)} revisions with {worker_count} workers')
			
			# Use context manager for better resource cleanup
			with Pool(processes=worker_count) as pool:
				time_rev_count = pool.map(getnumoffilesfromrev, revs_to_read)
		else:
			time_rev_count = []

		#Update cache with new revisions and append then to general list
		for (time, rev, count) in time_rev_count:
			if 'files_in_tree' not in self.cache:
				self.cache['files_in_tree'] = {}
			self.cache['files_in_tree'][rev] = count
			lines.append('%d %d' % (int(time), count))

		self.repository_stats['total_commits'] += len(lines)
		for line in lines:
			parts = line.split(' ')
			if len(parts) != 2:
				continue
			(stamp, files) = parts[0:2]
			try:
				timestamp = int(stamp)
				file_count = int(files)
				self.temporal_data['files_by_stamp'][timestamp] = file_count
				
				# Track files by year (use max file count per year)
				date = datetime.datetime.fromtimestamp(timestamp)
				year = date.year
				if year not in self.temporal_data['files_by_year'] or file_count > self.temporal_data['files_by_year'][year]:
					self.temporal_data['files_by_year'][year] = file_count
			except ValueError:
				print('Warning: failed to parse line "%s"' % line)

		# extensions and size of files
		lines = getpipeoutput(['git ls-tree -r -l -z %s' % getcommitrange('HEAD', end_only = True)]).split('\000')
		blobs_to_read = []
		all_blobs_for_sloc = []  # All blobs for SLOC analysis, regardless of cache status
		for line in lines:
			if len(line) == 0:
				continue
			parts = re.split(r'\s+', line, maxsplit=4)
			if parts[0] == '160000' and parts[3] == '-':
				# skip submodules
				continue
			blob_id = parts[2]
			size = int(parts[3])
			fullpath = parts[4]

			filename = fullpath.split('/')[-1] # strip directories
			
			# Apply extension filtering - skip files that don't match allowed extensions
			if not should_include_file(filename):
				if conf['verbose'] or conf['debug']:
					print(f'Skipping file (extension not in allowed list): {fullpath}')
				continue

			self.repository_stats['total_size'] += size
			self.repository_stats['total_files'] += 1
			
			# Track individual file sizes
			self.code_analysis['file_sizes'][fullpath] = size

			if filename.find('.') == -1 or filename.rfind('.') == 0:
				ext = ''
			else:
				ext = filename[(filename.rfind('.') + 1):]
			if len(ext) > conf['max_ext_length']:
				ext = ''
			if ext not in self.code_analysis['extensions']:
				self.code_analysis['extensions'][ext] = {'files': 0, 'lines': 0}
			self.code_analysis['extensions'][ext]['files'] += 1
			
			# Add all blobs to SLOC analysis list (regardless of cache status)
			all_blobs_for_sloc.append((ext, blob_id))
			
			#if cache empty then add ext and blob id to list of new blob's
			#otherwise try to read needed info from cache
			if 'lines_in_blob' not in self.cache:
				blobs_to_read.append((ext,blob_id))
				continue
			if blob_id in self.cache['lines_in_blob']:
				self.code_analysis['extensions'][ext]['lines'] += self.cache['lines_in_blob'][blob_id]
			else:
				blobs_to_read.append((ext,blob_id))

		#Get info abount line count for new blob's that wasn't found in cache
		if blobs_to_read:
			worker_count = min(len(blobs_to_read), conf['processes'])
			if conf['verbose']:
				print(f'Processing {len(blobs_to_read)} uncached blobs with {worker_count} workers')
			
			with Pool(processes=worker_count) as pool:
				ext_blob_linecount = pool.map(getnumoflinesinblob, blobs_to_read)
		else:
			ext_blob_linecount = []

		# Also get SLOC analysis for ALL blobs (not just uncached ones)
		if all_blobs_for_sloc:
			worker_count = min(len(all_blobs_for_sloc), conf['processes'])
			if conf['verbose']:
				print(f'Performing SLOC analysis on {len(all_blobs_for_sloc)} blobs with {worker_count} workers')
			
			with Pool(processes=worker_count) as pool:
				ext_blob_sloc = pool.map(analyzesloc, all_blobs_for_sloc)
		else:
			ext_blob_sloc = []

		#Update cache and write down info about number of number of lines
		for (ext, blob_id, linecount) in ext_blob_linecount:
			if 'lines_in_blob' not in self.cache:
				self.cache['lines_in_blob'] = {}
			self.cache['lines_in_blob'][blob_id] = linecount
			self.code_analysis['extensions'][ext]['lines'] += self.cache['lines_in_blob'][blob_id]

		# Update SLOC statistics
		for (ext, blob_id, total_lines, source_lines, comment_lines, blank_lines) in ext_blob_sloc:
			# Initialize extension SLOC tracking
			if ext not in self.code_analysis['sloc_by_extension']:
				self.code_analysis['sloc_by_extension'][ext] = {'source': 0, 'comments': 0, 'blank': 0, 'total': 0}
			
			# Update extension SLOC counts
			self.code_analysis['sloc_by_extension'][ext]['source'] += source_lines
			self.code_analysis['sloc_by_extension'][ext]['comments'] += comment_lines
			self.code_analysis['sloc_by_extension'][ext]['blank'] += blank_lines
			self.code_analysis['sloc_by_extension'][ext]['total'] += total_lines
			
			# Update global SLOC counts
			self.code_analysis['total_source_lines'] += source_lines
			self.code_analysis['total_comment_lines'] += comment_lines
			self.code_analysis['total_blank_lines'] += blank_lines
			


		# File revision counting
		print('Collecting file revision statistics...')
		first_parent_flag = get_first_parent_flag()
		revision_lines = getpipeoutput(['git log %s --name-only --pretty=format: %s' % (first_parent_flag, getlogrange('HEAD'))]).strip().split('\n')
		for line in revision_lines:
			line = line.strip()
			if len(line) > 0 and not line.startswith('commit'):
				# This is a filename
				filename = line.split('/')[-1]  # Get just the filename for extension check
				
				# Apply extension filtering
				if not should_include_file(filename):
					continue
				
				if line not in self.code_analysis['file_revisions']:
					self.code_analysis['file_revisions'][line] = 0
				self.code_analysis['file_revisions'][line] += 1
				
				# Track directory activity
				directory = os.path.dirname(line) if os.path.dirname(line) else '.'
				self.code_analysis['directory_revisions'][directory] += 1
				self.code_analysis['directories'][directory]['files'].add(line)

		# Directory activity analysis
		print('Collecting directory activity statistics...')
		first_parent_flag = get_first_parent_flag()
		numstat_lines = getpipeoutput(['git log %s --numstat --pretty=format:"%%at %%aN" %s' % (first_parent_flag, getlogrange('HEAD'))]).split('\n')
		current_author = None
		current_timestamp = None
		
		for line in numstat_lines:
			line = line.strip()
			if not line:
				continue
				
			# Check if this is a commit header line (timestamp + author)
			if line.count('\t') == 0 and ' ' in line:
				try:
					parts = line.split(' ', 1)
					current_timestamp = int(parts[0])
					current_author = parts[1]
					continue
				except (ValueError, IndexError):
					pass
			
			# Check if this is a numstat line (additions\tdeletions\tfilename)
			if line.count('\t') >= 2:
				parts = line.split('\t')
				if len(parts) >= 3:
					try:
						additions = int(parts[0]) if parts[0] != '-' else 0
						deletions = int(parts[1]) if parts[1] != '-' else 0
						filename = '\t'.join(parts[2:])  # Handle filenames with tabs
						
						# Apply extension filtering
						file_basename = filename.split('/')[-1]
						if not should_include_file(file_basename):
							continue
						
						# Track directory activity
						directory = os.path.dirname(filename) if os.path.dirname(filename) else '.'
						self.code_analysis['directories'][directory]['commits'] += 1  # Will be deduplicated later
						self.code_analysis['directories'][directory]['lines_added'] += additions
						self.code_analysis['directories'][directory]['lines_removed'] += deletions
						self.code_analysis['directories'][directory]['files'].add(filename)
					except ValueError:
						pass

		# line statistics
		# outputs:
		#  N files changed, N insertions (+), N deletions(-)
		# <stamp> <author>
		self.temporal_data['changes_by_date'] = {} # stamp -> { files, ins, del }
		# computation of lines of code by date is better done
		# on a linear history.
		extra = ''
		if conf['linear_linestats']:
			extra = '--first-parent -m'
		
		# Add --first-parent if scanning only default branch
		first_parent_flag = get_first_parent_flag()
		if first_parent_flag and not extra:
			extra = first_parent_flag
		elif first_parent_flag and extra:
			extra = f'{first_parent_flag} {extra}'
		
		lines = getpipeoutput(['git log --shortstat %s --pretty=format:"%%at %%aN" %s' % (extra, getlogrange('HEAD'))]).split('\n')
		lines.reverse()
		files = 0; inserted = 0; deleted = 0; total_lines = 0
		author = None
		for line in lines:
			if len(line) == 0:
				continue

			# <stamp> <author>
			if re.search('files? changed', line) == None:
				pos = line.find(' ')
				if pos != -1:
					try:
						(stamp, author) = (int(line[:pos]), line[pos+1:])
						self.temporal_data['changes_by_date'][stamp] = { 'files': files, 'ins': inserted, 'del': deleted, 'lines': total_lines }
						
						# Track pace of changes (total line changes)
						self.temporal_data['pace_of_changes'][stamp] = inserted + deleted

						date = datetime.datetime.fromtimestamp(stamp)
						
						# Track pace of changes by month and year
						yymm = date.strftime('%Y-%m')
						yy = date.year
						self.temporal_data['pace_of_changes_by_month'][yymm] += inserted + deleted
						self.temporal_data['pace_of_changes_by_year'][yy] += inserted + deleted
						
						# Track last 30 days activity
						import time as time_mod
						now = time_mod.time()
						if now - stamp <= 30 * 24 * 3600:  # 30 days in seconds
							self.recent_activity['last_30_days_commits'] += 1
							self.recent_activity['last_30_days_lines_added'] += inserted
							self.recent_activity['last_30_days_lines_removed'] += deleted
						
						# Track last 12 months activity
						if now - stamp <= 365 * 24 * 3600:  # 12 months in seconds
							yymm = date.strftime('%Y-%m')
							self.recent_activity['last_12_months_commits'][yymm] += 1
							self.recent_activity['last_12_months_lines_added'][yymm] += inserted
							self.recent_activity['last_12_months_lines_removed'][yymm] += deleted
						
						yymm = date.strftime('%Y-%m')
						self.temporal_data['lines_added_by_month'][yymm] += inserted
						self.temporal_data['lines_removed_by_month'][yymm] += deleted

						yy = date.year
						self.temporal_data['lines_added_by_year'][yy] += inserted
						self.temporal_data['lines_removed_by_year'][yy] += deleted

						files, inserted, deleted = 0, 0, 0
					except ValueError:
						print('Warning: unexpected line "%s"' % line)
				else:
					print('Warning: unexpected line "%s"' % line)
			else:
				numbers = getstatsummarycounts(line)

				if len(numbers) == 3:
					(files, inserted, deleted) = list(map(lambda el : int(el), numbers))
					total_lines += inserted
					total_lines -= deleted
					self.repository_stats['total_lines_added'] += inserted
					self.repository_stats['total_lines_removed'] += deleted

				else:
					print('Warning: failed to handle line "%s"' % line)
					(files, inserted, deleted) = (0, 0, 0)
				#self.changes_by_date[stamp] = { 'files': files, 'ins': inserted, 'del': deleted }
		self.repository_stats['total_lines'] += total_lines

		# Per-author statistics

		# defined for stamp, author only if author commited at this timestamp.
		self.changes_by_date_by_author = {} # stamp -> author -> lines_added

		# Similar to the above, but add --first-parent if configured to scan default branch only
		# When scanning default branch only, we only want commits from the main line
		first_parent_flag = get_first_parent_flag()
		lines = getpipeoutput(['git log %s --shortstat --date-order --pretty=format:"%%at %%aN" %s' % (first_parent_flag, getlogrange('HEAD'))]).split('\n')
		lines.reverse()
		files = 0; inserted = 0; deleted = 0
		author = None
		stamp = 0
		for line in lines:
			if len(line) == 0:
				continue

			# <stamp> <author>
			if re.search('files? changed', line) == None:
				pos = line.find(' ')
				if pos != -1:
					try:
						oldstamp = stamp
						(stamp, author) = (int(line[:pos]), line[pos+1:])
						if oldstamp > stamp:
							# clock skew, keep old timestamp to avoid having ugly graph
							stamp = oldstamp
						if author not in self.authors:
							self.authors[author] = { 'lines_added' : 0, 'lines_removed' : 0, 'commits' : 0}
						self.authors[author]['commits'] += 1
						self.authors[author]['lines_added'] += inserted
						self.authors[author]['lines_removed'] += deleted
						if stamp not in self.changes_by_date_by_author:
							self.changes_by_date_by_author[stamp] = {}
						if author not in self.changes_by_date_by_author[stamp]:
							self.changes_by_date_by_author[stamp][author] = {}
						self.changes_by_date_by_author[stamp][author]['lines_added'] = self.authors[author]['lines_added']
						self.changes_by_date_by_author[stamp][author]['commits'] = self.authors[author]['commits']
						
						# Track author data by year
						date = datetime.datetime.fromtimestamp(stamp)
						year = date.year
						self.temporal_data['lines_added_by_author_by_year'][year][author] += inserted
						self.temporal_data['commits_by_author_by_year'][year][author] += 1
						files, inserted, deleted = 0, 0, 0
					except ValueError:
						print('Warning: unexpected line "%s"' % line)
				else:
					print('Warning: unexpected line "%s"' % line)
			else:
				numbers = getstatsummarycounts(line);

				if len(numbers) == 3:
					(files, inserted, deleted) = list(map(lambda el : int(el), numbers))
				else:
					print('Warning: failed to handle line "%s"' % line)
					(files, inserted, deleted) = (0, 0, 0)
		
		# Branch analysis - collect unmerged branches and per-branch statistics
		if conf['verbose']:
			print('Analyzing branches and detecting unmerged branches...')
		self._analyzeBranches()
		
		# Calculate repository size (this is slow as noted in TODO)
		if conf['verbose']:
			print('Calculating repository size...')
		try:
			# Get .git directory size
			git_dir_size = getpipeoutput(['du -sm .git']).split()[0]
			self.repository_size_mb = float(git_dir_size)
			if conf['verbose']:
				print(f'Repository size: {self.repository_size_mb:.1f} MB')
		except (ValueError, IndexError):
			print('Warning: Could not calculate repository size')
			self.repository_size_mb = 0.0
		
		# Perform advanced team analysis
		self._analyzeTeamCollaboration()
		self._analyzeCommitPatterns()
		self._analyzeWorkingPatterns()
		self._analyzeImpactAndQuality()
		self._calculateTeamPerformanceMetrics()
	
	def _detectMainBranch(self):
		"""Detect the main branch (master, main, develop, etc.)"""
		# Try common main branch names in order of preference
		main_branch_candidates = ['master', 'main', 'develop', 'development']
		
		# Get all local branches
		branches_output = getpipeoutput(['git branch'])
		local_branches = [line.strip().lstrip('* ') for line in branches_output.split('\n') if line.strip()]
		
		# Check if any of the common main branches exist
		for candidate in main_branch_candidates:
			if candidate in local_branches:
				self.main_branch = candidate
				return candidate
		
		# If none found, use the first branch or fall back to 'master'
		if local_branches:
			self.main_branch = local_branches[0]
			return local_branches[0]
		
		# Fall back to master
		self.main_branch = 'master'
		return 'master'
	
	def _analyzeBranches(self):
		"""Analyze all branches and detect unmerged ones"""
		try:
			# Detect main branch
			main_branch = self._detectMainBranch()
			if conf['verbose']:
				print(f'Detected main branch: {main_branch}')
			
			# Get all local branches
			branches_output = getpipeoutput(['git branch'])
			all_branches = [line.strip().lstrip('* ') for line in branches_output.split('\n') if line.strip()]
			
			# Get unmerged branches (branches not merged into main)
			try:
				unmerged_output = getpipeoutput([f'git branch --no-merged {main_branch}'])
				self.unmerged_branches = [line.strip().lstrip('* ') for line in unmerged_output.split('\n') 
										if line.strip() and not line.strip().startswith('*')]
			except:
				# If main branch doesn't exist or command fails, assume all branches are unmerged
				self.unmerged_branches = [b for b in all_branches if b != main_branch]
			
			if conf['verbose']:
				print(f'Found {len(self.unmerged_branches)} unmerged branches: {", ".join(self.unmerged_branches)}')
			
			# Analyze each branch
			for branch in all_branches:
				if conf['verbose']:
					print(f'Analyzing branch: {branch}')
				self._analyzeBranch(branch, main_branch)
				
		except Exception as e:
			if conf['verbose'] or conf['debug']:
				print(f'Warning: Branch analysis failed: {e}')
			# Initialize empty structures if analysis fails
			self.unmerged_branches = []
			self.branches = {}
	
	def _analyzeBranch(self, branch_name, main_branch):
		"""Analyze a single branch for commits, authors, and line changes"""
		try:
			# Initialize branch data
			self.branches[branch_name] = {
				'commits': 0,
				'lines_added': 0,
				'lines_removed': 0,
				'authors': {},
				'is_merged': branch_name not in self.unmerged_branches,
				'merge_base': '',
				'unique_commits': []
			}
			
			# Get merge base with main branch
			try:
				merge_base = getpipeoutput([f'git merge-base {branch_name} {main_branch}']).strip()
				self.branches[branch_name]['merge_base'] = merge_base
			except:
				self.branches[branch_name]['merge_base'] = ''
			
			# Get commits unique to this branch (not in main branch)
			if branch_name != main_branch:
				try:
					# Get commits that are in branch but not in main
					unique_commits_output = getpipeoutput([f'git rev-list {branch_name} ^{main_branch}'])
					unique_commits = [line.strip() for line in unique_commits_output.split('\n') if line.strip()]
					self.branches[branch_name]['unique_commits'] = unique_commits
					
					# Analyze each unique commit
					for commit in unique_commits:
						self._analyzeBranchCommit(branch_name, commit)
						
				except:
					# If command fails, analyze all commits in the branch
					try:
						all_commits_output = getpipeoutput([f'git rev-list {branch_name}'])
						all_commits = [line.strip() for line in all_commits_output.split('\n') if line.strip()]
						self.branches[branch_name]['unique_commits'] = all_commits[:50]  # Limit to avoid too much data
						
						for commit in all_commits[:50]:
							self._analyzeBranchCommit(branch_name, commit)
					except:
						pass
			else:
				# For main branch, count all commits
				try:
					all_commits_output = getpipeoutput([f'git rev-list {branch_name}'])
					all_commits = [line.strip() for line in all_commits_output.split('\n') if line.strip()]
					self.branches[branch_name]['commits'] = len(all_commits)
					self.branches[branch_name]['unique_commits'] = all_commits[:100]  # Limit for performance
				except:
					pass
					
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Failed to analyze branch {branch_name}: {e}')
	
	def _analyzeBranchCommit(self, branch_name, commit_hash):
		"""Analyze a single commit for branch statistics"""
		try:
			# Get commit author and timestamp
			commit_info = getpipeoutput([f'git log -1 --pretty=format:"%aN %at" {commit_hash}'])
			if not commit_info:
				return
				
			parts = commit_info.rsplit(' ', 1)
			if len(parts) != 2:
				return
				
			author = parts[0]
			try:
				timestamp = int(parts[1])
			except ValueError:
				return
			
			# Update branch commit count
			self.branches[branch_name]['commits'] += 1
			
			# Update author statistics for this branch
			if author not in self.branches[branch_name]['authors']:
				self.branches[branch_name]['authors'][author] = {
					'commits': 0,
					'lines_added': 0,
					'lines_removed': 0
				}
			self.branches[branch_name]['authors'][author]['commits'] += 1
			
			# Get line changes for this commit
			try:
				numstat_output = getpipeoutput([f'git show --numstat --format="" {commit_hash}'])
				for line in numstat_output.split('\n'):
					if line.strip() and '\t' in line:
						parts = line.split('\t')
						if len(parts) >= 2:
							try:
								additions = int(parts[0]) if parts[0] != '-' else 0
								deletions = int(parts[1]) if parts[1] != '-' else 0
								
								# Update branch statistics
								self.branches[branch_name]['lines_added'] += additions
								self.branches[branch_name]['lines_removed'] += deletions
								
								# Update author statistics for this branch
								self.branches[branch_name]['authors'][author]['lines_added'] += additions
								self.branches[branch_name]['authors'][author]['lines_removed'] += deletions
								
							except ValueError:
								pass
			except:
				pass
				
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Failed to analyze commit {commit_hash}: {e}')
	
	def _analyzeTeamCollaboration(self):
		"""Analyze how team members collaborate on files and projects"""
		if conf['verbose']:
			print('Analyzing team collaboration patterns...')
		
		try:
			# Get commit details with files changed
			log_range = getlogrange('HEAD')
			first_parent_flag = get_first_parent_flag()
			commit_data = getpipeoutput(['git log %s --name-only --pretty=format:"COMMIT:%%H:%%aN:%%at" %s' % (first_parent_flag, log_range)]).split('\n')
			
			current_commit = None
			current_author = None
			current_timestamp = None
			
			for line in commit_data:
				line = line.strip()
				if line.startswith('COMMIT:'):
					# Parse commit header: COMMIT:hash:author:timestamp
					parts = line.split(':', 3)
					if len(parts) >= 4:
						current_commit = parts[1]
						current_author = parts[2]
						try:
							current_timestamp = int(parts[3])
						except ValueError:
							current_timestamp = None
				elif line and current_author and not line.startswith('COMMIT:'):
					# This is a filename
					filename = line
					
					# Apply extension filtering
					file_basename = filename.split('/')[-1]
					if not should_include_file(file_basename):
						continue
					
					# Initialize author collaboration data
					if current_author not in self.author_collaboration:
						self.author_collaboration[current_author] = {
							'worked_with': defaultdict(lambda: defaultdict(int)),
							'file_ownership': defaultdict(int)
						}
					
					# Track file ownership
					self.author_collaboration[current_author]['file_ownership'][filename] += 1
					
					# Track who else worked on this file
					file_history = getpipeoutput([f'git log --pretty=format:"%aN" -- "{filename}"']).split('\n')
					unique_authors = set(file_history) - {current_author}
					
					for other_author in unique_authors:
						if other_author.strip():
							self.author_collaboration[current_author]['worked_with'][other_author][filename] += 1
							
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Team collaboration analysis failed: {e}')
		
		# Enhanced Metrics Collection - College Project Implementation
		print('Calculating enhanced metrics...')
		
		# Analyze current files for enhanced metrics
		try:
			# Get list of all tracked files
			files_output = getpipeoutput(['git ls-files'])
			if files_output.strip():
				tracked_files = files_output.strip().split('\n')
				
				# Analyze each file for documentation and complexity
				for filepath in tracked_files[:100]:  # Limit to first 100 files for performance
					if os.path.exists(filepath):
						self.update_enhanced_metrics(filepath)
				
				# Check for README and documentation files
				readme_files = [f for f in tracked_files if 'readme' in f.lower() or 'doc' in f.lower()]
				self.documentation_metrics['readme_sections'] = len(readme_files) * 5  # Basic scoring
				
				# Count documentation files
				doc_extensions = ['.md', '.txt', '.rst', '.doc']
				self.documentation_metrics['total_documentation_files'] = sum(
					1 for f in tracked_files 
					if any(f.lower().endswith(ext) for ext in doc_extensions)
				)
		
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Enhanced file analysis failed: {e}')
		
		# Calculate comprehensive software metrics
		try:
			if conf['verbose']:
				print('Calculating comprehensive software metrics...')
			self.calculate_comprehensive_metrics()
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Comprehensive metrics calculation failed: {e}')
		

	
	def _analyzeCommitPatterns(self):
		"""Analyze commit patterns to identify commit behavior (small vs large commits, frequency, etc.)"""
		if conf['verbose']:
			print('Analyzing commit patterns...')
		
		try:
			# Get detailed commit information using a simpler, more reliable approach
			log_range = getlogrange('HEAD')
			first_parent_flag = get_first_parent_flag()
			commit_lines = getpipeoutput(['git log %s --shortstat --pretty=format:"COMMIT:%%H:%%aN:%%at:%%s" %s' % (first_parent_flag, log_range)]).split('\n')
			
			current_author = None
			current_timestamp = None
			current_message = None
			author_commits = defaultdict(list)
			
			for line in commit_lines:
				line = line.strip()
				if line.startswith('COMMIT:'):
					# Parse: COMMIT:hash:author:timestamp:subject
					parts = line.split(':', 4)
					if len(parts) >= 5:
						current_author = parts[2]
						try:
							current_timestamp = int(parts[3])
							current_message = parts[4] if len(parts) > 4 else ""
						except (ValueError, IndexError):
							current_timestamp = None
							current_message = ""
				elif line and current_author and re.search(r'files? changed', line):
					# Parse shortstat line: "1 file changed, 269 insertions(+), 91 deletions(-)"
					numbers = re.findall(r'\d+', line)
					if len(numbers) >= 1:
						files_changed = int(numbers[0])
						insertions = int(numbers[1]) if len(numbers) > 1 else 0
						deletions = int(numbers[2]) if len(numbers) > 2 else 0
						total_changes = insertions + deletions
						
						commit_info = {
							'timestamp': current_timestamp,
							'files_changed': files_changed,
							'lines_changed': total_changes,
							'insertions': insertions,
							'deletions': deletions,
							'message': current_message if current_message else ""
						}
						author_commits[current_author].append(commit_info)
			
			# Analyze patterns for each author
			for author, commits in author_commits.items():
				if not commits:
					continue
				
				total_commits = len(commits)
				total_lines = sum(c['lines_changed'] for c in commits)
				avg_commit_size = total_lines / total_commits if total_commits else 0
				
				# Categorize commits by size
				small_commits = sum(1 for c in commits if c['lines_changed'] < 10)
				medium_commits = sum(1 for c in commits if 10 <= c['lines_changed'] < 100)
				large_commits = sum(1 for c in commits if c['lines_changed'] >= 100)
				
				# Calculate commit frequency (commits per day)
				if commits:
					timestamps = [c['timestamp'] for c in commits if c['timestamp']]
					if len(timestamps) > 1:
						time_span = max(timestamps) - min(timestamps)
						days_active = time_span / (24 * 3600) if time_span > 0 else 1
						commit_frequency = total_commits / days_active
					else:
						commit_frequency = total_commits
				else:
					commit_frequency = 0
				
				# Analyze commit messages for patterns
				bug_related = sum(1 for c in commits if any(keyword in c['message'].lower() 
					for keyword in ['fix', 'bug', 'error', 'issue', 'patch', 'repair']))
				feature_related = sum(1 for c in commits if any(keyword in c['message'].lower() 
					for keyword in ['add', 'new', 'feature', 'implement', 'create']))
				refactor_related = sum(1 for c in commits if any(keyword in c['message'].lower() 
					for keyword in ['refactor', 'cleanup', 'reorganize', 'restructure', 'optimize']))
				
				self.team_analysis['commit_patterns'][author] = {
					'total_commits': total_commits,
					'avg_commit_size': avg_commit_size,
					'small_commits': small_commits,
					'medium_commits': medium_commits,
					'large_commits': large_commits,
					'commit_frequency': commit_frequency,
					'bug_related_commits': bug_related,
					'feature_related_commits': feature_related,
					'refactor_related_commits': refactor_related,
					'avg_files_per_commit': sum(c['files_changed'] for c in commits) / total_commits if total_commits else 0
				}
				
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Commit pattern analysis failed: {e}')
	
	def _analyzeWorkingPatterns(self):
		"""Analyze when authors typically work (time of day, day of week, timezone patterns)"""
		if conf['verbose']:
			print('Analyzing working time patterns...')
		
		try:
			# Get commit timestamps with timezone info
			log_range = getlogrange('HEAD')
			first_parent_flag = get_first_parent_flag()
			commit_lines = getpipeoutput(['git log %s --pretty=format:"%%aN|%%at|%%ai|%%s" %s' % (first_parent_flag, log_range)]).split('\n')
			
			for line in commit_lines:
				if not line.strip():
					continue
				
				parts = line.split('|', 3)
				if len(parts) < 3:
					continue
				
				author = parts[0]
				try:
					timestamp = int(parts[1])
					date_str = parts[2]  # ISO format with timezone
					message = parts[3] if len(parts) > 3 else ""
				except (ValueError, IndexError):
					continue
				
				# Parse date and time information
				date = datetime.datetime.fromtimestamp(timestamp)
				hour = date.hour
				day_of_week = date.weekday()  # Monday = 0, Sunday = 6
				
				# Initialize author working patterns
				if author not in self.team_analysis['working_patterns']:
					self.team_analysis['working_patterns'][author] = {
						'night_commits': 0,      # 22:00 - 06:00
						'weekend_commits': 0,    # Saturday, Sunday
						'peak_hours': defaultdict(int),
						'peak_days': defaultdict(int),
						'timezone_pattern': defaultdict(int),
						'early_bird': 0,         # 05:00 - 09:00
						'workday': 0,           # 09:00 - 17:00
						'evening': 0,           # 17:00 - 22:00
						'total_commits': 0
					}
				
				self.team_analysis['working_patterns'][author]['total_commits'] += 1
				self.team_analysis['working_patterns'][author]['peak_hours'][hour] += 1
				self.team_analysis['working_patterns'][author]['peak_days'][day_of_week] += 1
				
				# Extract timezone from date string
				if '+' in date_str or '-' in date_str:
					tz_part = date_str.split()[-1]
					self.team_analysis['working_patterns'][author]['timezone_pattern'][tz_part] += 1
				
				# Categorize by time of day
				if 22 <= hour or hour < 6:
					self.team_analysis['working_patterns'][author]['night_commits'] += 1
				elif 5 <= hour < 9:
					self.team_analysis['working_patterns'][author]['early_bird'] += 1
				elif 9 <= hour < 17:
					self.team_analysis['working_patterns'][author]['workday'] += 1
				elif 17 <= hour < 22:
					self.team_analysis['working_patterns'][author]['evening'] += 1
				
				# Weekend commits (Saturday = 5, Sunday = 6)
				if day_of_week >= 5:
					self.team_analysis['working_patterns'][author]['weekend_commits'] += 1
				
				# Classify commit types
				if any(keyword in message.lower() for keyword in ['fix', 'bug', 'error', 'patch']):
					if author not in self.commit_categories['bug_commits']:
						self.commit_categories['bug_commits'].append({'author': author, 'timestamp': timestamp, 'message': message})
				elif any(keyword in message.lower() for keyword in ['refactor', 'cleanup', 'optimize']):
					self.refactoring_commits.append({'author': author, 'timestamp': timestamp, 'message': message})
				elif any(keyword in message.lower() for keyword in ['add', 'new', 'feature', 'implement']):
					self.feature_commits.append({'author': author, 'timestamp': timestamp, 'message': message})
			
			# Calculate active periods for each author
			for author in self.authors:
				if 'active_days' in self.authors[author]:
					active_days = self.authors[author]['active_days']
					sorted_days = sorted(active_days)
					
					if len(sorted_days) > 1:
						# Calculate gaps between active days
						gaps = []
						for i in range(1, len(sorted_days)):
							prev_date = datetime.datetime.strptime(sorted_days[i-1], '%Y-%m-%d')
							curr_date = datetime.datetime.strptime(sorted_days[i], '%Y-%m-%d')
							gap = (curr_date - prev_date).days
							gaps.append(gap)
						
						avg_gap = sum(gaps) / len(gaps) if gaps else 0
						
						# Find longest streak
						longest_streak = 1
						current_streak = 1
						for gap in gaps:
							if gap == 1:
								current_streak += 1
								longest_streak = max(longest_streak, current_streak)
							else:
								current_streak = 1
					else:
						avg_gap = 0
						longest_streak = 1
					
					self.author_active_periods[author] = {
						'active_days_count': len(active_days),
						'longest_streak': longest_streak,
						'avg_gap': avg_gap
					}
				
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Working pattern analysis failed: {e}')
	
	def _analyzeImpactAndQuality(self):
		"""Analyze the impact of changes and identify critical files and potential quality issues"""
		if conf['verbose']:
			print('Analyzing impact and quality indicators...')
		
		try:
			# Identify critical files based on common patterns
			all_files = getpipeoutput(['git ls-tree -r --name-only %s' % getcommitrange('HEAD', end_only=True)]).split('\n')
			
			for filepath in all_files:
				if not filepath.strip():
					continue
				
				filename = os.path.basename(filepath)
				filename_lower = filename.lower()
				
				# Apply extension filtering
				if not should_include_file(filename):
					continue
				
				# Mark files as critical based on allowed extensions
				critical_patterns = {
					'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx', '.m', '.mm',
					'.swift', '.cu', '.cuh', '.cl', '.java', '.scala', '.kt', '.go', '.rs',
					'.py', '.pyi', '.pyx', '.pxd', '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
					'.d.ts', '.lua', '.proto', '.thrift', '.asm', '.s', '.S', '.R', '.r'
				}
				
				# Check if file has a critical extension
				file_extension = None
				if '.' in filename:
					file_extension = '.' + filename.split('.')[-1].lower()
					# Handle special cases like .d.ts
					if filename.lower().endswith('.d.ts'):
						file_extension = '.d.ts'
				
				if file_extension and file_extension in critical_patterns:
					self.critical_files.add(filepath)
				
				# Files in root directory are often critical
				if '/' not in filepath:
					self.critical_files.add(filepath)
			
			# Analyze file impact scores based on change frequency and author diversity
			file_authors = defaultdict(set)
			file_change_count = defaultdict(int)
			
			# Get file change history
			log_range = getlogrange('HEAD')
			first_parent_flag = get_first_parent_flag()
			log_lines = getpipeoutput(['git log %s --name-only --pretty=format:"AUTHOR:%%aN" %s' % (first_parent_flag, log_range)]).split('\n')
			current_author = None
			
			for line in log_lines:
				line = line.strip()
				if line.startswith('AUTHOR:'):
					current_author = line.replace('AUTHOR:', '')
				elif line and current_author and not line.startswith('AUTHOR:'):
					filename = line
					
					# Apply extension filtering
					file_basename = filename.split('/')[-1]
					if not should_include_file(file_basename):
						continue
					
					file_authors[filename].add(current_author)
					file_change_count[filename] += 1
			
			# Calculate impact scores
			for filename in file_change_count:
				change_count = file_change_count[filename]
				author_count = len(file_authors[filename])
				
				# Impact score based on change frequency and author diversity
				base_score = min(change_count * 10, 100)  # Cap at 100
				diversity_bonus = min(author_count * 5, 25)  # Bonus for multiple authors
				critical_bonus = 50 if filename in self.critical_files else 0
				
				impact_score = base_score + diversity_bonus + critical_bonus
				self.file_impact_scores[filename] = impact_score
			
			# Analyze author impact
			for author in self.authors:
				critical_files_touched = []
				total_impact_score = 0
				
				# Check which critical files this author touched
				for filename in self.critical_files:
					if author in file_authors.get(filename, set()):
						critical_files_touched.append(filename)
						total_impact_score += self.file_impact_scores.get(filename, 0)
				
				# Calculate maintenance work ratio (neutral term for bug fixes)
				author_commits = self.team_analysis['commit_patterns'].get(author, {})
				maintenance_commits = author_commits.get('bug_related_commits', 0)
				total_commits = author_commits.get('total_commits', 1)
				maintenance_ratio = maintenance_commits / total_commits if total_commits > 0 else 0
				
				# Maintenance work percentage (neutral metric, not "bug potential")
				maintenance_percentage = min(maintenance_ratio * 100, 100)
				
				self.impact_analysis[author] = {
					'critical_files': critical_files_touched,
					'impact_score': total_impact_score,
					'maintenance_percentage': maintenance_percentage,
					'high_impact_files': [f for f in file_authors if author in file_authors[f] and self.file_impact_scores.get(f, 0) > 50]
				}
				
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Impact analysis failed: {e}')
	
	def _calculateTeamPerformanceMetrics(self):
		"""Calculate comprehensive team performance metrics"""
		if conf['verbose']:
			print('Calculating team performance metrics...')
		
		try:
			total_commits = self.getTotalCommits()
			total_lines_changed = self.repository_stats['total_lines_added'] + self.repository_stats['total_lines_removed']
			
			for author in self.authors:
				author_info = self.authors[author]
				commit_patterns = self.team_analysis['commit_patterns'].get(author, {})
				working_patterns = self.team_analysis['working_patterns'].get(author, {})
				impact_info = self.impact_analysis.get(author, {})
				
				# Activity Score (based on commit patterns and code modification metrics)
				avg_commit_size = commit_patterns.get('avg_commit_size', 0)
				total_author_commits = author_info.get('commits', 0)
				
				# Commit size distribution scoring (no penalties, just measurement)
				if 20 <= avg_commit_size <= 50:
					size_score = 100  # Moderate-sized commits
				elif avg_commit_size < 20:
					size_score = max(0, avg_commit_size * 5)  # Small incremental commits
				else:
					size_score = max(0, 100 - (avg_commit_size - 50) * 2)  # Larger commits
				
				# Work type distribution (all types valued equally)
				maintenance_commits = commit_patterns.get('bug_related_commits', 0)
				feature_commits = commit_patterns.get('feature_related_commits', 0)
				refactor_commits = commit_patterns.get('refactor_related_commits', 0)
				
				work_diversity_score = 0
				if total_author_commits > 0:
					feature_ratio = feature_commits / total_author_commits
					refactor_ratio = refactor_commits / total_author_commits
					maintenance_ratio = maintenance_commits / total_author_commits
					
					# All work types contribute positively (no penalties for maintenance)
					work_diversity_score = (feature_ratio * 35 + refactor_ratio * 35 + maintenance_ratio * 30) * 100
					work_diversity_score = max(0, min(100, work_diversity_score))
				
				activity_score = (size_score * 0.6 + work_diversity_score * 0.4)
				
				# Consistency Score (based on commit frequency and working patterns)
				commit_frequency = commit_patterns.get('commit_frequency', 0)
				active_periods = self.author_active_periods.get(author, {})
				longest_streak = active_periods.get('longest_streak', 1)
				avg_gap = active_periods.get('avg_gap', 30)
				
				# Consistency based on regular commits and sustained activity
				frequency_score = min(commit_frequency * 20, 100)  # Up to 5 commits per day = max score
				streak_score = min(longest_streak * 5, 100)  # Longer streaks = better consistency
				gap_score = max(0, 100 - avg_gap * 3)  # Smaller gaps = better consistency
				
				consistency_score = (frequency_score * 0.4 + streak_score * 0.3 + gap_score * 0.3)
				
				# Collaboration Score (based on code interaction patterns and shared file work)
				impact_score = impact_info.get('impact_score', 0)
				critical_files_count = len(impact_info.get('critical_files', []))
				
				# Multi-author file collaboration based on working with others
				collaboration_data = self.author_collaboration.get(author, {})
				worked_with_count = len(collaboration_data.get('worked_with', {}))
				
				# Normalize collaboration metrics (objective measurement)
				impact_component = min(impact_score / 10, 100)  # Scale impact score
				multi_author_component = min(worked_with_count * 10, 100)  # Max score at 10 collaborators
				shared_files_component = min(critical_files_count * 20, 100)  # Max score at 5 critical files
				
				collaboration_score = (impact_component * 0.4 + multi_author_component * 0.3 + shared_files_component * 0.3)
				
				# Overall contribution percentage
				author_commits = author_info.get('commits', 0)
				contribution_percentage = (author_commits / total_commits * 100) if total_commits > 0 else 0
				
				# Store performance metrics
				self.team_performance[author] = {
					'activity_score': activity_score,
					'consistency': consistency_score,
					'collaboration_score': collaboration_score,
					'contribution_percentage': contribution_percentage,
					'overall_score': (activity_score * 0.4 + consistency_score * 0.3 + collaboration_score * 0.3),
					'commit_analysis': {
						'avg_commit_size': avg_commit_size,
						'small_commits_ratio': commit_patterns.get('small_commits', 0) / total_author_commits if total_author_commits > 0 else 0,
						'large_commits_ratio': commit_patterns.get('large_commits', 0) / total_author_commits if total_author_commits > 0 else 0,
						'maintenance_ratio': maintenance_commits / total_author_commits if total_author_commits > 0 else 0,
						'feature_ratio': feature_commits / total_author_commits if total_author_commits > 0 else 0
					}
				}
				
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Team performance calculation failed: {e}')
	
	def refine(self):
		# Calculate comprehensive metrics for all files
		print('Calculating comprehensive code metrics...')
		self._calculate_comprehensive_project_metrics(getattr(self, 'repository_path', None))
		

		
		# authors
		# name -> {place_by_commits, commits_frac, date_first, date_last, timedelta}
		self.authors_by_commits = getkeyssortedbyvaluekey(self.authors, 'commits')
		self.authors_by_commits.reverse() # most first
		for i, name in enumerate(self.authors_by_commits):
			self.authors[name]['place_by_commits'] = i + 1

		for name in list(self.authors.keys()):
			a = self.authors[name]
			a['commits_frac'] = (100 * float(a['commits'])) / self.getTotalCommits()
			date_first = datetime.datetime.fromtimestamp(a['first_commit_stamp'])
			date_last = datetime.datetime.fromtimestamp(a['last_commit_stamp'])
			delta = date_last - date_first
			a['date_first'] = date_first.strftime('%Y-%m-%d')
			a['date_last'] = date_last.strftime('%Y-%m-%d')
			a['timedelta'] = delta
			if 'lines_added' not in a: a['lines_added'] = 0
			if 'lines_removed' not in a: a['lines_removed'] = 0
	
	def getActiveDays(self):
		return self.active_days

	def getActivityByDayOfWeek(self):
		return self.activity_by_day_of_week

	def getActivityByHourOfDay(self):
		return self.activity_by_hour_of_day

	def getAuthorInfo(self, author):
		return self.authors[author]
	
	def getAuthors(self, limit = None):
		res = getkeyssortedbyvaluekey(self.authors, 'commits')
		res.reverse()
		return res[:limit]
	
	def getCommitDeltaDays(self):
		return (self.last_commit_stamp // 86400 - self.first_commit_stamp // 86400) + 1

	def getDomainInfo(self, domain):
		return self.domains[domain]

	def getDomains(self):
		return list(self.domains.keys())
	
	def getFirstCommitDate(self):
		return datetime.datetime.fromtimestamp(self.first_commit_stamp)
	
	def getLastCommitDate(self):
		return datetime.datetime.fromtimestamp(self.last_commit_stamp)
	
	def getTags(self):
		lines = getpipeoutput(['git show-ref --tags', 'cut -d/ -f3'])
		return lines.split('\n')
	
	def getTagDate(self, tag):
		return self.revToDate('tags/' + tag)
	
	def getTotalAuthors(self):
		return self.total_authors
	
	def getTotalCommits(self):
		return self.repository_stats['total_commits']

	def getTotalFiles(self):
		return self.repository_stats['total_files']
	
	def getTotalLOC(self):
		return self.repository_stats['total_lines']

	def getTotalSourceLines(self):
		return self.code_analysis['total_source_lines']
	
	def getTotalCommentLines(self):
		return self.total_comment_lines
	
	def getTotalBlankLines(self):
		return self.total_blank_lines
	
	def getSLOCByExtension(self):
		return self.sloc_by_extension
	
	def getLargestFiles(self, limit=10):
		"""Get the largest files by size."""
		sorted_files = sorted(self.file_sizes.items(), key=lambda x: x[1], reverse=True)
		return sorted_files[:limit]
	
	def getFilesWithMostRevisions(self, limit=10):
		"""Get files with most revisions (hotspots)."""
		sorted_files = sorted(self.file_revisions.items(), key=lambda x: x[1], reverse=True)
		return sorted_files[:limit]
	
	def getAverageFileSize(self):
		"""Get average file size in bytes."""
		if not self.file_sizes:
			return 0.0
		return sum(self.file_sizes.values()) / len(self.file_sizes)
	
	def getDirectoriesByActivity(self, limit=10):
		"""Get directories with most lines changed (added + removed)."""
		if not hasattr(self, 'directories'):
			return []
		directory_activity = []
		for directory, stats in self.directories.items():
			total_lines = stats['lines_added'] + stats['lines_removed']
			file_count = len(stats['files'])
			directory_activity.append((directory, total_lines, stats['lines_added'], stats['lines_removed'], file_count))
		return sorted(directory_activity, key=lambda x: x[1], reverse=True)[:limit]
	
	def getDirectoriesByRevisions(self, limit=10):
		"""Get directories with most file revisions."""
		if not hasattr(self, 'directory_revisions'):
			return []
		sorted_dirs = sorted(self.directory_revisions.items(), key=lambda x: x[1], reverse=True)
		return sorted_dirs[:limit]
	
	def getAverageRevisionsPerFile(self):
		"""Get average number of revisions per file."""
		if not self.file_revisions:
			return 0.0
		return sum(self.file_revisions.values()) / len(self.file_revisions)

	def getTotalSize(self):
		return self.total_size
	
	def getLast30DaysActivity(self):
		"""Get activity stats for last 30 days."""
		return {
			'commits': self.last_30_days_commits,
			'lines_added': self.last_30_days_lines_added,
			'lines_removed': self.last_30_days_lines_removed
		}
	
	def getLast12MonthsActivity(self):
		"""Get activity stats for last 12 months."""
		return {
			'commits': dict(self.last_12_months_commits),
			'lines_added': dict(self.last_12_months_lines_added),
			'lines_removed': dict(self.last_12_months_lines_removed)
		}
	
	def getPaceOfChanges(self):
		"""Get pace of changes (line changes over time)."""
		return self.pace_of_changes
	
	def getPaceOfChangesByMonth(self):
		"""Get pace of changes by month."""
		return dict(self.pace_of_changes_by_month)
	
	def getPaceOfChangesByYear(self):
		"""Get pace of changes by year."""
		return dict(self.pace_of_changes_by_year)
	
	def getPaceOfChangesByWeek(self):
		"""Get pace of changes aggregated by week."""
		weekly_data = {}
		for stamp, changes in self.pace_of_changes.items():
			# Get the date from timestamp
			date = datetime.datetime.fromtimestamp(stamp)
			# Get Monday of the week (start of week)
			monday = date - datetime.timedelta(days=date.weekday())
			week_key = monday.strftime('%Y-%m-%d')
			
			if week_key not in weekly_data:
				weekly_data[week_key] = 0
			weekly_data[week_key] += changes
		
		return weekly_data
	
	def getFilesByYear(self):
		"""Get file count by year."""
		return dict(self.files_by_year)
	
	def getLinesOfCodeByYear(self):
		"""Get lines of code by year."""
		return dict(self.lines_of_code_by_year)
	
	def getLinesAddedByAuthorByYear(self):
		"""Get lines added by author by year."""
		return dict(self.lines_added_by_author_by_year)
	
	def getCommitsByAuthorByYear(self):
		"""Get commits by author by year."""
		return dict(self.commits_by_author_by_year)
	
	def getRepositorySize(self):
		"""Get repository size in MB."""
		return getattr(self, 'repository_size_mb', 0.0)
	
	def getBranches(self):
		"""Get all branches with their statistics."""
		return self.branches
	
	def getUnmergedBranches(self):
		"""Get list of unmerged branch names."""
		return self.unmerged_branches
	
	def getMainBranch(self):
		"""Get the detected main branch name."""
		return getattr(self, 'main_branch', 'master')
	
	def getBranchInfo(self, branch_name):
		"""Get detailed information about a specific branch."""
		return self.branches.get(branch_name, {})
	
	def getBranchAuthors(self, branch_name):
		"""Get authors who contributed to a specific branch."""
		branch_info = self.branches.get(branch_name, {})
		return branch_info.get('authors', {})
	
	def getBranchesByCommits(self, limit=None):
		"""Get branches sorted by number of commits."""
		sorted_branches = sorted(self.branches.items(), 
								key=lambda x: x[1].get('commits', 0), 
								reverse=True)
		if limit:
			return sorted_branches[:limit]
		return sorted_branches
	
	def getBranchesByLinesChanged(self, limit=None):
		"""Get branches sorted by total lines changed."""
		sorted_branches = sorted(self.branches.items(), 
								key=lambda x: x[1].get('lines_added', 0) + x[1].get('lines_removed', 0), 
								reverse=True)
		if limit:
			return sorted_branches[:limit]
		return sorted_branches
	
	def getUnmergedBranchStats(self):
		"""Get statistics for unmerged branches only."""
		unmerged_stats = {}
		for branch_name in self.unmerged_branches:
			if branch_name in self.branches:
				unmerged_stats[branch_name] = self.branches[branch_name]
		return unmerged_stats
	
	# New methods for advanced team analysis
	def getCommitPatterns(self):
		"""Get commit patterns analysis for all authors."""
		return self.commit_patterns
	
	def getCommitPatternsForAuthor(self, author):
		"""Get commit patterns for a specific author."""
		return self.team_analysis['commit_patterns'].get(author, {})
	
	def getWorkingPatterns(self):
		"""Get working time patterns for all authors."""
		return self.working_patterns
	
	def getWorkingPatternsForAuthor(self, author):
		"""Get working patterns for a specific author."""
		return self.working_patterns.get(author, {})
	
	def getTeamCollaboration(self):
		"""Get team collaboration analysis."""
		return self.author_collaboration
	
	def getCollaborationForAuthor(self, author):
		"""Get collaboration data for a specific author."""
		return self.author_collaboration.get(author, {})
	
	def getImpactAnalysis(self):
		"""Get impact analysis for all authors."""
		return self.impact_analysis
	
	def getImpactAnalysisForAuthor(self, author):
		"""Get impact analysis for a specific author."""
		return self.impact_analysis.get(author, {})
	
	def getTeamPerformance(self):
		"""Get team performance metrics for all authors."""
		return self.team_performance
	
	def getTeamPerformanceForAuthor(self, author):
		"""Get team performance metrics for a specific author."""
		return self.team_performance.get(author, {})
	
	def getCriticalFiles(self):
		"""Get list of files identified as critical to the project."""
		return list(self.critical_files)
	
	def getFileImpactScores(self):
		"""Get impact scores for all files."""
		return dict(self.file_impact_scores)
	
	def getTopImpactFiles(self, limit=10):
		"""Get files with highest impact scores."""
		sorted_files = sorted(self.file_impact_scores.items(), key=lambda x: x[1], reverse=True)
		return sorted_files[:limit]
	
	def getBugRelatedCommits(self):
		"""Get commits that appear to be bug-related."""
		return self.potential_bug_commits
	
	def getRefactoringCommits(self):
		"""Get commits that appear to be refactoring."""
		return self.refactoring_commits
	
	def getFeatureCommits(self):
		"""Get commits that appear to add features."""
		return self.feature_commits
	
	def getAuthorActivePeriods(self):
		"""Get active periods analysis for all authors."""
		return self.author_active_periods
	
	def getAuthorsByContribution(self):
		"""Get authors sorted by contribution percentage."""
		performance_data = [(author, perf.get('contribution_percentage', 0)) 
						   for author, perf in self.team_performance.items()]
		return sorted(performance_data, key=lambda x: x[1], reverse=True)
	
	def getAuthorsByActivity(self):
		"""Get authors sorted by activity score."""
		performance_data = [(author, perf.get('activity_score', 0)) 
						   for author, perf in self.team_performance.items()]
		return sorted(performance_data, key=lambda x: x[1], reverse=True)
	
	def getAuthorsByRegularity(self):
		"""Get authors sorted by activity regularity score."""
		performance_data = [(author, perf.get('consistency', 0)) 
						   for author, perf in self.team_performance.items()]
		return sorted(performance_data, key=lambda x: x[1], reverse=True)
	
	def getAuthorsByCollaboration(self):
		"""Get authors sorted by collaboration score."""
		performance_data = [(author, perf.get('collaboration_score', 0)) 
						   for author, perf in self.team_performance.items()]
		return sorted(performance_data, key=lambda x: x[1], reverse=True)
	
	def getTeamWorkDistribution(self):
		"""Analyze work distribution across team members."""
		total_commits = self.getTotalCommits()
		total_lines = self.total_lines_added + self.total_lines_removed
		
		distribution = {}
		for author in self.authors:
			author_info = self.authors[author]
			author_commits = author_info.get('commits', 0)
			author_lines = author_info.get('lines_added', 0) + author_info.get('lines_removed', 0)
			
			distribution[author] = {
				'commit_percentage': (author_commits / total_commits * 100) if total_commits > 0 else 0,
				'lines_percentage': (author_lines / total_lines * 100) if total_lines > 0 else 0,
				'commits': author_commits,
				'lines_changed': author_lines
			}
		
		return distribution
	
	def getCommitSizeAnalysis(self):
		"""Get analysis of commit sizes across the team."""
		analysis = {
			'small_commits_authors': [],  # Authors with >50% small commits
			'large_commits_authors': [],  # Authors with >20% large commits
			'balanced_authors': [],       # Authors with balanced commit sizes
			'overall_stats': {
				'total_small': 0,
				'total_medium': 0,
				'total_large': 0
			}
		}
		
		for author, patterns in self.commit_patterns.items():
			total_commits = patterns.get('total_commits', 0)
			if total_commits == 0:
				continue
			
			small_ratio = patterns.get('small_commits', 0) / total_commits
			large_ratio = patterns.get('large_commits', 0) / total_commits
			
			analysis['overall_stats']['total_small'] += patterns.get('small_commits', 0)
			analysis['overall_stats']['total_medium'] += patterns.get('medium_commits', 0)
			analysis['overall_stats']['total_large'] += patterns.get('large_commits', 0)
			
			if small_ratio > 0.5:
				analysis['small_commits_authors'].append((author, small_ratio))
			elif large_ratio > 0.2:
				analysis['large_commits_authors'].append((author, large_ratio))
			else:
				analysis['balanced_authors'].append((author, small_ratio, large_ratio))
		
		return analysis
	
	def revToDate(self, rev):
		stamp = int(getpipeoutput(['git log --pretty=format:%%at "%s" -n 1' % rev]))
		return datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d')

class ReportCreator:
	"""Creates the actual report based on given data."""
	def __init__(self):
		pass
	
	def create(self, data, path):
		self.data = data
		self.path = path

def html_linkify(text):
	return text.lower().replace(' ', '_')

def html_header(level, text):
	name = html_linkify(text)
	return '\n<h%d id="%s"><a href="#%s">%s</a></h%d>\n\n' % (level, name, name, text, level)

class HTMLReportCreator(ReportCreator):
	def create(self, data, path):
		ReportCreator.create(self, data, path)
		self.title = data.projectname

		# Prepare safe local values to avoid division-by-zero and empty-collection errors
		total_commits = data.getTotalCommits()
		total_active_days = len(data.getActiveDays()) if hasattr(data, 'getActiveDays') else 0
		delta_days = data.getCommitDeltaDays() if hasattr(data, 'getCommitDeltaDays') else 0
		total_authors = data.getTotalAuthors()
		# busiest counters: use 1 as denominator if no activity recorded to avoid ZeroDivisionError
		hour_of_day_busiest = data.activity_by_hour_of_day_busiest if getattr(data, 'activity_by_hour_of_day_busiest', 0) > 0 else 1
		hour_of_week_busiest = data.activity_by_hour_of_week_busiest if getattr(data, 'activity_by_hour_of_week_busiest', 0) > 0 else 1
		# timezone max for coloring; default to 1 if empty
		max_commits_on_tz = max(data.commits_by_timezone.values()) if data.commits_by_timezone else 1

		# copy static files. Looks in the binary directory, ../share/gitstats and /usr/share/gitstats
		binarypath = os.path.dirname(os.path.abspath(__file__))
		secondarypath = os.path.join(binarypath, '..', 'share', 'gitstats')
		basedirs = [binarypath, secondarypath, '/usr/share/gitstats']
		for file in ('arrow-up.gif', 'arrow-down.gif', 'arrow-none.gif'):
			for base in basedirs:
				src = base + '/' + file
				if os.path.exists(src):
					shutil.copyfile(src, path + '/' + file)
					break
			else:
				print('Warning: "%s" not found, so not copied (searched: %s)' % (file, basedirs))

		# Create single combined HTML file
		f = open(path + "/index.html", 'w')
		format = '%Y-%m-%d %H:%M:%S'
		
		# Write HTML header with embedded CSS and JavaScript
		self.printCombinedHeader(f)

		f.write('<h1>GitStats - %s</h1>' % data.projectname)

		self.printCombinedNav(f)

		# General section
		f.write('<div id="general" class="section">')
		f.write(html_header(2, 'General'))

		f.write('<dl>')
		f.write('<dt>Project name</dt><dd>%s</dd>' % (data.projectname))
		f.write('<dt>Generated</dt><dd>%s (in %d seconds)</dd>' % (datetime.datetime.now().strftime(format), time.time() - data.getStampCreated()))
		f.write('<dt>Generator</dt><dd><a href="http://gitstats.sourceforge.net/">GitStats</a> (version %s), %s, %s</dd>' % (getversion(), getgitversion(), get_output_format()))
		f.write('<dt>Report Period</dt><dd>%s to %s</dd>' % (data.getFirstCommitDate().strftime(format), data.getLastCommitDate().strftime(format)))
		f.write('<dt>Age</dt><dd>%d days, %d active days (%3.2f%%)</dd>' % (data.getCommitDeltaDays(), total_active_days, (100.0 * total_active_days / data.getCommitDeltaDays()) if data.getCommitDeltaDays() else 0.0))
		f.write('<dt>Total Files</dt><dd>%s</dd>' % data.getTotalFiles())
		# Add file statistics
		try:
			avg_size = data.getAverageFileSize()
			f.write('<dt>Average File Size</dt><dd>%.2f bytes (%.1f KB)</dd>' % (avg_size, avg_size / 1024))
		except:
			pass
		try:
			avg_revisions = data.getAverageRevisionsPerFile()
			f.write('<dt>Average Revisions per File</dt><dd>%.2f</dd>' % avg_revisions)
		except:
			pass
		try:
			repo_size = data.getRepositorySize()
			if repo_size > 0:
				f.write('<dt>Repository Size</dt><dd>%.1f MB</dd>' % repo_size)
		except:
			pass
		f.write('<dt>Total Lines of Code</dt><dd>%s (%d added, %d removed)</dd>' % (data.getTotalLOC(), data.total_lines_added, data.total_lines_removed))
		f.write('<dt>Source Lines of Code</dt><dd>%s (%.1f%%)</dd>' % (data.getTotalSourceLines(), (100.0 * data.getTotalSourceLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0))
		f.write('<dt>Comment Lines</dt><dd>%s (%.1f%%)</dd>' % (data.getTotalCommentLines(), (100.0 * data.getTotalCommentLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0))
		f.write('<dt>Blank Lines</dt><dd>%s (%.1f%%)</dd>' % (data.getTotalBlankLines(), (100.0 * data.getTotalBlankLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0))
		avg_active = float(total_commits) / total_active_days if total_active_days else 0.0
		avg_all = float(total_commits) / delta_days if delta_days else 0.0
		f.write('<dt>Total Commits</dt><dd>%s (average %.1f commits per active day, %.1f per all days)</dd>' % (total_commits, avg_active, avg_all))
		avg_per_author = float(total_commits) / total_authors if total_authors else 0.0
		f.write('<dt>Authors</dt><dd>%s (average %.1f commits per author)</dd>' % (total_authors, avg_per_author))
		
		# Branch statistics
		branches = data.getBranches() if hasattr(data, 'getBranches') else {}
		unmerged_branches = data.getUnmergedBranches() if hasattr(data, 'getUnmergedBranches') else []
		main_branch = data.getMainBranch() if hasattr(data, 'getMainBranch') else 'master'
		
		if branches:
			f.write('<dt>Total Branches</dt><dd>%d</dd>' % len(branches))
			if unmerged_branches:
				f.write('<dt>Unmerged Branches</dt><dd>%d (%s)</dd>' % (len(unmerged_branches), ', '.join(unmerged_branches[:5]) + ('...' if len(unmerged_branches) > 5 else '')))
			f.write('<dt>Main Branch</dt><dd>%s</dd>' % main_branch)
		
		f.write('</dl>')
		f.write('</div>  <!-- end general section -->')

		###
		# Project Health - Enhanced Metrics for College Project
		f.write('<div id="project_health" class="section">')
		f.write(html_header(2, 'Project Health Dashboard'))
		
		# Code Quality Metrics
		f.write('<h3>Code Quality</h3>')
		code_metrics = data.code_quality_metrics
		f.write('<dl>')
		f.write('<dt>Cyclomatic Complexity</dt><dd>%d total</dd>' % code_metrics.get('cyclomatic_complexity', 0))
		if data.total_files > 0:
			avg_complexity = code_metrics.get('cyclomatic_complexity', 0) / data.total_files
			f.write('<dt>Average Complexity per File</dt><dd>%.1f</dd>' % avg_complexity)
		f.write('<dt>Large Files (>500 LOC)</dt><dd>%d</dd>' % len(data.file_analysis.get('large_files', [])))
		f.write('<dt>Complex Files (>20 complexity)</dt><dd>%d</dd>' % len(data.file_analysis.get('complex_files', [])))
		code_quality_score = data.calculate_code_quality_score()
		f.write('<dt>Code Quality Score</dt><dd><strong>%.1f/100</strong></dd>' % code_quality_score)
		f.write('</dl>')
		
		# Comprehensive Code Metrics Section
		cm = data.project_health.get('comprehensive_metrics', {})
		if cm:
			f.write('<h3>Comprehensive Code Metrics Per File</h3>')
			
			# Get file metrics list
			file_metrics_list = cm.get('file_metrics', [])
			
			if file_metrics_list:
				f.write('<p><strong>Individual file metrics (no aggregation/averaging):</strong></p>')
				
				# Create comprehensive table with all metrics
				f.write('<table class="file-metrics sortable" id="file-metrics" style="width: 100%; border-collapse: collapse; margin: 20px 0;">')
				f.write('<thead><tr style="background-color: #f0f0f0;">')
				f.write('<th style="border: 1px solid #ccc; padding: 8px; text-align: left;">File Path</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">LOCphy</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">LOCpro</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">LOCcom</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">Comment %</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">Halstead V</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">Halstead D</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">Halstead E</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">Est. Bugs</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">McCabe v(G)</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">MI</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px;">MI Status</th>')
				f.write('</tr></thead><tbody>')
				
				# Sort files by path for consistent display
				sorted_files = sorted(file_metrics_list, key=lambda x: x['filepath'])
				
				for file_metric in sorted_files:
					filepath = file_metric['filepath']
					loc = file_metric['loc']
					halstead = file_metric['halstead']
					mccabe = file_metric['mccabe']
					mi = file_metric['maintainability_index']
					
					# Determine MI color
					mi_value = mi['mi_raw']
					if mi_value >= 85:
						mi_color = 'green'
						mi_status = 'Good'
					elif mi_value >= 65:
						mi_color = 'orange'
						mi_status = 'Moderate'
					elif mi_value >= 0:
						mi_color = 'red'
						mi_status = 'Difficult'
					else:
						mi_color = 'darkred'
						mi_status = 'Critical'
					
					f.write('<tr>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; font-family: monospace; font-size: 0.9em;">{filepath}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{loc["loc_phy"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{loc["loc_pro"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{loc["loc_com"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{loc["comment_ratio"]:.1f}%</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{halstead["V"]:.1f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{halstead["D"]:.1f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{halstead["E"]:.1f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{halstead["B"]:.2f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{mccabe["cyclomatic_complexity"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{mi_value:.1f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center; color: {mi_color}; font-weight: bold;">{mi_status}</td>')
					f.write('</tr>')
				
				f.write('</tbody></table>')
				
				# Add legend
				f.write('<div style="margin: 20px 0; padding: 10px; background-color: #f9f9f9; border: 1px solid #ddd;">')
				f.write('<strong>Legend:</strong><br>')
				f.write('• <strong>LOCphy</strong>: Physical lines of code<br>')
				f.write('• <strong>LOCpro</strong>: Program lines (excluding comments and blanks)<br>')
				f.write('• <strong>LOCcom</strong>: Comment lines<br>')
				f.write('• <strong>Halstead V</strong>: Program Volume<br>')
				f.write('• <strong>Halstead D</strong>: Difficulty<br>')
				f.write('• <strong>Halstead E</strong>: Effort<br>')
				f.write('• <strong>McCabe v(G)</strong>: Cyclomatic Complexity<br>')
				f.write('• <strong>MI</strong>: Maintainability Index (≥85 Good, 65-84 Moderate, 0-64 Difficult, <0 Critical)<br>')
				f.write('</div>')
			
			# Maintainability Summary (keep this for quick overview)
			mi_summary = cm.get('maintainability_summary', {})
			if mi_summary:
				f.write('<h4>Maintainability Index Summary</h4>')
				f.write('<dl>')
				f.write('<dt>Good Files (MI ≥ 85)</dt><dd>%d</dd>' % mi_summary.get('good_files', 0))
				f.write('<dt>Moderate Files (65 ≤ MI < 85)</dt><dd>%d</dd>' % mi_summary.get('moderate_files', 0))
				f.write('<dt>Difficult Files (0 ≤ MI < 65)</dt><dd>%d</dd>' % mi_summary.get('difficult_files', 0))
				f.write('<dt>Critical Files (MI < 0)</dt><dd>%d</dd>' % mi_summary.get('critical_files', 0))
				f.write('</dl>')
			
			# OOP Summary (just count, no averages)
			oop_summary = cm.get('oop_summary', {})
			if oop_summary and oop_summary.get('files_with_oop', 0) > 0:
				f.write('<h4>Object-Oriented Programming Summary</h4>')
				f.write('<p>Files with OOP constructs: %d / %d</p>' % (
					oop_summary.get('files_with_oop', 0),
					oop_summary.get('files_analyzed', 0)
				))
			
			# OOP Metrics - Distance from Main Sequence Analysis
			f.write('<h3>OOP Metrics - Distance from Main Sequence (D)</h3>')
			f.write('<p style="margin: 10px 0; padding: 10px; background-color: #f0f8ff; border-left: 4px solid #2196F3;">')
			f.write('<strong>Note:</strong> The Distance from Main Sequence (D) metric measures the balance between ')
			f.write('abstraction and stability in object-oriented designs. ')
			f.write('Lower values indicate better design balance.')
			f.write('</p>')
			
			# Calculate afferent coupling after all files are analyzed
			data.oop_analyzer.calculate_afferent_coupling()
			
			# Generate summary report
			oop_report = data.oop_analyzer.get_summary_report()
			
			if oop_report and 'total_files_analyzed' in oop_report:
				# Summary metrics
				f.write('<h4>Overall Statistics</h4>')
				f.write('<dl>')
				f.write('<dt>Files Analyzed</dt><dd>%d</dd>' % oop_report['total_files_analyzed'])
				f.write('<dt>Average Distance (D)</dt><dd><strong>%.3f</strong></dd>' % oop_report['average_distance'])
				f.write('<dt>Min Distance</dt><dd>%.3f</dd>' % oop_report['min_distance'])
				f.write('<dt>Max Distance</dt><dd>%.3f</dd>' % oop_report['max_distance'])
				f.write('</dl>')
				
				# Zone distribution
				f.write('<h4>Design Zone Distribution</h4>')
				zone_dist = oop_report['zone_distribution']
				total_files = oop_report['total_files_analyzed']
				
				f.write('<table style="width: 100%; border-collapse: collapse; margin: 20px 0;">')
				f.write('<thead><tr style="background-color: #f0f0f0;">')
				f.write('<th style="border: 1px solid #ccc; padding: 8px; text-align: left;">Zone</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px; text-align: right;">Count</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px; text-align: right;">Percentage</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 8px; text-align: left;">Description</th>')
				f.write('</tr></thead><tbody>')
				
				zone_descriptions = {
					'main_sequence': ('✅ Main Sequence', 'Good - Well-balanced design'),
					'near_main_sequence': ('⚡ Near Main Sequence', 'Moderate - Minor improvements possible'),
					'zone_of_pain': ('🔴 Zone of Pain', 'Poor - Too concrete and stable (rigid)'),
					'zone_of_uselessness': ('🟡 Zone of Uselessness', 'Poor - Too abstract and unstable (unused)'),
					'far_from_main_sequence': ('⚠️  Far from Main Sequence', 'Poor - Needs refactoring')
				}
				
				for zone, (title, description) in zone_descriptions.items():
					count = zone_dist.get(zone, 0)
					percentage = (count / total_files * 100) if total_files > 0 else 0
					
					# Color code based on zone
					if 'main_sequence' in zone:
						row_color = '#e8f5e9'
					elif 'near' in zone:
						row_color = '#fff3e0'
					elif 'pain' in zone or 'uselessness' in zone or 'far' in zone:
						row_color = '#ffebee'
					else:
						row_color = 'white'
					
					f.write(f'<tr style="background-color: {row_color};">')
					f.write(f'<td style="border: 1px solid #ccc; padding: 8px;">{title}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 8px; text-align: right;">{count}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 8px; text-align: right;">{percentage:.1f}%</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 8px;">{description}</td>')
					f.write('</tr>')
				
				f.write('</tbody></table>')
				
				# Detailed file metrics table
				f.write('<h4>Detailed OOP Metrics by File</h4>')
				f.write('<p style="color: #666; font-style: italic;">Top 20 files by Distance from Main Sequence</p>')
				
				# Sort files by distance (descending) to show problem files first
				sorted_files = sorted(
					data.oop_analyzer.files.items(),
					key=lambda x: x[1]['distance_main_sequence'],
					reverse=True
				)[:20]
				
				f.write('<table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 0.9em;">')
				f.write('<thead><tr style="background-color: #f0f0f0;">')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: left;">File</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: center;" title="Number of classes defined">Classes</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: center;" title="Number of abstract classes">Abstract</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: center;" title="Efferent Coupling">Ce</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: center;" title="Afferent Coupling">Ca</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: center;" title="Abstractness: Abstract/Total">A</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: center;" title="Instability: Ce/(Ce+Ca)">I</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: center;" title="Distance from Main Sequence: |A+I-1|">D</th>')
				f.write('<th style="border: 1px solid #ccc; padding: 5px; text-align: left;">Zone</th>')
				f.write('</tr></thead><tbody>')
				
				for filepath, metrics in sorted_files:
					# Determine color based on distance
					d_value = metrics['distance_main_sequence']
					if d_value < 0.2:
						d_color = 'green'
					elif d_value < 0.4:
						d_color = 'orange'
					else:
						d_color = 'red'
					
					zone_short = {
						'main_sequence': '✅ Main Seq',
						'near_main_sequence': '⚡ Near Main',
						'zone_of_pain': '🔴 Pain',
						'zone_of_uselessness': '🟡 Useless',
						'far_from_main_sequence': '⚠️  Far'
					}.get(metrics['zone'], metrics['zone'])
					
					f.write('<tr>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; font-family: monospace; font-size: 0.85em;">{filepath}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{metrics["classes_defined"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{metrics["abstract_classes"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{metrics["efferent_coupling"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{metrics["afferent_coupling"]}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{metrics["abstractness"]:.3f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center;">{metrics["instability"]:.3f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px; text-align: center; color: {d_color}; font-weight: bold;">{d_value:.3f}</td>')
					f.write(f'<td style="border: 1px solid #ccc; padding: 5px;">{zone_short}</td>')
					f.write('</tr>')
				
				f.write('</tbody></table>')
				
				# Add legend
				f.write('<div style="margin: 20px 0; padding: 15px; background-color: #f9f9f9; border: 1px solid #ddd;">')
				f.write('<strong>Legend:</strong><br><br>')
				f.write('<strong>Metrics:</strong><br>')
				f.write('• <strong>Ce (Efferent Coupling)</strong>: Number of classes this class depends on<br>')
				f.write('• <strong>Ca (Afferent Coupling)</strong>: Number of classes that depend on this class<br>')
				f.write('• <strong>A (Abstractness)</strong>: Abstract classes / Total classes (0 = fully concrete, 1 = fully abstract)<br>')
				f.write('• <strong>I (Instability)</strong>: Ce / (Ce + Ca) (0 = stable, 1 = unstable)<br>')
				f.write('• <strong>D (Distance)</strong>: |A + I - 1| (0 = on main sequence, 1 = maximum distance)<br><br>')
				f.write('<strong>Design Principles:</strong><br>')
				f.write('• <strong>Main Sequence</strong>: Ideal balance - classes should have D close to 0<br>')
				f.write('• <strong>Zone of Pain</strong> (A→0, I→0): Concrete and stable - difficult to extend<br>')
				f.write('• <strong>Zone of Uselessness</strong> (A→1, I→1): Abstract and unstable - unused abstractions<br>')
				f.write('</div>')
				
				# Recommendations
				recommendations = oop_report.get('recommendations', [])
				if recommendations:
					f.write('<h4>Recommendations</h4>')
					f.write('<ul style="line-height: 1.8;">')
					for rec in recommendations:
						f.write(f'<li>{rec}</li>')
					f.write('</ul>')
		
		
		# Team Collaboration Metrics  
		f.write('<h3>Team Collaboration</h3>')
		bus_factor = data.calculate_bus_factor()
		f.write('<dl>')
		f.write('<dt>Bus Factor</dt><dd><strong>%d</strong> (minimum contributors for 50%% of work)</dd>' % bus_factor)
		
		if bus_factor <= 2:
			contribution_distribution = '<span style="color: red;">Highly concentrated contribution (few contributors handle most work)</span>'
		elif bus_factor <= 4:
			contribution_distribution = '<span style="color: orange;">Moderately concentrated contribution</span>'
		else:
			contribution_distribution = '<span style="color: green;">Well-distributed contribution across team</span>'
		f.write('<dt>Contribution Distribution</dt><dd>%s</dd>' % contribution_distribution)
		f.write('</dl>')
		
		# File Analysis
		f.write('<h3>File Analysis</h3>')
		file_analysis = data.file_analysis
		f.write('<dl>')
		
		# Top file types
		file_types = file_analysis.get('file_types', {})
		if file_types:
			top_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:5]
			f.write('<dt>Top File Types</dt><dd>')
			for ext, count in top_types:
				ext_display = ext if ext else '(no extension)'
				f.write('%s: %d files<br>' % (ext_display, count))
			f.write('</dd>')
		
		f.write('</dl>')
		
		# Actionable Issues
		issues = data.project_health.get('actionable_issues', [])
		if issues:
			f.write('<h3>Actionable Issues</h3>')
			f.write('<ul>')
			for issue in issues:
				f.write('<li>%s</li>' % issue)
			f.write('</ul>')
		
		f.write('</div>  <!-- end project health section -->')

		###
		# Team Analysis - New comprehensive team analysis section
		f.write('<div id="team_analysis" class="section">')
		f.write(html_header(2, 'Team Analysis'))

		# Team Overview
		f.write(html_header(2, 'Team Overview'))
		total_authors = data.getTotalAuthors()
		work_distribution = data.getTeamWorkDistribution()
		
		f.write('<dl>')
		f.write('<dt>Total Team Members</dt><dd>%d</dd>' % total_authors)
		
		# Calculate work distribution metrics
		commit_contributions = [dist['commit_percentage'] for dist in work_distribution.values()]
		lines_contributions = [dist['lines_percentage'] for dist in work_distribution.values()]
		
		if commit_contributions:
			max_commit_contrib = max(commit_contributions)
			min_commit_contrib = min(commit_contributions)
			avg_commit_contrib = sum(commit_contributions) / len(commit_contributions)
			
			f.write('<dt>Work Distribution (Commits)</dt><dd>Max: %.1f%%, Min: %.1f%%, Avg: %.1f%%</dd>' % 
				(max_commit_contrib, min_commit_contrib, avg_commit_contrib))
		
		if lines_contributions:
			max_lines_contrib = max(lines_contributions)
			min_lines_contrib = min(lines_contributions)
			avg_lines_contrib = sum(lines_contributions) / len(lines_contributions)
			
			f.write('<dt>Work Distribution (Lines)</dt><dd>Max: %.1f%%, Min: %.1f%%, Avg: %.1f%%</dd>' % 
				(max_lines_contrib, min_lines_contrib, avg_lines_contrib))
		
		f.write('</dl>')

		# Team Performance Rankings
		f.write(html_header(2, 'Team Performance Rankings'))
		
		# Top contributors by different metrics
		contrib_ranking = data.getAuthorsByContribution()
		activity_ranking = data.getAuthorsByActivity()
		regularity_ranking = data.getAuthorsByRegularity()
		collaboration_ranking = data.getAuthorsByCollaboration()
		
		f.write('<div class="rankings">')
		f.write('<div class="ranking-section">')
		f.write('<h3>Top Contributors (by Commit %)</h3>')
		f.write('<ol>')
		for author, percentage in contrib_ranking[:10]:
			f.write('<li>%s (%.1f%%)</li>' % (author, percentage))
		f.write('</ol>')
		f.write('</div>')
		
		f.write('<div class="ranking-section">')
		f.write('<h3>Most Efficient (by Quality Score)</h3>')
		f.write('<ol>')
		for author, score in activity_ranking[:10]:
			f.write('<li>%s (%.1f)</li>' % (author, score))
		f.write('</ol>')
		f.write('</div>')
		
		f.write('<div class="ranking-section">')
		f.write('<h3>Most Consistent</h3>')
		f.write('<ol>')
		for author, score in regularity_ranking[:10]:
			f.write('<li>%s (%.1f)</li>' % (author, score))
		f.write('</ol>')
		f.write('</div>')
		
		f.write('<div class="ranking-section">')
		f.write('<h3>Leadership Score</h3>')
		f.write('<ol>')
		for author, score in collaboration_ranking[:10]:
			f.write('<li>%s (%.1f)</li>' % (author, score))
		f.write('</ol>')
		f.write('</div>')
		f.write('</div>')

		# Detailed Team Performance Table
		f.write(html_header(2, 'Contributor Activity Metrics'))
		f.write('<table class="team-performance sortable" id="team-performance">')
		f.write('<tr>')
		f.write('<th>Author</th>')
		f.write('<th>Commits</th>')
		f.write('<th>Contrib %</th>')
		f.write('<th>Lines Changed</th>')
		f.write('<th>Avg Commit Size</th>')
		f.write('<th>Activity Score</th>')
		f.write('<th>Regularity Score</th>')
		f.write('<th>Collaboration Score</th>')
		f.write('<th>Composite Score</th>')
		f.write('<th>Activity Pattern</th>')
		f.write('</tr>')
		
		team_performance = data.getTeamPerformance()
		commit_patterns = data.getCommitPatterns()
		
		# Sort by overall score
		sorted_authors = sorted(team_performance.items(), key=lambda x: x[1].get('overall_score', 0), reverse=True)
		
		for author, perf in sorted_authors:
			author_info = data.getAuthorInfo(author)
			patterns = commit_patterns.get(author, {})
			
			commits = author_info.get('commits', 0)
			lines_changed = author_info.get('lines_added', 0) + author_info.get('lines_removed', 0)
			contrib_pct = perf.get('contribution_percentage', 0)
			avg_commit_size = patterns.get('avg_commit_size', 0)
			activity = perf.get('activity_score', 0)
			consistency = perf.get('consistency', 0)
			collaboration = perf.get('collaboration_score', 0)
			overall = perf.get('overall_score', 0)
			
			# Generate assessment
			assessment = self._generateAssessment(perf, patterns)
			
			f.write('<tr>')
			f.write('<td>%s</td>' % author)
			f.write('<td>%d</td>' % commits)
			f.write('<td>%.1f%%</td>' % contrib_pct)
			f.write('<td>%d</td>' % lines_changed)
			f.write('<td>%.1f</td>' % avg_commit_size)
			f.write('<td>%.1f</td>' % activity)
			f.write('<td>%.1f</td>' % consistency)
			f.write('<td>%.1f</td>' % collaboration)
			f.write('<td>%.1f</td>' % overall)
			f.write('<td>%s</td>' % assessment)
			f.write('</tr>')
		
		f.write('</table>')

		# Commit Patterns Analysis
		f.write(html_header(2, 'Commit Patterns Analysis'))
		
		commit_size_analysis = data.getCommitSizeAnalysis()
		
		f.write('<h3>Commit Size Distribution</h3>')
		f.write('<p><strong>Small commits (&lt;10 lines):</strong> %d commits</p>' % commit_size_analysis['overall_stats']['total_small'])
		f.write('<p><strong>Medium commits (10-100 lines):</strong> %d commits</p>' % commit_size_analysis['overall_stats']['total_medium'])
		f.write('<p><strong>Large commits (&gt;100 lines):</strong> %d commits</p>' % commit_size_analysis['overall_stats']['total_large'])
		
		if commit_size_analysis['small_commits_authors']:
			f.write('<h4>Authors with predominantly small commits (possible commit splitting):</h4>')
			f.write('<ul>')
			for author, ratio in commit_size_analysis['small_commits_authors']:
				f.write('<li>%s (%.1f%% small commits)</li>' % (author, ratio * 100))
			f.write('</ul>')
		
		if commit_size_analysis['large_commits_authors']:
			f.write('<h4>Authors with frequent large commits:</h4>')
			f.write('<ul>')
			for author, ratio in commit_size_analysis['large_commits_authors']:
				f.write('<li>%s (%.1f%% large commits)</li>' % (author, ratio * 100))
			f.write('</ul>')

		# Working Patterns Analysis
		f.write(html_header(2, 'Working Time Patterns'))
		
		working_patterns = data.getWorkingPatterns()
		
		f.write('<table class="working-patterns sortable" id="working-patterns">')
		f.write('<tr>')
		f.write('<th>Author</th>')
		f.write('<th>Night Worker<br>(22:00-06:00)</th>')
		f.write('<th>Weekend Worker</th>')
		f.write('<th>Early Bird<br>(05:00-09:00)</th>')
		f.write('<th>Regular Hours<br>(09:00-17:00)</th>')
		f.write('<th>Evening<br>(17:00-22:00)</th>')
		f.write('<th>Peak Hour</th>')
		f.write('<th>Peak Day</th>')
		f.write('</tr>')
		
		for author, patterns in working_patterns.items():
			total_commits = patterns.get('total_commits', 1)
			
			night_pct = (patterns.get('night_commits', 0) / total_commits) * 100
			weekend_pct = (patterns.get('weekend_commits', 0) / total_commits) * 100
			early_pct = (patterns.get('early_bird', 0) / total_commits) * 100
			workday_pct = (patterns.get('workday', 0) / total_commits) * 100
			evening_pct = (patterns.get('evening', 0) / total_commits) * 100
			
			# Find peak hour and day
			peak_hours = patterns.get('peak_hours', {})
			peak_days = patterns.get('peak_days', {})
			
			peak_hour = max(peak_hours.keys(), key=lambda k: peak_hours[k]) if peak_hours else 'N/A'
			peak_day = max(peak_days.keys(), key=lambda k: peak_days[k]) if peak_days else 'N/A'
			peak_day_name = WEEKDAYS[peak_day] if isinstance(peak_day, int) and 0 <= peak_day < 7 else peak_day
			
			f.write('<tr>')
			f.write('<td>%s</td>' % author)
			f.write('<td>%.1f%%</td>' % night_pct)
			f.write('<td>%.1f%%</td>' % weekend_pct)
			f.write('<td>%.1f%%</td>' % early_pct)
			f.write('<td>%.1f%%</td>' % workday_pct)
			f.write('<td>%.1f%%</td>' % evening_pct)
			f.write('<td>%s:00</td>' % peak_hour)
			f.write('<td>%s</td>' % peak_day_name)
			f.write('</tr>')
		
		f.write('</table>')

		# Impact Analysis
		f.write(html_header(2, 'Contribution Impact Analysis'))
		
		impact_analysis = data.getImpactAnalysis()
		critical_files = data.getCriticalFiles()
		
		f.write('<h3>Critical Files in Project (%d files identified)</h3>' % len(critical_files))
		if critical_files:
			f.write('<ul>')
			for critical_file in critical_files:  # Show all critical files
				f.write('<li>%s</li>' % critical_file)
			f.write('</ul>')
		
		f.write('<h3>Author Impact Analysis</h3>')
		f.write('<table class="impact-analysis sortable" id="impact-analysis">')
		f.write('<tr>')
		f.write('<th>Author</th>')
		f.write('<th>Impact Score</th>')
		f.write('<th>Critical Files Touched</th>')
		f.write('<th>Maintenance Work %</th>')
		f.write('<th>High Impact Files</th>')
		f.write('<th>Assessment</th>')
		f.write('</tr>')
		
		# Sort by impact score
		sorted_impact = sorted(impact_analysis.items(), key=lambda x: x[1].get('impact_score', 0), reverse=True)
		
		for author, impact in sorted_impact:
			impact_score = impact.get('impact_score', 0)
			critical_files_touched = len(impact.get('critical_files', []))
			maintenance_percentage = impact.get('maintenance_percentage', 0)
			high_impact_files = len(impact.get('high_impact_files', []))
			
			# Generate objective impact description
			impact_assessment = f"Score: {impact_score:.1f}"
			
			if critical_files_touched > 0:
				impact_assessment += f", {critical_files_touched} critical files"
			
			if maintenance_percentage > 0:
				impact_assessment += f", {maintenance_percentage:.1f}% maintenance commits"
			
			f.write('<tr>')
			f.write('<td>%s</td>' % author)
			f.write('<td>%.1f</td>' % impact_score)
			f.write('<td>%d</td>' % critical_files_touched)
			f.write('<td>%.1f%%</td>' % maintenance_percentage)
			f.write('<td>%d</td>' % high_impact_files)
			f.write('<td>%s</td>' % impact_assessment)
			f.write('</tr>')
		
		f.write('</table>')

		# Team Collaboration Analysis
		f.write(html_header(2, 'Team Collaboration Analysis'))
		
		collaboration_data = data.getTeamCollaboration()
		
		f.write('<table class="collaboration sortable" id="collaboration">')
		f.write('<tr>')
		f.write('<th>Author</th>')
		f.write('<th>Files Owned</th>')
		f.write('<th>Collaborators</th>')
		f.write('<th>Shared Files</th>')
		f.write('<th>Top Collaborations</th>')
		f.write('</tr>')
		
		for author, collab in collaboration_data.items():
			files_owned = len(collab.get('file_ownership', {}))
			worked_with = collab.get('worked_with', {})
			collaborators_count = len(worked_with)
			
			# Count total shared files
			shared_files = 0
			top_collabs = []
			
			for other_author, shared_files_dict in worked_with.items():
				shared_count = len(shared_files_dict)
				shared_files += shared_count
				top_collabs.append((other_author, shared_count))
			
			# Sort and take top 3 collaborations
			top_collabs.sort(key=lambda x: x[1], reverse=True)
			top_collabs_str = ', '.join([f"{author}({count})" for author, count in top_collabs[:3]])
			
			f.write('<tr>')
			f.write('<td>%s</td>' % author)
			f.write('<td>%d</td>' % files_owned)
			f.write('<td>%d</td>' % collaborators_count)
			f.write('<td>%d</td>' % shared_files)
			f.write('<td>%s</td>' % top_collabs_str)
			f.write('</tr>')
		
		f.write('</table>')

		f.write('</div>  <!-- end team_analysis section -->')

		###
		# Activity section
		f.write('<div id="activity" class="section">')
		f.write(html_header(2, 'Activity'))

		# Last 30 days
		f.write(html_header(2, 'Last 30 Days'))
		last_30_days = data.getLast30DaysActivity()
		f.write('<dl>')
		f.write('<dt>Commits</dt><dd>%d</dd>' % last_30_days['commits'])
		f.write('<dt>Lines added</dt><dd>%d</dd>' % last_30_days['lines_added'])
		f.write('<dt>Lines removed</dt><dd>%d</dd>' % last_30_days['lines_removed'])
		f.write('<dt>Net lines</dt><dd>%d</dd>' % (last_30_days['lines_added'] - last_30_days['lines_removed']))
		f.write('</dl>')

		# Last 12 months
		f.write(html_header(2, 'Last 12 Months'))
		last_12_months = data.getLast12MonthsActivity()
		if last_12_months['commits']:
			f.write('<table class="sortable" id="last12months">')
			f.write('<tr><th>Month</th><th>Commits</th><th>Lines Added</th><th>Lines Removed</th><th>Net Lines</th></tr>')
			
			# Sort months in reverse chronological order
			sorted_months = sorted(last_12_months['commits'].keys(), reverse=True)
			for month in sorted_months:
				commits = last_12_months['commits'][month]
				lines_added = last_12_months['lines_added'].get(month, 0)
				lines_removed = last_12_months['lines_removed'].get(month, 0)
				net_lines = lines_added - lines_removed
				
				f.write('<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>' % 
					(month, commits, lines_added, lines_removed, net_lines))
			
			f.write('</table>')
		else:
			f.write('<p>No activity in the last 12 months.</p>')

		# Pace of Changes
		f.write(html_header(2, 'Pace of Changes'))
		f.write('<p>Number of line changes (additions + deletions) over time (weekly aggregation)</p>')
		weekly_pace_data = data.getPaceOfChangesByWeek()
		if weekly_pace_data:
			# Generate pace of changes data file (using weekly data)
			fg = open(path + '/pace_of_changes.dat', 'w')
			# Convert week dates to timestamps for the data file
			for week_date in sorted(weekly_pace_data.keys()):
				week_timestamp = int(datetime.datetime.strptime(week_date, '%Y-%m-%d').timestamp())
				fg.write('%d %d\n' % (week_timestamp, weekly_pace_data[week_date]))
			fg.close()
			
			# Display weekly pace data as a table
			if hasattr(self, 'table_data') and 'pace_of_changes' in self.table_data:
				f.write(self.table_data['pace_of_changes'])
			else:
				# Weekly aggregated table
				f.write('<table class="sortable" id="pace_changes_detail">')
				f.write('<tr><th>Week Starting (Monday)</th><th>Line Changes</th></tr>')
				for week_date in sorted(weekly_pace_data.keys()):
					f.write('<tr><td>%s</td><td>%d</td></tr>' % (week_date, weekly_pace_data[week_date]))
				f.write('</table>')
		else:
			f.write('<p>No pace data available.</p>')

		# Monthly Pace of Changes Table
		f.write('<h3>Monthly Pace of Changes</h3>')
		pace_by_month = data.getPaceOfChangesByMonth()
		if pace_by_month:
			f.write('<table class="sortable" id="pace_by_month">')
			f.write('<tr><th>Month</th><th>Line Changes (Additions + Deletions)</th><th>% of Total Changes</th></tr>')
			
			total_pace_changes = sum(pace_by_month.values())
			for month in sorted(pace_by_month.keys(), reverse=True):
				changes = pace_by_month[month]
				percentage = (100.0 * changes / total_pace_changes) if total_pace_changes > 0 else 0.0
				f.write('<tr><td>%s</td><td>%d</td><td>%.2f%%</td></tr>' % (month, changes, percentage))
			f.write('</table>')
		else:
			f.write('<p>No monthly pace data available.</p>')

		# Yearly Pace of Changes Summary
		f.write('<h3>Yearly Pace of Changes Summary</h3>')
		pace_by_year = data.getPaceOfChangesByYear()
		if pace_by_year:
			f.write('<table class="sortable" id="pace_by_year">')
			f.write('<tr><th>Year</th><th>Line Changes (Additions + Deletions)</th><th>% of Total Changes</th><th>Average per Month</th></tr>')
			
			total_pace_changes = sum(pace_by_year.values())
			for year in sorted(pace_by_year.keys(), reverse=True):
				changes = pace_by_year[year]
				percentage = (100.0 * changes / total_pace_changes) if total_pace_changes > 0 else 0.0
				avg_per_month = changes / 12.0  # Simple average
				f.write('<tr><td>%s</td><td>%d</td><td>%.2f%%</td><td>%.1f</td></tr>' % (year, changes, percentage, avg_per_month))
			f.write('</table>')
		else:
			f.write('<p>No yearly pace data available.</p>')

		# Weekly activity
		WEEKS = 32
		f.write(html_header(2, 'Weekly activity'))
		f.write('<p>Last %d weeks</p>' % WEEKS)

		# generate weeks to show (previous N weeks from now)
		now = datetime.datetime.now()
		deltaweek = datetime.timedelta(7)
		weeks = []
		stampcur = now
		for i in range(0, WEEKS):
			weeks.insert(0, stampcur.strftime('%Y-%W'))
			stampcur -= deltaweek

		# top row: commits & bar
		f.write('<table class="noborders"><tr>')
		for i in range(0, WEEKS):
			commits = 0
			if weeks[i] in data.activity_by_year_week:
				commits = data.activity_by_year_week[weeks[i]]

			percentage = 0
			if weeks[i] in data.activity_by_year_week:
				percentage = float(data.activity_by_year_week[weeks[i]]) / data.activity_by_year_week_peak
			height = max(1, int(200 * percentage))
			f.write('<td style="text-align: center; vertical-align: bottom">%d<div style="display: block; background-color: red; width: 20px; height: %dpx"></div></td>' % (commits, height))

		# bottom row: year/week
		f.write('</tr><tr>')
		for i in range(0, WEEKS):
			f.write('<td>%s</td>' % (WEEKS - i))
		f.write('</tr></table>')

		# Hour of Day
		f.write(html_header(2, 'Hour of Day'))
		hour_of_day = data.getActivityByHourOfDay()
		fg = open(path + '/hour_of_day.dat', 'w')
		for i in range(0, 24):
			if i in hour_of_day:
				fg.write('%d %d\n' % (i + 1, hour_of_day[i]))
			else:
				fg.write('%d 0\n' % (i + 1))
		fg.close()
		
		# Display hour of day data as a table instead of chart
		if hasattr(self, 'table_data') and 'hour_of_day' in self.table_data:
			f.write(self.table_data['hour_of_day'])
		else:
			# Fallback simple table
			f.write('<table class="sortable" id="hour_of_day_detail">')
			f.write('<tr><th>Hour</th><th>Commits</th><th>Percentage</th></tr>')
			total_commits = sum(hour_of_day.values()) if hour_of_day else 0
			for i in range(0, 24):
				commits = hour_of_day.get(i, 0)
				percent = (commits * 100.0 / total_commits) if total_commits > 0 else 0
				f.write('<tr><td>%02d:00</td><td>%d</td><td>%.1f%%</td></tr>' % (i, commits, percent))
			f.write('</table>')
		f.write('<table><tr><th>Hour</th>')
		for i in range(0, 24):
			f.write('<th>%d</th>' % i)
		f.write('</tr>\n<tr><th>Commits</th>')
		for i in range(0, 24):
			if i in hour_of_day:
				r = 127 + int((float(hour_of_day[i]) / hour_of_day_busiest) * 128)
				f.write('<td style="background-color: rgb(%d, 0, 0)">%d</td>' % (r, hour_of_day[i]))
			else:
				f.write('<td>0</td>')
		f.write('</tr>\n<tr><th>%</th>')
		totalcommits = total_commits
		for i in range(0, 24):
			if i in hour_of_day:
				r = 127 + int((float(hour_of_day[i]) / hour_of_day_busiest) * 128)
				percent = (100.0 * hour_of_day[i]) / totalcommits if totalcommits else 0.0
				f.write('<td style="background-color: rgb(%d, 0, 0)">%.2f</td>' % (r, percent))
			else:
				f.write('<td>0.00</td>')
		f.write('</tr></table>')

		# Day of Week
		f.write(html_header(2, 'Day of Week'))
		day_of_week = data.getActivityByDayOfWeek()
		fp = open(path + '/day_of_week.dat', 'w')
		for d in range(0, 7):
			commits = 0
			if d in day_of_week:
				commits = day_of_week[d]
			fp.write('%d %s %d\n' % (d + 1, WEEKDAYS[d], commits))
		fp.close()
		
		# Display consolidated day of week data as a single table
		if hasattr(self, 'table_data') and 'day_of_week' in self.table_data:
			f.write(self.table_data['day_of_week'])
		else:
			# Consolidated table with day, commits, percentage, and total
			f.write('<table class="sortable day-of-week" id="day_of_week_detail">')
			f.write('<tr><th>Day of Week</th><th>Commits</th><th>Percentage</th><th>Total (%)</th></tr>')
			total_commits_week = sum(day_of_week.values()) if day_of_week else 0
			for d in range(0, 7):
				commits = day_of_week.get(d, 0)
				week_percent = (commits * 100.0 / total_commits_week) if total_commits_week > 0 else 0
				total_percent = (100.0 * commits) / totalcommits if totalcommits else 0.0
				f.write('<tr><td>%s</td><td>%d</td><td>%.1f%%</td><td>%.2f%%</td></tr>' % (WEEKDAYS[d], commits, week_percent, total_percent))
			f.write('</table>')		# Hour of Week
		f.write(html_header(2, 'Hour of Week'))
		f.write('<table>')

		f.write('<tr><th>Weekday</th>')
		for hour in range(0, 24):
			f.write('<th>%d</th>' % (hour))
		f.write('</tr>')

		for weekday in range(0, 7):
			f.write('<tr><th>%s</th>' % (WEEKDAYS[weekday]))
			for hour in range(0, 24):
				try:
					commits = data.activity_by_hour_of_week[weekday][hour]
				except KeyError:
					commits = 0
				if commits != 0:
					f.write('<td')
					r = 127 + int((float(commits) / data.activity_by_hour_of_week_busiest) * 128)
					f.write(' style="background-color: rgb(%d, 0, 0)"' % r)
					f.write('>%d</td>' % commits)
				else:
					f.write('<td></td>')
			f.write('</tr>')

		f.write('</table>')

		# Month of Year
		f.write(html_header(2, 'Month of Year'))
		fp = open (path + '/month_of_year.dat', 'w')
		for mm in range(1, 13):
			commits = 0
			if mm in data.activity_by_month_of_year:
				commits = data.activity_by_month_of_year[mm]
			fp.write('%d %d\n' % (mm, commits))
		fp.close()
		
		# Display month of year data as a table instead of chart
		if hasattr(self, 'table_data') and 'month_of_year' in self.table_data:
			f.write(self.table_data['month_of_year'])
		f.write('<div class="vtable"><table>')
		f.write('<tr><th>Month</th><th>Commits (%)</th></tr>')
		for mm in range(1, 13):
			commits = 0
			if mm in data.activity_by_month_of_year:
				commits = data.activity_by_month_of_year[mm]
			percent = (100.0 * commits) / total_commits if total_commits else 0.0
			f.write('<tr><td>%d</td><td>%d (%.2f %%)</td></tr>' % (mm, commits, percent))
		f.write('</table></div>')

		# Commits by year/month
		f.write(html_header(2, 'Commits by year/month'))
		fg = open(path + '/commits_by_year_month.dat', 'w')
		for yymm in sorted(data.commits_by_month.keys()):
			fg.write('%s %s\n' % (yymm, data.commits_by_month[yymm]))
		fg.close()
		# Display commits by year/month data as table instead of chart
		if hasattr(self, 'table_data') and 'commits_by_year_month' in self.table_data:
			f.write(self.table_data['commits_by_year_month'])
		f.write('<div class="vtable"><table><tr><th>Month</th><th>Commits</th><th>Lines added</th><th>Lines removed</th></tr>')
		for yymm in reversed(sorted(data.commits_by_month.keys())):
			f.write('<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td></tr>' % (yymm, data.commits_by_month.get(yymm,0), data.lines_added_by_month.get(yymm,0), data.lines_removed_by_month.get(yymm,0)))
		f.write('</table></div>')

		# Commits by year
		f.write(html_header(2, 'Commits by Year'))
		fg = open(path + '/commits_by_year.dat', 'w')
		for yy in sorted(data.commits_by_year.keys()):
			fg.write('%d %d\n' % (yy, data.commits_by_year[yy]))
		fg.close()
		# Display commits by year data as table instead of chart
		if hasattr(self, 'table_data') and 'commits_by_year' in self.table_data:
			f.write(self.table_data['commits_by_year'])
		f.write('<div class="vtable"><table><tr><th>Year</th><th>Commits (% of all)</th><th>Lines added</th><th>Lines removed</th></tr>')
		for yy in reversed(sorted(data.commits_by_year.keys())):
			commits = data.commits_by_year.get(yy, 0)
			percent = (100.0 * commits) / total_commits if total_commits else 0.0
			f.write('<tr><td>%s</td><td>%d (%.2f%%)</td><td>%d</td><td>%d</td></tr>' % (yy, commits, percent, data.lines_added_by_year.get(yy,0), data.lines_removed_by_year.get(yy,0)))
		f.write('</table></div>')

		# Commits by timezone
		f.write(html_header(2, 'Commits by Timezone'))
		f.write('<table><tr>')
		f.write('<th>Timezone</th><th>Commits</th>')
		f.write('</tr>')
		max_commits_on_tz = max(data.commits_by_timezone.values()) if data.commits_by_timezone else 1
		for i in sorted(data.commits_by_timezone.keys(), key = lambda n : int(n)):
			commits = data.commits_by_timezone[i]
			r = 127 + int((float(commits) / max_commits_on_tz) * 128)
			f.write('<tr><th>%s</th><td style="background-color: rgb(%d, 0, 0)">%d</td></tr>' % (i, r, commits))
		f.write('</table>')
		f.write('</div>  <!-- end activity section -->')

		###
		# Authors section
		f.write('<div id="authors" class="section">')
		f.write(html_header(2, 'Authors'))

		# Authors :: List of authors
		f.write(html_header(2, 'List of Authors'))

		f.write('<table class="authors sortable" id="authors">')
		f.write('<tr><th>Author</th><th>Commits (%)</th><th>+ lines</th><th>- lines</th><th>First commit</th><th>Last commit</th><th class="unsortable">Age</th><th>Active days</th><th># by commits</th></tr>')
		for author in data.getAuthors(conf['max_authors']):
			info = data.getAuthorInfo(author)
			f.write('<tr><td>%s</td><td>%d (%.2f%%)</td><td>%d</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%d</td></tr>' % (author, info['commits'], info['commits_frac'], info['lines_added'], info['lines_removed'], info['date_first'], info['date_last'], info['timedelta'], len(info['active_days']), info['place_by_commits']))
		f.write('</table>')

		allauthors = data.getAuthors()
		if len(allauthors) > conf['max_authors']:
			rest = allauthors[conf['max_authors']:]
			f.write('<p class="moreauthors">These didn\'t make it to the top: %s</p>' % ', '.join(rest))

		f.write(html_header(2, 'Cumulated Added Lines of Code per Author'))
		# Display lines of code by author data as table instead of chart
		if hasattr(self, 'table_data') and 'lines_of_code_by_author' in self.table_data:
			f.write(self.table_data['lines_of_code_by_author'])
		if len(allauthors) > conf['max_authors']:
			f.write('<p class="moreauthors">Only top %d authors shown</p>' % conf['max_authors'])

		# Yearly Lines Added by Author
		f.write('<h3>Cumulated Added Lines of Code per Author - Yearly Data (Top 20 Authors)</h3>')
		lines_by_author_by_year = data.getLinesAddedByAuthorByYear()
		if lines_by_author_by_year:
			# Calculate top 20 authors by total lines added
			from collections import defaultdict
			author_totals = defaultdict(int)
			for year_data in lines_by_author_by_year.values():
				for author, lines in year_data.items():
					author_totals[author] += lines
			
			top_20_authors = sorted(author_totals.items(), key=lambda x: x[1], reverse=True)[:20]
			top_20_author_names = [author for author, _ in top_20_authors]
			
			years = sorted(lines_by_author_by_year.keys())
			
			f.write('<table class="sortable" id="yearly_lines_by_author">')
			f.write('<tr><th>Author</th>')
			for year in years:
				f.write('<th>%d</th>' % year)
			f.write('<th>Total</th><th>% of All Lines</th></tr>')
			
			total_all_lines = sum(author_totals.values())
			
			for author, total_lines in top_20_authors:
				f.write('<tr><td>%s</td>' % author)
				for year in years:
					lines_in_year = lines_by_author_by_year.get(year, {}).get(author, 0)
					f.write('<td>%d</td>' % lines_in_year)
				percentage = (100.0 * total_lines / total_all_lines) if total_all_lines > 0 else 0.0
				f.write('<td><strong>%d</strong></td><td>%.2f%%</td></tr>' % (total_lines, percentage))
			
			f.write('</table>')
		else:
			f.write('<p>No yearly author lines data available.</p>')

		f.write(html_header(2, 'Commits per Author'))
		# Display commits by author data as table instead of chart
		if hasattr(self, 'table_data') and 'commits_by_author' in self.table_data:
			f.write(self.table_data['commits_by_author'])
		if len(allauthors) > conf['max_authors']:
			f.write('<p class="moreauthors">Only top %d authors shown</p>' % conf['max_authors'])

		# Yearly Commits by Author  
		f.write('<h3>Commits per Author - Yearly Data</h3>')
		commits_by_author_by_year = data.getCommitsByAuthorByYear()
		if commits_by_author_by_year:
			# Calculate top authors by total commits
			author_commit_totals = defaultdict(int)
			for year_data in commits_by_author_by_year.values():
				for author, commits in year_data.items():
					author_commit_totals[author] += commits
			
			top_authors_by_commits = sorted(author_commit_totals.items(), key=lambda x: x[1], reverse=True)[:20]
			
			years = sorted(commits_by_author_by_year.keys())
			
			f.write('<table class="sortable" id="yearly_commits_by_author">')
			f.write('<tr><th>Author</th>')
			for year in years:
				f.write('<th>%d</th>' % year)
			f.write('<th>Total</th><th>% of All Commits</th></tr>')
			
			total_all_commits = sum(author_commit_totals.values())
			
			for author, total_commits in top_authors_by_commits:
				f.write('<tr><td>%s</td>' % author)
				for year in years:
					commits_in_year = commits_by_author_by_year.get(year, {}).get(author, 0)
					f.write('<td>%d</td>' % commits_in_year)
				percentage = (100.0 * total_commits / total_all_commits) if total_all_commits > 0 else 0.0
				f.write('<td><strong>%d</strong></td><td>%.2f%%</td></tr>' % (total_commits, percentage))
			
			f.write('</table>')
		else:
			f.write('<p>No yearly author commits data available.</p>')

		fgl = open(path + '/lines_of_code_by_author.dat', 'w')
		fgc = open(path + '/commits_by_author.dat', 'w')

		lines_by_authors = {} # cumulated added lines by
		# author. to save memory,
		# changes_by_date_by_author[stamp][author] is defined
		# only at points where author commits.
		# lines_by_authors allows us to generate all the
		# points in the .dat file.

		# Don't rely on getAuthors to give the same order each
		# time. Be robust and keep the list in a variable.
		commits_by_authors = {} # cumulated added lines by

		self.authors_to_plot = data.getAuthors(conf['max_authors'])
		for author in self.authors_to_plot:
			lines_by_authors[author] = 0
			commits_by_authors[author] = 0
		for stamp in sorted(data.changes_by_date_by_author.keys()):
			fgl.write('%d' % stamp)
			fgc.write('%d' % stamp)
			for author in self.authors_to_plot:
				if author in data.changes_by_date_by_author[stamp]:
					lines_by_authors[author] = data.changes_by_date_by_author[stamp][author]['lines_added']
					commits_by_authors[author] = data.changes_by_date_by_author[stamp][author]['commits']
				fgl.write(' %d' % lines_by_authors[author])
				fgc.write(' %d' % commits_by_authors[author])
			fgl.write('\n')
			fgc.write('\n')
		fgl.close()
		fgc.close()

		# Add table for Cumulated Added Lines of Code per Author
		f.write('<h3>Cumulated Added Lines of Code per Author (Data Table)</h3>')
		f.write('<table class="sortable" id="lines_by_author_table">')
		f.write('<tr><th>Author</th><th>Total Lines Added</th><th>Percentage</th><th>First Commit</th><th>Last Commit</th></tr>')
		authors_by_lines = sorted([(author, data.getAuthorInfo(author)['lines_added']) for author in self.authors_to_plot], 
								 key=lambda x: x[1], reverse=True)
		total_lines_all_authors = sum(data.getAuthorInfo(author)['lines_added'] for author in self.authors_to_plot)
		
		for author, lines_added in authors_by_lines:
			author_info = data.getAuthorInfo(author)
			percentage = (100.0 * lines_added / total_lines_all_authors) if total_lines_all_authors > 0 else 0.0
			f.write('<tr><td>%s</td><td>%d</td><td>%.2f%%</td><td>%s</td><td>%s</td></tr>' % 
					(author, lines_added, percentage, author_info['date_first'], author_info['date_last']))
		f.write('</table>')

		# Add table for Commits per Author
		f.write('<h3>Commits per Author (Data Table)</h3>')
		f.write('<table class="sortable" id="commits_by_author_table">')
		f.write('<tr><th>Author</th><th>Total Commits</th><th>Percentage</th><th>Lines Added</th><th>Lines Removed</th><th>Active Days</th></tr>')
		authors_by_commits_sorted = sorted([(author, data.getAuthorInfo(author)['commits']) for author in self.authors_to_plot], 
										  key=lambda x: x[1], reverse=True)
		total_commits_all_authors = sum(data.getAuthorInfo(author)['commits'] for author in self.authors_to_plot)
		
		for author, commits in authors_by_commits_sorted:
			author_info = data.getAuthorInfo(author)
			percentage = (100.0 * commits / total_commits_all_authors) if total_commits_all_authors > 0 else 0.0
			f.write('<tr><td>%s</td><td>%d</td><td>%.2f%%</td><td>%d</td><td>%d</td><td>%d</td></tr>' % 
					(author, commits, percentage, author_info.get('lines_added', 0), 
					 author_info.get('lines_removed', 0), len(author_info.get('active_days', []))))
		f.write('</table>')

		# Authors :: Author of Month
		f.write(html_header(2, 'Author of Month'))
		f.write('<table class="sortable" id="aom">')
		f.write('<tr><th>Month</th><th>Author</th><th>Commits (%%)</th><th class="unsortable">Next top %d</th><th>Number of authors</th></tr>' % conf['authors_top'])
		for yymm in reversed(sorted(data.author_of_month.keys())):
			authordict = data.author_of_month[yymm]
			authors = getkeyssortedbyvalues(authordict)
			authors.reverse()
			commits = data.author_of_month[yymm][authors[0]]
			next = ', '.join(authors[1:conf['authors_top']+1])
			f.write('<tr><td>%s</td><td>%s</td><td>%d (%.2f%% of %d)</td><td>%s</td><td>%d</td></tr>' % (yymm, authors[0], commits, (100.0 * commits) / data.commits_by_month[yymm], data.commits_by_month[yymm], next, len(authors)))

		f.write('</table>')

		f.write(html_header(2, 'Author of Year'))
		f.write('<table class="sortable" id="aoy"><tr><th>Year</th><th>Author</th><th>Commits (%%)</th><th class="unsortable">Next top %d</th><th>Number of authors</th></tr>' % conf['authors_top'])
		for yy in reversed(sorted(data.author_of_year.keys())):
			authordict = data.author_of_year[yy]
			authors = getkeyssortedbyvalues(authordict)
			authors.reverse()
			commits = data.author_of_year[yy][authors[0]]
			next = ', '.join(authors[1:conf['authors_top']+1])
			f.write('<tr><td>%s</td><td>%s</td><td>%d (%.2f%% of %d)</td><td>%s</td><td>%d</td></tr>' % (yy, authors[0], commits, (100.0 * commits) / data.commits_by_year[yy], data.commits_by_year[yy], next, len(authors)))
		f.write('</table>')

		# Domains
		f.write(html_header(2, 'Commits by Domains'))
		domains_by_commits = getkeyssortedbyvaluekey(data.domains, 'commits')
		domains_by_commits.reverse() # most first
		fp = open(path + '/domains.dat', 'w')
		n = 0
		for domain in domains_by_commits:
			if n == conf['max_domains']:
				break
			commits = 0
			n += 1
			info = data.getDomainInfo(domain)
			fp.write('%s %d %d\n' % (domain, n , info['commits']))
		fp.close()
		# Display domains data as table instead of chart
		if hasattr(self, 'table_data') and 'domains' in self.table_data:
			f.write(self.table_data['domains'])
		f.write('<div class="vtable"><table>')
		f.write('<tr><th>Domains</th><th>Total (%)</th></tr>')
		n = 0
		for domain in domains_by_commits:
			if n == conf['max_domains']:
				break
			commits = 0
			n += 1
			info = data.getDomainInfo(domain)
			percent = (100.0 * info['commits'] / total_commits) if total_commits else 0.0
			f.write('<tr><th>%s</th><td>%d (%.2f%%)</td></tr>' % (domain, info['commits'], percent))
		f.write('</table></div>')
		f.write('</div>  <!-- end authors section -->')

		###
		# Files section
		f.write('<div id="files" class="section">')
		f.write(html_header(2, 'Files'))

		f.write('<dl>\n')
		f.write('<dt>Total files</dt><dd>%d</dd>' % data.getTotalFiles())
		f.write('<dt>Total lines</dt><dd>%d</dd>' % data.getTotalLOC())
		try:
			avg_size = data.getAverageFileSize()
			f.write('<dt>Average file size</dt><dd>%.2f bytes</dd>' % avg_size)
		except (AttributeError, ZeroDivisionError):
			# Fallback to old calculation if new method fails
			avg_size = float(data.getTotalSize()) / data.getTotalFiles() if data.getTotalFiles() else 0.0
			f.write('<dt>Average file size</dt><dd>%.2f bytes</dd>' % avg_size)
		try:
			avg_revisions = data.getAverageRevisionsPerFile()
			f.write('<dt>Average revisions per file</dt><dd>%.2f</dd>' % avg_revisions)
		except AttributeError:
			pass
		f.write('</dl>\n')

		# Files :: File count by year
		f.write(html_header(2, 'File count by year'))

		# Generate yearly file count data
		files_by_year = data.getFilesByYear()
		
		if files_by_year:
			fg = open(path + '/files_by_year.dat', 'w')
			for year in sorted(files_by_year.keys()):
				fg.write('%d %d\n' % (year, files_by_year[year]))
			fg.close()
			
			# Display files by year data as table instead of chart
			if hasattr(self, 'table_data') and 'files_by_year' in self.table_data:
				f.write(self.table_data['files_by_year'])

			# Add table for File count by year
			f.write('<table class="sortable" id="files_by_year_table">')
			f.write('<tr><th>Year</th><th>Max File Count</th><th>Change from Previous Year</th><th>Growth Rate</th></tr>')
			
			prev_count = 0
			for year in sorted(files_by_year.keys()):
				file_count = files_by_year[year]
				change = file_count - prev_count if prev_count > 0 else 0
				growth_rate = (100.0 * change / prev_count) if prev_count > 0 and change > 0 else 0.0
				
				change_str = f"+{change}" if change > 0 else str(change) if change < 0 else "0"
				f.write('<tr><td>%d</td><td>%d</td><td>%s</td><td>%.1f%%</td></tr>' % (year, file_count, change_str, growth_rate))
				prev_count = file_count
			f.write('</table>')
		else:
			f.write('<p>No yearly file count data available.</p>')

		# Keep original files by date data for reference
		f.write('<h3>Recent File Count Changes (Last 20 commits)</h3>')
		f.write('<table class="sortable" id="files_by_date_table">')
		f.write('<tr><th>Date</th><th>File Count</th><th>Change from Previous</th></tr>')
		
		# Sort the file count data by date
		sorted_file_data = []
		for stamp in sorted(data.files_by_stamp.keys()):
			date_str = datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d')
			file_count = data.files_by_stamp[stamp]
			sorted_file_data.append((date_str, file_count, stamp))
		
		# Calculate changes from previous counts
		prev_count = 0
		for i, (date_str, file_count, stamp) in enumerate(sorted_file_data[-20:]):  # Show last 20 entries
			change = file_count - prev_count if prev_count > 0 else 0
			change_str = f"+{change}" if change > 0 else str(change) if change < 0 else "0"
			f.write('<tr><td>%s</td><td>%d</td><td>%s</td></tr>' % (date_str, file_count, change_str))
			prev_count = file_count
		f.write('</table>')

		#f.write('<h2>Average file size by date</h2>')

		# Files :: Extensions
		f.write(html_header(2, 'Extensions'))
		f.write('<table class="sortable" id="ext"><tr><th>Extension</th><th>Files (%)</th><th>Lines (%)</th><th>Lines/file</th></tr>')
		for ext in sorted(data.extensions.keys()):
			files = data.extensions[ext]['files']
			lines = data.extensions[ext]['lines']
			loc_percentage = (100.0 * lines) / data.getTotalLOC() if data.getTotalLOC() else 0.0
			files_percentage = (100.0 * files) / data.getTotalFiles() if data.getTotalFiles() else 0.0
			lines_per_file = (lines // files) if files else 0
			f.write('<tr><td>%s</td><td>%d (%.2f%%)</td><td>%d (%.2f%%)</td><td>%d</td></tr>' % (ext, files, files_percentage, lines, loc_percentage, lines_per_file))
		f.write('</table>')

		# SLOC Breakdown by Extension
		f.write(html_header(2, 'Source Lines of Code (SLOC) Breakdown'))
		f.write('<table class="sortable" id="sloc"><tr><th>Extension</th><th>Source Lines (%)</th><th>Comment Lines (%)</th><th>Blank Lines (%)</th><th>Total Lines</th></tr>')
		sloc_data = data.getSLOCByExtension()
		for ext in sorted(sloc_data.keys()):
			if sloc_data[ext]['total'] == 0:
				continue
			source = sloc_data[ext]['source']
			comments = sloc_data[ext]['comments']
			blank = sloc_data[ext]['blank']
			total = sloc_data[ext]['total']
			source_pct = (100.0 * source / total) if total else 0.0
			comment_pct = (100.0 * comments / total) if total else 0.0
			blank_pct = (100.0 * blank / total) if total else 0.0
			f.write('<tr><td>%s</td><td>%d (%.1f%%)</td><td>%d (%.1f%%)</td><td>%d (%.1f%%)</td><td>%d</td></tr>' % 
				(ext, source, source_pct, comments, comment_pct, blank, blank_pct, total))
		f.write('</table>')

		# Largest Files
		try:
			largest_files = data.getLargestFiles(15)
			if largest_files:
				f.write(html_header(2, 'Largest Files'))
				f.write('<table class="sortable" id="largest_files"><tr><th>File</th><th>Size (bytes)</th><th>Size (KB)</th></tr>')
				for filepath, size in largest_files:
					size_kb = size / 1024.0
					f.write('<tr><td>%s</td><td>%d</td><td>%.1f</td></tr>' % (filepath, size, size_kb))
				f.write('</table>')
		except (AttributeError, TypeError):
			pass

		# Files with Most Revisions (Hotspots)
		try:
			hotspot_files = data.getFilesWithMostRevisions(15)
			if hotspot_files:
				f.write(html_header(2, 'Files with Most Revisions (Hotspots)'))
				f.write('<table class="sortable" id="hotspot_files"><tr><th>File</th><th>Revisions</th><th>% of Total Commits</th></tr>')
				total_commits = data.getTotalCommits()
				for filepath, revisions in hotspot_files:
					revision_pct = (100.0 * revisions / total_commits) if total_commits else 0.0
					f.write('<tr><td>%s</td><td>%d</td><td>%.2f%%</td></tr>' % (filepath, revisions, revision_pct))
				f.write('</table>')
		except (AttributeError, TypeError):
			pass

		# Directory Activity
		try:
			active_directories = data.getDirectoriesByActivity(15)
			if active_directories:
				f.write(html_header(2, 'Most Active Directories'))
				f.write('<table class="sortable" id="active_directories"><tr><th>Directory</th><th>Total Lines Changed</th><th>Lines Added</th><th>Lines Removed</th><th>Files</th></tr>')
				for directory, total_lines, lines_added, lines_removed, file_count in active_directories:
					directory_display = directory if directory != '.' else '(root)'
					f.write('<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>' % (directory_display, total_lines, lines_added, lines_removed, file_count))
				f.write('</table>')
		except (AttributeError, TypeError):
			pass

		f.write('</div>  <!-- end files section -->')

		###
		# Lines section
		f.write('<div id="lines" class="section">')
		f.write(html_header(2, 'Lines'))

		f.write('<dl>\n')
		f.write('<dt>Total lines</dt><dd>%d</dd>' % data.getTotalLOC())
		f.write('<dt>Source lines</dt><dd>%d (%.1f%%)</dd>' % (
			data.getTotalSourceLines(), 
			(100.0 * data.getTotalSourceLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0
		))
		f.write('<dt>Comment lines</dt><dd>%d (%.1f%%)</dd>' % (
			data.getTotalCommentLines(),
			(100.0 * data.getTotalCommentLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0
		))
		f.write('<dt>Blank lines</dt><dd>%d (%.1f%%)</dd>' % (
			data.getTotalBlankLines(),
			(100.0 * data.getTotalBlankLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0
		))
		f.write('</dl>\n')

		f.write(html_header(2, 'Lines of Code'))
		f.write('<p>This table shows the total lines of code over time, including source code, comments, and blank lines.</p>')
		# Display lines of code data as table instead of chart
		if hasattr(self, 'table_data') and 'lines_of_code' in self.table_data:
			f.write(self.table_data['lines_of_code'])

		fg = open(path + '/lines_of_code.dat', 'w')
		for stamp in sorted(data.changes_by_date.keys()):
			fg.write('%d %d\n' % (stamp, data.changes_by_date[stamp]['lines']))
		fg.close()

		# Add yearly Lines of Code data
		f.write('<h3>Lines of Code - Yearly Data</h3>')
		lines_by_year_data = data.lines_added_by_year
		lines_removed_by_year_data = data.lines_removed_by_year
		
		if lines_by_year_data:
			f.write('<table class="sortable" id="lines_of_code_yearly">')
			f.write('<tr><th>Year</th><th>Lines Added</th><th>Lines Removed</th><th>Net Change</th><th>Growth Rate</th></tr>')
			
			years = sorted(set(list(lines_by_year_data.keys()) + list(lines_removed_by_year_data.keys())))
			prev_net = 0
			
			for year in years:
				lines_added = lines_by_year_data.get(year, 0)
				lines_removed = lines_removed_by_year_data.get(year, 0)
				net_change = lines_added - lines_removed
				
				if prev_net > 0:
					growth_rate = (100.0 * net_change / prev_net) if prev_net > 0 else 0.0
				else:
					growth_rate = 0.0
				
				f.write('<tr><td>%d</td><td>%d</td><td>%d</td><td>%+d</td><td>%.1f%%</td></tr>' % 
						(year, lines_added, lines_removed, net_change, growth_rate))
				prev_net = net_change if net_change > 0 else prev_net
			
			f.write('</table>')
		else:
			f.write('<p>No yearly lines of code data available.</p>')

		# Keep original detailed table for recent changes
		f.write('<h3>Recent Lines of Code Changes (Last 25 commits)</h3>')
		f.write('<table class="sortable" id="lines_of_code_table">')
		f.write('<tr><th>Date</th><th>Total Lines</th><th>Files Changed</th><th>Lines Added</th><th>Lines Removed</th><th>Net Change</th></tr>')
		
		# Show data from the changes_by_date dictionary (last 25 entries)
		sorted_changes = sorted(data.changes_by_date.items(), key=lambda x: x[0])[-25:]
		
		for stamp, change_data in sorted_changes:
			date_str = datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d')
			total_lines = change_data['lines']
			files_changed = change_data['files']
			lines_added = change_data['ins']
			lines_removed = change_data['del']
			net_change = lines_added - lines_removed
			
			f.write('<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%+d</td></tr>' % 
					(date_str, total_lines, files_changed, lines_added, lines_removed, net_change))
		f.write('</table>')

		# Add SLOC composition chart data
		f.write(html_header(2, 'Source Lines of Code (SLOC) Composition'))
		f.write('<p>Breakdown of code composition by file type and content type:</p>')
		sloc_data = data.getSLOCByExtension()
		if sloc_data:
			f.write('<table class="sortable" id="sloc_breakdown">')
			f.write('<tr><th>Extension</th><th>Source Lines</th><th>Comment Lines</th><th>Blank Lines</th><th>Total</th><th>Source %</th><th>Comment %</th></tr>')
			
			sorted_sloc = sorted(sloc_data.items(), key=lambda x: x[1]['total'], reverse=True)
			for ext, sloc_info in sorted_sloc[:15]:  # Top 15 extensions
				if sloc_info['total'] == 0:
					continue
				
				ext_display = ext if ext else '(no extension)'
				source_pct = (100.0 * sloc_info['source'] / sloc_info['total']) if sloc_info['total'] else 0.0
				comment_pct = (100.0 * sloc_info['comments'] / sloc_info['total']) if sloc_info['total'] else 0.0
				
				f.write('<tr>')
				f.write('<td>%s</td>' % ext_display)
				f.write('<td>%d</td>' % sloc_info['source'])
				f.write('<td>%d</td>' % sloc_info['comments'])
				f.write('<td>%d</td>' % sloc_info['blank'])
				f.write('<td>%d</td>' % sloc_info['total'])
				f.write('<td>%.1f%%</td>' % source_pct)
				f.write('<td>%.1f%%</td>' % comment_pct)
				f.write('</tr>')
			
			f.write('</table>')
		else:
			f.write('<p>No SLOC data available.</p>')

		f.write('</div>  <!-- end lines section -->')

		###
		# Tags section
		f.write('<div id="tags" class="section">')
		f.write(html_header(2, 'Tags'))

		f.write('<dl>')
		f.write('<dt>Total tags</dt><dd>%d</dd>' % len(data.tags))
		if len(data.tags) > 0:
			f.write('<dt>Average commits per tag</dt><dd>%.2f</dd>' % (1.0 * data.getTotalCommits() / len(data.tags)))
		f.write('</dl>')

		f.write('<table class="tags">')
		f.write('<tr><th>Name</th><th>Date</th><th>Commits</th><th>Authors</th></tr>')
		# sort the tags by date desc
		tags_sorted_by_date_desc = list(map(lambda el : el[1], reversed(sorted(map(lambda el : (el[1]['date'], el[0]), data.tags.items())))))
		for tag in tags_sorted_by_date_desc:
			authorinfo = []
			self.authors_by_commits = getkeyssortedbyvalues(data.tags[tag]['authors'])
			for i in reversed(self.authors_by_commits):
				authorinfo.append('%s (%d)' % (i, data.tags[tag]['authors'][i]))
			f.write('<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td></tr>' % (tag, data.tags[tag]['date'], data.tags[tag]['commits'], ', '.join(authorinfo)))
		f.write('</table>')
		f.write('</div>  <!-- end tags section -->')

		# Close the combined HTML file
		f.write('</body></html>')
		f.close()

		self.createTableData(path)
	
	def _generateAssessment(self, performance, patterns):
		"""Generate an objective, fact-based analysis for an author based on their metrics."""
		activity = performance.get('activity_score', 0)
		consistency = performance.get('consistency', 0)
		collaboration = performance.get('collaboration_score', 0)
		contribution = performance.get('contribution_percentage', 0)
		
		small_commits_ratio = patterns.get('small_commits', 0) / max(patterns.get('total_commits', 1), 1)
		large_commits_ratio = patterns.get('large_commits', 0) / max(patterns.get('total_commits', 1), 1)
		
		metrics = []
		
		# Contribution level (factual percentage)
		metrics.append(f"{contribution:.1f}% of total commits")
		
		# Activity patterns (factual description)
		if small_commits_ratio > 0.7:
			metrics.append(f"{small_commits_ratio*100:.0f}% small commits")
		elif large_commits_ratio > 0.3:
			metrics.append(f"{large_commits_ratio*100:.0f}% large commits")
		else:
			metrics.append("Balanced commit sizes")
		
		# Consistency metric (factual)
		if consistency >= 80:
			metrics.append(f"High consistency ({consistency:.0f}/100)")
		elif consistency >= 60:
			metrics.append(f"Moderate consistency ({consistency:.0f}/100)")
		else:
			metrics.append(f"Variable activity ({consistency:.0f}/100)")
		
		# Collaboration indicator (factual)
		if collaboration >= 70:
			metrics.append(f"Extensive collaboration ({collaboration:.0f}/100)")
		elif collaboration >= 50:
			metrics.append(f"Regular collaboration ({collaboration:.0f}/100)")
		else:
			metrics.append(f"Limited collaboration ({collaboration:.0f}/100)")
		
		return ", ".join(metrics) if metrics else "Standard activity pattern"
	
	def createTableData(self, path):
		print('Generating table data for reports...')
		
		# Initialize table data generator
		table_generator = TableDataGenerator()
		
		# Store table data for HTML generation
		self.table_data = {}
		
		# Change to the output directory
		old_dir = os.getcwd()
		os.chdir(path)
		
		try:
			# Generate table data for all chart types if their data files exist
			
			# hour of day
			if os.path.exists('hour_of_day.dat'):
				self.table_data['hour_of_day'] = table_generator.format_hour_of_day_data('hour_of_day.dat')
			
			# day of week
			if os.path.exists('day_of_week.dat'):
				self.table_data['day_of_week'] = table_generator.format_day_of_week_data('day_of_week.dat')
			
			# domains
			if os.path.exists('domains.dat'):
				self.table_data['domains'] = table_generator.format_domains_data('domains.dat')
			
			# month of year
			if os.path.exists('month_of_year.dat'):
				self.table_data['month_of_year'] = table_generator.format_month_of_year_data('month_of_year.dat')
			
			# commits by year-month
			if os.path.exists('commits_by_year_month.dat'):
				self.table_data['commits_by_year_month'] = table_generator.format_commits_by_year_month_data('commits_by_year_month.dat')
			
			# commits by year
			if os.path.exists('commits_by_year.dat'):
				self.table_data['commits_by_year'] = table_generator.format_commits_by_year_data('commits_by_year.dat')
			
			# files by date
			if os.path.exists('files_by_date.dat'):
				self.table_data['files_by_date'] = table_generator.format_files_by_date_data('files_by_date.dat')
			
			# files by year
			if os.path.exists('files_by_year.dat'):
				self.table_data['files_by_year'] = table_generator.format_files_by_year_data('files_by_year.dat')
			
			# lines of code
			if os.path.exists('lines_of_code.dat'):
				self.table_data['lines_of_code'] = table_generator.format_lines_of_code_data('lines_of_code.dat')
			
			# lines of code by author
			if os.path.exists('lines_of_code_by_author.dat') and hasattr(self, 'authors_to_plot'):
				self.table_data['lines_of_code_by_author'] = table_generator.format_lines_of_code_by_author_data('lines_of_code_by_author.dat', self.authors_to_plot)
			
			# commits by author
			if os.path.exists('commits_by_author.dat') and hasattr(self, 'authors_to_plot'):
				self.table_data['commits_by_author'] = table_generator.format_commits_by_author_data('commits_by_author.dat', self.authors_to_plot)
			
			# pace of changes
			if os.path.exists('pace_of_changes.dat'):
				self.table_data['pace_of_changes'] = table_generator.format_pace_of_changes_data('pace_of_changes.dat')
				
		except Exception as e:
			print(f"Warning: Error generating table data: {e}")
			if conf.get('debug', False):
				import traceback
				traceback.print_exc()
		finally:
			# Always restore the original directory
			os.chdir(old_dir)

	def printHeader(self, f, title = ''):
		f.write(
"""<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8">
	<title>GitStats - %s</title>
	<link rel="stylesheet" href="%s" type="text/css">
	<meta name="generator" content="GitStats %s">
	<script type="text/javascript" src="sortable.js"></script>
</head>
<body>
""" % (self.title, conf['style'], getversion()))

	def printCombinedHeader(self, f):
		# Read CSS content
		css_content = ""
		binarypath = os.path.dirname(os.path.abspath(__file__))
		css_path = os.path.join(binarypath, 'gitstats.css')
		try:
			with open(css_path, 'r') as css_file:
				css_content = css_file.read()
				# Escape % characters to prevent string formatting issues
				css_content = css_content.replace('%', '%%')
		except FileNotFoundError:
			print(f'Warning: CSS file not found at {css_path}')

		# Read JavaScript content  
		js_content = ""
		js_path = os.path.join(binarypath, 'sortable.js')
		try:
			with open(js_path, 'r') as js_file:
				js_content = js_file.read()
				# Escape % characters to prevent string formatting issues
				js_content = js_content.replace('%', '%%')
		except FileNotFoundError:
			print(f'Warning: JavaScript file not found at {js_path}')

		f.write(
"""<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8">
	<title>GitStats - %s</title>
	<meta name="generator" content="GitStats %s">
	<style type="text/css">
%s
	.section {
		margin-bottom: 2em;
	}
	
	/* Print styles - ensure everything prints including backgrounds */
	@media print {
		* {
			-webkit-print-color-adjust: exact !important;
			color-adjust: exact !important;
			print-color-adjust: exact !important;
		}
		
		body {
			background-color: #dfd !important;
			color: black !important;
		}
		
		table {
			border: 1px solid black !important;
			border-collapse: collapse !important;
			page-break-inside: avoid;
		}
		
		td, th {
			border: 1px solid black !important;
			padding: 0.2em !important;
			background-color: white !important;
		}
		
		th {
			background-color: #ddf !important;
		}
		
		tr:hover {
			background-color: #ddf !important;
		}
		
		h2 {
			background-color: #564 !important;
			border: 1px solid black !important;
			color: white !important;
			page-break-after: avoid;
		}
		
		.nav {
			border-bottom: 1px solid black !important;
			background-color: #dfd !important;
		}
		
		.nav li a {
			background-color: #ddf !important;
			border: 1px solid black !important;
			color: black !important;
		}
		
		/* Preserve colored table cells */
		td[style*="background-color"] {
			-webkit-print-color-adjust: exact !important;
			color-adjust: exact !important;
			print-color-adjust: exact !important;
		}
		
		/* Branch-specific styles for printing */
		.branches tr.unmerged {
			background-color: #ffd0d0 !important;
		}
		
		.unmerged-branches {
			border: 2px solid #ff6666 !important;
		}
		
		.unmerged-branches th {
			background-color: #ffcccc !important;
		}
		
		/* Team performance tables */
		.team-performance th {
			background-color: #564 !important;
			color: white !important;
		}
		
		.working-patterns th {
			background-color: #446 !important;
			color: white !important;
		}
		
		.impact-analysis th {
			background-color: #644 !important;
			color: white !important;
		}
		
		.collaboration th {
			background-color: #464 !important;
			color: white !important;
		}
		
		/* Highlight high performers */
		tr.high-performer {
			background-color: #e6ffe6 !important;
		}
		
		/* Highlight concerning patterns */
		tr.concern {
			background-color: #ffe6e6 !important;
		}
		
		/* Preserve chart bar colors */
		div[style*="background-color: red"] {
			background-color: red !important;
			-webkit-print-color-adjust: exact !important;
			color-adjust: exact !important;
			print-color-adjust: exact !important;
		}
		
		/* Images should fit on page */
		img {
			max-width: 100%% !important;
			height: auto !important;
		}
		
		/* Ensure sections start on new page if needed */
		.section {
			page-break-before: auto;
			margin-bottom: 2em !important;
		}
		
		/* Prevent page breaks inside important elements */
		table, .section h2, dl {
			page-break-inside: avoid;
		}
	}
	
	/* Enhanced Project Health Dashboard Styles */
	#project_health {
		background: linear-gradient(135deg, #f8f9fa 0%%, #e9ecef 100%%);
		border: 2px solid #dee2e6;
		border-radius: 10px;
		padding: 20px;
		margin: 20px 0;
		box-shadow: 0 4px 6px rgba(0,0,0,0.1);
	}
	
	#project_health h2 {
		background: linear-gradient(135deg, #28a745 0%%, #20c997 100%%);
		color: white;
		text-align: center;
		margin: -20px -20px 20px -20px;
		padding: 15px;
		border-radius: 8px 8px 0 0;
		border: none;
	}
	
	#project_health h3 {
		color: #495057;
		border-bottom: 2px solid #dee2e6;
		padding-bottom: 5px;
		margin-top: 25px;
	}
	
	#project_health dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 10px 20px;
		margin-bottom: 20px;
	}
	
	#project_health dt {
		font-weight: bold;
		color: #495057;
		align-self: center;
	}
	
	#project_health dd {
		margin: 0;
		padding: 8px 12px;
		background-color: white;
		border: 1px solid #dee2e6;
		border-radius: 5px;
		align-self: center;
	}
	
	#project_health .health-score {
		font-size: 1.2em;
		font-weight: bold;
	}
	
	#project_health .risk-high {
		background-color: #f8d7da;
		border-color: #f1aeb5;
		color: #721c24;
	}
	
	#project_health .risk-medium {
		background-color: #fff3cd;
		border-color: #ffeaa7;
		color: #856404;
	}
	
	#project_health .risk-low {
		background-color: #d1edff;
		border-color: #bee5eb;
		color: #0c5460;
	}
	
	#project_health ul {
		list-style-type: none;
		padding: 0;
	}
	
	#project_health li {
		background-color: #fff3cd;
		border: 1px solid #ffeaa7;
		border-radius: 5px;
		padding: 10px;
		margin-bottom: 8px;
		position: relative;
		padding-left: 35px;
	}
	
	#project_health li:before {
		content: "⚠";
		position: absolute;
		left: 10px;
		color: #856404;
		font-weight: bold;
	}
	</style>
	<script type="text/javascript">
%s
	</script>
</head>
<body>
""" % (self.title, getversion(), css_content, js_content))

	def printCombinedNav(self, f):
		f.write("""
<div class="nav">
<ul>
<li><a href="#general">General</a></li>
<li><a href="#project_health">Project Health</a></li>
<li><a href="#activity">Activity</a></li>
<li><a href="#authors">Authors</a></li>
<li><a href="#team_analysis">Team Analysis</a></li>
<li><a href="#branches">Branches</a></li>
<li><a href="#files">Files</a></li>
<li><a href="#lines">Lines</a></li>
<li><a href="#tags">Tags</a></li>
</ul>
</div>
""")

	def printNav(self, f):
		f.write("""
<div class="nav">
<ul>
<li><a href="index.html">General</a></li>
<li><a href="activity.html">Activity</a></li>
<li><a href="authors.html">Authors</a></li>
<li><a href="team_analysis.html">Team Analysis</a></li>
<li><a href="branches.html">Branches</a></li>
<li><a href="files.html">Files</a></li>
<li><a href="lines.html">Lines</a></li>
<li><a href="tags.html">Tags</a></li>
</ul>
</div>
""")

def _is_bare_repository(path):
	"""Check if the directory is a bare git repository."""
	try:
		# Bare repositories have objects and refs directories directly
		objects_dir = os.path.join(path, 'objects')
		refs_dir = os.path.join(path, 'refs')
		head_file = os.path.join(path, 'HEAD')
		
		if not (os.path.exists(objects_dir) and os.path.exists(refs_dir) and os.path.exists(head_file)):
			return False
		
		# Additional check: try to run git command to confirm it's a bare repo
		try:
			result = getpipeoutput([f'cd "{path}" && git rev-parse --is-bare-repository'], quiet=True)
			return result.strip().lower() == 'true'
		except:
			return False
			
	except (OSError, PermissionError):
		return False
	
	return True

def discover_repositories(scan_path, recursive=False, max_depth=10, include_patterns=None, exclude_patterns=None):
	"""Discover all git repositories in a directory with advanced options and concurrent scanning.
	
	Args:
		scan_path: Directory to scan for repositories
		recursive: If True, scan subdirectories recursively
		max_depth: Maximum depth for recursive scanning (default: 3)
		include_patterns: List of glob patterns for directories to include
		exclude_patterns: List of glob patterns for directories to exclude
	
	Returns:
		List of tuples: (repo_name, repo_path, repo_type)
		where repo_type is 'regular', 'bare', or 'worktree'
	"""
	repositories = []
	
	if not os.path.exists(scan_path):
		print(f'Warning: Scan path does not exist: {scan_path}')
		return repositories
	
	if not os.path.isdir(scan_path):
		print(f'Warning: Scan path is not a directory: {scan_path}')
		return repositories
	
	# Set default patterns if not provided
	if exclude_patterns is None:
		exclude_patterns = [
			'.*',  # Hidden directories
			'node_modules', 
			'venv', 
			'__pycache__',
			'build',
			'dist',
			'target',  # Maven/Gradle build dirs
			'bin',
			'obj'      # .NET build dirs
		]
	
	# Use fast concurrent scanning if enabled
	if conf.get('multi_repo_fast_scan', True) and recursive:
		return _discover_repositories_concurrent(scan_path, max_depth, include_patterns, exclude_patterns)
	
	# Fallback to original sequential scanning
	
	def _should_exclude_directory(dir_name, dir_path):
		"""Check if directory should be excluded based on patterns."""
		import fnmatch
		
		# Check exclude patterns
		for pattern in exclude_patterns:
			if fnmatch.fnmatch(dir_name, pattern):
				return True
		
		# Check include patterns (if specified, directory must match at least one)
		if include_patterns:
			for pattern in include_patterns:
				if fnmatch.fnmatch(dir_name, pattern):
					return False
			return True  # No include pattern matched
		
		return False
	
	def _determine_repo_type(repo_path):
		"""Determine the type of git repository."""
		git_dir = os.path.join(repo_path, '.git')
		
		if os.path.isdir(git_dir):
			return 'regular'
		elif os.path.isfile(git_dir):
			return 'worktree'
		elif _is_bare_repository(repo_path):
			return 'bare'
		else:
			return 'unknown'
	
	def _scan_directory(current_path, current_depth=0):
		"""Recursively scan directory for git repositories."""
		if current_depth > max_depth:
			return
		
		try:
			# Get list of items, handle permission errors gracefully
			try:
				items = os.listdir(current_path)
			except PermissionError:
				if conf['verbose']:
					print(f'  Permission denied accessing: {current_path}')
				return
			except OSError as e:
				if conf['verbose']:
					print(f'  Error accessing {current_path}: {e}')
				return
			
			# Check if current directory is a git repository
			if is_git_repository(current_path):
				repo_name = os.path.basename(current_path)
				repo_type = _determine_repo_type(current_path)
				repositories.append((repo_name, current_path, repo_type))
				
				if conf['verbose']:
					print(f'  Found {repo_type} repository: {repo_name} at {current_path}')
				
				# Don't scan inside git repositories to avoid nested repos
				return
			
			# If recursive scanning is enabled, scan subdirectories
			if recursive:
				for item in sorted(items):  # Sort for consistent ordering
					item_path = os.path.join(current_path, item)
					
					# Skip if not a directory or if it's a symbolic link to avoid loops
					if not os.path.isdir(item_path):
						continue
					
					# Handle symbolic links carefully to avoid infinite loops
					if os.path.islink(item_path):
						try:
							# Resolve the link and check if it points outside scan_path
							real_item_path = os.path.realpath(item_path)
							scan_real_path = os.path.realpath(scan_path)
							
							# Skip if symlink points outside the scan directory
							if not real_item_path.startswith(scan_real_path):
								if conf['debug']:
									print(f'  Skipping symlink pointing outside scan path: {item_path}')
								continue
								
							# Skip if we've already seen this real path (circular symlinks)
							if real_item_path in seen_paths:
								if conf['debug']:
									print(f'  Skipping circular symlink: {item_path}')
								continue
							seen_paths.add(real_item_path)
							
						except (OSError, ValueError):
							if conf['debug']:
								print(f'  Skipping invalid symlink: {item_path}')
							continue
					
					# Check exclusion patterns
					if _should_exclude_directory(item, item_path):
						if conf['debug']:
							print(f'  Excluding directory: {item_path}')
						continue
					
					# Recursively scan subdirectory
					_scan_directory(item_path, current_depth + 1)
			
		except Exception as e:
			if conf['verbose']:
				print(f'  Error scanning {current_path}: {e}')
	
	# Keep track of seen paths to handle symbolic links
	seen_paths = set()
	seen_paths.add(os.path.realpath(scan_path))
	
	if conf['verbose']:
		print(f'Scanning for repositories in: {scan_path}')
		print(f'  Recursive: {recursive}')
		print(f'  Max depth: {max_depth}')
		if include_patterns:
			print(f'  Include patterns: {include_patterns}')
		if exclude_patterns:
			print(f'  Exclude patterns: {exclude_patterns}')
	
	# Start scanning
	_scan_directory(scan_path)
	
	if conf['verbose']:
		print(f'Repository discovery complete. Found {len(repositories)} repositories.')
	
	return repositories

def _discover_repositories_concurrent(scan_path, max_depth=10, include_patterns=None, exclude_patterns=None):
	"""Fast concurrent repository discovery using ThreadPoolExecutor."""
	repositories = []
	repositories_lock = threading.Lock()
	
	# Set default patterns
	if exclude_patterns is None:
		exclude_patterns = [
			'.*', 'node_modules', 'venv', '__pycache__',
			'build', 'dist', 'target', 'bin', 'obj'
		]
	
	def _should_exclude_directory(dir_name, dir_path):
		"""Check if directory should be excluded based on patterns."""
		import fnmatch
		
		for pattern in exclude_patterns:
			if fnmatch.fnmatch(dir_name, pattern):
				return True
		
		if include_patterns:
			for pattern in include_patterns:
				if fnmatch.fnmatch(dir_name, pattern):
					return False
			return True
		
		return False
	
	def _determine_repo_type(repo_path):
		"""Determine the type of git repository."""
		git_dir = os.path.join(repo_path, '.git')
		
		if os.path.isdir(git_dir):
			return 'regular'
		elif os.path.isfile(git_dir):
			return 'worktree'
		elif _is_bare_repository(repo_path):
			return 'bare'
		else:
			return 'unknown'
	
	def _scan_directory_concurrent(path_depth_tuple):
		"""Thread-safe directory scanning function."""
		current_path, current_depth = path_depth_tuple
		
		if current_depth > max_depth:
			return []
		
		local_repos = []
		
		try:
			# Handle permission errors gracefully
			try:
				items = os.listdir(current_path)
			except (PermissionError, OSError) as e:
				if conf['verbose']:
					print(f'  Permission/access error: {current_path}: {e}')
				return []
			
			# Check if current directory is a git repository
			if is_git_repository(current_path):
				repo_name = os.path.basename(current_path)
				repo_type = _determine_repo_type(current_path)
				local_repos.append((repo_name, current_path, repo_type))
				
				if conf['verbose']:
					print(f'  Found {repo_type} repository: {repo_name}')
				
				# Don't scan inside git repositories
				return local_repos
			
			# Collect subdirectories to scan
			subdirs_to_scan = []
			for item in sorted(items):
				item_path = os.path.join(current_path, item)
				
				if not os.path.isdir(item_path):
					continue
				
				# Handle symlinks carefully
				if os.path.islink(item_path):
					try:
						real_path = os.path.realpath(item_path)
						scan_real_path = os.path.realpath(scan_path)
						
						if not real_path.startswith(scan_real_path):
							continue
					except (OSError, ValueError):
						continue
				
				# Check exclusion patterns
				if _should_exclude_directory(item, item_path):
					if conf['debug']:
						print(f'  Excluding: {item_path}')
					continue
				
				subdirs_to_scan.append((item_path, current_depth + 1))
			
			# Recursively scan subdirectories (will be handled by thread pool)
			return subdirs_to_scan
			
		except Exception as e:
			if conf['verbose']:
				print(f'  Error scanning {current_path}: {e}')
			return []
	
	if conf['verbose']:
		print(f'Starting concurrent repository discovery in: {scan_path}')
		print(f'  Max depth: {max_depth}')
		print(f'  Max workers: {min(conf["multi_repo_max_workers"], 8)}')
	
	# Use ThreadPoolExecutor for I/O bound directory scanning
	max_workers = min(conf.get('multi_repo_max_workers', 4), 8)  # Cap at 8 threads
	
	# Queue of directories to scan
	dirs_to_scan = queue.Queue()
	dirs_to_scan.put((scan_path, 0))
	
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		# Keep track of active futures
		active_futures = set()
		
		while not dirs_to_scan.empty() or active_futures:
			# Submit new tasks if we have directories to scan and available workers
			while not dirs_to_scan.empty() and len(active_futures) < max_workers:
				path_depth = dirs_to_scan.get()
				future = executor.submit(_scan_directory_concurrent, path_depth)
				active_futures.add(future)
			
			# Check completed futures
			completed_futures = set()
			for future in active_futures:
				if future.done():
					completed_futures.add(future)
					try:
						result = future.result()
						
						# Result can be either repositories or subdirectories to scan
						for item in result:
							if len(item) == 3:  # It's a repository (name, path, type)
								with repositories_lock:
									repositories.append(item)
							elif len(item) == 2:  # It's a directory to scan (path, depth)
								dirs_to_scan.put(item)
					except Exception as e:
						if conf['verbose']:
							print(f'  Error in scanning task: {e}')
			
			# Remove completed futures
			active_futures -= completed_futures
			
			# Small delay to prevent busy waiting
			if active_futures:
				import time
				time.sleep(0.001)
	
	if conf['verbose']:
		print(f'Concurrent repository discovery complete. Found {len(repositories)} repositories.')
	
	return repositories

def usage():
	print("""
Usage: gitstats [options] <gitpath..> <outputpath>
       gitstats [options] --multi-repo <scan-folder> <outputpath>

Options:
-c key=value     Override configuration value
--debug          Enable debug output
--verbose        Enable verbose output
--multi-repo     Scan folder recursively for multiple repositories and generate reports for each
-h, --help       Show this help message

Note: GitStats generates HTML reports with charts and detailed statistics.

Examples:
  gitstats repo output                    # Generates HTML report
  gitstats --verbose repo output          # With verbose output
  gitstats --multi-repo /path/to/repos output  # Generate reports for all repos found recursively
  gitstats --debug -c max_authors=50 repo output
  
  # Multi-repo with configuration options:
  gitstats -c multi_repo_max_depth=5 --multi-repo /path/to/repos output
  gitstats -c multi_repo_include_patterns=proj*,app* --multi-repo /path/to/repos output

With --multi-repo mode:
- Recursively scans the specified folder and all subdirectories for git repositories
- Creates a report for each repository in a subfolder named <reponame>_report
- Only processes directories that are valid git repositories
- Generates a summary report with links to all individual reports
- Default maximum scan depth is 3 levels (configurable)

Multi-repo configuration options (use with -c key=value):
  multi_repo_max_depth=N               # Maximum depth for recursive scanning (default: 10)
  multi_repo_include_patterns=pat1,pat2 # Comma-separated glob patterns for directories to include
  multi_repo_exclude_patterns=pat1,pat2 # Comma-separated glob patterns for directories to exclude
  multi_repo_timeout=N                 # Timeout in seconds per repository (default: 3600)
  multi_repo_cleanup_on_error=True/False # Clean up partial output on error (default: True)
  multi_repo_parallel=True/False       # Enable parallel processing (default: True)
  multi_repo_max_workers=N             # Maximum parallel workers (default: 4)
  multi_repo_fast_scan=True/False      # Enable concurrent repository discovery (default: True)
  multi_repo_batch_size=N              # Process repositories in batches (default: 10)
  multi_repo_progress_interval=N       # Progress update interval in seconds (default: 5)

File extension filtering options (use with -c key=value):
  filter_by_extensions=True/False      # Enable/disable file extension filtering (default: True)
  allowed_extensions=.py,.js,.java    # Comma-separated list of allowed extensions (default: see below)

Maintainability Index (MI) calculation options (use with -c key=value):
  calculate_mi_per_repository=True/False # Enable/disable per-repository MI calculation (default: True)
  
Note about MI Calculation:
- When enabled, GitStats scans each repository for files matching 'allowed_extensions'
- Calculates comprehensive metrics including Lines of Code, Halstead, and McCabe complexity
- Computes Maintainability Index (MI) for each file and displays summary
- Outputs found files in CLI and their MI scores for transparency
- MI results are included in the generated HTML reports

Default config values:
%s

Default multi-repo exclude patterns:
  .* (hidden dirs), node_modules, venv, __pycache__, build, dist, target, bin, obj

Please see the manual page for more details.
""" % conf)


class GitStats:
	def run(self, args_orig):
		multi_repo_mode = False
		optlist, args = getopt.getopt(args_orig, 'hc:', ["help", "debug", "verbose", "multi-repo"])
		for o,v in optlist:
			if o == '-c':
				if '=' not in v:
					print(f'FATAL: Invalid configuration format. Use key=value: {v}')
					sys.exit(1)
				key, value = v.split('=', 1)
				if key not in conf:
					raise KeyError('no such key "%s" in config' % key)
				
				# Validate configuration values
				try:
					if isinstance(conf[key], bool):
						conf[key] = value.lower() in ('true', '1', 'yes', 'on')
					elif isinstance(conf[key], int):
						new_value = int(value)
						if key in ['max_authors', 'max_domains'] and new_value < 1:
							print(f'FATAL: {key} must be at least 1, got: {new_value}')
							sys.exit(1)
						conf[key] = new_value
					elif key.endswith('_patterns') and value:
						# Handle comma-separated patterns
						conf[key] = [pattern.strip() for pattern in value.split(',') if pattern.strip()]
					elif key == 'allowed_extensions' and value:
						# Handle comma-separated extensions, ensure they start with '.'
						extensions = []
						for ext in value.split(','):
							ext = ext.strip()
							if ext and not ext.startswith('.'):
								ext = '.' + ext
							if ext:
								extensions.append(ext)
						conf[key] = set(extensions)
					else:
						conf[key] = value
				except ValueError as e:
					print(f'FATAL: Invalid value for {key}: {value} ({e})')
					sys.exit(1)
			elif o == '--debug':
				conf['debug'] = True
				conf['verbose'] = True  # Debug implies verbose
			elif o == '--verbose':
				conf['verbose'] = True
			elif o == '--multi-repo':
				multi_repo_mode = True
			elif o in ('-h', '--help'):
				usage()
				sys.exit()

		if multi_repo_mode:
			if len(args) != 2:
				print('FATAL: --multi-repo requires exactly two arguments: <scan-folder> <outputpath>')
				usage()
				sys.exit(1)
			
			scan_folder = os.path.abspath(args[0])
			outputpath = os.path.abspath(args[1])
			
			# Enhanced validation of scan folder
			if not os.path.exists(scan_folder):
				print(f'FATAL: Scan folder does not exist: {scan_folder}')
				sys.exit(1)
			if not os.path.isdir(scan_folder):
				print(f'FATAL: Scan folder is not a directory: {scan_folder}')
				sys.exit(1)
			if not os.access(scan_folder, os.R_OK):
				print(f'FATAL: No read permission for scan folder: {scan_folder}')
				sys.exit(1)
			
			# Check for multi-repo configuration options
			max_depth = conf.get('multi_repo_max_depth', 10)
			include_patterns = conf.get('multi_repo_include_patterns', None)
			exclude_patterns = conf.get('multi_repo_exclude_patterns', None)
			
			# Discover repositories with recursive scanning always enabled
			print(f'Scanning folder recursively for git repositories: {scan_folder}')
			print(f'  Maximum scanning depth: {max_depth}')
			
			try:
				repositories = discover_repositories(
					scan_folder, 
					recursive=True,  # Always use recursive scanning
					max_depth=max_depth,
					include_patterns=include_patterns,
					exclude_patterns=exclude_patterns
				)
			except Exception as e:
				print(f'FATAL: Error during repository discovery: {e}')
				if conf['debug']:
					import traceback
					traceback.print_exc()
				sys.exit(1)
			
			if not repositories:
				print(f'No git repositories found in: {scan_folder}')
				print(f'Searched recursively up to depth {max_depth}')
				sys.exit(0)
			
			print(f'Found {len(repositories)} git repositories:')
			for repo_name, repo_path, repo_type in repositories:
				type_indicator = f' ({repo_type})' if repo_type != 'regular' else ''
				print(f'  - {repo_name}{type_indicator}')
			
			# Generate reports for each repository
			self.run_multi_repo(repositories, outputpath)
		else:
			# Original single/multiple repository mode
			if len(args) < 2:
				usage()
				sys.exit(0)
			
			self.run_single_mode(args)
	
	def run_multi_repo(self, repositories, base_outputpath):
		"""Generate reports for multiple repositories with enhanced error handling."""
		rundir = os.getcwd()
		
		# Validate and create base output directory
		try:
			os.makedirs(base_outputpath, exist_ok=True)
		except PermissionError:
			print(f'FATAL: Permission denied creating output directory: {base_outputpath}')
			sys.exit(1)
		except OSError as e:
			print(f'FATAL: Error creating output directory {base_outputpath}: {e}')
			sys.exit(1)
		
		if not os.path.isdir(base_outputpath):
			print('FATAL: Output path is not a directory or does not exist')
			sys.exit(1)
		
		# Check write permissions
		if not os.access(base_outputpath, os.W_OK):
			print(f'FATAL: No write permission for output directory: {base_outputpath}')
			sys.exit(1)

		# Using table-based output format (no matplotlib required)
		if conf['verbose']:
			print('Using table-based output format for all visualizations')

		if conf['verbose']:
			print('Multi-repo Configuration:')
			for key, value in conf.items():
				if key.startswith('multi_repo') or key in ['verbose', 'debug', 'processes']:
					print(f'  {key}: {value}')
			print()

		print(f'Base output path: {base_outputpath}')
		
		successful_reports = 0
		failed_reports = []
		skipped_repos = []
		total_start_time = time.time()
		
		# Pre-validate all repositories before processing
		print('Pre-validating repositories...')
		validated_repos = []
		for repo_data in repositories:
			if len(repo_data) == 3:
				repo_name, repo_path, repo_type = repo_data
			else:
				# Handle old format for backward compatibility
				repo_name, repo_path = repo_data[:2]
				repo_type = 'regular'
			
			# Validate repository accessibility
			if not self._validate_repository_access(repo_name, repo_path):
				skipped_repos.append((repo_name, 'Repository validation failed'))
				continue
			
			validated_repos.append((repo_name, repo_path, repo_type))
		
		if skipped_repos:
			print(f'Skipping {len(skipped_repos)} invalid repositories:')
			for repo_name, reason in skipped_repos:
				print(f'  - {repo_name}: {reason}')
		
		if not validated_repos:
			print('FATAL: No valid repositories to process')
			sys.exit(1)
		
		print(f'Processing {len(validated_repos)} validated repositories...')
		
		# Determine if we should use parallel processing
		use_parallel = (conf.get('multi_repo_parallel', True) and 
						len(validated_repos) > 1 and 
						conf.get('multi_repo_max_workers', 4) > 1)
		
		if use_parallel:
			successful_reports, failed_reports = self._process_repositories_parallel(
				validated_repos, base_outputpath, rundir)
		else:
			# Sequential processing (original approach)
			for i, (repo_name, repo_path, repo_type) in enumerate(validated_repos, 1):
				repo_start_time = time.time()
				print(f'\n{"="*60}')
				print(f'Processing repository {i}/{len(validated_repos)}: {repo_name}')
				print(f'Repository path: {repo_path}')
				print(f'Repository type: {repo_type}')
				
				# Create repository-specific output directory with safe naming
				safe_repo_name = self._sanitize_filename(repo_name)
				repo_output_path = os.path.join(base_outputpath, f'{safe_repo_name}_report')
				
				try:
					# Create output directory
					os.makedirs(repo_output_path, exist_ok=True)
					if not os.access(repo_output_path, os.W_OK):
						raise PermissionError(f'No write permission for {repo_output_path}')
					
					print(f'Report output path: {repo_output_path}')
					
					# Process this repository with timeout protection
					self._process_single_repository_safe(repo_path, repo_output_path, rundir, repo_name)
					
					repo_time = time.time() - repo_start_time
					successful_reports += 1
					print(f'✓ Successfully generated report for {repo_name} in {repo_time:.2f}s')
					
				except KeyboardInterrupt:
					print(f'\n✗ Interrupted while processing {repo_name}')
					failed_reports.append((repo_name, 'Processing interrupted by user'))
					break
				except Exception as e:
					repo_time = time.time() - repo_start_time
					error_msg = str(e)
					failed_reports.append((repo_name, error_msg))
					print(f'✗ Failed to generate report for {repo_name} after {repo_time:.2f}s: {error_msg}')
					if conf['debug']:
						import traceback
						traceback.print_exc()
					
					# Try to clean up partial output
					try:
						if os.path.exists(repo_output_path):
							import shutil
							shutil.rmtree(repo_output_path)
							if conf['verbose']:
								print(f'  Cleaned up partial output directory: {repo_output_path}')
					except Exception as cleanup_error:
						if conf['debug']:
							print(f'  Warning: Could not clean up {repo_output_path}: {cleanup_error}')
		
		# Generate summary report
		total_time = time.time() - total_start_time
		self._generate_multi_repo_summary(base_outputpath, validated_repos, successful_reports, 
										 failed_reports, skipped_repos, total_time)
		
		# Final summary
		print(f'\n{"="*60}')
		print(f'Multi-repository report generation complete in {total_time:.2f}s!')
		print(f'Successfully processed: {successful_reports}/{len(validated_repos)} repositories')
		
		if skipped_repos:
			print(f'Skipped repositories: {len(skipped_repos)}')
		
		if failed_reports:
			print(f'\nFailed repositories:')
			for repo_name, error in failed_reports:
				print(f'  - {repo_name}: {error}')
		
		if successful_reports > 0:
			print(f'\nReports generated in: {base_outputpath}')
			print('Repository reports:')
			for repo_name, repo_path, repo_type in validated_repos:
				safe_repo_name = self._sanitize_filename(repo_name)
				if not any(repo_name == failed[0] for failed in failed_reports):
					report_path = os.path.join(base_outputpath, f'{safe_repo_name}_report')
					print(f'  - {repo_name}: {report_path}/index.html')
			
			summary_path = os.path.join(base_outputpath, 'multi_repo_summary.html')
			if os.path.exists(summary_path):
				print(f'\nSummary report: {summary_path}')
	
	def _validate_repository_access(self, repo_name, repo_path):
		"""Validate that a repository is accessible and can be processed."""
		try:
			# Check basic path validity
			if not os.path.exists(repo_path):
				if conf['verbose']:
					print(f'  Repository path does not exist: {repo_path}')
				return False
			
			if not os.path.isdir(repo_path):
				if conf['verbose']:
					print(f'  Repository path is not a directory: {repo_path}')
				return False
			
			# Check read permissions
			if not os.access(repo_path, os.R_OK):
				if conf['verbose']:
					print(f'  No read permission for repository: {repo_path}')
				return False
			
			# Validate it's a proper git repository
			if not is_git_repository(repo_path):
				if conf['verbose']:
					print(f'  Not a valid git repository: {repo_path}')
				return False
			
			# Try to access the repository with git
			prev_dir = os.getcwd()
			try:
				os.chdir(repo_path)
				# Try a simple git command to ensure the repo is accessible
				result = getpipeoutput(['git rev-parse --git-dir'], quiet=True)
				if not result.strip():
					if conf['verbose']:
						print(f'  Git repository appears to be corrupted: {repo_path}')
					return False
			except Exception as e:
				if conf['verbose']:
					print(f'  Error accessing git repository {repo_path}: {e}')
				return False
			finally:
				os.chdir(prev_dir)
			
			return True
			
		except Exception as e:
			if conf['verbose']:
				print(f'  Error validating repository {repo_name}: {e}')
			return False
	
	def _sanitize_filename(self, filename):
		"""Sanitize a filename to be safe for filesystem use."""
		import re
		# Replace any characters that might be problematic in filenames
		safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
		# Remove any leading/trailing dots or spaces
		safe_name = safe_name.strip('. ')
		# Ensure it's not empty
		if not safe_name:
			safe_name = 'unnamed_repo'
		return safe_name
	
	def _process_single_repository_safe(self, repo_path, output_path, rundir, repo_name):
		"""Process a single repository with additional safety measures."""
		try:
			self.process_single_repository(repo_path, output_path, rundir)
		except KeyboardInterrupt:
			# Re-raise keyboard interrupt to allow proper cleanup
			raise
		except Exception as e:
			# Enhance error message with repository context
			enhanced_error = f"Error processing {repo_name}: {str(e)}"
			raise Exception(enhanced_error) from e
	
	def _generate_multi_repo_summary(self, base_outputpath, repositories, successful_count, 
									failed_reports, skipped_repos, total_time):
		"""Generate a summary HTML report for multi-repository processing."""
		try:
			summary_file = os.path.join(base_outputpath, 'multi_repo_summary.html')
			
			with open(summary_file, 'w') as f:
				f.write('<!DOCTYPE html>\n<html>\n<head>\n')
				f.write('<meta charset="UTF-8">\n')
				f.write('<title>Multi-Repository Summary</title>\n')
				f.write('<style>\n')
				f.write('body { font-family: Arial, sans-serif; margin: 20px; }\n')
				f.write('table { border-collapse: collapse; width: 100%; }\n')
				f.write('th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n')
				f.write('th { background-color: #f2f2f2; }\n')
				f.write('.success { color: green; }\n')
				f.write('.failure { color: red; }\n')
				f.write('.skipped { color: orange; }\n')
				f.write('</style>\n')
				f.write('</head>\n<body>\n')
				
				f.write('<h1>Multi-Repository Analysis Summary</h1>\n')
				f.write(f'<p>Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>\n')
				f.write(f'<p>Total processing time: {total_time:.2f} seconds</p>\n')
				
				# Summary statistics
				f.write('<h2>Summary Statistics</h2>\n')
				f.write('<ul>\n')
				f.write(f'<li>Total repositories found: {len(repositories)}</li>\n')
				f.write(f'<li class="success">Successfully processed: {successful_count}</li>\n')
				f.write(f'<li class="failure">Failed: {len(failed_reports)}</li>\n')
				f.write(f'<li class="skipped">Skipped: {len(skipped_repos)}</li>\n')
				f.write('</ul>\n')
				
				# Repository table
				f.write('<h2>Repository Details</h2>\n')
				f.write('<table>\n')
				f.write('<tr><th>Repository</th><th>Type</th><th>Status</th><th>Report Link</th></tr>\n')
				
				# Successful repositories
				for repo_name, repo_path, repo_type in repositories:
					if not any(repo_name == failed[0] for failed in failed_reports):
						safe_repo_name = self._sanitize_filename(repo_name)
						report_link = f'{safe_repo_name}_report/index.html'
						f.write(f'<tr><td>{repo_name}</td><td>{repo_type}</td>')
						f.write(f'<td class="success">Success</td>')
						f.write(f'<td><a href="{report_link}">View Report</a></td></tr>\n')
				
				# Failed repositories
				for repo_name, error in failed_reports:
					f.write(f'<tr><td>{repo_name}</td><td>-</td>')
					f.write(f'<td class="failure">Failed: {error}</td>')
					f.write(f'<td>-</td></tr>\n')
				
				# Skipped repositories
				for repo_name, reason in skipped_repos:
					f.write(f'<tr><td>{repo_name}</td><td>-</td>')
					f.write(f'<td class="skipped">Skipped: {reason}</td>')
					f.write(f'<td>-</td></tr>\n')
				
				f.write('</table>\n')
				f.write('</body>\n</html>\n')
			
			if conf['verbose']:
				print(f'Generated summary report: {summary_file}')
				
		except Exception as e:
			if conf['verbose']:
				print(f'Warning: Could not generate summary report: {e}')
	
	def run_single_mode(self, args):
		"""Original single/multiple repository mode with subfolder creation."""
		base_outputpath = os.path.abspath(args[-1])
		rundir = os.getcwd()

		# Validate git paths
		git_paths = args[0:-1]
		for gitpath in git_paths:
			if not os.path.exists(gitpath):
				print(f'FATAL: Git repository path does not exist: {gitpath}')
				sys.exit(1)
			if not os.path.isdir(gitpath):
				print(f'FATAL: Git repository path is not a directory: {gitpath}')
				sys.exit(1)
			git_dir = os.path.join(gitpath, '.git')
			if not os.path.exists(git_dir):
				print(f'FATAL: Path is not a git repository (no .git directory found): {gitpath}')
				sys.exit(1)

		# Validate and create base output directory
		try:
			os.makedirs(base_outputpath, exist_ok=True)
		except PermissionError:
			print(f'FATAL: Permission denied creating output directory: {base_outputpath}')
			sys.exit(1)
		except OSError as e:
			print(f'FATAL: Error creating output directory {base_outputpath}: {e}')
			sys.exit(1)
		
		if not os.path.isdir(base_outputpath):
			print('FATAL: Output path is not a directory or does not exist')
			sys.exit(1)
		
		# Check write permissions
		if not os.access(base_outputpath, os.W_OK):
			print(f'FATAL: No write permission for output directory: {base_outputpath}')
			sys.exit(1)

		print('Using table-based output format (matplotlib not required)')

		if conf['verbose']:
			print('Configuration:')
			for key, value in conf.items():
				print(f'  {key}: {value}')
			print()

		# Initialize variables for Pylance static analysis
		outputpath = None
		
		# Process each repository and create subfolders
		for gitpath in git_paths:
			# Get repository name from the path
			repo_name = os.path.basename(os.path.abspath(gitpath))
			safe_repo_name = self._sanitize_filename(repo_name)
			
			# Create repository-specific output directory
			outputpath = os.path.join(base_outputpath, f'{safe_repo_name}_report')
			
			# Validate and create specific output directory
			try:
				os.makedirs(outputpath, exist_ok=True)
			except PermissionError:
				print(f'FATAL: Permission denied creating repository output directory: {outputpath}')
				sys.exit(1)
			except OSError as e:
				print(f'FATAL: Error creating repository output directory {outputpath}: {e}')
				sys.exit(1)
			
			if not os.access(outputpath, os.W_OK):
				print(f'FATAL: No write permission for repository output directory: {outputpath}')
				sys.exit(1)

			print('Git path: %s' % gitpath)
			print('Output path: %s' % outputpath)
			
			cachefile = os.path.join(outputpath, 'gitstats.cache')

			data = GitDataCollector()
			data.loadCache(cachefile)

			prevdir = os.getcwd()
			os.chdir(gitpath)

			print('Collecting data...')
			data.collect(gitpath)

			# Calculate MI for current repository (if enabled)
			if conf['calculate_mi_per_repository']:
				print('Calculating Maintainability Index (MI) for current repository...')
				mi_results = data.calculate_mi_for_repository(gitpath)
				if mi_results:
					print(f'✓ MI calculation completed for {mi_results.get("files_analyzed", 0)} files')
				else:
					print('⚠️  MI calculation failed or no files found')
				
				print('')
				mccabe_results = data.calculate_mccabe_for_repository(gitpath)
				if mccabe_results:
					print(f'✓ McCabe calculation completed for {mccabe_results.get("files_analyzed", 0)} files')
				else:
					print('⚠️  McCabe calculation failed or no files found')
				
				print('')
				halstead_results = data.calculate_halstead_for_repository(gitpath)
				if halstead_results:
					print(f'✓ Halstead calculation completed for {halstead_results.get("files_analyzed", 0)} files')
				else:
					print('⚠️  Halstead calculation failed or no files found')
				
				print('')
				oop_results = data.calculate_oop_for_repository(gitpath)
				if oop_results:
					print(f'✓ OOP calculation completed for {oop_results.get("files_analyzed", 0)} files')
				else:
					print('⚠️  OOP calculation failed or no files found')
			else:
				print('Skipping per-repository metrics calculation (disabled in configuration)')

			os.chdir(prevdir)

			print('Refining data...')
			data.saveCache(cachefile)
			data.refine()

			os.chdir(rundir)

			print('Generating report...')
			
			print('Creating HTML report...')
			html_report = HTMLReportCreator()
			html_report.create(data, outputpath)
			
			print(f'✓ Successfully generated report for {repo_name}')

		time_end = time.time()
		exectime_internal = time_end - time_start
		external_percentage = (100.0 * exectime_external) / exectime_internal if exectime_internal > 0 else 0.0
		print('Execution time %.5f secs, %.5f secs (%.2f %%) in external commands)' % (exectime_internal, exectime_external, external_percentage))
		
		if len(git_paths) == 1:
			# For single repository, show the direct path to the report
			repo_name = os.path.basename(os.path.abspath(git_paths[0]))
			safe_repo_name = self._sanitize_filename(repo_name)
			outputpath = os.path.join(base_outputpath, f'{safe_repo_name}_report')
			
			if sys.stdin.isatty():
				print('You may now run:')
				print()
				print('   sensible-browser \'%s\'' % os.path.join(outputpath, 'index.html').replace("'", "'\\''"))
				print()
		else:
			# For multiple repositories, show the base path
			if sys.stdin.isatty():
				print('Reports have been generated in subfolders under:')
				print(f'  {base_outputpath}')
				print()
				print('You may run:')
				for gitpath in git_paths:
					repo_name = os.path.basename(os.path.abspath(gitpath))
					safe_repo_name = self._sanitize_filename(repo_name)
					repo_outputpath = os.path.join(base_outputpath, f'{safe_repo_name}_report')
					print('   sensible-browser \'%s\'' % os.path.join(repo_outputpath, 'index.html').replace("'", "'\\''"))
				print()
	
	def _process_repositories_parallel(self, repositories, base_outputpath, rundir):
		"""Process repositories in parallel for improved performance."""
		# Configuration
		max_workers = conf.get('multi_repo_max_workers', 4)
		batch_size = conf.get('multi_repo_batch_size', 10)
		progress_interval = conf.get('multi_repo_progress_interval', 5)
		
		print(f'Using parallel processing with {max_workers} workers, batch size: {batch_size}')
		
		# Process repositories in batches to manage memory
		total_repos = len(repositories)
		
		# Shared state for progress tracking
		progress_state = {
			'processed_count': 0,
			'last_progress_time': time.time(),
			'start_time': time.time(),
			'completion_times': [],
			'successful_reports': 0,
			'failed_reports': []
		}
		
		# Create a thread-safe progress tracker
		progress_lock = threading.Lock()
		
		def _process_repository_worker(repo_data):
			"""Worker function for processing a single repository."""
			repo_name, repo_path, repo_type = repo_data
			
			try:
				# Create output directory with safe naming
				safe_repo_name = self._sanitize_filename(repo_name)
				repo_output_path = os.path.join(base_outputpath, f'{safe_repo_name}_report')
				
				# Create directory
				os.makedirs(repo_output_path, exist_ok=True)
				if not os.access(repo_output_path, os.W_OK):
					raise PermissionError(f'No write permission for {repo_output_path}')
				
				# Process the repository
				repo_start_time = time.time()
				self._process_single_repository_safe(repo_path, repo_output_path, rundir, repo_name)
				repo_time = time.time() - repo_start_time
				
				# Thread-safe progress update with ETA
				with progress_lock:
					progress_state['processed_count'] += 1
					current_time = time.time()
					progress_state['completion_times'].append(current_time)
					
					if (current_time - progress_state['last_progress_time'] >= progress_interval or 
						progress_state['processed_count'] == total_repos):
						
						# Calculate ETA
						if len(progress_state['completion_times']) >= 5:
							avg_time_per_repo = (current_time - progress_state['start_time']) / progress_state['processed_count']
							remaining_repos = total_repos - progress_state['processed_count']
							eta_seconds = remaining_repos * avg_time_per_repo
							eta_str = f', ETA: {int(eta_seconds//60)}m {int(eta_seconds%60)}s' if eta_seconds > 0 else ''
						else:
							eta_str = ''
						
						print(f'Progress: {progress_state["processed_count"]}/{total_repos} repositories completed '
							  f'({(progress_state["processed_count"]/total_repos)*100:.1f}%){eta_str}')
						progress_state['last_progress_time'] = current_time
				
				return (repo_name, 'success', repo_time, None)
				
			except Exception as e:
				error_msg = str(e)
				
				# Clean up partial output on error
				if conf.get('multi_repo_cleanup_on_error', True):
					try:
						safe_repo_name = self._sanitize_filename(repo_name)
						repo_output_path = os.path.join(base_outputpath, f'{safe_repo_name}_report')
						if os.path.exists(repo_output_path):
							import shutil
							shutil.rmtree(repo_output_path)
					except Exception:
						pass  # Ignore cleanup errors
				
				with progress_lock:
					progress_state['processed_count'] += 1
				
				return (repo_name, 'failed', 0, error_msg)
		
		# Process repositories in batches
		for batch_start in range(0, total_repos, batch_size):
			batch_end = min(batch_start + batch_size, total_repos)
			batch_repos = repositories[batch_start:batch_end]
			
			if conf['verbose']:
				print(f'\nProcessing batch {batch_start//batch_size + 1}/{(total_repos + batch_size - 1)//batch_size}: '
					  f'repositories {batch_start + 1}-{batch_end}')
			
			# Use ThreadPoolExecutor for I/O-bound repository processing
			# (ProcessPoolExecutor would be better for CPU-bound, but git operations are mostly I/O)
			with ThreadPoolExecutor(max_workers=max_workers) as executor:
				try:
					# Submit all jobs in the batch
					futures = {executor.submit(_process_repository_worker, repo_data): repo_data 
							  for repo_data in batch_repos}
					
					# Collect results as they complete
					for future in as_completed(futures):
						repo_name, status, duration, error = future.result()
						
						if status == 'success':
							progress_state['successful_reports'] += 1
							if conf['verbose']:
								print(f'✓ {repo_name} completed in {duration:.2f}s')
						else:
							progress_state['failed_reports'].append((repo_name, error))
							if conf['verbose']:
								print(f'✗ {repo_name} failed: {error}')
				
				except KeyboardInterrupt:
					print('\nProcessing interrupted by user')
					# Cancel remaining futures
					for future in futures:
						future.cancel()
					break
			
			# Memory cleanup between batches
			import gc
			gc.collect()
		
		return progress_state['successful_reports'], progress_state['failed_reports']
	
	def process_single_repository(self, repo_path, output_path, rundir):
		"""Process a single repository and generate its report with improved resource management."""
		import gc
		
		# Validate inputs
		if not os.path.exists(repo_path):
			raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
		if not os.path.isdir(repo_path):
			raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")
		if not is_git_repository(repo_path):
			raise ValueError(f"Path is not a valid git repository: {repo_path}")
		
		cachefile = os.path.join(output_path, 'gitstats.cache')

		# Initialize data collector with proper cleanup
		data = None
		try:
			data = GitDataCollector()
			
			# Load cache if available
			try:
				data.loadCache(cachefile)
				if conf['verbose']:
					print(f'  Loaded cache from: {cachefile}')
			except Exception as e:
				if conf['verbose']:
					print(f'  Could not load cache: {e}')
			
			if conf['verbose']:
				print(f'  Collecting data from: {repo_path}')
			
			# Change to repository directory
			prevdir = os.getcwd()
			try:
				os.chdir(repo_path)
				
				# Collect data with memory monitoring
				initial_memory = self._get_memory_usage()
				
				data.collect(repo_path)

				# Calculate comprehensive metrics for current repository (if enabled)
				if conf['calculate_mi_per_repository']:
					print('  Calculating Maintainability Index (MI)...')
					mi_results = data.calculate_mi_for_repository(repo_path)
					if mi_results:
						files_analyzed = mi_results.get("files_analyzed", 0)
						print(f'  ✓ MI calculation completed for {files_analyzed} files')
						if files_analyzed > 0:
							avg_mi = mi_results.get("summary", {}).get("average_mi", 0)
							print(f'  📊 Average MI: {avg_mi:.1f}')
					else:
						print('  ⚠️  MI calculation failed or no files found')
					
					print('  Calculating McCabe Complexity...')
					mccabe_results = data.calculate_mccabe_for_repository(repo_path)
					if mccabe_results:
						files_analyzed = mccabe_results.get("files_analyzed", 0)
						print(f'  ✓ McCabe calculation completed for {files_analyzed} files')
						if files_analyzed > 0:
							avg_complexity = mccabe_results.get("summary", {}).get("average_complexity", 0)
							print(f'  📊 Average Complexity: {avg_complexity:.1f}')
					else:
						print('  ⚠️  McCabe calculation failed or no files found')
					
					print('  Calculating Halstead Metrics...')
					halstead_results = data.calculate_halstead_for_repository(repo_path)
					if halstead_results:
						files_analyzed = halstead_results.get("files_analyzed", 0)
						print(f'  ✓ Halstead calculation completed for {files_analyzed} files')
						if files_analyzed > 0:
							avg_effort = halstead_results.get("summary", {}).get("average_effort", 0)
							print(f'  📊 Average Effort: {avg_effort:.1f}')
					else:
						print('  ⚠️  Halstead calculation failed or no files found')
					
					print('  Calculating OOP Metrics...')
					oop_results = data.calculate_oop_for_repository(repo_path)
					if oop_results:
						files_analyzed = oop_results.get("files_analyzed", 0)
						print(f'  ✓ OOP calculation completed for {files_analyzed} files')
						if files_analyzed > 0:
							files_with_oop = oop_results.get("summary", {}).get("files_with_oop", 0)
							print(f'  📊 Files with OOP: {files_with_oop}/{files_analyzed}')
					else:
						print('  ⚠️  OOP calculation failed or no files found')
				else:
					if conf['verbose']:
						print('  Skipping comprehensive metrics calculation (disabled in configuration)')
				
				final_memory = self._get_memory_usage()
				if conf['verbose'] and initial_memory and final_memory:
					memory_delta = final_memory - initial_memory
					print(f'  Memory usage: {memory_delta:.1f} MB')
				
			finally:
				os.chdir(prevdir)

			if conf['verbose']:
				print('  Refining data...')
			
			# Save cache before refining (in case refining fails)
			try:
				data.saveCache(cachefile)
				if conf['verbose']:
					print(f'  Saved cache to: {cachefile}')
			except Exception as e:
				if conf['verbose']:
					print(f'  Warning: Could not save cache: {e}')
			
			data.refine()

			# Return to original directory
			os.chdir(rundir)

			if conf['verbose']:
				print('  Generating reports...')
			
			# Generate HTML report
			try:
				if conf['verbose']:
					print('  Creating HTML report...')
				html_report = HTMLReportCreator()
				html_report.create(data, output_path)
			except Exception as e:
				print(f'  Warning: HTML report generation failed: {e}')
				if conf['debug']:
					import traceback
					traceback.print_exc()
				
				# Clean up partial output on error if configured to do so
				if conf.get('multi_repo_cleanup_on_error', True):
					try:
						if os.path.exists(output_path):
							import shutil
							# Only clean up if it looks like our output directory
							if output_path.endswith('_report'):
								shutil.rmtree(output_path)
								if conf['verbose']:
									print(f'  Cleaned up partial output: {output_path}')
					except Exception as cleanup_error:
						if conf['debug']:
							print(f'  Warning: Cleanup failed: {cleanup_error}')
				raise
		
		finally:
			# Force garbage collection to free memory
			if data:
				del data
			gc.collect()
	
	def _get_memory_usage(self):
		"""Get current memory usage in MB. Returns None if unavailable."""
		try:
			import psutil
			process = psutil.Process()
			return process.memory_info().rss / 1024 / 1024  # Convert to MB
		except ImportError:
			# Fallback to basic memory info on systems without psutil
			try:
				import resource
				return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Convert to MB (Linux)
			except (ImportError, AttributeError):
				return None
		except Exception:
			return None
	
	def _check_memory_pressure(self, max_memory_mb=2048):
		"""Check if we're using too much memory and suggest cleanup."""
		current_memory = self._get_memory_usage()
		if current_memory and current_memory > max_memory_mb:
			if conf['verbose']:
				print(f'Warning: High memory usage detected ({current_memory:.1f} MB). '
					  f'Consider reducing batch size or max workers.')
			return True
		return False

if __name__=='__main__':
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