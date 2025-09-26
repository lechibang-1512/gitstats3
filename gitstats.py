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
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg

if sys.version_info < (3, 6):
	print("Python 3.6 or higher is required for gitstats", file=sys.stderr)
	sys.exit(1)

from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import threading
import queue

os.environ['LC_ALL'] = 'C'

# Matplotlib configuration
MATPLOTLIB_DPI = 100
MATPLOTLIB_FIGSIZE = (6.4, 2.4)  # Equivalent to 640x240 at 100 DPI

ON_LINUX = (platform.system() == 'Linux')
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

exectime_internal = 0.0
exectime_external = 0.0
time_start = time.time()

class MatplotlibChartGenerator:
	"""Generates charts using matplotlib to replace gnuplot functionality."""
	
	def __init__(self):
		self.dpi = MATPLOTLIB_DPI
		self.figsize = MATPLOTLIB_FIGSIZE
		
	def _setup_figure(self, title=""):
		"""Create and configure a new figure."""
		plt.style.use('default')
		fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
		ax.grid(True, alpha=0.3)
		return fig, ax
	
	def _save_figure(self, fig, output_path):
		"""Save the figure to a file with improved layout handling."""
		# Apply tight layout with padding for better text visibility
		fig.tight_layout(pad=2.0)
		
		# Additional bottom margin for rotated x-axis labels
		fig.subplots_adjust(bottom=0.15)
		
		fig.savefig(output_path, dpi=self.dpi, bbox_inches='tight', 
					facecolor='white', edgecolor='none', transparent=True,
					pad_inches=0.2)  # Add padding around the plot
		plt.close(fig)
	
	def create_hour_of_day_chart(self, data_file, output_path):
		"""Create hour of day activity chart."""
		try:
			# Read data file
			hours = []
			commits = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						hours.append(int(parts[0]))
						commits.append(int(parts[1]))
			
			if not hours:
				return
			
			fig, ax = self._setup_figure()
			
			# Create bar chart
			bars = ax.bar(hours, commits, width=0.8, color='#4472C4', alpha=0.7)
			
			ax.set_xlabel('Hour of Day')
			ax.set_ylabel('Commits')
			ax.set_xlim(0.5, 24.5)
			ax.set_xticks(range(0, 25, 4))
			ax.set_ylim(0, max(commits) * 1.1 if commits else 1)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create hour_of_day chart: {e}")
	
	def create_day_of_week_chart(self, data_file, output_path):
		"""Create day of week activity chart."""
		try:
			# Read data file
			day_nums = []
			day_names = []
			commits = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 3:
						day_nums.append(int(parts[0]))
						day_names.append(parts[1])
						commits.append(int(parts[2]))
			
			if not day_nums:
				return
			
			fig, ax = self._setup_figure()
			
			# Create bar chart
			bars = ax.bar(day_nums, commits, width=0.8, color='#4472C4', alpha=0.7)
			
			ax.set_xlabel('Day of Week')
			ax.set_ylabel('Commits')
			ax.set_xlim(0.5, 7.5)
			ax.set_xticks(day_nums)
			ax.set_xticklabels(day_names)
			ax.set_ylim(0, max(commits) * 1.1 if commits else 1)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create day_of_week chart: {e}")
	
	def create_domains_chart(self, data_file, output_path):
		"""Create domains activity chart."""
		try:
			# Read data file
			domains = []
			commits = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 3:
						domains.append(parts[0])
						commits.append(int(parts[2]))
			
			if not domains:
				return
			
			fig, ax = self._setup_figure()
			
			# Create horizontal bar chart for better domain name visibility
			y_pos = range(len(domains))
			bars = ax.barh(y_pos, commits, color='#4472C4', alpha=0.7)
			
			ax.set_xlabel('Commits')
			ax.set_ylabel('Domains')
			ax.set_yticks(y_pos)
			ax.set_yticklabels(domains, fontsize=9)
			ax.set_xlim(0, max(commits) * 1.1 if commits else 1)
			
			# Invert y-axis to match gnuplot behavior
			ax.invert_yaxis()
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create domains chart: {e}")
	
	def create_month_of_year_chart(self, data_file, output_path):
		"""Create month of year activity chart."""
		try:
			# Read data file
			months = []
			commits = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						months.append(int(parts[0]))
						commits.append(int(parts[1]))
			
			if not months:
				return
			
			fig, ax = self._setup_figure()
			
			# Create bar chart
			bars = ax.bar(months, commits, width=0.8, color='#4472C4', alpha=0.7)
			
			ax.set_xlabel('Month')
			ax.set_ylabel('Commits')
			ax.set_xlim(0.5, 12.5)
			ax.set_xticks(range(1, 13))
			ax.set_ylim(0, max(commits) * 1.1 if commits else 1)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create month_of_year chart: {e}")
	
	def create_commits_by_year_month_chart(self, data_file, output_path):
		"""Create commits by year-month chart."""
		try:
			# Read data file
			dates = []
			commits = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						try:
							date_obj = datetime.datetime.strptime(parts[0], '%Y-%m')
							dates.append(date_obj)
							commits.append(int(parts[1]))
						except ValueError:
							continue
			
			if not dates:
				return
			
			fig, ax = self._setup_figure()
			
			# Create bar chart
			bars = ax.bar(dates, commits, width=20, color='#4472C4', alpha=0.7)
			
			ax.set_xlabel('Year-Month')
			ax.set_ylabel('Commits')
			ax.set_ylim(0, max(commits) * 1.1 if commits else 1)
			
			# Format x-axis with improved spacing and readability
			ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
			# Use smarter locator based on data range
			date_range = max(dates) - min(dates)
			if date_range.days > 1460:  # > 4 years
				ax.xaxis.set_major_locator(mdates.YearLocator())
			elif date_range.days > 730:  # > 2 years
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
			elif date_range.days > 365:  # > 1 year
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
			else:
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=max(1, len(dates)//8)))
			
			# Improve label formatting
			plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create commits_by_year_month chart: {e}")
	
	def create_commits_by_year_chart(self, data_file, output_path):
		"""Create commits by year chart."""
		try:
			# Read data file
			years = []
			commits = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						years.append(int(parts[0]))
						commits.append(int(parts[1]))
			
			if not years:
				return
			
			fig, ax = self._setup_figure()
			
			# Create bar chart
			bars = ax.bar(years, commits, width=0.8, color='#4472C4', alpha=0.7)
			
			ax.set_xlabel('Year')
			ax.set_ylabel('Commits')
			ax.set_ylim(0, max(commits) * 1.1 if commits else 1)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create commits_by_year chart: {e}")
	
	def create_files_by_date_chart(self, data_file, output_path):
		"""Create files by date chart."""
		try:
			# Read data file
			dates = []
			files = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						try:
							date_obj = datetime.datetime.strptime(parts[0], '%Y-%m-%d')
							dates.append(date_obj)
							files.append(int(parts[1]))
						except ValueError:
							continue
			
			if not dates:
				return
			
			fig, ax = self._setup_figure()
			
			# Create step plot
			ax.step(dates, files, where='post', color='#4472C4', linewidth=1.5)
			
			ax.set_xlabel('Date')
			ax.set_ylabel('Files')
			ax.set_ylim(0, max(files) * 1.1 if files else 1)
			
			# Format x-axis with smart date locating and improved readability
			date_range = max(dates) - min(dates)
			if date_range.days > 1825:  # > 5 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
				ax.xaxis.set_major_locator(mdates.YearLocator())
			elif date_range.days > 730:  # > 2 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
			elif date_range.days > 90:  # > 3 months
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator())
			else:
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
				ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, date_range.days//10)))
			
			# Improve label formatting
			plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create files_by_date chart: {e}")

	def create_files_by_year_chart(self, data_file, output_path):
		"""Create files by year chart."""
		try:
			# Read data file
			years = []
			files = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						years.append(int(parts[0]))
						files.append(int(parts[1]))
			
			if not years:
				return
			
			fig, ax = self._setup_figure()
			
			# Create bar chart
			bars = ax.bar(years, files, width=0.8, color='#4472C4', alpha=0.7)
			
			ax.set_xlabel('Year')
			ax.set_ylabel('Files')
			ax.set_ylim(0, max(files) * 1.1 if files else 1)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create files_by_year chart: {e}")
	
	def create_lines_of_code_chart(self, data_file, output_path):
		"""Create lines of code chart."""
		try:
			# Read data file
			timestamps = []
			lines = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						try:
							timestamp = int(parts[0])
							date_obj = datetime.datetime.fromtimestamp(timestamp)
							timestamps.append(date_obj)
							lines.append(int(parts[1]))
						except ValueError:
							continue
			
			if not timestamps:
				return
			
			fig, ax = self._setup_figure()
			
			# Create line plot
			ax.plot(timestamps, lines, color='#4472C4', linewidth=1.5)
			
			ax.set_xlabel('Date')
			ax.set_ylabel('Lines')
			ax.set_ylim(0, max(lines) * 1.1 if lines else 1)
			
			# Format x-axis with smart date locating and improved readability
			date_range = max(timestamps) - min(timestamps)
			if date_range.days > 1825:  # > 5 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
				ax.xaxis.set_major_locator(mdates.YearLocator())
			elif date_range.days > 730:  # > 2 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
			elif date_range.days > 90:  # > 3 months
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator())
			else:
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
				ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, date_range.days//10)))
			
			# Improve label formatting
			plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create lines_of_code chart: {e}")
	
	def create_lines_of_code_by_author_chart(self, data_file, output_path, authors):
		"""Create lines of code by author chart."""
		try:
			# Read data file
			data = {}
			timestamps = []
			
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						try:
							timestamp = int(parts[0])
							date_obj = datetime.datetime.fromtimestamp(timestamp)
							timestamps.append(date_obj)
							
							# Initialize data for this timestamp
							if date_obj not in data:
								data[date_obj] = {}
							
							# Read values for each author
							for i, author in enumerate(authors):
								if i + 1 < len(parts):
									data[date_obj][author] = int(parts[i + 1])
								else:
									data[date_obj][author] = 0
						except ValueError:
							continue
			
			if not timestamps:
				return
			
			fig, ax = self._setup_figure()
			fig.set_size_inches(6.4, 4.8)  # Larger for multiple lines
			
			# Create line plots for each author
			colors = plt.cm.tab10(range(len(authors)))
			for i, author in enumerate(authors):
				author_data = [data.get(ts, {}).get(author, 0) for ts in timestamps]
				ax.plot(timestamps, author_data, color=colors[i], 
						linewidth=1.5, label=author, alpha=0.8)
			
			ax.set_xlabel('Date')
			ax.set_ylabel('Lines')
			ax.legend(loc='upper left', fontsize=8)
			
			# Format x-axis with smart date locating and improved readability
			date_range = max(timestamps) - min(timestamps)
			if date_range.days > 1825:  # > 5 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
				ax.xaxis.set_major_locator(mdates.YearLocator())
			elif date_range.days > 730:  # > 2 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
			elif date_range.days > 90:  # > 3 months
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator())
			else:
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
				ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, date_range.days//10)))
			
			# Improve label formatting
			plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create lines_of_code_by_author chart: {e}")
	
	def create_commits_by_author_chart(self, data_file, output_path, authors):
		"""Create commits by author chart."""
		try:
			# Read data file
			data = {}
			timestamps = []
			
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						try:
							timestamp = int(parts[0])
							date_obj = datetime.datetime.fromtimestamp(timestamp)
							timestamps.append(date_obj)
							
							# Initialize data for this timestamp
							if date_obj not in data:
								data[date_obj] = {}
							
							# Read values for each author
							for i, author in enumerate(authors):
								if i + 1 < len(parts):
									data[date_obj][author] = int(parts[i + 1])
								else:
									data[date_obj][author] = 0
						except ValueError:
							continue
			
			if not timestamps:
				return
			
			fig, ax = self._setup_figure()
			fig.set_size_inches(6.4, 4.8)  # Larger for multiple lines
			
			# Create line plots for each author
			colors = plt.cm.tab10(range(len(authors)))
			for i, author in enumerate(authors):
				author_data = [data.get(ts, {}).get(author, 0) for ts in timestamps]
				ax.plot(timestamps, author_data, color=colors[i], 
						linewidth=1.5, label=author, alpha=0.8)
			
			ax.set_xlabel('Date')
			ax.set_ylabel('Commits')
			ax.legend(loc='upper left', fontsize=8)
			
			# Format x-axis with smart date locating and improved readability
			date_range = max(timestamps) - min(timestamps)
			if date_range.days > 1825:  # > 5 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
				ax.xaxis.set_major_locator(mdates.YearLocator())
			elif date_range.days > 730:  # > 2 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
			elif date_range.days > 90:  # > 3 months
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator())
			else:
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
				ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, date_range.days//10)))
			
			# Improve label formatting
			plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create commits_by_author chart: {e}")
	
	def create_pace_of_changes_chart(self, data_file, output_path):
		"""Create pace of changes chart."""
		try:
			# Read data file
			timestamps = []
			changes = []
			with open(data_file, 'r') as f:
				for line in f:
					parts = line.strip().split()
					if len(parts) >= 2:
						try:
							timestamp = int(parts[0])
							date_obj = datetime.datetime.fromtimestamp(timestamp)
							timestamps.append(date_obj)
							changes.append(int(parts[1]))
						except ValueError:
							continue
			
			if not timestamps:
				return
			
			fig, ax = self._setup_figure()
			
			# Create line plot
			ax.plot(timestamps, changes, color='#4472C4', linewidth=2)
			
			ax.set_xlabel('Date')
			ax.set_ylabel('Line Changes (Additions + Deletions)')
			ax.set_ylim(0, max(changes) * 1.1 if changes else 1)
			
			# Format x-axis with smart date locating and improved readability
			date_range = max(timestamps) - min(timestamps)
			if date_range.days > 1825:  # > 5 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
				ax.xaxis.set_major_locator(mdates.YearLocator())
			elif date_range.days > 730:  # > 2 years
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
			elif date_range.days > 90:  # > 3 months
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
				ax.xaxis.set_major_locator(mdates.MonthLocator())
			else:
				ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
				ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, date_range.days//10)))
			
			# Improve label formatting
			plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
			
			self._save_figure(fig, output_path)
			
		except Exception as e:
			print(f"Warning: Failed to create pace_of_changes chart: {e}")

