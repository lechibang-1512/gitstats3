"""
OOP Metrics Module - Normalized Distance from Main Sequence Analysis

This module implements Object-Oriented Programming metrics analysis with a focus on
the Normalized Distance from Main Sequence (D) metric as defined by Robert C. Martin.

Key Metrics:
- Afferent Coupling (Ca): Number of classes outside the package that depend on classes inside the package
- Efferent Coupling (Ce): Number of classes inside the package that depend on classes outside the package
- Instability (I): Ce / (Ce + Ca) - Measures package's resilience to change
- Abstractness (A): Abstract classes / Total classes - Measures package's abstraction level
- Distance from Main Sequence (D): |A + I - 1| - Measures balance between abstraction and stability

Benefits of Low Distance (D):
• The value of D should be as low as possible so that the components were located close to the main sequence
• A = 0 and I = 0: Extremely stable and concrete package - undesirable because the package is very stiff
  and cannot be extended
• A = 1 and I = 1: Impossible situation because a completely abstract package must have some connection
  to the outside, so that the instance that implements the functionality defined in abstract classes
  contained in this package could be created

Interpretation:
• D close to 0 (< 0.2): Good - Package is well-balanced
• D between 0.2-0.4: Moderate - Package may need refactoring
• D > 0.4: Poor - Package has design issues (Zone of Pain or Zone of Uselessness)
• Zone of Pain: High stability, low abstraction (A→0, I→0, D→1)
• Zone of Uselessness: High abstraction, low stability (A→1, I→1, D→1)

Author: GitStats3 Enhancement
Date: 2025
"""

import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple, Set


