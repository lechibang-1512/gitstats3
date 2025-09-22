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
from fpdf import FPDF
from fpdf.enums import XPos, YPos

if sys.version_info < (3, 6):
	print("Python 3.6 or higher is required for gitstats", file=sys.stderr)
	sys.exit(1)

from multiprocessing import Pool

os.environ['LC_ALL'] = 'C'

GNUPLOT_COMMON = 'set terminal png transparent size 640,240\nset size 1.0,1.0\n'
ON_LINUX = (platform.system() == 'Linux')
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

exectime_internal = 0.0
exectime_external = 0.0
time_start = time.time()

# By default, gnuplot is searched from path, but can be overridden with the
# environment variable "GNUPLOT"
gnuplot_cmd = 'gnuplot'
if 'GNUPLOT' in os.environ:
	gnuplot_cmd = os.environ['GNUPLOT']

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
	'processes': 8,
	'start_date': '',
	'debug': False,
	'verbose': False,
	# Multi-repo specific configuration
	'multi_repo_recursive': False,
	'multi_repo_max_depth': 3,
	'multi_repo_include_patterns': None,
	'multi_repo_exclude_patterns': None,
	'multi_repo_parallel': False,
	'multi_repo_max_workers': 4,
	'multi_repo_timeout': 3600,  # 1 hour timeout per repository
	'multi_repo_cleanup_on_error': True
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

def getgnuplotversion():
	return getpipeoutput(['%s --version' % gnuplot_cmd]).split('\n')[0]

def getnumoffilesfromrev(time_rev):
	"""
	Get number of files changed in commit
	"""
	time, rev = time_rev
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
		
		# Last 30 days activity
		self.last_30_days_commits = 0
		self.last_30_days_lines_added = 0
		self.last_30_days_lines_removed = 0
		
		# Last 12 months activity  
		self.last_12_months_commits = defaultdict(int) # month -> commits
		self.last_12_months_lines_added = defaultdict(int) # month -> lines added
		self.last_12_months_lines_removed = defaultdict(int) # month -> lines removed
		
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
			with open(tempfile, 'wb') as f:
				#pickle.dump(self.cache, f)
				data = zlib.compress(pickle.dumps(self.cache))
				f.write(data)
			try:
				os.remove(cachefile)
			except OSError:
				pass
			os.rename(tempfile, cachefile)
		except IOError as e:
			print(f'Warning: Could not save cache file {cachefile}: {e}')
			# Clean up temp file if it exists
			try:
				os.remove(tempfile)
			except OSError:
				pass