# By default, matplotlib is used for chart generation

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
	'processes': min(8, os.cpu_count() or 4),  # Auto-detect optimal process count
	'start_date': '',
	'debug': False,
	'verbose': False,
	'scan_default_branch_only': True,  # Only scan commits from the default branch
	# Multi-repo specific configuration
	'multi_repo_max_depth': 10,
	'multi_repo_max_depth': 10,
	'multi_repo_include_patterns': None,
	'multi_repo_exclude_patterns': None,
	'multi_repo_parallel': True,
	'multi_repo_max_workers': 4,
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
	'filter_by_extensions': True  # Enable/disable extension filtering
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
	exectime_external += (end - start)
	return output.decode('utf-8', errors='replace').rstrip('\n')

def get_default_branch():
	"""Get the default branch name from git configuration or detect it"""
	# First try to get the default branch from git config
	try:
		default_branch = getpipeoutput(['git symbolic-ref refs/remotes/origin/HEAD']).strip()
		if default_branch:
			# Extract branch name from refs/remotes/origin/HEAD -> refs/remotes/origin/main
			return default_branch.replace('refs/remotes/origin/', '')
	except:
		pass
	
	# Try to get from git config init.defaultBranch
	try:
		default_branch = getpipeoutput(['git config --get init.defaultBranch']).strip()
		if default_branch:
			return default_branch
	except:
		pass
	
	# Try common main branch names in order of preference
	main_branch_candidates = ['main', 'master', 'develop', 'development']
	
	# Get all local branches
	try:
		branches_output = getpipeoutput(['git branch'])
		local_branches = [line.strip().lstrip('* ') for line in branches_output.split('\n') if line.strip()]
		
		# Check if any of the common main branches exist
		for candidate in main_branch_candidates:
			if candidate in local_branches:
				return candidate
		
		# If none found, use the first branch
		if local_branches:
			return local_branches[0]
	except:
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