class OOPMetricsAnalyzer:
	"""Analyzer for Object-Oriented Programming metrics with focus on Distance from Main Sequence."""
	
	def __init__(self):
		"""Initialize the OOP metrics analyzer."""
		self.packages = {}  # package_path -> metrics
		self.files = {}     # file_path -> metrics
		self.dependencies = defaultdict(set)  # file_path -> set of dependencies
		self.dependents = defaultdict(set)    # file_path -> set of dependents
		
	def analyze_file(self, filepath: str, content: str, file_extension: str) -> Dict:
		"""
		Analyze a single file for OOP metrics.
		
		Args:
			filepath: Path to the file
			content: Content of the file
			file_extension: File extension (e.g., '.py', '.java')
			
		Returns:
			Dictionary containing OOP metrics for the file
		"""
		metrics = {
			'filepath': filepath,
			'extension': file_extension,
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'instability': 0.0,
			'abstractness': 0.0,
			'distance_main_sequence': 0.0,
			'zone': 'unknown',
			'interpretation': 'unknown',
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': [],
			'dependents': []
		}
		
		if not content.strip():
			return metrics
		
		try:
			# Remove comments and strings for accurate analysis
			cleaned_content = self._remove_comments_and_strings(content, file_extension)
			
			# Language-specific OOP analysis
			if file_extension in ['.java', '.scala', '.kt']:
				metrics.update(self._analyze_java_oop(cleaned_content, filepath))
			elif file_extension in ['.py', '.pyi']:
				metrics.update(self._analyze_python_oop(cleaned_content, filepath))
			elif file_extension in ['.cpp', '.cc', '.cxx', '.hpp', '.hxx', '.h']:
				metrics.update(self._analyze_cpp_oop(cleaned_content, filepath))
			elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
				metrics.update(self._analyze_javascript_oop(cleaned_content, filepath))
			elif file_extension in ['.swift']:
				metrics.update(self._analyze_swift_oop(cleaned_content, filepath))
			elif file_extension in ['.go']:
				metrics.update(self._analyze_go_oop(cleaned_content, filepath))
			elif file_extension in ['.rs']:
				metrics.update(self._analyze_rust_oop(cleaned_content, filepath))
			
			# Calculate derived metrics
			metrics = self._calculate_derived_metrics(metrics)
			
			# Store for package-level analysis
			self.files[filepath] = metrics
			
		except Exception as e:
			print(f'Warning: OOP metrics calculation failed for {filepath}: {e}')
		
		return metrics
	
	def _calculate_derived_metrics(self, metrics: Dict) -> Dict:
		"""
		Calculate derived OOP metrics from base measurements.
		
		Args:
			metrics: Dictionary containing base metrics
			
		Returns:
			Updated metrics dictionary with derived values
		"""
		# Calculate Abstractness: A = Abstract classes / Total classes
		if metrics['classes_defined'] > 0:
			metrics['abstractness'] = metrics['abstract_classes'] / metrics['classes_defined']
		else:
			metrics['abstractness'] = 0.0
		
		# Calculate Instability: I = Ce / (Ce + Ca)
		ce = metrics['efferent_coupling']
		ca = metrics['afferent_coupling']
		
		if (ce + ca) > 0:
			metrics['instability'] = ce / (ce + ca)
		else:
			metrics['instability'] = 0.0
		
		# Calculate Distance from Main Sequence: D = |A + I - 1|
		a = metrics['abstractness']
		i = metrics['instability']
		metrics['distance_main_sequence'] = abs(a + i - 1.0)
		
		# Add overall coupling metric
		metrics['coupling'] = ce + ca
		
		# Determine zone and interpretation
		metrics['zone'] = self._determine_zone(a, i, metrics['distance_main_sequence'])
		metrics['interpretation'] = self._interpret_distance(metrics['distance_main_sequence'], 
															  a, i, metrics['zone'])
		
		return metrics
	
	def _determine_zone(self, abstractness: float, instability: float, distance: float) -> str:
		"""
		Determine which zone the package/file falls into.
		
		Args:
			abstractness: Abstractness metric (A)
			instability: Instability metric (I)
			distance: Distance from main sequence (D)
			
		Returns:
			Zone classification string
		"""
		# Main Sequence: Ideal zone where D is close to 0
		if distance < 0.2:
			return 'main_sequence'
		
		# Zone of Pain: High stability (low I), low abstraction (low A)
		# A → 0, I → 0, making A + I - 1 → -1, so D → 1
		if abstractness < 0.3 and instability < 0.3:
			return 'zone_of_pain'
		
		# Zone of Uselessness: High abstraction (high A), low stability (high I)
		# A → 1, I → 1, making A + I - 1 → 1, so D → 1
		if abstractness > 0.7 and instability > 0.7:
			return 'zone_of_uselessness'
		
		# Transitional zones
		if distance < 0.4:
			return 'near_main_sequence'
		else:
			return 'far_from_main_sequence'
	
	def _interpret_distance(self, distance: float, abstractness: float, 
						   instability: float, zone: str) -> str:
		"""
		Provide interpretation of the distance metric.
		
		Args:
			distance: Distance from main sequence
			abstractness: Abstractness metric
			instability: Instability metric
			zone: Zone classification
			
		Returns:
			Human-readable interpretation
		"""
		interpretations = {
			'main_sequence': 'Good - Well-balanced package design',
			'near_main_sequence': 'Moderate - Package may benefit from minor refactoring',
			'zone_of_pain': 'Poor - Package is too concrete and stable (difficult to extend)',
			'zone_of_uselessness': 'Poor - Package is too abstract and unstable (unused abstractions)',
			'far_from_main_sequence': 'Poor - Package needs significant refactoring'
		}
		
		return interpretations.get(zone, 'Unknown design state')
	
	def _remove_comments_and_strings(self, content: str, file_extension: str) -> str:
		"""
		Remove comments and string literals from code.
		
		Args:
			content: Source code content
			file_extension: File extension
			
		Returns:
			Cleaned content without comments and strings
		"""
		if file_extension == '.py':
			# Remove Python comments and strings
			content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
			content = re.sub(r'""".*?"""', '', content, flags=re.DOTALL)
			content = re.sub(r"'''.*?'''", '', content, flags=re.DOTALL)
			content = re.sub(r'"[^"]*"', '', content)
			content = re.sub(r"'[^']*'", '', content)
			
		elif file_extension in ['.js', '.ts', '.jsx', '.tsx', '.java', '.scala', '.kt', 
							   '.cpp', '.c', '.cc', '.cxx', '.h', '.hpp', '.go', '.rs']:
			# Remove C-style comments and strings
			content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
			content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
			content = re.sub(r'"[^"]*"', '', content)
			content = re.sub(r"'[^']*'", '', content)
		
		return content
	
	def _analyze_java_oop(self, content: str, filepath: str) -> Dict:
		"""Analyze OOP metrics for Java/Scala/Kotlin files."""
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': []
		}
		
		# Count classes (including inner classes)
		class_patterns = [
			r'\bclass\s+(\w+)',
			r'\benum\s+(\w+)',
			r'\b@interface\s+(\w+)'
		]
		for pattern in class_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['classes_defined'] += len(matches)
		
		# Count abstract classes
		abstract_patterns = [
			r'\babstract\s+class\s+(\w+)',
			r'\babstract\s+.*\s+class\s+(\w+)'
		]
		for pattern in abstract_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['abstract_classes'] += len(matches)
		
		# Count interfaces
		interface_matches = re.findall(r'\binterface\s+(\w+)', content, re.MULTILINE)
		metrics['interfaces_defined'] = len(interface_matches)
		metrics['abstract_classes'] += len(interface_matches)  # Interfaces are abstract
		
		# Count methods
		method_patterns = [
			r'\b(public|private|protected|static).*\s+\w+\s*\([^)]*\)\s*\{',
			r'\b\w+\s*\([^)]*\)\s*\{'
		]
		for pattern in method_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['method_count'] += len(matches)
		
		# Count attributes/fields
		field_patterns = [
			r'\b(public|private|protected|static)\s+[\w<>,\[\]]+\s+\w+\s*[=;]'
		]
		for pattern in field_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['attribute_count'] += len(matches)
		
		# Analyze dependencies (efferent coupling)
		import_matches = re.findall(r'\bimport\s+([\w.]+)', content)
		metrics['dependencies'] = list(set(import_matches))
		metrics['efferent_coupling'] = len(metrics['dependencies'])
		
		# Store dependencies for later analysis
		self.dependencies[filepath] = set(metrics['dependencies'])
		
		return metrics
	
	def _analyze_python_oop(self, content: str, filepath: str) -> Dict:
		"""Analyze OOP metrics for Python files."""
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': []
		}
		
		# Count classes
		class_matches = re.findall(r'^class\s+(\w+).*:', content, re.MULTILINE)
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
			# More accurate: count classes that inherit from ABC
			abc_classes = re.findall(r'^class\s+\w+\([^)]*ABC[^)]*\):', content, re.MULTILINE)
			metrics['abstract_classes'] = max(len(abc_classes), 1)
		
		# Count methods (def within classes)
		method_matches = re.findall(r'^\s+def\s+(\w+)\s*\(.*\):', content, re.MULTILINE)
		metrics['method_count'] = len(method_matches)
		
		# Count attributes (self.attribute assignments)
		attribute_matches = re.findall(r'self\.(\w+)\s*=', content)
		metrics['attribute_count'] = len(set(attribute_matches))
		
		# Analyze dependencies (efferent coupling)
		import_patterns = [
			r'^from\s+([\w.]+)\s+import',
			r'^import\s+([\w.]+)'
		]
		dependencies = []
		for pattern in import_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			dependencies.extend(matches)
		
		metrics['dependencies'] = list(set(dependencies))
		metrics['efferent_coupling'] = len(metrics['dependencies'])
		
		# Store dependencies for later analysis
		self.dependencies[filepath] = set(metrics['dependencies'])
		
		return metrics
	
	def _analyze_cpp_oop(self, content: str, filepath: str) -> Dict:
		"""Analyze OOP metrics for C++ files."""
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': []
		}
		
		# Count classes and structs
		class_patterns = [
			r'\bclass\s+(\w+)',
			r'\bstruct\s+(\w+)'
		]
		for pattern in class_patterns:
			matches = re.findall(pattern, content)
			metrics['classes_defined'] += len(matches)
		
		# Count abstract classes (virtual methods = 0)
		virtual_matches = re.findall(r'virtual\s+.*\s*=\s*0\s*;', content)
		if virtual_matches:
			metrics['abstract_classes'] = 1  # Conservative estimate
		
		# Count methods
		method_patterns = [
			r'\b\w+\s*\([^)]*\)\s*\{',
			r'\b(public|private|protected):\s*\n\s*\w+\s*\([^)]*\)'
		]
		for pattern in method_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['method_count'] += len(matches)
		
		# Count attributes (member variables)
		member_patterns = [
			r'\b(public|private|protected):\s*\n\s*[\w<>,\*&\[\]]+\s+\w+\s*;'
		]
		for pattern in member_patterns:
			matches = re.findall(pattern, content, re.MULTILINE)
			metrics['attribute_count'] += len(matches)
		
		# Analyze dependencies (includes)
		include_matches = re.findall(r'#include\s*[<"]([\w./]+)[>"]', content)
		metrics['dependencies'] = list(set(include_matches))
		metrics['efferent_coupling'] = len(metrics['dependencies'])
		
		# Store dependencies
		self.dependencies[filepath] = set(metrics['dependencies'])
		
		return metrics
	
	def _analyze_javascript_oop(self, content: str, filepath: str) -> Dict:
		"""Analyze OOP metrics for JavaScript/TypeScript files."""
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': []
		}
		
		# Count classes
		class_matches = re.findall(r'\bclass\s+(\w+)', content)
		metrics['classes_defined'] = len(class_matches)
		
		# Count interfaces (TypeScript)
		interface_matches = re.findall(r'\binterface\s+(\w+)', content)
		metrics['interfaces_defined'] = len(interface_matches)
		metrics['abstract_classes'] += len(interface_matches)
		
		# Count abstract classes (TypeScript)
		abstract_matches = re.findall(r'\babstract\s+class\s+(\w+)', content)
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
			r'this\.(\w+)\s*=',
			r'\b\w+:\s*[\w\[\]<>]+\s*[;,]'
		]
		for pattern in property_patterns:
			matches = re.findall(pattern, content)
			metrics['attribute_count'] += len(matches)
		
		# Analyze dependencies
		import_patterns = [
			r'import\s+.*\s+from\s+["\']+([\w./]+)["\']',
			r'require\s*\(["\']+([\w./]+)["\']'
		]
		dependencies = []
		for pattern in import_patterns:
			matches = re.findall(pattern, content)
			dependencies.extend(matches)
		
		metrics['dependencies'] = list(set(dependencies))
		metrics['efferent_coupling'] = len(metrics['dependencies'])
		
		# Store dependencies
		self.dependencies[filepath] = set(metrics['dependencies'])
		
		return metrics
	
	def _analyze_swift_oop(self, content: str, filepath: str) -> Dict:
		"""Analyze OOP metrics for Swift files."""
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': []
		}
		
		# Count classes and structs
		class_patterns = [
			r'\bclass\s+(\w+)',
			r'\bstruct\s+(\w+)'
		]
		for pattern in class_patterns:
			matches = re.findall(pattern, content)
			metrics['classes_defined'] += len(matches)
		
		# Count protocols (Swift's interfaces)
		protocol_matches = re.findall(r'\bprotocol\s+(\w+)', content)
		metrics['interfaces_defined'] = len(protocol_matches)
		metrics['abstract_classes'] += len(protocol_matches)
		
		# Count methods/functions
		method_matches = re.findall(r'\bfunc\s+(\w+)\s*\(', content)
		metrics['method_count'] = len(method_matches)
		
		# Count properties
		property_patterns = [
			r'\bvar\s+(\w+)\s*:',
			r'\blet\s+(\w+)\s*:'
		]
		for pattern in property_patterns:
			matches = re.findall(pattern, content)
			metrics['attribute_count'] += len(matches)
		
		# Analyze dependencies
		import_matches = re.findall(r'\bimport\s+(\w+)', content)
		metrics['dependencies'] = list(set(import_matches))
		metrics['efferent_coupling'] = len(metrics['dependencies'])
		
		# Store dependencies
		self.dependencies[filepath] = set(metrics['dependencies'])
		
		return metrics
	
	def _analyze_go_oop(self, content: str, filepath: str) -> Dict:
		"""Analyze OOP-like metrics for Go files."""
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': []
		}
		
		# Count structs (Go's equivalent to classes)
		struct_matches = re.findall(r'\btype\s+(\w+)\s+struct\s*\{', content)
		metrics['classes_defined'] = len(struct_matches)
		
		# Count interfaces
		interface_matches = re.findall(r'\btype\s+(\w+)\s+interface\s*\{', content)
		metrics['interfaces_defined'] = len(interface_matches)
		metrics['abstract_classes'] = len(interface_matches)
		
		# Count methods (functions with receivers)
		method_matches = re.findall(r'\bfunc\s*\([^)]*\)\s*(\w+)\s*\(', content)
		metrics['method_count'] = len(method_matches)
		
		# Count struct fields
		field_matches = re.findall(r'^\s*(\w+)\s+[\w\[\]\*]+\s*$', content, re.MULTILINE)
		metrics['attribute_count'] = len(field_matches)
		
		# Analyze dependencies
		import_matches = re.findall(r'\bimport\s+["\']([\\w/.-]+)["\']', content)
		metrics['dependencies'] = list(set(import_matches))
		metrics['efferent_coupling'] = len(metrics['dependencies'])
		
		# Store dependencies
		self.dependencies[filepath] = set(metrics['dependencies'])
		
		return metrics
	
	def _analyze_rust_oop(self, content: str, filepath: str) -> Dict:
		"""Analyze OOP-like metrics for Rust files."""
		metrics = {
			'classes_defined': 0,
			'abstract_classes': 0,
			'interfaces_defined': 0,
			'efferent_coupling': 0,
			'afferent_coupling': 0,
			'method_count': 0,
			'attribute_count': 0,
			'dependencies': []
		}
		
		# Count structs and enums
		struct_matches = re.findall(r'\bstruct\s+(\w+)', content)
		enum_matches = re.findall(r'\benum\s+(\w+)', content)
		metrics['classes_defined'] = len(struct_matches) + len(enum_matches)
		
		# Count traits (Rust's interfaces)
		trait_matches = re.findall(r'\btrait\s+(\w+)', content)
		metrics['interfaces_defined'] = len(trait_matches)
		metrics['abstract_classes'] = len(trait_matches)
		
		# Count impl methods
		method_matches = re.findall(r'\bfn\s+(\w+)\s*\(', content)
		metrics['method_count'] = len(method_matches)
		
		# Count struct fields
		field_matches = re.findall(r'^\s*(\w+)\s*:\s*[\w<>,\[\]]+\s*,?', content, re.MULTILINE)
		metrics['attribute_count'] = len(field_matches)
		
		# Analyze dependencies
		use_matches = re.findall(r'\buse\s+([\w:]+)', content)
		extern_matches = re.findall(r'\bextern\s+crate\s+(\w+)', content)
		dependencies = use_matches + extern_matches
		metrics['dependencies'] = list(set(dependencies))
		metrics['efferent_coupling'] = len(metrics['dependencies'])
		
		# Store dependencies
		self.dependencies[filepath] = set(metrics['dependencies'])
		
		return metrics
	
	def calculate_afferent_coupling(self):
		"""
		Calculate afferent coupling (Ca) for all files based on dependency analysis.
		This requires analyzing all files first to understand the dependency graph.
		"""
		# Build reverse dependency map (who depends on whom)
		for filepath, deps in self.dependencies.items():
			for dep in deps:
				# Try to find matching files
				for target_file in self.files.keys():
					# Simple matching: if dependency name is in target file path
					if dep.replace('.', '/') in target_file or dep in target_file:
						self.dependents[target_file].add(filepath)
		
		# Update afferent coupling counts
		for filepath, metrics in self.files.items():
			metrics['afferent_coupling'] = len(self.dependents.get(filepath, set()))
			metrics['dependents'] = list(self.dependents.get(filepath, set()))
			
			# Recalculate derived metrics with updated afferent coupling
			self.files[filepath] = self._calculate_derived_metrics(metrics)
	
	def analyze_package(self, package_path: str) -> Dict:
		"""
		Aggregate OOP metrics at the package level.
		
		Args:
			package_path: Path to the package directory
			
		Returns:
			Dictionary containing aggregated package metrics
		"""
		package_files = [fp for fp in self.files.keys() if fp.startswith(package_path)]
		
		if not package_files:
			return None
		
		# Aggregate metrics
		total_classes = sum(self.files[fp]['classes_defined'] for fp in package_files)
		total_abstract = sum(self.files[fp]['abstract_classes'] for fp in package_files)
		total_ce = sum(self.files[fp]['efferent_coupling'] for fp in package_files)
		total_ca = sum(self.files[fp]['afferent_coupling'] for fp in package_files)
		
		# Calculate package-level metrics
		package_metrics = {
			'package_path': package_path,
			'file_count': len(package_files),
			'total_classes': total_classes,
			'total_abstract_classes': total_abstract,
			'efferent_coupling': total_ce,
			'afferent_coupling': total_ca,
			'abstractness': total_abstract / total_classes if total_classes > 0 else 0.0,
			'instability': total_ce / (total_ce + total_ca) if (total_ce + total_ca) > 0 else 0.0
		}
		
		# Calculate distance from main sequence
		a = package_metrics['abstractness']
		i = package_metrics['instability']
		package_metrics['distance_main_sequence'] = abs(a + i - 1.0)
		package_metrics['zone'] = self._determine_zone(a, i, package_metrics['distance_main_sequence'])
		package_metrics['interpretation'] = self._interpret_distance(
			package_metrics['distance_main_sequence'], a, i, package_metrics['zone']
		)
		
		self.packages[package_path] = package_metrics
		return package_metrics
	
	def get_summary_report(self) -> Dict:
		"""
		Generate a summary report of all analyzed OOP metrics.
		
		Returns:
			Dictionary containing summary statistics
		"""
		if not self.files:
			return {'error': 'No files analyzed'}
		
		distances = [m['distance_main_sequence'] for m in self.files.values()]
		zones = [m['zone'] for m in self.files.values()]
		
		report = {
			'total_files_analyzed': len(self.files),
			'average_distance': sum(distances) / len(distances) if distances else 0.0,
			'min_distance': min(distances) if distances else 0.0,
			'max_distance': max(distances) if distances else 0.0,
			'zone_distribution': {
				'main_sequence': zones.count('main_sequence'),
				'near_main_sequence': zones.count('near_main_sequence'),
				'zone_of_pain': zones.count('zone_of_pain'),
				'zone_of_uselessness': zones.count('zone_of_uselessness'),
				'far_from_main_sequence': zones.count('far_from_main_sequence')
			},
			'files_by_zone': {
				'main_sequence': [fp for fp, m in self.files.items() if m['zone'] == 'main_sequence'],
				'zone_of_pain': [fp for fp, m in self.files.items() if m['zone'] == 'zone_of_pain'],
				'zone_of_uselessness': [fp for fp, m in self.files.items() if m['zone'] == 'zone_of_uselessness']
			},
			'recommendations': self._generate_recommendations(distances, zones)
		}
		
		return report
	
	def _generate_recommendations(self, distances: List[float], zones: List[str]) -> List[str]:
		"""
		Generate recommendations based on OOP metrics analysis.
		
		Args:
			distances: List of distance values
			zones: List of zone classifications
			
		Returns:
			List of recommendation strings
		"""
		recommendations = []
		
		avg_distance = sum(distances) / len(distances) if distances else 0.0
		
		if avg_distance > 0.4:
			recommendations.append(
				"⚠️  Average distance from main sequence is high (> 0.4). "
				"Consider significant refactoring to improve design balance."
			)
		elif avg_distance > 0.2:
			recommendations.append(
				"⚡ Average distance from main sequence is moderate (0.2-0.4). "
				"Some refactoring may improve design quality."
			)
		else:
			recommendations.append(
				"✅ Average distance from main sequence is good (< 0.2). "
				"Package design is well-balanced."
			)
		
		pain_count = zones.count('zone_of_pain')
		if pain_count > 0:
			recommendations.append(
				f"🔴 {pain_count} file(s) in Zone of Pain (stable but concrete). "
				"Consider adding abstraction layers to improve extensibility."
			)
		
		useless_count = zones.count('zone_of_uselessness')
		if useless_count > 0:
			recommendations.append(
				f"🟡 {useless_count} file(s) in Zone of Uselessness (abstract but unstable). "
				"Consider adding concrete implementations or removing unused abstractions."
			)
		
		return recommendations