class GitDataCollector(DataCollector):
	def collect(self, dir):
		DataCollector.collect(self, dir)

		self.total_authors += int(getpipeoutput(['git shortlog -s %s' % getlogrange(), 'wc -l']))
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
		lines = getpipeoutput(['git rev-list --pretty=format:"%%at %%ai %%aN <%%aE>" %s' % getlogrange('HEAD'), 'grep -v ^commit']).split('\n')
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
		revlines = getpipeoutput(['git rev-list --pretty=format:"%%at %%T" %s' % getlogrange('HEAD'), 'grep -v ^commit']).strip().split('\n')
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
		pool = Pool(processes=conf['processes'])
		time_rev_count = pool.map(getnumoffilesfromrev, revs_to_read)
		pool.terminate()
		pool.join()

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
				self.files_by_stamp[int(stamp)] = int(files)
			except ValueError:
				print('Warning: failed to parse line "%s"' % line)

		# extensions and size of files
		lines = getpipeoutput(['git ls-tree -r -l -z %s' % getcommitrange('HEAD', end_only = True)]).split('\000')
		blobs_to_read = []
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

			self.total_size += size
			self.total_files += 1
			
			# Track individual file sizes
			self.file_sizes[fullpath] = size

			filename = fullpath.split('/')[-1] # strip directories
			if filename.find('.') == -1 or filename.rfind('.') == 0:
				ext = ''
			else:
				ext = filename[(filename.rfind('.') + 1):]
			if len(ext) > conf['max_ext_length']:
				ext = ''
			if ext not in self.extensions:
				self.extensions[ext] = {'files': 0, 'lines': 0}
			self.extensions[ext]['files'] += 1
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
		pool = Pool(processes=conf['processes'])
		ext_blob_linecount = pool.map(getnumoflinesinblob, blobs_to_read)
		pool.terminate()
		pool.join()

		# Also get SLOC analysis for the same blobs
		pool = Pool(processes=conf['processes'])
		ext_blob_sloc = pool.map(analyzesloc, blobs_to_read)
		pool.terminate()
		pool.join()

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

		# File revision counting
		print('Collecting file revision statistics...')
		revision_lines = getpipeoutput(['git log --name-only --pretty=format: %s' % getlogrange('HEAD')]).strip().split('\n')
		for line in revision_lines:
			line = line.strip()
			if len(line) > 0 and not line.startswith('commit'):
				# This is a filename
				if line not in self.file_revisions:
					self.file_revisions[line] = 0
				self.file_revisions[line] += 1
				
				# Track directory activity
				directory = os.path.dirname(line) if os.path.dirname(line) else '.'
				self.directory_revisions[directory] += 1
				self.directories[directory]['files'].add(line)

		# Directory activity analysis
		print('Collecting directory activity statistics...')
		numstat_lines = getpipeoutput(['git log --numstat --pretty=format:"%%at %%aN" %s' % getlogrange('HEAD')]).split('\n')
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

		# Similar to the above, but never use --first-parent
		# (we need to walk through every commit to know who
		# committed what, not just through mainline)
		lines = getpipeoutput(['git log --shortstat --date-order --pretty=format:"%%at %%aN" %s' % (getlogrange('HEAD'))]).split('\n')
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
			commit_data = getpipeoutput(['git log --name-only --pretty=format:"COMMIT:%H:%aN:%at" %s' % getlogrange('HEAD')]).split('\n')
			
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
	
	def _analyzeCommitPatterns(self):
		"""Analyze commit patterns to identify commit behavior (small vs large commits, frequency, etc.)"""
		if conf['verbose']:
			print('Analyzing commit patterns...')
		
		try:
			# Get detailed commit information
			commit_lines = getpipeoutput(['git log --shortstat --pretty=format:"COMMIT:%H:%aN:%at:%s" %s' % getlogrange('HEAD')]).split('\n')
			
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
							current_message = parts[4]
						except ValueError:
							current_timestamp = None
							current_message = ""
				elif line and current_author and re.search(r'files? changed', line):
					# Parse shortstat line
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
							'message': current_message
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
			commit_lines = getpipeoutput(['git log --pretty=format:"%aN|%at|%ai|%s" %s' % getlogrange('HEAD')]).split('\n')
			
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
				
				filename = os.path.basename(filepath).lower()
				
				# Mark files as critical based on common patterns
				critical_patterns = [
					'main.', 'app.', 'index.', 'config.', 'settings.',
					'setup.', 'package.json', 'requirements.txt', 'Dockerfile',
					'makefile', 'readme', 'license', '.env'
				]
				
				if any(pattern in filename for pattern in critical_patterns):
					self.critical_files.add(filepath)
				
				# Files in root directory are often critical
				if '/' not in filepath:
					self.critical_files.add(filepath)
			
			# Analyze file impact scores based on change frequency and author diversity
			file_authors = defaultdict(set)
			file_change_count = defaultdict(int)
			
			# Get file change history
			log_lines = getpipeoutput(['git log --name-only --pretty=format:"AUTHOR:%aN" %s' % getlogrange('HEAD')]).split('\n')
			current_author = None
			
			for line in log_lines:
				line = line.strip()
				if line.startswith('AUTHOR:'):
					current_author = line.replace('AUTHOR:', '')
				elif line and current_author and not line.startswith('AUTHOR:'):
					filename = line
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
		for file in (conf['style'], 'sortable.js', 'arrow-up.gif', 'arrow-down.gif', 'arrow-none.gif'):
			for base in basedirs:
				src = base + '/' + file
				if os.path.exists(src):
					shutil.copyfile(src, path + '/' + file)
					break
			else:
				print('Warning: "%s" not found, so not copied (searched: %s)' % (file, basedirs))

		f = open(path + "/index.html", 'w')
		format = '%Y-%m-%d %H:%M:%S'
		self.printHeader(f)

		f.write('<h1>GitStats - %s</h1>' % data.projectname)

		self.printNav(f)

		f.write('<dl>')
		f.write('<dt>Project name</dt><dd>%s</dd>' % (data.projectname))
		f.write('<dt>Generated</dt><dd>%s (in %d seconds)</dd>' % (datetime.datetime.now().strftime(format), time.time() - data.getStampCreated()))
		f.write('<dt>Generator</dt><dd><a href="http://gitstats.sourceforge.net/">GitStats</a> (version %s), %s, %s</dd>' % (getversion(), getgitversion(), getgnuplotversion()))
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

		f.write('</body>\n</html>')
		f.close()

		###
		# Team Analysis - New comprehensive team analysis page
		f = open(path + '/team_analysis.html', 'w')
		self.printHeader(f)
		f.write('<h1>Team Analysis</h1>')
		self.printNav(f)

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

		f.write('</body></html>')
		f.close()

		###
		# Activity
		f = open(path + '/activity.html', 'w')
		self.printHeader(f)
		f.write('<h1>Activity</h1>')
		self.printNav(f)

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
		f.write('<table><tr><th>Hour</th>')
		for i in range(0, 24):
			f.write('<th>%d</th>' % i)
		f.write('</tr>\n<tr><th>Commits</th>')
		fp = open(path + '/hour_of_day.dat', 'w')
		for i in range(0, 24):
			if i in hour_of_day:
				r = 127 + int((float(hour_of_day[i]) / hour_of_day_busiest) * 128)
				f.write('<td style="background-color: rgb(%d, 0, 0)">%d</td>' % (r, hour_of_day[i]))
				fp.write('%d %d\n' % (i, hour_of_day[i]))
			else:
				f.write('<td>0</td>')
				fp.write('%d 0\n' % i)
		fp.close()
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
		f.write('<img src="hour_of_day.png" alt="Hour of Day">')
		fg = open(path + '/hour_of_day.dat', 'w')
		for i in range(0, 24):
			if i in hour_of_day:
				fg.write('%d %d\n' % (i + 1, hour_of_day[i]))
			else:
				fg.write('%d 0\n' % (i + 1))
		fg.close()

		# Day of Week
		f.write(html_header(2, 'Day of Week'))
		day_of_week = data.getActivityByDayOfWeek()
		f.write('<div class="vtable"><table>')
		f.write('<tr><th>Day</th><th>Total (%)</th></tr>')
		fp = open(path + '/day_of_week.dat', 'w')
		for d in range(0, 7):
			commits = 0
			if d in day_of_week:
				commits = day_of_week[d]
			fp.write('%d %s %d\n' % (d + 1, WEEKDAYS[d], commits))
			f.write('<tr>')
			f.write('<th>%s</th>' % (WEEKDAYS[d]))
			if d in day_of_week:
				percent = (100.0 * day_of_week[d]) / totalcommits if totalcommits else 0.0
				f.write('<td>%d (%.2f%%)</td>' % (day_of_week[d], percent))
			else:
				f.write('<td>0</td>')
			f.write('</tr>')
		f.write('</table></div>')
		f.write('<img src="day_of_week.png" alt="Day of Week">')
		fp.close()

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
		f.write('<div class="vtable"><table>')
		f.write('<tr><th>Month</th><th>Commits (%)</th></tr>')
		fp = open (path + '/month_of_year.dat', 'w')
		for mm in range(1, 13):
			commits = 0
			if mm in data.activity_by_month_of_year:
				commits = data.activity_by_month_of_year[mm]
			percent = (100.0 * commits) / total_commits if total_commits else 0.0
			f.write('<tr><td>%d</td><td>%d (%.2f %%)</td></tr>' % (mm, commits, percent))
			fp.write('%d %d\n' % (mm, commits))
		fp.close()
		f.write('</table></div>')
		f.write('<img src="month_of_year.png" alt="Month of Year">')

		# Commits by year/month
		f.write(html_header(2, 'Commits by year/month'))
		f.write('<div class="vtable"><table><tr><th>Month</th><th>Commits</th><th>Lines added</th><th>Lines removed</th></tr>')
		for yymm in reversed(sorted(data.commits_by_month.keys())):
			f.write('<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td></tr>' % (yymm, data.commits_by_month.get(yymm,0), data.lines_added_by_month.get(yymm,0), data.lines_removed_by_month.get(yymm,0)))
		f.write('</table></div>')
		f.write('<img src="commits_by_year_month.png" alt="Commits by year/month">')
		fg = open(path + '/commits_by_year_month.dat', 'w')
		for yymm in sorted(data.commits_by_month.keys()):
			fg.write('%s %s\n' % (yymm, data.commits_by_month[yymm]))
		fg.close()

		# Commits by year
		f.write(html_header(2, 'Commits by Year'))
		f.write('<div class="vtable"><table><tr><th>Year</th><th>Commits (% of all)</th><th>Lines added</th><th>Lines removed</th></tr>')
		for yy in reversed(sorted(data.commits_by_year.keys())):
			commits = data.commits_by_year.get(yy, 0)
			percent = (100.0 * commits) / total_commits if total_commits else 0.0
			f.write('<tr><td>%s</td><td>%d (%.2f%%)</td><td>%d</td><td>%d</td></tr>' % (yy, commits, percent, data.lines_added_by_year.get(yy,0), data.lines_removed_by_year.get(yy,0)))
		f.write('</table></div>')
		f.write('<img src="commits_by_year.png" alt="Commits by Year">')
		fg = open(path + '/commits_by_year.dat', 'w')
		for yy in sorted(data.commits_by_year.keys()):
			fg.write('%d %d\n' % (yy, data.commits_by_year[yy]))
		fg.close()

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

		f.write('</body></html>')
		f.close()

		###
		# Authors
		f = open(path + '/authors.html', 'w')
		self.printHeader(f)

		f.write('<h1>Authors</h1>')
		self.printNav(f)

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

		f.write(html_header(2, 'Commits per Author'))
		f.write('<img src="commits_by_author.png" alt="Commits per Author">')
		if len(allauthors) > conf['max_authors']:
			f.write('<p class="moreauthors">Only top %d authors shown</p>' % conf['max_authors'])

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
		f.write('<div class="vtable"><table>')
		f.write('<tr><th>Domains</th><th>Total (%)</th></tr>')
		fp = open(path + '/domains.dat', 'w')
		n = 0
		for domain in domains_by_commits:
			if n == conf['max_domains']:
				break
			commits = 0
			n += 1
			info = data.getDomainInfo(domain)
			fp.write('%s %d %d\n' % (domain, n , info['commits']))
			percent = (100.0 * info['commits'] / total_commits) if total_commits else 0.0
			f.write('<tr><th>%s</th><td>%d (%.2f%%)</td></tr>' % (domain, info['commits'], percent))
		f.write('</table></div>')
		f.write('<img src="domains.png" alt="Commits by Domains">')
		fp.close()

		f.write('</body></html>')
		f.close()

		###
		# Branches
		f = open(path + '/branches.html', 'w')
		self.printHeader(f)
		f.write('<h1>Branches</h1>')
		self.printNav(f)

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

		f.write('</body></html>')
		f.close()

		###
		# Files
		f = open(path + '/files.html', 'w')
		self.printHeader(f)
		f.write('<h1>Files</h1>')
		self.printNav(f)

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

		# Files :: File count by date
		f.write(html_header(2, 'File count by date'))

		# use set to get rid of duplicate/unnecessary entries
		files_by_date = set()
		for stamp in sorted(data.files_by_stamp.keys()):
			files_by_date.add('%s %d' % (datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d'), data.files_by_stamp[stamp]))

		fg = open(path + '/files_by_date.dat', 'w')
		for line in sorted(list(files_by_date)):
			fg.write('%s\n' % line)
		#for stamp in sorted(data.files_by_stamp.keys()):
		#	fg.write('%s %d\n' % (datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d'), data.files_by_stamp[stamp]))
		fg.close()
			
		f.write('<img src="files_by_date.png" alt="Files by Date">')

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

		f.write('</body></html>')
		f.close()

		###
		# Lines
		f = open(path + '/lines.html', 'w')
		self.printHeader(f)
		f.write('<h1>Lines</h1>')
		self.printNav(f)

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

		f.write('</body></html>')
		f.close()

		###
		# tags.html
		f = open(path + '/tags.html', 'w')
		self.printHeader(f)
		f.write('<h1>Tags</h1>')
		self.printNav(f)

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
		print('Generating graphs...')

		# hour of day
		f = open(path + '/hour_of_day.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'hour_of_day.png'
unset key
set xrange [0.5:24.5]
set yrange [0:]
set xtics 4
set grid y
set ylabel "Commits"
plot 'hour_of_day.dat' using 1:2:(0.5) w boxes fs solid
""")
		f.close()

		# day of week
		f = open(path + '/day_of_week.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'day_of_week.png'
unset key
set xrange [0.5:7.5]
set yrange [0:]
set xtics 1
set grid y
set ylabel "Commits"
plot 'day_of_week.dat' using 1:3:(0.5):xtic(2) w boxes fs solid
""")
		f.close()

		# Domains
		f = open(path + '/domains.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'domains.png'
unset key
unset xtics
set yrange [0:]
set grid y
set ylabel "Commits"
plot 'domains.dat' using 2:3:(0.5) with boxes fs solid, '' using 2:3:1 with labels rotate by 45 offset 0,1
""")
		f.close()

		# Month of Year
		f = open(path + '/month_of_year.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'month_of_year.png'
unset key
set xrange [0.5:12.5]
set yrange [0:]
set xtics 1
set grid y
set ylabel "Commits"
plot 'month_of_year.dat' using 1:2:(0.5) w boxes fs solid
""")
		f.close()

		# commits_by_year_month
		f = open(path + '/commits_by_year_month.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'commits_by_year_month.png'
unset key
set yrange [0:]
set xdata time
set timefmt "%Y-%m"
set format x "%Y-%m"
set xtics rotate
set bmargin 5
set grid y
set ylabel "Commits"
plot 'commits_by_year_month.dat' using 1:2:(0.5) w boxes fs solid
""")
		f.close()

		# commits_by_year
		f = open(path + '/commits_by_year.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'commits_by_year.png'
unset key
set yrange [0:]
set xtics 1 rotate
set grid y
set ylabel "Commits"
set yrange [0:]
plot 'commits_by_year.dat' using 1:2:(0.5) w boxes fs solid
""")
		f.close()

		# Files by date
		f = open(path + '/files_by_date.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'files_by_date.png'
unset key
set yrange [0:]
set xdata time
set timefmt "%Y-%m-%d"
set format x "%Y-%m-%d"
set grid y
set ylabel "Files"
set xtics rotate
set ytics autofreq
set bmargin 6
plot 'files_by_date.dat' using 1:2 w steps
""")
		f.close()

		# Lines of Code
		f = open(path + '/lines_of_code.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'lines_of_code.png'
unset key
set yrange [0:]
set xdata time
set timefmt "%s"
set format x "%Y-%m-%d"
set grid y
set ylabel "Lines"
set xtics rotate
set bmargin 6
plot 'lines_of_code.dat' using 1:2 w lines
""")
		f.close()

		# Lines of Code Added per author
		f = open(path + '/lines_of_code_by_author.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set terminal png transparent size 640,480
set output 'lines_of_code_by_author.png'
set key left top
set yrange [0:]
set xdata time
set timefmt "%s"
set format x "%Y-%m-%d"
set grid y
set ylabel "Lines"
set xtics rotate
set bmargin 6
plot """
)
		i = 1
		plots = []
		for a in self.authors_to_plot:
			i = i + 1
			author = a.replace("\"", "\\\"").replace("`", "")
			plots.append("""'lines_of_code_by_author.dat' using 1:%d title "%s" w lines""" % (i, author))
		f.write(", ".join(plots))
		f.write('\n')

		f.close()

		# Commits per author
		f = open(path + '/commits_by_author.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set terminal png transparent size 640,480
set output 'commits_by_author.png'
set key left top
set yrange [0:]
set xdata time
set timefmt "%s"
set format x "%Y-%m-%d"
set grid y
set ylabel "Commits"
set xtics rotate
set bmargin 6
plot """
)
		i = 1
		plots = []
		for a in self.authors_to_plot:
			i = i + 1
			author = a.replace("\"", "\\\"").replace("`", "")
			plots.append("""'commits_by_author.dat' using 1:%d title "%s" w lines""" % (i, author))
		f.write(", ".join(plots))
		f.write('\n')

		f.close()

		# Pace of Changes plot
		f = open(path + '/pace_of_changes.plot', 'w')
		f.write(GNUPLOT_COMMON)
		f.write(
"""
set output 'pace_of_changes.png'
unset key
set yrange [0:]
set xdata time
set timefmt "%s"
set format x "%Y-%m-%d"
set grid y
set ylabel "Line Changes (Additions + Deletions)"
set xtics rotate
set bmargin 6
plot 'pace_of_changes.dat' using 1:2 w lines lw 2
""")
		f.close()

		os.chdir(path)
		files = glob.glob(path + '/*.plot')
		for f in files:
			out = getpipeoutput([gnuplot_cmd + ' "%s"' % f])
			if len(out) > 0:
				print(out)

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

class PDFReportCreator(ReportCreator):
	"""Creates PDF reports using fpdf2 library with embedded charts and tab-based structure."""
	
	def __init__(self):
		ReportCreator.__init__(self)
		self.pdf = None
		self.output_path = None
		# Define color schemes for better visual appeal
		self.colors = {
			'header': (41, 128, 185),    # Blue
			'text': (0, 0, 0),           # Black
			'table_header': (52, 152, 219), # Light blue
			'table_alt': (245, 245, 245)    # Light gray
		}
		# Unicode-compatible font selection
		self.font_family = self._detect_unicode_font()
	
	def _detect_unicode_font(self):
		"""Detect and return a Unicode-compatible font family that supports Chinese characters."""
		# List of Unicode-compatible fonts in order of preference with their typical paths
		unicode_fonts = [
			# Liberation fonts - widely available and support Unicode
			{
				'name': 'LiberationSans',
				'paths': [
					'/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
					'/usr/share/fonts/TTF/LiberationSans-Regular.ttf',
					'/System/Library/Fonts/Liberation Sans.ttf'
				]
			},
			# Noto fonts - comprehensive Unicode support
			{
				'name': 'NotoSans',
				'paths': [
					'/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
					'/usr/share/fonts/TTF/NotoSans-Regular.ttf',
					'/System/Library/Fonts/Noto Sans.ttf'
				]
			},
			# DejaVu fonts - good Unicode support
			{
				'name': 'DejaVuSans',
				'paths': [
					'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
					'/usr/share/fonts/TTF/DejaVuSans.ttf',
					'/System/Library/Fonts/DejaVu Sans.ttf'
				]
			},
			# Droid fonts - Android's Unicode fonts
			{
				'name': 'DroidSansFallback',
				'paths': [
					'/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
					'/usr/share/fonts/TTF/DroidSansFallbackFull.ttf'
				]
			}
		]
		
		# Try to find an available Unicode font
		for font_info in unicode_fonts:
			for font_path in font_info['paths']:
				if os.path.exists(font_path):
					try:
						# Test if we can add this font
						test_pdf = FPDF()
						test_pdf.add_font(font_info['name'], '', font_path)
						# If successful, return the font info
						return {
							'name': font_info['name'],
							'path': font_path,
							'loaded': False
						}
					except Exception as e:
						if conf['debug']:
							print(f"Debug: Could not load font {font_path}: {e}")
						continue
		
		# If no Unicode font found, return None - will use fallback
		if conf['verbose']:
			print("Warning: No Unicode-compatible fonts found. Chinese characters may cause errors.")
		return None
	
	def _load_unicode_font(self):
		"""Load the detected Unicode font into the PDF."""
		if self.font_family and not self.font_family.get('loaded', False):
			try:
				# Add the Unicode font to the PDF
				self.pdf.add_font(self.font_family['name'], '', self.font_family['path'])
				
				# Add bold variant if available
				bold_path = self.font_family['path'].replace('-Regular.ttf', '-Bold.ttf')
				if os.path.exists(bold_path):
					self.pdf.add_font(self.font_family['name'], 'B', bold_path)
					if conf['debug']:
						print(f"Debug: Loaded bold variant: {bold_path}")
				else:
					if conf['debug']:
						print(f"Debug: Bold variant not found: {bold_path}")
				
				# Add italic variant if available  
				italic_path = self.font_family['path'].replace('-Regular.ttf', '-Italic.ttf')
				if os.path.exists(italic_path):
					self.pdf.add_font(self.font_family['name'], 'I', italic_path)
					if conf['debug']:
						print(f"Debug: Loaded italic variant: {italic_path}")
				
				# Add bold-italic variant if available
				bold_italic_path = self.font_family['path'].replace('-Regular.ttf', '-BoldItalic.ttf')
				if os.path.exists(bold_italic_path):
					self.pdf.add_font(self.font_family['name'], 'BI', bold_italic_path)
					if conf['debug']:
						print(f"Debug: Loaded bold-italic variant: {bold_italic_path}")
				
				self.font_family['loaded'] = True
				
				if conf['verbose']:
					print(f"Loaded Unicode font: {self.font_family['name']} from {self.font_family['path']}")
				
				return True
			except Exception as e:
				if conf['verbose'] or conf['debug']:
					print(f"Warning: Failed to load Unicode font {self.font_family}: {e}")
				return False
		return True
	
	def _set_font(self, style='', size=12):
		"""Set font using the Unicode-compatible font family."""
		# First try to use the Unicode font if available
		if self.font_family:
			if not self.font_family.get('loaded', False):
				self._load_unicode_font()
			
			if self.font_family.get('loaded', False):
				try:
					self.pdf.set_font(self.font_family['name'], style, size)
					return
				except Exception as e:
					if conf['debug']:
						print(f"Debug: Unicode font failed, falling back: {e}")
		
		# Fallback to built-in fonts (may not support Unicode)
		try:
			# Try Arial first as it's more commonly available
			self.pdf.set_font('Arial', style, size)
		except Exception as e:
			try:
				# Fallback to Times
				self.pdf.set_font('Times', style, size)
			except Exception as e2:
				try:
					# Final fallback to helvetica (original problematic font)
					self.pdf.set_font('helvetica', style, size)
					if conf['verbose']:
						print("Warning: Using helvetica font - Chinese characters may cause errors")
				except Exception as e3:
					# If all else fails, let the error propagate
					raise e3
	
	def _sanitize_text_for_pdf(self, text):
		"""Sanitize text to ensure it can be rendered in PDF, with fallback for unsupported characters."""
		if not isinstance(text, str):
			text = str(text)
		
		# If we have a Unicode font loaded, try to use the text as-is first
		if self.font_family and self.font_family.get('loaded', False):
			return text
		
		# For non-Unicode fonts, replace problematic characters
		# Create a mapping of common Chinese characters to transliterations
		chinese_transliterations = {
			'罗': 'Luo',
			'贾': 'Jia', 
			'李': 'Li',
			'王': 'Wang',
			'张': 'Zhang',
			'刘': 'Liu',
			'陈': 'Chen',
			'杨': 'Yang',
			'赵': 'Zhao',
			'黄': 'Huang',
			'周': 'Zhou',
			'吴': 'Wu',
			'徐': 'Xu',
			'孙': 'Sun',
			'胡': 'Hu',
			'朱': 'Zhu',
			'高': 'Gao',
			'林': 'Lin',
			'何': 'He',
			'郭': 'Guo',
			'马': 'Ma',
			'罗': 'Luo',
			'梁': 'Liang',
			'宋': 'Song',
			'郑': 'Zheng',
			'谢': 'Xie',
			'韩': 'Han',
			'唐': 'Tang',
			'冯': 'Feng',
			'于': 'Yu',
			'董': 'Dong',
			'萧': 'Xiao',
			'程': 'Cheng',
			'曹': 'Cao',
			'袁': 'Yuan',
			'邓': 'Deng',
			'许': 'Xu',
			'傅': 'Fu',
			'沈': 'Shen',
			'曾': 'Zeng',
			'彭': 'Peng',
			'吕': 'Lu',
			'苏': 'Su',
			'卢': 'Lu',
			'蒋': 'Jiang',
			'蔡': 'Cai',
			'贾': 'Jia',
			'丁': 'Ding',
			'魏': 'Wei'
		}
		
		# Replace Chinese characters with transliterations
		for chinese_char, transliteration in chinese_transliterations.items():
			text = text.replace(chinese_char, transliteration)
		
		# Remove any remaining non-ASCII characters that might cause issues
		try:
			# Try to encode as latin-1 (which is what helvetica supports)
			text.encode('latin-1')
			return text
		except UnicodeEncodeError:
			# If that fails, replace non-ASCII characters with '?'
			return ''.join(c if ord(c) < 128 else '?' for c in text)
	
	def _safe_cell(self, w, h, txt='', border=0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=False):
		"""Safely add a cell with text, handling Unicode errors gracefully."""
		try:
			# First try with the original text
			self.pdf.cell(w, h, txt, border, new_x=new_x, new_y=new_y, align=align, fill=fill)
		except Exception as e:
			if "outside the range of characters supported" in str(e):
				# Try with sanitized text
				try:
					sanitized_txt = self._sanitize_text_for_pdf(txt)
					self.pdf.cell(w, h, sanitized_txt, border, new_x=new_x, new_y=new_y, align=align, fill=fill)
					if conf['verbose'] and sanitized_txt != txt:
						print(f"Sanitized text: '{txt}' -> '{sanitized_txt}'")
				except Exception as e2:
					# Final fallback: replace with placeholder
					placeholder = f"[{len(txt)} chars]"
					self.pdf.cell(w, h, placeholder, border, new_x=new_x, new_y=new_y, align=align, fill=fill)
					if conf['verbose']:
						print(f"Text rendering failed, used placeholder: '{txt}' -> '{placeholder}'")
			else:
				# Re-raise other types of errors
				raise e
	
	def _set_color(self, color_type='text', fill=False):
		"""Set text or fill color using predefined color scheme."""
		if color_type in self.colors:
			r, g, b = self.colors[color_type]
			if fill:
				self.pdf.set_fill_color(r, g, b)
			else:
				self.pdf.set_text_color(r, g, b)
	
	def _add_section_header(self, title, level=1):
		"""Add a standardized section header with consistent formatting."""
		# Add some space before header
		self.pdf.ln(h=10)
		
		# Set header color and font
		self._set_color('header')
		if level == 1:
			self._set_font('B', 20)
			height = 15
		elif level == 2:
			self._set_font('B', 16)
			height = 12
		else:
			self._set_font('B', 14)
			height = 10
		
		# Add the header
		self.pdf.cell(0, height, title, 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Reset color to text
		self._set_color('text')
		self.pdf.ln(h=5)  # Small gap after header
	
	def _create_table_header(self, headers, widths=None, font_size=9):
		"""Create a standardized table header with consistent formatting."""
		if widths is None:
			# Auto-calculate widths if not provided
			total_width = 180  # Reasonable default
			widths = [total_width // len(headers)] * len(headers)
		
		# Set header styling
		self._set_color('table_header')
		self._set_color('table_header', fill=True)
		self._set_font('B', font_size)
		
		# Create header cells
		for i, (header, width) in enumerate(zip(headers, widths)):
			is_last = (i == len(headers) - 1)
			new_x = XPos.LMARGIN if is_last else XPos.RIGHT
			new_y = YPos.NEXT if is_last else YPos.TOP
			
			self.pdf.cell(width, 8, str(header), 1, 
						 new_x=new_x, new_y=new_y, align='C', fill=True)
		
		# Reset styling for table content
		self._set_color('text')
		self._set_font('', font_size - 1)
	
	def _create_table_row(self, values, widths, alternate_row=False, font_size=8):
		"""Create a table row with optional alternating background."""
		if alternate_row:
			self._set_color('table_alt', fill=True)
		
		for i, (value, width) in enumerate(zip(values, widths)):
			is_last = (i == len(values) - 1)
			new_x = XPos.LMARGIN if is_last else XPos.RIGHT
			new_y = YPos.NEXT if is_last else YPos.TOP
			
			# Truncate long values to fit
			str_value = str(value)
			if len(str_value) > width // 3:  # Rough character width estimation
				str_value = str_value[:width//3-2] + '...'
			
			self.pdf.cell(width, 6, str_value, 1,
						 new_x=new_x, new_y=new_y, align='C', fill=alternate_row)
	
	def create(self, data, path):
		ReportCreator.create(self, data, path)
		self.title = data.projectname
		self.output_path = path
		
		# Initialize PDF document with fpdf2 features
		self.pdf = FPDF()
		self.pdf.set_auto_page_break(auto=True, margin=15)
		
		# Load Unicode font for Chinese character support
		if self.font_family:
			unicode_loaded = self._load_unicode_font()
			if unicode_loaded and conf['verbose']:
				print(f"✓ Unicode font loaded: {self.font_family['name']}")
		else:
			if conf['verbose']:
				print("⚠ No Unicode font available - Chinese characters may cause errors")
		
		# Set metadata for better PDF properties
		self.pdf.set_title(f"GitStats Report - {data.projectname}")
		self.pdf.set_author("GitStats")
		self.pdf.set_subject(f"Git repository analysis for {data.projectname}")
		self.pdf.set_creator("GitStats with fpdf2")
		self.pdf.set_keywords("git,statistics,analysis,repository")
		
		# Create all pages (tabs)
		self._create_title_page(data)
		self._create_general_page(data)
		self._create_activity_page(data)
		self._create_authors_page(data)
		self._create_team_analysis_page(data)
		self._create_files_page(data)
		self._create_lines_page(data)
		self._create_tags_page(data)
		self._create_branches_page(data)
		
		# Save PDF with fpdf2's enhanced output method
		pdf_path = os.path.join(path, f"gitstats_{data.projectname.replace(' ', '_')}.pdf")
		
		# Use fpdf2's output method with proper file handling
		try:
			self.pdf.output(pdf_path)
			print(f"PDF report saved to: {pdf_path}")
			# Verify file was created and has content
			if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
				print(f"PDF file size: {os.path.getsize(pdf_path)} bytes")
			else:
				print("Warning: PDF file was not created properly")
		except Exception as e:
			print(f"Error saving PDF: {e}")
			raise
	
	def _add_chart_if_exists(self, chart_filename, width=None, height=None):
		"""Add a chart image to the PDF if it exists, with improved fpdf2 handling."""
		chart_path = os.path.join(self.output_path, chart_filename)
		if os.path.exists(chart_path):
			try:
				# Get current position
				x = self.pdf.get_x()
				y = self.pdf.get_y()
				
				# Calculate dimensions with better defaults
				if width is None:
					width = 150  # Default width
				if height is None:
					height = 80  # Default height
				
				# Get page dimensions for better space calculation
				page_width = self.pdf.w
				page_height = self.pdf.h
				margin = 15  # Same as auto_page_break margin
				
				# Check if there's enough space on current page
				if y + height > (page_height - margin):
					self.pdf.add_page()
					x = self.pdf.get_x()
					y = self.pdf.get_y()
				
				# Add image with fpdf2's enhanced image handling
				# fpdf2 automatically handles different image formats
				self.pdf.image(chart_path, x=x, y=y, w=width, h=height)
				
				# Move cursor below image with better spacing
				self.pdf.set_y(y + height + 8)  # Increased spacing for better layout
				
				return True
			except Exception as e:
				print(f"Warning: Could not add chart {chart_filename}: {e}")
				return False
		return False
	
	def _create_title_page(self, data):
		"""Create the title page of the PDF report."""
		self.pdf.add_page()
		self._set_font('B', 24)
		self.pdf.cell(0, 20, f'GitStats Report - {data.projectname}', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		self.pdf.ln(h=10)
		self._set_font('', 12)
		format = '%Y-%m-%d %H:%M:%S'
		
		# Report generation info
		self.pdf.cell(0, 10, f'Generated: {datetime.datetime.now().strftime(format)}', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
		self.pdf.cell(0, 10, f'Generator: GitStats (version {getversion()})', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
		self.pdf.cell(0, 10, f'Git Version: {getgitversion()}', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
		if getgnuplotversion():
			self.pdf.cell(0, 10, f'Gnuplot Version: {getgnuplotversion()}', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
		
		self.pdf.ln(h=10)
		self.pdf.cell(0, 10, f'Report Period: {data.getFirstCommitDate().strftime(format)} to {data.getLastCommitDate().strftime(format)}', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
		
		# Table of contents
		self.pdf.ln(h=15)
		self._set_font('B', 16)
		self.pdf.cell(0, 10, 'Table of Contents', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 12)
		sections = [
			'1. General Statistics',
			'2. Activity Statistics', 
			'3. Authors Statistics',
			'4. Team Analysis',
			'5. Files Statistics',
			'6. Lines of Code Statistics',
			'7. Tags Statistics',
			'8. Branches Statistics'
		]
		
		for section in sections:
			self.pdf.cell(0, 8, section, 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
	
	def _create_general_page(self, data):
		"""Create the general statistics page (mirrors index.html)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '1. General Statistics', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 12)
		
		# Calculate basic stats
		total_commits = data.getTotalCommits()
		total_active_days = len(data.getActiveDays()) if hasattr(data, 'getActiveDays') else 0
		delta_days = data.getCommitDeltaDays() if hasattr(data, 'getCommitDeltaDays') else 0
		total_authors = data.getTotalAuthors()
		
		# General statistics (matching index.html exactly)
		stats = [
			('Project name', data.projectname),
			('Generated', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
			('Report Period', f"{data.getFirstCommitDate().strftime('%Y-%m-%d %H:%M:%S')} to {data.getLastCommitDate().strftime('%Y-%m-%d %H:%M:%S')}"),
			('Age', f"{delta_days} days, {total_active_days} active days ({(100.0 * total_active_days / delta_days) if delta_days else 0.0:.2f}%)"),
			('Total Files', str(data.getTotalFiles())),
			('Total Lines of Code', f"{data.getTotalLOC()} ({data.total_lines_added} added, {data.total_lines_removed} removed)"),
			('Source Lines of Code', f"{data.getTotalSourceLines()} ({(100.0 * data.getTotalSourceLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0:.1f}%)"),
			('Comment Lines', f"{data.getTotalCommentLines()} ({(100.0 * data.getTotalCommentLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0:.1f}%)"),
			('Blank Lines', f"{data.getTotalBlankLines()} ({(100.0 * data.getTotalBlankLines() / data.getTotalLOC()) if data.getTotalLOC() else 0.0:.1f}%)"),
			('Total Commits', f"{total_commits} (average {(float(total_commits) / total_active_days) if total_active_days else 0.0:.1f} commits per active day, {(float(total_commits) / delta_days) if delta_days else 0.0:.1f} per all days)"),
			('Authors', f"{total_authors} (average {(float(total_commits) / total_authors) if total_authors else 0.0:.1f} commits per author)"),
			('Total Branches', str(len(data.getBranches()))),
			('Unmerged Branches', str(len(data.getUnmergedBranches()))),
			('Main Branch', data.main_branch if hasattr(data, 'main_branch') else 'N/A')
		]
		
		# Display stats
		for label, value in stats:
			self.pdf.cell(50, 8, f"{label}:", 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(0, 8, str(value), 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=10)
	
	def _create_activity_page(self, data):
		"""Create the activity statistics page with charts (mirrors activity.html)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '2. Activity Statistics', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Weekly activity section
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Weekly Activity', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._set_font('', 10)
		self.pdf.cell(0, 6, 'Last 32 weeks activity (see chart below)', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self.pdf.ln(h=5)
		
		# Hour of Day section
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Hour of Day', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 10)
		hour_of_day = data.getActivityByHourOfDay()
		total_commits = data.getTotalCommits()
		
		# Create hour of day table
		self._set_font('B', 8)
		self.pdf.cell(20, 6, 'Hour', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		for h in range(0, 24):
			self.pdf.cell(7, 6, str(h), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.ln()
		
		self.pdf.cell(20, 6, 'Commits', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		for h in range(0, 24):
			commits = hour_of_day.get(h, 0)
			self.pdf.cell(7, 6, str(commits), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.ln()
		
		self.pdf.cell(20, 6, '%', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		for h in range(0, 24):
			commits = hour_of_day.get(h, 0)
			percent = (100.0 * commits / total_commits) if total_commits else 0.0
			self.pdf.cell(7, 6, f"{percent:.1f}", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.ln(h=10)
		
		# Add hour of day chart
		self._add_chart_if_exists('hour_of_day.png', 180, 90)
		
		# Day of Week section
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Day of Week', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 10)
		day_of_week = data.getActivityByDayOfWeek()
		
		# Create day of week table
		self._set_font('B', 10)
		self.pdf.cell(30, 8, 'Day', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(30, 8, 'Total (%)', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		self._set_font('', 10)
		for d in range(0, 7):
			day_name = WEEKDAYS[d]
			commits = day_of_week.get(d, 0)
			percent = (100.0 * commits / total_commits) if total_commits else 0.0
			self.pdf.cell(30, 6, day_name, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(30, 6, f"{commits} ({percent:.2f}%)", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=5)
		self._add_chart_if_exists('day_of_week.png', 180, 90)
		
		# Month of Year section  
		if hasattr(data, 'activity_by_month_of_year'):
			self._set_font('B', 14) 
			self.pdf.cell(0, 10, 'Month of Year', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			
			self._set_font('B', 10)
			self.pdf.cell(30, 8, 'Month', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(40, 8, 'Commits (%)', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
			
			self._set_font('', 10)
			for mm in range(1, 13):
				commits = data.activity_by_month_of_year.get(mm, 0)
				percent = (100.0 * commits / total_commits) if total_commits else 0.0
				self.pdf.cell(30, 6, str(mm), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(40, 6, f"{commits} ({percent:.2f} %)", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			
			self.pdf.ln(h=5)
			self._add_chart_if_exists('month_of_year.png', 180, 90)
		
		# Add page break for next major chart
		if self.pdf.get_y() > 200:
			self.pdf.add_page()
		
		# Commits by year/month chart
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Commits by Year/Month', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._add_chart_if_exists('commits_by_year_month.png', 180, 100)
		
		# Commits by year chart 
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Commits by Year', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._add_chart_if_exists('commits_by_year.png', 180, 100)
	
	def _create_authors_page(self, data):
		"""Create the authors statistics page with charts (mirrors authors.html)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '3. Authors Statistics', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# List of Authors table
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'List of Authors', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		authors = data.getAuthors(conf['max_authors'])
		
		# Table header
		self._set_font('B', 8)
		self.pdf.cell(35, 6, 'Author', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(20, 6, 'Commits (%)', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(15, 6, '+ lines', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(15, 6, '- lines', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 6, 'First commit', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 6, 'Last commit', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(20, 6, 'Age', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(15, 6, 'Active days', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		# Table data
		self._set_font('', 7)
		for author in authors[:20]:  # Top 20 authors
			info = data.getAuthorInfo(author)
			
			# Truncate long author names
			display_author = author[:18] + "..." if len(author) > 21 else author
			
			self.pdf.cell(35, 5, display_author, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(20, 5, f"{info['commits']} ({info['commits_frac']:.1f}%)", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(15, 5, str(info['lines_added']), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(15, 5, str(info['lines_removed']), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 5, info['date_first'][:10], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 5, info['date_last'][:10], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			
			# Calculate age
			try:
				age_days = (datetime.datetime.strptime(info['date_last'][:10], '%Y-%m-%d') - 
						   datetime.datetime.strptime(info['date_first'][:10], '%Y-%m-%d')).days
				age_text = f"{age_days} days" if age_days > 0 else "1 day"
			except:
				age_text = "N/A"
			
			active_days = len(info.get('active_days', [0])) if 'active_days' in info else 1
			
			self.pdf.cell(20, 5, age_text[:12], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(15, 5, str(active_days), 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		self.pdf.ln(h=10)
		
		# Lines of code by author chart
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Cumulated Added Lines of Code per Author', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._add_chart_if_exists('lines_of_code_by_author.png', 180, 110)
		
		# Commits per author chart
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Commits per Author', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._add_chart_if_exists('commits_by_author.png', 180, 110)
		
		# Commits by domains chart
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Commits by Domains', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._add_chart_if_exists('domains.png', 180, 100)
	
	def _create_team_analysis_page(self, data):
		"""Create the team analysis page for comprehensive team evaluation (new feature)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '4. Team Analysis', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Team Overview
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Team Overview', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 12)
		total_authors = data.getTotalAuthors()
		work_distribution = data.getTeamWorkDistribution()
		
		self.pdf.cell(50, 8, 'Total Team Members:', 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
		self.pdf.cell(0, 8, str(total_authors), 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Calculate work distribution metrics
		commit_contributions = [dist['commit_percentage'] for dist in work_distribution.values()]
		if commit_contributions:
			max_contrib = max(commit_contributions)
			min_contrib = min(commit_contributions)
			avg_contrib = sum(commit_contributions) / len(commit_contributions)
			
			self.pdf.cell(50, 8, 'Work Distribution:', 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(0, 8, f'Max: {max_contrib:.1f}%, Min: {min_contrib:.1f}%, Avg: {avg_contrib:.1f}%', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=10)
		
		# Team Performance Rankings
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Team Performance Rankings', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Top Contributors
		contrib_ranking = data.getAuthorsByContribution()
		efficiency_ranking = data.getAuthorsByEfficiency()
		
		self._set_font('B', 12)
		self.pdf.cell(0, 8, 'Top 10 Contributors (by commit percentage):', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._set_font('', 10)
		
		for i, (author, percentage) in enumerate(contrib_ranking[:10], 1):
			display_author = author[:30] + "..." if len(author) > 33 else author
			self.pdf.cell(0, 6, f'{i}. {display_author} ({percentage:.1f}%)', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=5)
		
		# Team Performance Table
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Detailed Performance Analysis', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		team_performance = data.getTeamPerformance()
		commit_patterns = data.getCommitPatterns()
		
		# Table header
		self._set_font('B', 8)
		self.pdf.cell(35, 6, 'Author', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(20, 6, 'Commits', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(20, 6, 'Contrib %', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 6, 'Efficiency', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 6, 'Consistency', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 6, 'Leadership', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 6, 'Overall', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		# Table data - show top 15 performers
		self._set_font('', 7)
		sorted_authors = sorted(team_performance.items(), key=lambda x: x[1].get('overall_score', 0), reverse=True)
		
		for author, perf in sorted_authors[:15]:
			author_info = data.getAuthorInfo(author)
			
			commits = author_info.get('commits', 0)
			contrib_pct = perf.get('contribution_percentage', 0)
			efficiency = perf.get('efficiency_score', 0)
			consistency = perf.get('consistency', 0)
			leadership = perf.get('leadership_score', 0)
			overall = perf.get('overall_score', 0)
			
			# Truncate long author names
			display_author = author[:18] + "..." if len(author) > 21 else author
			
			self.pdf.cell(35, 5, display_author, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(20, 5, str(commits), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(20, 5, f'{contrib_pct:.1f}%', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 5, f'{efficiency:.1f}', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 5, f'{consistency:.1f}', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 5, f'{leadership:.1f}', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 5, f'{overall:.1f}', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		self.pdf.ln(h=10)
		
		# Team Assessment Conclusion
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Team Assessment Conclusion', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 10)
		
		# Generate team insights
		top_contributor = contrib_ranking[0] if contrib_ranking else ("N/A", 0)
		most_efficient = efficiency_ranking[0] if efficiency_ranking else ("N/A", 0)
		
		self.pdf.cell(0, 6, f'- Top contributor: {top_contributor[0]} ({top_contributor[1]:.1f}% of commits)', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self.pdf.cell(0, 6, f'- Most efficient developer: {most_efficient[0]} (score: {most_efficient[1]:.1f})', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self.pdf.cell(0, 6, f'- Team size: {total_authors} active contributors', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Work distribution assessment
		if commit_contributions:
			gini_coefficient = self._calculate_gini_coefficient(commit_contributions)
			if gini_coefficient < 0.3:
				distribution_assessment = "Well-distributed (very balanced team)"
			elif gini_coefficient < 0.5:
				distribution_assessment = "Moderately distributed (some imbalance)"
			else:
				distribution_assessment = "Highly concentrated (few dominant contributors)"
			
			self.pdf.cell(0, 6, f'- Work distribution: {distribution_assessment}', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
	
	def _calculate_gini_coefficient(self, values):
		"""Calculate Gini coefficient for work distribution analysis."""
		if not values:
			return 0
		
		sorted_values = sorted(values)
		n = len(sorted_values)
		cumsum = sum(sorted_values)
		
		if cumsum == 0:
			return 0
		
		sum_of_differences = 0
		for i in range(n):
			for j in range(n):
				sum_of_differences += abs(sorted_values[i] - sorted_values[j])
		
		gini = sum_of_differences / (2 * n * cumsum)
		return gini
	
	def _create_files_page(self, data):
		"""Create the files statistics page with charts (mirrors files.html)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '5. Files Statistics', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Basic file stats
		total_files = data.getTotalFiles()
		total_loc = data.getTotalLOC()
		
		self._set_font('', 12)
		stats = [
			('Total files', str(total_files)),
			('Total lines', str(total_loc)),
		]
		
		try:
			avg_size = data.getAverageFileSize()
			stats.append(('Average file size', f"{avg_size:.2f} bytes"))
		except (AttributeError, ZeroDivisionError):
			# Fallback to old calculation if new method fails
			avg_size = float(data.getTotalSize()) / total_files if total_files else 0.0
			stats.append(('Average file size', f"{avg_size:.2f} bytes"))
		
		try:
			avg_revisions = data.getAverageRevisionsPerFile()
			stats.append(('Average revisions per file', f"{avg_revisions:.2f}"))
		except AttributeError:
			pass
		
		for label, value in stats:
			self.pdf.cell(50, 8, f"{label}:", 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(0, 8, str(value), 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=10)
		
		# File extensions
		if hasattr(data, 'extensions') and data.extensions:
			self._set_font('B', 14)
			self.pdf.cell(0, 10, 'File Extensions', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			
			# Table header
			self._set_font('B', 9)
			self.pdf.cell(25, 8, 'Extension', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(20, 8, 'Files', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(20, 8, '% Files', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 8, 'Lines', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(20, 8, '% Lines', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 8, 'Lines/File', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
			
			# Table data - show top extensions
			self._set_font('', 8)
			sorted_extensions = sorted(data.extensions.items(), 
									 key=lambda x: x[1]['files'], reverse=True)[:15]
			
			for ext, ext_data in sorted_extensions:
				files = ext_data['files']
				lines = ext_data['lines']
				loc_percentage = (100.0 * lines / total_loc) if total_loc else 0.0
				files_percentage = (100.0 * files / total_files) if total_files else 0.0
				lines_per_file = (lines // files) if files else 0
				
				display_ext = ext if ext else '(no ext)'
				
				self.pdf.cell(25, 6, display_ext[:12], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
				self.pdf.cell(20, 6, str(files), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(20, 6, f"{files_percentage:.1f}%", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(25, 6, str(lines), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(20, 6, f"{loc_percentage:.1f}%", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(25, 6, str(lines_per_file), 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		self.pdf.ln(h=10)
		
		# SLOC Breakdown by Extension
		sloc_data = data.getSLOCByExtension()
		if sloc_data:
			self._set_font('B', 14)
			self.pdf.cell(0, 10, 'Source Lines of Code (SLOC) Breakdown', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			
			# Table header
			self._set_font('B', 8)
			self.pdf.cell(20, 8, 'Extension', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 8, 'Source Lines', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 8, 'Comment Lines', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 8, 'Blank Lines', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(20, 8, 'Total', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
			
			# Table data
			self._set_font('', 7)
			sorted_sloc = sorted(sloc_data.items(), 
								key=lambda x: x[1]['total'], reverse=True)[:15]
			
			for ext, sloc_info in sorted_sloc:
				if sloc_info['total'] == 0:
					continue
				
				display_ext = ext if ext else '(no ext)'
				source_pct = (100.0 * sloc_info['source'] / sloc_info['total']) if sloc_info['total'] else 0.0
				comment_pct = (100.0 * sloc_info['comments'] / sloc_info['total']) if sloc_info['total'] else 0.0
				blank_pct = (100.0 * sloc_info['blank'] / sloc_info['total']) if sloc_info['total'] else 0.0
				
				self.pdf.cell(20, 5, display_ext[:8], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
				self.pdf.cell(25, 5, f"{sloc_info['source']} ({source_pct:.1f}%)", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(25, 5, f"{sloc_info['comments']} ({comment_pct:.1f}%)", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(25, 5, f"{sloc_info['blank']} ({blank_pct:.1f}%)", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(20, 5, str(sloc_info['total']), 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		self.pdf.ln(h=10)
		
		# Add new file statistics tables
		try:
			# Largest Files
			largest_files = data.getLargestFiles(10)
			if largest_files:
				self._set_font('B', 14)
				self.pdf.cell(0, 10, 'Largest Files', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
				
				# Table header
				self._set_font('B', 9)
				self.pdf.cell(80, 8, 'File', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(30, 8, 'Size (bytes)', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(30, 8, 'Size (KB)', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
				
				# Table data
				self._set_font('', 8)
				for filepath, size in largest_files:
					size_kb = size / 1024.0
					display_path = filepath[:40] + '...' if len(filepath) > 40 else filepath
					self.pdf.cell(80, 6, display_path, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
					self.pdf.cell(30, 6, str(size), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
					self.pdf.cell(30, 6, f"{size_kb:.1f}", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		except (AttributeError, TypeError):
			pass
		
		try:
			# Files with Most Revisions (Hotspots)
			hotspot_files = data.getFilesWithMostRevisions(10)
			if hotspot_files:
				self.pdf.ln(h=10)
				self._set_font('B', 14)
				self.pdf.cell(0, 10, 'Files with Most Revisions (Hotspots)', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
				
				# Table header
				self._set_font('B', 9)
				self.pdf.cell(80, 8, 'File', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(30, 8, 'Revisions', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(30, 8, '% of Commits', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
				
				# Table data
				self._set_font('', 8)
				total_commits = data.getTotalCommits()
				for filepath, revisions in hotspot_files:
					revision_pct = (100.0 * revisions / total_commits) if total_commits else 0.0
					display_path = filepath[:40] + '...' if len(filepath) > 40 else filepath
					self.pdf.cell(80, 6, display_path, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
					self.pdf.cell(30, 6, str(revisions), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
					self.pdf.cell(30, 6, f"{revision_pct:.2f}%", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		except (AttributeError, TypeError):
			pass
		
		self.pdf.ln(h=10)
		
		# Files by date chart
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Files by Date', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._add_chart_if_exists('files_by_date.png', 180, 100)
	
	def _create_lines_page(self, data):
		"""Create the lines of code statistics page with charts (mirrors lines.html)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '6. Lines of Code Statistics', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Basic line stats
		self._set_font('', 12)
		stats = [
			('Total lines', str(data.getTotalLOC())),
			('Lines added', str(data.total_lines_added)),
			('Lines removed', str(data.total_lines_removed)),
			('Net lines', str(data.total_lines_added - data.total_lines_removed)),
		]
		
		for label, value in stats:
			self.pdf.cell(50, 8, f"{label}:", 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(0, 8, str(value), 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=10)
		
		# Lines by year
		if hasattr(data, 'commits_by_year') and data.commits_by_year:
			self._set_font('B', 14)
			self.pdf.cell(0, 10, 'Activity by Year', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			
			# Table header
			self._set_font('B', 10)
			self.pdf.cell(25, 8, 'Year', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(30, 8, 'Commits', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(30, 8, '% of Total', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(35, 8, 'Lines Added', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(35, 8, 'Lines Removed', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
			
			# Table data
			self._set_font('', 9)
			total_commits = data.getTotalCommits()
			
			for yy in sorted(data.commits_by_year.keys(), reverse=True):
				commits = data.commits_by_year.get(yy, 0)
				percent = (100.0 * commits / total_commits) if total_commits else 0.0
				lines_added = data.lines_added_by_year.get(yy, 0) if hasattr(data, 'lines_added_by_year') else 0
				lines_removed = data.lines_removed_by_year.get(yy, 0) if hasattr(data, 'lines_removed_by_year') else 0
				
				self.pdf.cell(25, 6, str(yy), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(30, 6, str(commits), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(30, 6, f"{percent:.1f}%", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(35, 6, str(lines_added), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(35, 6, str(lines_removed), 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		self.pdf.ln(h=10)
		
		# Lines of code chart
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Lines of Code Over Time', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		self._add_chart_if_exists('lines_of_code.png', 180, 100)
	
	def _create_tags_page(self, data):
		"""Create the tags statistics page (mirrors tags.html)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '7. Tags Statistics', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 12)
		
		if not hasattr(data, 'tags') or not data.tags:
			self.pdf.cell(0, 10, 'No tags found in repository.', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			return
		
		# Basic tag stats
		total_tags = len(data.tags)
		avg_commits_per_tag = (1.0 * data.getTotalCommits() / total_tags) if total_tags else 0.0
		
		stats = [
			('Total tags', str(total_tags)),
			('Average commits per tag', f"{avg_commits_per_tag:.2f}"),
		]
		
		for label, value in stats:
			self.pdf.cell(50, 8, f"{label}:", 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(0, 8, str(value), 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=10)
		
		# Tags table
		if hasattr(data, 'tags') and data.tags:
			self._set_font('B', 12)
			self.pdf.cell(0, 10, 'List of Tags', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			
			# Table header
			self._set_font('B', 10)
			self.pdf.cell(40, 8, 'Tag', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(30, 8, 'Date', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(30, 8, 'Commits', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(50, 8, 'Author', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
			
			# Table data
			self._set_font('', 9)
			tag_list = sorted(data.tags.items(), key=lambda x: x[1]['date'], reverse=True)
			
			for tag, tag_data in tag_list[:20]:  # Show top 20 tags
				self.pdf.cell(40, 6, tag[:20], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
				self.pdf.cell(30, 6, tag_data.get('date', 'N/A')[:10], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				self.pdf.cell(30, 6, str(tag_data.get('commits', 0)), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
				author = tag_data.get('author', 'N/A')[:25]
				self.pdf.cell(50, 6, author, 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Tags table
		self._set_font('B', 14)
		self.pdf.cell(0, 10, 'Recent Tags', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Table header
		self._set_font('B', 10)
		self.pdf.cell(40, 8, 'Tag Name', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(30, 8, 'Date', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 8, 'Commits', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(80, 8, 'Top Authors', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		# Sort tags by date (most recent first)
		tags_sorted_by_date_desc = list(map(lambda el : el[1], 
										  reversed(sorted(map(lambda el : (el[1]['date'], el[0]), 
														  data.tags.items())))))
		
		# Show up to 20 most recent tags
		self._set_font('', 8)
		for tag in tags_sorted_by_date_desc[:20]:
			tag_info = data.tags[tag]
			
			# Get top authors for this tag
			if 'authors' in tag_info:
				authors = sorted(tag_info['authors'].items(), 
							   key=lambda x: x[1], reverse=True)[:3]
				author_list = ', '.join([f"{author}({commits})" for author, commits in authors])
			else:
				author_list = ''
			
			# Truncate long names
			display_tag = tag[:18] + "..." if len(tag) > 21 else tag
			display_authors = author_list[:35] + "..." if len(author_list) > 38 else author_list
			
			self.pdf.cell(40, 6, display_tag, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(30, 6, tag_info['date'][:10], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 6, str(tag_info['commits']), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(80, 6, display_authors, 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

	def _create_branches_page(self, data):
		"""Create the branches statistics page (mirrors branches.html)."""
		self.pdf.add_page()
		self._set_font('B', 20)
		self.pdf.cell(0, 15, '8. Branches Statistics', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self._set_font('', 12)
		
		if not hasattr(data, 'branches') or not data.branches:
			self.pdf.cell(0, 10, 'No branches found in repository.', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			return
		
		# Basic branch stats
		total_branches = len(data.getBranches())
		unmerged_branches = data.getUnmergedBranches()
		total_unmerged = len(unmerged_branches)
		main_branch = data.main_branch if hasattr(data, 'main_branch') else 'N/A'
		
		stats = [
			('Total branches', str(total_branches)),
			('Unmerged branches', str(total_unmerged)),
			('Main branch', main_branch),
		]
		
		for label, value in stats:
			self.pdf.cell(50, 8, f"{label}:", 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(0, 8, str(value), 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		self.pdf.ln(h=10)
		
		# Branches summary table
		self._set_font('B', 12)
		self.pdf.cell(0, 10, 'All Branches', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Table header
		self._set_font('B', 9)
		self.pdf.cell(35, 8, 'Branch Name', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(20, 8, 'Status', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(20, 8, 'Commits', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 8, 'Lines Added', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(25, 8, 'Lines Removed', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(20, 8, 'Authors', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
		self.pdf.cell(45, 8, 'First Author', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
		
		# Table data - sort by commits descending
		self._set_font('', 8)
		branches_sorted = sorted(data.branches.items(), 
								key=lambda x: x[1].get('commits', 0), reverse=True)
		
		for branch_name, branch_data in branches_sorted:
			# Determine status
			status = 'Unmerged' if branch_name in [b for b in unmerged_branches] else 'Merged'
			
			# Get branch statistics
			commits = branch_data.get('commits', 0)
			lines_added = branch_data.get('lines_added', 0)
			lines_removed = branch_data.get('lines_removed', 0)
			authors_count = len(branch_data.get('authors', {}))
			
			# Get first/main author
			authors = branch_data.get('authors', {})
			if authors:
				first_author = max(authors.items(), key=lambda x: x[1])[0]
				first_author = first_author[:20] + "..." if len(first_author) > 23 else first_author
			else:
				first_author = 'N/A'
			
			# Truncate branch name if too long
			display_branch = branch_name[:18] + "..." if len(branch_name) > 21 else branch_name
			
			self.pdf.cell(35, 6, display_branch, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
			self.pdf.cell(20, 6, status, 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(20, 6, str(commits), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 6, str(lines_added), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(25, 6, str(lines_removed), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(20, 6, str(authors_count), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
			self.pdf.cell(45, 6, first_author, 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
		
		# Unmerged branches detail section
		if total_unmerged > 0:
			self.pdf.ln(h=10)
			self._set_font('B', 14)
			self.pdf.cell(0, 10, f'Unmerged Branches Details ({total_unmerged})', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			
			self._set_font('', 10)
			for branch_name in unmerged_branches:
				if branch_name in data.branches:
					branch_data = data.branches[branch_name]
					
					self._set_font('B', 10)
					self.pdf.cell(0, 8, f"Branch: {branch_name}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
					
					self._set_font('', 9)
					self.pdf.cell(20, 6, f"  Commits: {branch_data.get('commits', 0)}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
					self.pdf.cell(20, 6, f"  Lines: +{branch_data.get('lines_added', 0)} -{branch_data.get('lines_removed', 0)}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
					
					# Show authors
					authors = branch_data.get('authors', {})
					if authors:
						author_list = sorted(authors.items(), key=lambda x: x[1], reverse=True)
						author_str = ', '.join([f"{author}({commits})" for author, commits in author_list[:3]])
						if len(author_list) > 3:
							author_str += f" and {len(author_list) - 3} more"
						self.pdf.cell(20, 6, f"  Authors: {author_str}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
					
					self.pdf.ln(h=2)
		
		
		
def is_git_repository(path):
	"""Check if a directory is a valid git repository.
	
	Handles regular repositories, bare repositories, and git worktrees.
	Also validates that the repository is accessible and not corrupted.
	"""
	if not os.path.exists(path):
		return False
	
	# Resolve symbolic links to get the real path
	try:
		real_path = os.path.realpath(path)
		if not os.path.isdir(real_path):
			return False
	except (OSError, PermissionError):
		return False
	
	# Check for regular git repository (.git directory)
	git_dir = os.path.join(real_path, '.git')
	if os.path.exists(git_dir):
		# For regular repos, .git can be a directory or a file (worktree)
		if os.path.isdir(git_dir):
			# Regular repository - verify it's not corrupted
			return _validate_git_directory(git_dir)
		elif os.path.isfile(git_dir):
			# Git worktree - read the gitdir path
			try:
				with open(git_dir, 'r') as f:
					gitdir_line = f.read().strip()
					if gitdir_line.startswith('gitdir: '):
						gitdir_path = gitdir_line[8:]  # Remove 'gitdir: ' prefix
						if not os.path.isabs(gitdir_path):
							gitdir_path = os.path.join(real_path, gitdir_path)
						return os.path.exists(gitdir_path) and _validate_git_directory(gitdir_path)
			except (IOError, OSError):
				return False
	
	# Check for bare repository (no .git directory, but has git objects)
	if _is_bare_repository(real_path):
		return True
	
	return False

def _validate_git_directory(git_dir):
	"""Validate that a .git directory contains the essential git structure."""
	try:
		# Check for essential git directories/files
		essential_items = ['objects', 'refs', 'HEAD']
		for item in essential_items:
			item_path = os.path.join(git_dir, item)
			if not os.path.exists(item_path):
				return False
		
		# Verify we can run basic git commands in this directory
		# This is the most reliable way to check if git can work with this repo
		parent_dir = os.path.dirname(git_dir)
		try:
			# Try to get the git directory path - if this fails, the repo is corrupted
			result = getpipeoutput([f'cd "{parent_dir}" && git rev-parse --git-dir'], quiet=True)
			return result.strip() != ''
		except:
			return False
			
	except (OSError, PermissionError):
		return False
	
	return True

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

def discover_repositories(scan_path, recursive=False, max_depth=3, include_patterns=None, exclude_patterns=None):
	"""Discover all git repositories in a directory with advanced options.
	
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

def usage():
	print("""
Usage: gitstats [options] <gitpath..> <outputpath>
       gitstats [options] --multi-repo <scan-folder> <outputpath>

Options:
-c key=value     Override configuration value
--debug          Enable debug output
--verbose        Enable verbose output
--multi-repo     Scan folder for multiple repositories and generate reports for each
-h, --help       Show this help message

Note: GitStats always generates both HTML and PDF reports.

Examples:
  gitstats repo output                    # Generates both HTML and PDF reports
  gitstats --verbose repo output          # With verbose output
  gitstats --multi-repo /path/to/repos output  # Generate reports for all repos in folder
  gitstats --debug -c max_authors=50 repo output
  
  # Multi-repo with configuration options:
  gitstats -c multi_repo_recursive=True --multi-repo /path/to/repos output
  gitstats -c multi_repo_max_depth=5 -c multi_repo_recursive=True --multi-repo /path/to/repos output

With --multi-repo mode:
- Scans the specified folder for git repositories
- Creates a report for each repository in a subfolder named <reponame>_report
- Only processes directories that are valid git repositories
- Generates a summary report with links to all individual reports

Multi-repo configuration options (use with -c key=value):
  multi_repo_recursive=True/False       # Enable recursive directory scanning (default: False)
  multi_repo_max_depth=N               # Maximum depth for recursive scanning (default: 3)
  multi_repo_include_patterns=pat1,pat2 # Comma-separated glob patterns for directories to include
  multi_repo_exclude_patterns=pat1,pat2 # Comma-separated glob patterns for directories to exclude
  multi_repo_timeout=N                 # Timeout in seconds per repository (default: 3600)
  multi_repo_cleanup_on_error=True/False # Clean up partial output on error (default: True)

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
			
			# Check for additional multi-repo configuration options
			recursive_scan = conf.get('multi_repo_recursive', False)
			max_depth = conf.get('multi_repo_max_depth', 3)
			include_patterns = conf.get('multi_repo_include_patterns', None)
			exclude_patterns = conf.get('multi_repo_exclude_patterns', None)
			
			# Discover repositories with enhanced options
			print(f'Scanning folder for git repositories: {scan_folder}')
			if recursive_scan:
				print(f'  Using recursive scanning (max depth: {max_depth})')
			
			try:
				repositories = discover_repositories(
					scan_folder, 
					recursive=recursive_scan,
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
				if not recursive_scan:
					print('Hint: Try using recursive scanning with --multi-repo-recursive option')
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

		# Validate gnuplot availability
		try:
			gnuplot_version = getgnuplotversion()
			if not gnuplot_version:
				print('FATAL: gnuplot not found - required for generating charts')
				sys.exit(1)
			if conf['verbose']:
				print(f'Using {gnuplot_version}')
		except Exception as e:
			print(f'FATAL: Error checking gnuplot: {e}')
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
		import signal
		import threading
		
		# Store original signal handler
		original_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)
		
		try:
			self.process_single_repository(repo_path, output_path, rundir)
		except KeyboardInterrupt:
			# Re-raise keyboard interrupt to allow proper cleanup
			raise
		except Exception as e:
			# Enhance error message with repository context
			enhanced_error = f"Error processing {repo_name}: {str(e)}"
			raise Exception(enhanced_error) from e
		finally:
			# Restore original signal handler
			signal.signal(signal.SIGTERM, original_sigterm)
	
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
		"""Original single/multiple repository mode."""
		outputpath = os.path.abspath(args[-1])
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

		# Validate and create output directory
		try:
			os.makedirs(outputpath, exist_ok=True)
		except PermissionError:
			print(f'FATAL: Permission denied creating output directory: {outputpath}')
			sys.exit(1)
		except OSError as e:
			print(f'FATAL: Error creating output directory {outputpath}: {e}')
			sys.exit(1)
		
		if not os.path.isdir(outputpath):
			print('FATAL: Output path is not a directory or does not exist')
			sys.exit(1)
		
		# Check write permissions
		if not os.access(outputpath, os.W_OK):
			print(f'FATAL: No write permission for output directory: {outputpath}')
			sys.exit(1)

		if not getgnuplotversion():
			print('gnuplot not found')
			sys.exit(1)

		if conf['verbose']:
			print('Configuration:')
			for key, value in conf.items():
				print(f'  {key}: {value}')
			print()

		print('Output path: %s' % outputpath)
		cachefile = os.path.join(outputpath, 'gitstats.cache')

		data = GitDataCollector()
		data.loadCache(cachefile)

		for gitpath in git_paths:
			print('Git path: %s' % gitpath)

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
		
		# Always generate both HTML and PDF reports
		print('Creating HTML report...')
		html_report = HTMLReportCreator()
		html_report.create(data, outputpath)
		
		print('Creating PDF report...')
		pdf_report = PDFReportCreator()
		pdf_report.create(data, outputpath)

		time_end = time.time()
		exectime_internal = time_end - time_start
		external_percentage = (100.0 * exectime_external) / exectime_internal if exectime_internal > 0 else 0.0
		print('Execution time %.5f secs, %.5f secs (%.2f %%) in external commands)' % (exectime_internal, exectime_external, external_percentage))
		
		if sys.stdin.isatty():
			print('You may now run:')
			print()
			print('   sensible-browser \'%s\'' % os.path.join(outputpath, 'index.html').replace("'", "'\\''"))
			pdf_filename = f"gitstats_{data.projectname.replace(' ', '_')}.pdf"
			print('   PDF report: \'%s\'' % os.path.join(outputpath, pdf_filename).replace("'", "'\\''"))
			print()
	
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
			
			# Generate PDF report
			try:
				if conf['verbose']:
					print('  Creating PDF report...')
				pdf_report = PDFReportCreator()
				pdf_report.create(data, output_path)
			except Exception as e:
				print(f'  Warning: PDF report generation failed: {e}')
				if conf['debug']:
					import traceback
					traceback.print_exc()

			if conf['verbose']:
				print(f'  Report generated in: {output_path}')
		
		except Exception as e:
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
			raise e
		
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
			return None
		except Exception:
			return None

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