def getkeyssortedbyvalues(dict):
	return list(map(lambda el : el[1], sorted(map(lambda el : (el[1], el[0]), dict.items()))))

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
		gitstats_repo = os.path.dirname(os.path.abspath(__file__))
		VERSION = getpipeoutput(["git --git-dir=%s/.git --work-tree=%s rev-parse --short %s" %
			(gitstats_repo, gitstats_repo, getcommitrange('HEAD').split('\n')[0])])
	return VERSION

def getgitversion():
	return getpipeoutput(['git --version']).split('\n')[0]

def getmatplotlibversion():
	try:
		import matplotlib
		return f"matplotlib {matplotlib.__version__}"
	except ImportError:
		return "matplotlib not available"

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
	
	# Get the file extension
	if filename.find('.') == -1 or filename.rfind('.') == 0:
		# No extension or hidden file
		return False
	
	ext = '.' + filename[(filename.rfind('.') + 1):]
	return ext.lower() in conf['allowed_extensions']

def getnumoffilesfromrev(time_rev):
	"""
	Get number of files changed in commit (filtered by allowed extensions)
	"""
	time, rev = time_rev
	if conf['filter_by_extensions']:
		# Get all files and filter by extension
		all_files = getpipeoutput(['git ls-tree -r --name-only "%s"' % rev]).split('\n')
		filtered_files = []
		for file_path in all_files:
			if file_path.strip():  # Skip empty lines
				filename = file_path.split('/')[-1]
				if should_include_file(filename):
					filtered_files.append(file_path)
		return (int(time), rev, len(filtered_files))
	else:
		# Original behavior - count all files
		return (int(time), rev, int(getpipeoutput(['git ls-tree -r --name-only "%s"' % rev, 'wc -l']).split('\n')[0]))

