"""
HTML report generator module for Gitstats3.

Contains the ReportCreator base class and HTMLReportCreator for generating HTML reports.
"""

import datetime
import os
import time

from .gitstats_config import conf, get_config
from .gitstats_helpers import WEEKDAYS, getkeyssortedbyvalues, getkeyssortedbyvaluekey, get_output_format
from .gitstats_gitcommands import getversion, getgitversion, get_exectime_external
from .gitstats_tabledata import TableDataGenerator
from .gitstats_sortable import get_sortable_js
from .gitstats_oopmetrics import format_oop_report


def html_linkify(text):
    return text

def html_header(level, text):
    return '<h%d>%s</h%d>\n' % (level, text, level)


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
			from collections import defaultdict as dd
			author_commit_totals = dd(int)
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
		# Get JavaScript content from sortable module
		js_content = get_sortable_js().replace('%', '%%')
		
		f.write(
"""<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8">
	<title>GitStats - %s</title>
	<link rel="stylesheet" href="%s" type="text/css">
	<meta name="generator" content="GitStats %s">
	<script type="text/javascript">
%s
	</script>
</head>
<body>
""" % (self.title, conf['style'], getversion(), js_content))

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

		# Get JavaScript content from sortable module
		js_content = get_sortable_js().replace('%', '%%')

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


