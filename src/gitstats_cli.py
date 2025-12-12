"""
Command-line interface module for Gitstats3.

Contains the GitStats CLI class and usage functions.
"""

import gc
import getopt
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from .gitstats_config import conf, get_config
from .gitstats_gitcommands import getversion, getgitversion, is_git_repository, get_exectime_external
from .gitstats_gitdatacollector import GitDataCollector
from .gitstats_htmlreport import HTMLReportCreator
from .gitstats_repository import discover_repositories, _discover_repositories_concurrent
from .gitstats_helpers import time_start



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
		exectime_external = get_exectime_external()
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
			futures = {}
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
			import psutil  # type: ignore
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