def getnumoflinesinblob(ext_blob):
	"""
	Get number of lines in blob
	"""
	ext, blob_id = ext_blob
	return (ext, blob_id, int(getpipeoutput(['git cat-file blob %s' % blob_id, 'wc -l']).split()[0]))

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
	"""Manages data collection from a revision control repository."""
	def __init__(self):
		self.stamp_created = time.time()
		self.cache = {}
		self.total_authors = 0
		self.activity_by_hour_of_day = defaultdict(int) # hour -> commits
		self.activity_by_day_of_week = defaultdict(int) # day -> commits
		self.activity_by_month_of_year = defaultdict(int) # month [1-12] -> commits
		self.activity_by_hour_of_week = defaultdict(lambda: defaultdict(int)) # weekday -> hour -> commits
		self.activity_by_hour_of_day_busiest = 0
		self.activity_by_hour_of_week_busiest = 0
		self.activity_by_year_week = defaultdict(int) # yy_wNN -> commits
		self.activity_by_year_week_peak = 0

		self.authors = {} # name -> {commits, first_commit_stamp, last_commit_stamp, last_active_day, active_days, lines_added, lines_removed}

		self.total_commits = 0
		self.total_files = 0
		self.authors_by_commits = 0

		# domains
		self.domains = defaultdict(lambda: defaultdict(int)) # domain -> commits

		# author of the month
		self.author_of_month = defaultdict(lambda: defaultdict(int)) # month -> author -> commits
		self.author_of_year = defaultdict(lambda: defaultdict(int)) # year -> author -> commits
		self.commits_by_month = defaultdict(int) # month -> commits
		self.commits_by_year = defaultdict(int) # year -> commits
		self.lines_added_by_month = defaultdict(int) # month -> lines added
		self.lines_added_by_year = defaultdict(int) # year -> lines added
		self.lines_removed_by_month = defaultdict(int) # month -> lines removed
		self.lines_removed_by_year = defaultdict(int) # year -> lines removed
		self.first_commit_stamp = 0
		self.last_commit_stamp = 0
		self.last_active_day = None
		self.active_days = set()

		# lines
		self.total_lines = 0
		self.total_lines_added = 0
		self.total_lines_removed = 0
		
		# SLOC (Source Lines of Code) analysis
		self.total_source_lines = 0
		self.total_comment_lines = 0
		self.total_blank_lines = 0
		self.sloc_by_extension = {} # ext -> {'source': 0, 'comments': 0, 'blank': 0, 'total': 0}
		
		# File size and revision tracking
		self.file_sizes = {} # filepath -> size in bytes
		
		# Enhanced Metrics - College Project Consolidation
		# 1. Documentation Quality Metrics (12% weight - highest priority)
		self.documentation_metrics = {
			'total_comment_lines': 0,
			'total_documentation_files': 0,
			'api_documented_functions': 0,
			'total_functions': 0,
			'readme_sections': 0,
			'inline_comments': 0,
			'docstring_coverage': 0.0
		}
		
		# 2. Code Quality Metrics (SonarQube-inspired)
		self.code_quality_metrics = {
			'cyclomatic_complexity': 0,
			'code_duplication_lines': 0,
			'technical_debt_minutes': 0,
			'maintainability_index': 0.0,
			'code_smells': 0,
			'security_hotspots': 0
		}
		
		# 3. Team Collaboration Metrics (Enhanced)
		self.collaboration_metrics = {
			'bus_factor': 0,
			'knowledge_concentration': {},  # file -> primary_authors
			'pair_programming_commits': 0,
			'review_coverage': 0.0,
			'cross_team_commits': 0,
			'mentorship_pairs': {}
		}
		
		# 4. Project Health Metrics
		self.project_health = {
			'overall_health_score': 0.0,
			'trend_direction': 'stable',  # improving/declining/stable
			'risk_level': 'low',  # low/medium/high
			'actionable_issues': [],
			'quality_gate_status': 'unknown'
		}
		
		# 5. Enhanced File Analysis
		self.file_analysis = {
			'file_types': defaultdict(int),
			'large_files': [],  # files > 500 LOC
			'complex_files': [],  # high complexity files
			'orphaned_files': [],  # files with single contributor
			'hot_files': []  # frequently modified files
		}
		self.file_revisions = {} # filepath -> revision count

		# Directory activity tracking
		self.directories = defaultdict(lambda: {'commits': 0, 'lines_added': 0, 'lines_removed': 0, 'files': set()})
		self.directory_revisions = defaultdict(int) # directory -> total file revisions in directory

		# size
		self.total_size = 0

		# timezone
		self.commits_by_timezone = defaultdict(int) # timezone -> commits

		# tags
		self.tags = {}

		self.files_by_stamp = {} # stamp -> files

		# extensions
		self.extensions = {} # extension -> files, lines

		# line statistics
		self.changes_by_date = {} # stamp -> { files, ins, del }
		
		# Pace of Changes tracking (number of line changes happening over time)
		self.pace_of_changes = {} # stamp -> total_line_changes (ins + del)
		self.pace_of_changes_by_month = defaultdict(int) # month -> total_line_changes (ins + del)
		self.pace_of_changes_by_year = defaultdict(int) # year -> total_line_changes (ins + del)
		
		# Last 30 days activity
		self.last_30_days_commits = 0
		self.last_30_days_lines_added = 0
		self.last_30_days_lines_removed = 0
		
		# Last 12 months activity  
		self.last_12_months_commits = defaultdict(int) # month -> commits
		self.last_12_months_lines_added = defaultdict(int) # month -> lines added
		self.last_12_months_lines_removed = defaultdict(int) # month -> lines removed
		
		# File count tracking by year  
		self.files_by_year = defaultdict(int) # year -> max_file_count
		
		# Lines of code tracking by year
		self.lines_of_code_by_year = defaultdict(int) # year -> total_lines
		
		# Author yearly data
		self.lines_added_by_author_by_year = defaultdict(lambda: defaultdict(int)) # year -> author -> lines_added
		self.commits_by_author_by_year = defaultdict(lambda: defaultdict(int)) # year -> author -> commits
		
		# Repository size tracking
		self.repository_size_mb = 0.0
		
		# Branch analysis
		self.branches = {} # branch_name -> {'commits': 0, 'lines_added': 0, 'lines_removed': 0, 'authors': {}, 'is_merged': True, 'merge_base': '', 'unique_commits': []}
		self.unmerged_branches = [] # list of branch names that are not merged into main branch
		self.main_branch = 'master' # will be detected automatically
		
		# Team collaboration analysis
		self.author_collaboration = {} # author -> {'worked_with': {other_author: shared_files}, 'file_ownership': {file: change_count}}
		self.commit_patterns = {} # author -> {'avg_commit_size': lines, 'small_commits': count, 'large_commits': count, 'commit_frequency': commits_per_day}
		self.working_patterns = {} # author -> {'night_commits': count, 'weekend_commits': count, 'peak_hours': [hours], 'timezone_pattern': {tz: count}}
		self.impact_analysis = {} # author -> {'critical_files': [files], 'impact_score': score, 'bug_potential': score}
		self.team_performance = {} # author -> {'efficiency_score': score, 'consistency': score, 'leadership_score': score}
		
		# File importance tracking
		self.critical_files = set() # Files that are likely critical (main.py, app.py, index.html, etc.)
		self.file_impact_scores = {} # file -> impact_score based on how often it's changed and by whom
		
		# Time-based analysis
		self.commits_by_time_of_day = defaultdict(lambda: defaultdict(int)) # author -> hour -> commits
		self.commits_by_day_of_week = defaultdict(lambda: defaultdict(int)) # author -> day -> commits
		self.author_active_periods = {} # author -> {'active_days': set, 'longest_streak': days, 'avg_gap': days}
		
		# Quality indicators
		self.potential_bug_commits = [] # List of commits that might indicate bugs (reverts, fixes, etc.)
		self.refactoring_commits = [] # List of commits that appear to be refactoring
		self.feature_commits = [] # List of commits that appear to add features

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
	
	def calculate_documentation_quality(self):
		"""Calculate documentation quality metrics (12% weight priority)"""
		if self.total_lines == 0:
			return 0.0
			
		comment_density = (self.documentation_metrics['total_comment_lines'] / self.total_lines) * 100
		
		# API documentation coverage
		if self.documentation_metrics['total_functions'] > 0:
			api_coverage = (self.documentation_metrics['api_documented_functions'] / 
						   self.documentation_metrics['total_functions']) * 100
		else:
			api_coverage = 0
		
		# README quality (basic assessment)
		readme_score = min(self.documentation_metrics['readme_sections'] * 20, 100)
		
		# Weighted documentation score
		doc_score = (comment_density * 0.4 + api_coverage * 0.4 + readme_score * 0.2)
		
		return min(doc_score, 100.0)
	
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
		if self.total_files > 0:
			avg_complexity = self.code_quality_metrics['cyclomatic_complexity'] / self.total_files
			complexity_score = max(0, 100 - (avg_complexity - 10) * 10)  # Penalize complexity > 10
			scores.append(complexity_score)
		
		# Documentation score
		doc_score = self.calculate_documentation_quality()
		scores.append(doc_score)
		
		# Team collaboration score
		bus_factor = self.calculate_bus_factor()
		collaboration_score = min(bus_factor * 25, 100)  # Higher bus factor = better
		scores.append(collaboration_score)
		
		# File organization score
		if self.total_files > 0:
			large_files_ratio = len(self.file_analysis['large_files']) / self.total_files
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
				# Count function definitions
				if line.startswith('def ') or line.startswith('function ') or 'function(' in line:
					self.documentation_metrics['total_functions'] += 1
					# Check for docstring/comments after function
					if '"""' in content or "'''" in content or '/*' in content:
						self.documentation_metrics['api_documented_functions'] += 1
			
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
			self.file_analysis['file_types'][ext] += 1
			
			# Large files detection (>500 LOC)
			if len(lines) > 500:
				self.file_analysis['large_files'].append(filepath)
			
			# Documentation analysis
			comment_lines = 0
			for line in lines:
				line = line.strip()
				if line.startswith('#') or line.startswith('//') or line.startswith('*') or line.startswith('/*'):
					comment_lines += 1
				if '"""' in line or "'''" in line:
					comment_lines += 1
			
			self.documentation_metrics['total_comment_lines'] += comment_lines
			
			# Complexity analysis
			complexity = self.analyze_file_complexity(filepath)
			self.code_quality_metrics['cyclomatic_complexity'] += complexity
			
			if complexity > 20:  # High complexity threshold
				self.file_analysis['complex_files'].append(filepath)
			
		except Exception as e:
			pass  # Skip files that can't be read
	
	def calculate_project_health_score(self):
		"""Calculate overall project health score for college project"""
		scores = {}
		
		# 1. Documentation Quality (12% weight)
		scores['documentation'] = self.calculate_documentation_quality() * 0.12
		
		# 2. Code Quality (20% weight)
		scores['code_quality'] = self.calculate_code_quality_score() * 0.20
		
		# 3. Team Collaboration (15% weight) 
		bus_factor = self.calculate_bus_factor()
		collaboration_score = min(bus_factor * 20, 100)  # Scale bus factor
		scores['collaboration'] = collaboration_score * 0.15
		
		# 4. Project Activity (10% weight)
		if self.total_commits > 0:
			# More commits in recent period = better activity
			activity_score = min((self.total_commits / 10) * 10, 100)
		else:
			activity_score = 0
		scores['activity'] = activity_score * 0.10
		
		# 5. File Organization (8% weight)
		if self.total_files > 0:
			large_files_penalty = len(self.file_analysis['large_files']) / self.total_files
			org_score = max(0, 100 - (large_files_penalty * 50))
		else:
			org_score = 50
		scores['organization'] = org_score * 0.08
		
		# 6. Basic Technical Metrics (35% weight - remaining)
		if self.total_lines > 0:
			lines_per_commit = self.total_lines / max(self.total_commits, 1)
			# Reasonable lines per commit (not too high, not too low)
			technical_score = max(0, 100 - abs(lines_per_commit - 50))
		else:
			technical_score = 50
		scores['technical'] = technical_score * 0.35
		
		# Calculate total
		total_score = sum(scores.values())
		
		# Update project health
		self.project_health['overall_health_score'] = total_score
		
		# Set risk level
		if total_score >= 80:
			self.project_health['risk_level'] = 'low'
			self.project_health['quality_gate_status'] = 'passed'
		elif total_score >= 60:
			self.project_health['risk_level'] = 'medium' 
			self.project_health['quality_gate_status'] = 'warning'
		else:
			self.project_health['risk_level'] = 'high'
			self.project_health['quality_gate_status'] = 'failed'
		
		# Generate actionable recommendations
		self.project_health['actionable_issues'] = []
		
		if scores['documentation'] < 10:
			self.project_health['actionable_issues'].append('Improve code documentation and comments')
		
		if scores['collaboration'] < 10:
			self.project_health['actionable_issues'].append('Increase team collaboration - current bus factor too low')
		
		if len(self.file_analysis['large_files']) > 5:
			self.project_health['actionable_issues'].append('Consider breaking down large files (>500 LOC)')
		
		if len(self.file_analysis['complex_files']) > 3:
			self.project_health['actionable_issues'].append('Reduce complexity in identified complex files')
		
		return total_score
	
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