def format_oop_report(metrics: Dict, verbose: bool = False) -> str:
	"""
	Format OOP metrics into a human-readable report.
	
	Args:
		metrics: Dictionary containing OOP metrics
		verbose: Whether to include detailed information
		
	Returns:
		Formatted report string
	"""
	report = []
	report.append("\n" + "="*80)
	report.append("OOP METRICS - DISTANCE FROM MAIN SEQUENCE ANALYSIS")
	report.append("="*80)
	
	if 'error' in metrics:
		report.append(f"\nError: {metrics['error']}")
		return "\n".join(report)
	
	# File-level metrics
	if 'filepath' in metrics:
		report.append(f"\nFile: {metrics['filepath']}")
		report.append(f"Extension: {metrics['extension']}")
		report.append(f"\nClasses: {metrics['classes_defined']}")
		report.append(f"Abstract Classes: {metrics['abstract_classes']}")
		report.append(f"Interfaces: {metrics['interfaces_defined']}")
		report.append(f"\nEfferent Coupling (Ce): {metrics['efferent_coupling']}")
		report.append(f"Afferent Coupling (Ca): {metrics['afferent_coupling']}")
		report.append(f"\nAbstractness (A): {metrics['abstractness']:.3f}")
		report.append(f"Instability (I): {metrics['instability']:.3f}")
		report.append(f"\n📏 Distance from Main Sequence (D): {metrics['distance_main_sequence']:.3f}")
		report.append(f"🎯 Zone: {metrics['zone'].replace('_', ' ').title()}")
		report.append(f"💡 Interpretation: {metrics['interpretation']}")
		
		if verbose and metrics.get('dependencies'):
			report.append(f"\nDependencies ({len(metrics['dependencies'])}):")
			for dep in metrics['dependencies'][:10]:  # Show first 10
				report.append(f"  • {dep}")
	
	# Summary report
	elif 'total_files_analyzed' in metrics:
		report.append(f"\nTotal Files Analyzed: {metrics['total_files_analyzed']}")
		report.append(f"\nAverage Distance (D): {metrics['average_distance']:.3f}")
		report.append(f"Min Distance: {metrics['min_distance']:.3f}")
		report.append(f"Max Distance: {metrics['max_distance']:.3f}")
		
		report.append("\n📊 Zone Distribution:")
		for zone, count in metrics['zone_distribution'].items():
			percentage = (count / metrics['total_files_analyzed'] * 100) if metrics['total_files_analyzed'] > 0 else 0
			report.append(f"  {zone.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")
		
		report.append("\n💡 Recommendations:")
		for rec in metrics['recommendations']:
			report.append(f"  {rec}")
	
	report.append("\n" + "="*80)
	return "\n".join(report)