class GitDataCollector(DataCollector):
	def collect(self, dir):
		DataCollector.collect(self, dir)
		
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
			if stamp > self.last_commit_stamp:
				self.last_commit_stamp = stamp
			if self.first_commit_stamp == 0 or stamp < self.first_commit_stamp:
				self.first_commit_stamp = stamp

			# activity
			# hour
			hour = date.hour
			self.activity_by_hour_of_day[hour] += 1
			# most active hour?
			if self.activity_by_hour_of_day[hour] > self.activity_by_hour_of_day_busiest:
				self.activity_by_hour_of_day_busiest = self.activity_by_hour_of_day[hour]

			# day of week
			day = date.weekday()
			self.activity_by_day_of_week[day] += 1

			# domain stats
			if domain not in self.domains:
				self.domains[domain] = defaultdict(int)
			# commits
			self.domains[domain]['commits'] += 1

			# hour of week  
			self.activity_by_hour_of_week[day][hour] += 1
			# most active hour?
			if self.activity_by_hour_of_week[day][hour] > self.activity_by_hour_of_week_busiest:
				self.activity_by_hour_of_week_busiest = self.activity_by_hour_of_week[day][hour]

			# month of year
			month = date.month
			self.activity_by_month_of_year[month] += 1

			# yearly/weekly activity
			yyw = date.strftime('%Y-%W')
			self.activity_by_year_week[yyw] += 1
			if self.activity_by_year_week_peak < self.activity_by_year_week[yyw]:
				self.activity_by_year_week_peak = self.activity_by_year_week[yyw]

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
			self.author_of_month[yymm][author] += 1
			self.commits_by_month[yymm] += 1

			yy = date.year
			self.author_of_year[yy][author] += 1
			self.commits_by_year[yy] += 1

			# authors: active days
			yymmdd = date.strftime('%Y-%m-%d')
			if 'last_active_day' not in self.authors[author]:
				self.authors[author]['last_active_day'] = yymmdd
				self.authors[author]['active_days'] = set([yymmdd])
			elif yymmdd != self.authors[author]['last_active_day']:
				self.authors[author]['last_active_day'] = yymmdd
				self.authors[author]['active_days'].add(yymmdd)

			# project: active days
			if yymmdd != self.last_active_day:
				self.last_active_day = yymmdd
				self.active_days.add(yymmdd)

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

		self.total_commits += len(lines)
		for line in lines:
			parts = line.split(' ')
			if len(parts) != 2:
				continue
			(stamp, files) = parts[0:2]
			try:
				timestamp = int(stamp)
				file_count = int(files)
				self.files_by_stamp[timestamp] = file_count
				
				# Track files by year (use max file count per year)
				date = datetime.datetime.fromtimestamp(timestamp)
				year = date.year
				if year not in self.files_by_year or file_count > self.files_by_year[year]:
					self.files_by_year[year] = file_count
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

			self.total_size += size
			self.total_files += 1
			
			# Track individual file sizes
			self.file_sizes[fullpath] = size

			if filename.find('.') == -1 or filename.rfind('.') == 0:
				ext = ''
			else:
				ext = filename[(filename.rfind('.') + 1):]
			if len(ext) > conf['max_ext_length']:
				ext = ''
			if ext not in self.extensions:
				self.extensions[ext] = {'files': 0, 'lines': 0}
			self.extensions[ext]['files'] += 1
			
			# Add all blobs to SLOC analysis list (regardless of cache status)
			all_blobs_for_sloc.append((ext, blob_id))
			
			#if cache empty then add ext and blob id to list of new blob's
			#otherwise try to read needed info from cache
			if 'lines_in_blob' not in self.cache:
				blobs_to_read.append((ext,blob_id))
				continue
			if blob_id in self.cache['lines_in_blob']:
				self.extensions[ext]['lines'] += self.cache['lines_in_blob'][blob_id]
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
			self.extensions[ext]['lines'] += self.cache['lines_in_blob'][blob_id]

		# Update SLOC statistics
		for (ext, blob_id, total_lines, source_lines, comment_lines, blank_lines) in ext_blob_sloc:
			# Initialize extension SLOC tracking
			if ext not in self.sloc_by_extension:
				self.sloc_by_extension[ext] = {'source': 0, 'comments': 0, 'blank': 0, 'total': 0}
			
			# Update extension SLOC counts
			self.sloc_by_extension[ext]['source'] += source_lines
			self.sloc_by_extension[ext]['comments'] += comment_lines
			self.sloc_by_extension[ext]['blank'] += blank_lines
			self.sloc_by_extension[ext]['total'] += total_lines
			
			# Update global SLOC counts
			self.total_source_lines += source_lines
			self.total_comment_lines += comment_lines
			self.total_blank_lines += blank_lines
			
			# Update enhanced documentation metrics
			self.documentation_metrics['total_comment_lines'] += comment_lines

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
				
				if line not in self.file_revisions:
					self.file_revisions[line] = 0
				self.file_revisions[line] += 1
				
				# Track directory activity
				directory = os.path.dirname(line) if os.path.dirname(line) else '.'
				self.directory_revisions[directory] += 1
				self.directories[directory]['files'].add(line)

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
						self.directories[directory]['commits'] += 1  # Will be deduplicated later
						self.directories[directory]['lines_added'] += additions
						self.directories[directory]['lines_removed'] += deletions
						self.directories[directory]['files'].add(filename)
					except ValueError:
						pass

		# line statistics
		# outputs:
		#  N files changed, N insertions (+), N deletions(-)
		# <stamp> <author>
		self.changes_by_date = {} # stamp -> { files, ins, del }
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
						self.changes_by_date[stamp] = { 'files': files, 'ins': inserted, 'del': deleted, 'lines': total_lines }
						
						# Track pace of changes (total line changes)
						self.pace_of_changes[stamp] = inserted + deleted

						date = datetime.datetime.fromtimestamp(stamp)
						
						# Track pace of changes by month and year
						yymm = date.strftime('%Y-%m')
						yy = date.year
						self.pace_of_changes_by_month[yymm] += inserted + deleted
						self.pace_of_changes_by_year[yy] += inserted + deleted
						
						# Track last 30 days activity
						import time as time_mod
						now = time_mod.time()
						if now - stamp <= 30 * 24 * 3600:  # 30 days in seconds
							self.last_30_days_commits += 1
							self.last_30_days_lines_added += inserted
							self.last_30_days_lines_removed += deleted
						
						# Track last 12 months activity
						if now - stamp <= 365 * 24 * 3600:  # 12 months in seconds
							yymm = date.strftime('%Y-%m')
							self.last_12_months_commits[yymm] += 1
							self.last_12_months_lines_added[yymm] += inserted
							self.last_12_months_lines_removed[yymm] += deleted
						
						yymm = date.strftime('%Y-%m')
						self.lines_added_by_month[yymm] += inserted
						self.lines_removed_by_month[yymm] += deleted

						yy = date.year
						self.lines_added_by_year[yy] += inserted
						self.lines_removed_by_year[yy] += deleted

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
					self.total_lines_added += inserted
					self.total_lines_removed += deleted

				else:
					print('Warning: failed to handle line "%s"' % line)
					(files, inserted, deleted) = (0, 0, 0)
				#self.changes_by_date[stamp] = { 'files': files, 'ins': inserted, 'del': deleted }
		self.total_lines += total_lines

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
						self.lines_added_by_author_by_year[year][author] += inserted
						self.commits_by_author_by_year[year][author] += 1
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
		
		# Calculate final project health score
		try:
			health_score = self.calculate_project_health_score()
			print(f'Project Health Score: {health_score:.1f}/100')
			print(f'Quality Gate Status: {self.project_health["quality_gate_status"]}')
			print(f'Risk Level: {self.project_health["risk_level"]}')
			
			if self.project_health['actionable_issues']:
				print('Actionable Issues:')
				for issue in self.project_health['actionable_issues']:
					print(f'  - {issue}')
		
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Health score calculation failed: {e}')
	
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
				
				self.commit_patterns[author] = {
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
				if author not in self.working_patterns:
					self.working_patterns[author] = {
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
				
				self.working_patterns[author]['total_commits'] += 1
				self.working_patterns[author]['peak_hours'][hour] += 1
				self.working_patterns[author]['peak_days'][day_of_week] += 1
				
				# Extract timezone from date string
				if '+' in date_str or '-' in date_str:
					tz_part = date_str.split()[-1]
					self.working_patterns[author]['timezone_pattern'][tz_part] += 1
				
				# Categorize by time of day
				if 22 <= hour or hour < 6:
					self.working_patterns[author]['night_commits'] += 1
				elif 5 <= hour < 9:
					self.working_patterns[author]['early_bird'] += 1
				elif 9 <= hour < 17:
					self.working_patterns[author]['workday'] += 1
				elif 17 <= hour < 22:
					self.working_patterns[author]['evening'] += 1
				
				# Weekend commits (Saturday = 5, Sunday = 6)
				if day_of_week >= 5:
					self.working_patterns[author]['weekend_commits'] += 1
				
				# Classify commit types
				if any(keyword in message.lower() for keyword in ['fix', 'bug', 'error', 'patch']):
					if author not in self.potential_bug_commits:
						self.potential_bug_commits.append({'author': author, 'timestamp': timestamp, 'message': message})
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
				
				# Calculate bug potential based on commit messages and patterns
				author_commits = self.commit_patterns.get(author, {})
				bug_commits = author_commits.get('bug_related_commits', 0)
				total_commits = author_commits.get('total_commits', 1)
				bug_ratio = bug_commits / total_commits if total_commits > 0 else 0
				
				# Higher bug potential if author has many bug-fix commits
				bug_potential = min(bug_ratio * 100, 100)
				
				self.impact_analysis[author] = {
					'critical_files': critical_files_touched,
					'impact_score': total_impact_score,
					'bug_potential': bug_potential,
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
			total_lines_changed = self.total_lines_added + self.total_lines_removed
			
			for author in self.authors:
				author_info = self.authors[author]
				commit_patterns = self.commit_patterns.get(author, {})
				working_patterns = self.working_patterns.get(author, {})
				impact_info = self.impact_analysis.get(author, {})
				
				# Efficiency Score (based on lines changed per commit and commit quality)
				avg_commit_size = commit_patterns.get('avg_commit_size', 0)
				total_author_commits = author_info.get('commits', 0)
				
				# Normalize efficiency (sweet spot is around 20-50 lines per commit)
				if 20 <= avg_commit_size <= 50:
					size_efficiency = 100
				elif avg_commit_size < 20:
					size_efficiency = max(0, avg_commit_size * 5)  # Penalty for too small commits
				else:
					size_efficiency = max(0, 100 - (avg_commit_size - 50) * 2)  # Penalty for too large commits
				
				# Quality indicators
				bug_commits = commit_patterns.get('bug_related_commits', 0)
				feature_commits = commit_patterns.get('feature_related_commits', 0)
				refactor_commits = commit_patterns.get('refactor_related_commits', 0)
				
				quality_score = 0
				if total_author_commits > 0:
					feature_ratio = feature_commits / total_author_commits
					refactor_ratio = refactor_commits / total_author_commits
					bug_ratio = bug_commits / total_author_commits
					
					quality_score = (feature_ratio * 40 + refactor_ratio * 30 - bug_ratio * 20) * 100
					quality_score = max(0, min(100, quality_score))
				
				efficiency_score = (size_efficiency * 0.6 + quality_score * 0.4)
				
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
				
				# Leadership Score (based on impact on critical files, collaboration, and mentoring indicators)
				impact_score = impact_info.get('impact_score', 0)
				critical_files_count = len(impact_info.get('critical_files', []))
				
				# Collaboration score based on working with others
				collaboration_data = self.author_collaboration.get(author, {})
				worked_with_count = len(collaboration_data.get('worked_with', {}))
				
				# Normalize impact and collaboration
				impact_leadership = min(impact_score / 10, 100)  # Scale impact score
				collaboration_leadership = min(worked_with_count * 10, 100)  # Max score at 10 collaborators
				critical_file_leadership = min(critical_files_count * 20, 100)  # Max score at 5 critical files
				
				leadership_score = (impact_leadership * 0.4 + collaboration_leadership * 0.3 + critical_file_leadership * 0.3)
				
				# Overall contribution percentage
				author_commits = author_info.get('commits', 0)
				contribution_percentage = (author_commits / total_commits * 100) if total_commits > 0 else 0
				
				# Store performance metrics
				self.team_performance[author] = {
					'efficiency_score': efficiency_score,
					'consistency': consistency_score,
					'leadership_score': leadership_score,
					'contribution_percentage': contribution_percentage,
					'overall_score': (efficiency_score * 0.4 + consistency_score * 0.3 + leadership_score * 0.3),
					'commit_quality_analysis': {
						'avg_commit_size': avg_commit_size,
						'small_commits_ratio': commit_patterns.get('small_commits', 0) / total_author_commits if total_author_commits > 0 else 0,
						'large_commits_ratio': commit_patterns.get('large_commits', 0) / total_author_commits if total_author_commits > 0 else 0,
						'bug_fix_ratio': bug_commits / total_author_commits if total_author_commits > 0 else 0,
						'feature_ratio': feature_commits / total_author_commits if total_author_commits > 0 else 0
					}
				}
				
		except Exception as e:
			if conf['debug']:
				print(f'Warning: Team performance calculation failed: {e}')
	
	def refine(self):
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
		return self.total_commits

	def getTotalFiles(self):
		return self.total_files
	
	def getTotalLOC(self):
		return self.total_lines

	def getTotalSourceLines(self):
		return self.total_source_lines
	
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
		return self.commit_patterns.get(author, {})
	
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
	
	def getAuthorsByEfficiency(self):
		"""Get authors sorted by efficiency score."""
		performance_data = [(author, perf.get('efficiency_score', 0)) 
						   for author, perf in self.team_performance.items()]
		return sorted(performance_data, key=lambda x: x[1], reverse=True)
	
	def getAuthorsByConsistency(self):
		"""Get authors sorted by consistency score."""
		performance_data = [(author, perf.get('consistency', 0)) 
						   for author, perf in self.team_performance.items()]
		return sorted(performance_data, key=lambda x: x[1], reverse=True)
	
	def getAuthorsByLeadership(self):
		"""Get authors sorted by leadership score."""
		performance_data = [(author, perf.get('leadership_score', 0)) 
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
		f.write('<dt>Generator</dt><dd><a href="http://gitstats.sourceforge.net/">GitStats</a> (version %s), %s, %s</dd>' % (getversion(), getgitversion(), getmatplotlibversion()))
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
		
		# Overall Health Score
		health_score = data.project_health.get('overall_health_score', 0)
		risk_level = data.project_health.get('risk_level', 'unknown')
		quality_gate = data.project_health.get('quality_gate_status', 'unknown')
		
		f.write('<dl>')
		f.write('<dt>Overall Health Score</dt><dd><strong>%.1f/100</strong></dd>' % health_score)
		
		# Color-code risk level
		risk_color = {'low': 'green', 'medium': 'orange', 'high': 'red'}.get(risk_level, 'gray')
		f.write('<dt>Risk Level</dt><dd><span style="color: %s; font-weight: bold;">%s</span></dd>' % (risk_color, risk_level.upper()))
		
		# Quality Gate Status
		gate_color = {'passed': 'green', 'warning': 'orange', 'failed': 'red'}.get(quality_gate, 'gray')
		f.write('<dt>Quality Gate</dt><dd><span style="color: %s; font-weight: bold;">%s</span></dd>' % (gate_color, quality_gate.upper()))
		f.write('</dl>')
		
		# Documentation Quality Metrics
		f.write('<h3>Documentation Quality</h3>')
		doc_metrics = data.documentation_metrics
		f.write('<dl>')
		f.write('<dt>Comment Density</dt><dd>%.1f lines</dd>' % doc_metrics.get('total_comment_lines', 0))
		f.write('<dt>Documentation Files</dt><dd>%d</dd>' % doc_metrics.get('total_documentation_files', 0))
		f.write('<dt>Functions Documented</dt><dd>%d/%d</dd>' % (
			doc_metrics.get('api_documented_functions', 0),
			doc_metrics.get('total_functions', 0)
		))
		doc_quality_score = data.calculate_documentation_quality()
		f.write('<dt>Documentation Score</dt><dd><strong>%.1f/100</strong></dd>' % doc_quality_score)
		f.write('</dl>')
		
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
		
		# Team Collaboration Metrics  
		f.write('<h3>Team Collaboration</h3>')
		bus_factor = data.calculate_bus_factor()
		f.write('<dl>')
		f.write('<dt>Bus Factor</dt><dd><strong>%d</strong> (minimum contributors for 50%% of work)</dd>' % bus_factor)
		
		if bus_factor <= 2:
			bus_warning = '<span style="color: red;">⚠ High risk - very few contributors</span>'
		elif bus_factor <= 4:
			bus_warning = '<span style="color: orange;">⚠ Medium risk - limited contributor diversity</span>'
		else:
			bus_warning = '<span style="color: green;">✓ Good contributor diversity</span>'
		f.write('<dt>Risk Assessment</dt><dd>%s</dd>' % bus_warning)
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
		efficiency_ranking = data.getAuthorsByEfficiency()
		consistency_ranking = data.getAuthorsByConsistency()
		leadership_ranking = data.getAuthorsByLeadership()
		
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
		for author, score in efficiency_ranking[:10]:
			f.write('<li>%s (%.1f)</li>' % (author, score))
		f.write('</ol>')
		f.write('</div>')
		
		f.write('<div class="ranking-section">')
		f.write('<h3>Most Consistent</h3>')
		f.write('<ol>')
		for author, score in consistency_ranking[:10]:
			f.write('<li>%s (%.1f)</li>' % (author, score))
		f.write('</ol>')
		f.write('</div>')
		
		f.write('<div class="ranking-section">')
		f.write('<h3>Leadership Score</h3>')
		f.write('<ol>')
		for author, score in leadership_ranking[:10]:
			f.write('<li>%s (%.1f)</li>' % (author, score))
		f.write('</ol>')
		f.write('</div>')
		f.write('</div>')

		# Detailed Team Performance Table
		f.write(html_header(2, 'Detailed Team Performance Analysis'))
		f.write('<table class="team-performance sortable" id="team-performance">')
		f.write('<tr>')
		f.write('<th>Author</th>')
		f.write('<th>Commits</th>')
		f.write('<th>Contrib %</th>')
		f.write('<th>Lines Changed</th>')
		f.write('<th>Avg Commit Size</th>')
		f.write('<th>Efficiency</th>')
		f.write('<th>Consistency</th>')
		f.write('<th>Leadership</th>')
		f.write('<th>Overall Score</th>')
		f.write('<th>Assessment</th>')
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
			efficiency = perf.get('efficiency_score', 0)
			consistency = perf.get('consistency', 0)
			leadership = perf.get('leadership_score', 0)
			overall = perf.get('overall_score', 0)
			
			# Generate assessment
			assessment = self._generateAssessment(perf, patterns)
			
			f.write('<tr>')
			f.write('<td>%s</td>' % author)
			f.write('<td>%d</td>' % commits)
			f.write('<td>%.1f%%</td>' % contrib_pct)
			f.write('<td>%d</td>' % lines_changed)
			f.write('<td>%.1f</td>' % avg_commit_size)
			f.write('<td>%.1f</td>' % efficiency)
			f.write('<td>%.1f</td>' % consistency)
			f.write('<td>%.1f</td>' % leadership)
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
		f.write(html_header(2, 'Impact and Quality Analysis'))
		
		impact_analysis = data.getImpactAnalysis()
		critical_files = data.getCriticalFiles()
		
		f.write('<h3>Critical Files in Project (%d files identified)</h3>' % len(critical_files))
		if critical_files:
			f.write('<ul>')
			for critical_file in critical_files[:20]:  # Show first 20
				f.write('<li>%s</li>' % critical_file)
			f.write('</ul>')
			if len(critical_files) > 20:
				f.write('<p>... and %d more files</p>' % (len(critical_files) - 20))
		
		f.write('<h3>Author Impact Analysis</h3>')
		f.write('<table class="impact-analysis sortable" id="impact-analysis">')
		f.write('<tr>')
		f.write('<th>Author</th>')
		f.write('<th>Impact Score</th>')
		f.write('<th>Critical Files Touched</th>')
		f.write('<th>Bug Potential</th>')
		f.write('<th>High Impact Files</th>')
		f.write('<th>Assessment</th>')
		f.write('</tr>')
		
		# Sort by impact score
		sorted_impact = sorted(impact_analysis.items(), key=lambda x: x[1].get('impact_score', 0), reverse=True)
		
		for author, impact in sorted_impact:
			impact_score = impact.get('impact_score', 0)
			critical_files_touched = len(impact.get('critical_files', []))
			bug_potential = impact.get('bug_potential', 0)
			high_impact_files = len(impact.get('high_impact_files', []))
			
			# Generate impact assessment
			if impact_score > 200:
				impact_assessment = "Very High Impact"
			elif impact_score > 100:
				impact_assessment = "High Impact"
			elif impact_score > 50:
				impact_assessment = "Medium Impact"
			else:
				impact_assessment = "Low Impact"
			
			if bug_potential > 30:
				impact_assessment += " (High Bug Risk)"
			elif bug_potential > 15:
				impact_assessment += " (Medium Bug Risk)"
			
			f.write('<tr>')
			f.write('<td>%s</td>' % author)
			f.write('<td>%.1f</td>' % impact_score)
			f.write('<td>%d</td>' % critical_files_touched)
			f.write('<td>%.1f%%</td>' % bug_potential)
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
		f.write('<p>Number of line changes (additions + deletions) over time</p>')
		pace_data = data.getPaceOfChanges()
		if pace_data:
			f.write('<img src="pace_of_changes.png" alt="Pace of Changes">')
			
			# Generate pace of changes data file
			fg = open(path + '/pace_of_changes.dat', 'w')
			for stamp in sorted(pace_data.keys()):
				fg.write('%d %d\n' % (stamp, pace_data[stamp]))
			fg.close()
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
		f.write('<img src="hour_of_day.png" alt="Hour of Day">')
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
		f.write('<img src="day_of_week.png" alt="Day of Week">')
		f.write('<div class="vtable"><table>')
		f.write('<tr><th>Day</th><th>Total (%)</th></tr>')
		for d in range(0, 7):
			commits = 0
			if d in day_of_week:
				commits = day_of_week[d]
			f.write('<tr>')
			f.write('<th>%s</th>' % (WEEKDAYS[d]))
			if d in day_of_week:
				percent = (100.0 * day_of_week[d]) / totalcommits if totalcommits else 0.0
				f.write('<td>%d (%.2f%%)</td>' % (day_of_week[d], percent))
			else:
				f.write('<td>0</td>')
			f.write('</tr>')
		f.write('</table></div>')

		# Hour of Week
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
		f.write('<img src="month_of_year.png" alt="Month of Year">')
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
		f.write('<img src="commits_by_year_month.png" alt="Commits by year/month">')
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
		f.write('<img src="commits_by_year.png" alt="Commits by Year">')
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
		f.write('<img src="lines_of_code_by_author.png" alt="Lines of code per Author">')
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
		f.write('<img src="commits_by_author.png" alt="Commits per Author">')
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
		f.write('<img src="domains.png" alt="Commits by Domains">')
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
		# Branches section
		f.write('<div id="branches" class="section">')
		f.write(html_header(2, 'Branches'))

		# Branch summary
		branches = data.getBranches() if hasattr(data, 'getBranches') else {}
		unmerged_branches = data.getUnmergedBranches() if hasattr(data, 'getUnmergedBranches') else []
		main_branch = data.getMainBranch() if hasattr(data, 'getMainBranch') else 'master'
		
		f.write('<dl>')
		f.write('<dt>Total Branches</dt><dd>%d</dd>' % len(branches))
		if unmerged_branches:
			f.write('<dt>Unmerged Branches</dt><dd>%d</dd>' % len(unmerged_branches))
		f.write('<dt>Main Branch</dt><dd>%s</dd>' % main_branch)
		f.write('</dl>')

		if branches:
			# Branches :: All Branches
			f.write(html_header(2, 'All Branches'))
			f.write('<table class="branches sortable" id="branches">')
			f.write('<tr><th>Branch</th><th>Status</th><th>Commits</th><th>Lines Added</th><th>Lines Removed</th><th>Total Changes</th><th>Authors</th></tr>')
			
			# Sort branches by total changes (lines added + removed)
			sorted_branches = sorted(branches.items(), 
									key=lambda x: x[1].get('lines_added', 0) + x[1].get('lines_removed', 0), 
									reverse=True)
			
			for branch_name, branch_info in sorted_branches:
				status = 'Merged' if branch_info.get('is_merged', True) else 'Unmerged'
				commits = branch_info.get('commits', 0)
				lines_added = branch_info.get('lines_added', 0)
				lines_removed = branch_info.get('lines_removed', 0)
				total_changes = lines_added + lines_removed
				authors_count = len(branch_info.get('authors', {}))
				
				# Highlight unmerged branches
				row_class = 'class="unmerged"' if not branch_info.get('is_merged', True) else ''
				f.write('<tr %s><td>%s</td><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>' % 
						(row_class, branch_name, status, commits, lines_added, lines_removed, total_changes, authors_count))
			f.write('</table>')

			# Unmerged Branches Detail
			if unmerged_branches:
				f.write(html_header(2, 'Unmerged Branches Detail'))
				f.write('<p>These branches have not been merged into the main branch (%s) and may represent ongoing work or abandoned features.</p>' % main_branch)
				
				f.write('<table class="unmerged-branches sortable" id="unmerged">')
				f.write('<tr><th>Branch</th><th>Commits</th><th>Authors</th><th>Top Contributors</th><th>Lines Added</th><th>Lines Removed</th></tr>')
				
				unmerged_stats = data.getUnmergedBranchStats() if hasattr(data, 'getUnmergedBranchStats') else {}
				
				for branch_name in unmerged_branches:
					if branch_name in unmerged_stats:
						branch_info = unmerged_stats[branch_name]
						commits = branch_info.get('commits', 0)
						authors = branch_info.get('authors', {})
						lines_added = branch_info.get('lines_added', 0)
						lines_removed = branch_info.get('lines_removed', 0)
						
						# Get top contributors
						top_contributors = sorted(authors.items(), key=lambda x: x[1].get('commits', 0), reverse=True)[:3]
						contributors_str = ', '.join([f"{author} ({info.get('commits', 0)})" for author, info in top_contributors])
						
						f.write('<tr><td>%s</td><td>%d</td><td>%d</td><td>%s</td><td>%d</td><td>%d</td></tr>' % 
								(branch_name, commits, len(authors), contributors_str, lines_added, lines_removed))
				f.write('</table>')

			# Branch Activity by Author
			f.write(html_header(2, 'Branch Activity by Author'))
			f.write('<p>This table shows which authors have contributed to which branches.</p>')
			
			# Collect all unique authors across all branches
			all_authors = set()
			for branch_info in branches.values():
				all_authors.update(branch_info.get('authors', {}).keys())
			
			if all_authors and len(branches) > 1:
				f.write('<table class="branch-authors sortable" id="branch-authors">')
				header = '<tr><th>Author</th>'
				for branch_name in sorted(branches.keys()):
					header += '<th>%s</th>' % branch_name
				header += '<th>Total Branches</th></tr>'
				f.write(header)
				
				for author in sorted(all_authors):
					row = '<tr><td>%s</td>' % author
					branch_count = 0
					for branch_name in sorted(branches.keys()):
						branch_authors = branches[branch_name].get('authors', {})
						if author in branch_authors:
							commits = branch_authors[author].get('commits', 0)
							row += '<td>%d</td>' % commits
							branch_count += 1
						else:
							row += '<td>-</td>'
					row += '<td>%d</td></tr>' % branch_count
					f.write(row)
				f.write('</table>')
		f.write('</div>  <!-- end branches section -->')

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
			
			f.write('<img src="files_by_year.png" alt="Files by Year">')

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
		f.write('<p>This chart shows the total lines of code over time, including source code, comments, and blank lines.</p>')
		f.write('<img src="lines_of_code.png" alt="Lines of Code">')

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

		self.createGraphs(path)
	
	def _generateAssessment(self, performance, patterns):
		"""Generate a text assessment for an author based on their performance metrics."""
		efficiency = performance.get('efficiency_score', 0)
		consistency = performance.get('consistency', 0)
		leadership = performance.get('leadership_score', 0)
		contribution = performance.get('contribution_percentage', 0)
		
		small_commits_ratio = patterns.get('small_commits', 0) / max(patterns.get('total_commits', 1), 1)
		large_commits_ratio = patterns.get('large_commits', 0) / max(patterns.get('total_commits', 1), 1)
		
		assessments = []
		
		# Contribution level
		if contribution > 25:
			assessments.append("Major Contributor")
		elif contribution > 10:
			assessments.append("Regular Contributor")
		elif contribution > 2:
			assessments.append("Minor Contributor")
		else:
			assessments.append("Occasional Contributor")
		
		# Quality assessment
		if efficiency > 80:
			assessments.append("High Quality")
		elif efficiency > 60:
			assessments.append("Good Quality")
		elif efficiency > 40:
			assessments.append("Average Quality")
		else:
			assessments.append("Needs Improvement")
		
		# Work pattern assessment
		if small_commits_ratio > 0.7:
			assessments.append("Frequent Small Commits")
		elif large_commits_ratio > 0.3:
			assessments.append("Prefers Large Commits")
		
		if consistency > 80:
			assessments.append("Very Consistent")
		elif consistency > 60:
			assessments.append("Consistent")
		
		if leadership > 70:
			assessments.append("Leadership Role")
		elif leadership > 50:
			assessments.append("Collaborative")
		
		return ", ".join(assessments) if assessments else "Standard Contributor"
	
	def createGraphs(self, path):
		print('Generating graphs with matplotlib...')
		
		# Initialize matplotlib chart generator
		chart_generator = MatplotlibChartGenerator()
		
		# Change to the output directory
		old_dir = os.getcwd()
		os.chdir(path)
		
		try:
			# Generate all the chart types if their data files exist
			
			# hour of day
			if os.path.exists('hour_of_day.dat'):
				chart_generator.create_hour_of_day_chart('hour_of_day.dat', 'hour_of_day.png')
			
			# day of week
			if os.path.exists('day_of_week.dat'):
				chart_generator.create_day_of_week_chart('day_of_week.dat', 'day_of_week.png')
			
			# domains
			if os.path.exists('domains.dat'):
				chart_generator.create_domains_chart('domains.dat', 'domains.png')
			
			# month of year
			if os.path.exists('month_of_year.dat'):
				chart_generator.create_month_of_year_chart('month_of_year.dat', 'month_of_year.png')
			
			# commits by year-month
			if os.path.exists('commits_by_year_month.dat'):
				chart_generator.create_commits_by_year_month_chart('commits_by_year_month.dat', 'commits_by_year_month.png')
			
			# commits by year
			if os.path.exists('commits_by_year.dat'):
				chart_generator.create_commits_by_year_chart('commits_by_year.dat', 'commits_by_year.png')
			
			# files by date
			if os.path.exists('files_by_date.dat'):
				chart_generator.create_files_by_date_chart('files_by_date.dat', 'files_by_date.png')
			
			# files by year
			if os.path.exists('files_by_year.dat'):
				chart_generator.create_files_by_year_chart('files_by_year.dat', 'files_by_year.png')
			
			# lines of code
			if os.path.exists('lines_of_code.dat'):
				chart_generator.create_lines_of_code_chart('lines_of_code.dat', 'lines_of_code.png')
			
			# lines of code by author
			if os.path.exists('lines_of_code_by_author.dat') and hasattr(self, 'authors_to_plot'):
				chart_generator.create_lines_of_code_by_author_chart('lines_of_code_by_author.dat', 'lines_of_code_by_author.png', self.authors_to_plot)
			
			# commits by author
			if os.path.exists('commits_by_author.dat') and hasattr(self, 'authors_to_plot'):
				chart_generator.create_commits_by_author_chart('commits_by_author.dat', 'commits_by_author.png', self.authors_to_plot)
			
			# pace of changes
			if os.path.exists('pace_of_changes.dat'):
				chart_generator.create_pace_of_changes_chart('pace_of_changes.dat', 'pace_of_changes.png')
				
		except Exception as e:
			print(f"Warning: Error generating charts: {e}")
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

		# Validate matplotlib availability
		try:
			matplotlib_version = getmatplotlibversion()
			if not matplotlib_version or "not available" in matplotlib_version:
				print('FATAL: matplotlib not found - required for generating charts')
				sys.exit(1)
			if conf['verbose']:
				print(f'Using {matplotlib_version}')
		except Exception as e:
			print(f'FATAL: Error checking matplotlib: {e}')
			sys.exit(1)

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

		if not getmatplotlibversion():
			print('matplotlib not found')
			sys.exit(1)

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