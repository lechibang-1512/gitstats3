"""
GitStats OOP Metrics Module - Multi-Language AST Parser and OOP Metrics Analyzer

This module provides:
1. A custom AST-like parser for multi-language OOP construct detection
   (Python, Java, JavaScript/TypeScript, C++, Go, Rust, Swift)
2. OOP metrics analysis with focus on Distance from Main Sequence (D)

Key Metrics:
- Afferent Coupling (Ca): Classes outside depending on classes inside
- Efferent Coupling (Ce): Classes inside depending on classes outside
- Instability (I): Ce / (Ce + Ca)
- Abstractness (A): Abstract classes / Total classes
- Distance from Main Sequence (D): |A + I - 1|

Zone Interpretations:
- D < 0.2: Good - Well-balanced package design
- 0.2 <= D <= 0.4: Moderate - May need refactoring
- D > 0.4: Poor - Design issues (Zone of Pain or Zone of Uselessness)

Author: GitStats3 Enhancement
Date: 2025
"""

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Any, Iterator, Tuple


# =============================================================================
# AST Node Classes
# =============================================================================

@dataclass
class ASTNode:
    """Base class for all AST nodes, inspired by Python's ast.AST."""
    lineno: int = 0
    col_offset: int = 0
    end_lineno: int = 0
    end_col_offset: int = 0
    
    @property
    def _fields(self) -> tuple:
        """Returns names of child node fields (like Python's ast)."""
        return ()


@dataclass
class ImportDef(ASTNode):
    """Represents an import statement."""
    module: str = ""
    names: List[str] = field(default_factory=list)
    is_from: bool = False  # True for 'from X import Y'
    
    @property
    def _fields(self) -> tuple:
        return ('module', 'names')


@dataclass 
class AttributeDef(ASTNode):
    """Represents a class attribute/field."""
    name: str = ""
    type_annotation: Optional[str] = None
    visibility: str = "public"  # public, private, protected
    
    @property
    def _fields(self) -> tuple:
        return ('name', 'type_annotation', 'visibility')


@dataclass
class FunctionDef(ASTNode):
    """Represents a function or method definition."""
    name: str = ""
    args: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_abstract: bool = False
    is_static: bool = False
    visibility: str = "public"
    body_start: int = 0
    body_end: int = 0
    # CK Metrics - Function level
    cyclomatic_complexity: int = 1  # Base complexity is 1
    accessed_attributes: Set[str] = field(default_factory=set)  # Instance vars accessed
    called_methods: Set[str] = field(default_factory=set)  # Methods called within this function
    parameter_types: List[str] = field(default_factory=list)  # Types of parameters (for coupling)
    
    @property
    def _fields(self) -> tuple:
        return ('name', 'args', 'decorators')


@dataclass
class ClassDef(ASTNode):
    """Represents a class definition."""
    name: str = ""
    bases: List[str] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    attributes: List[AttributeDef] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    is_abstract: bool = False
    is_interface: bool = False  # For Java interfaces, TS interfaces, Go interfaces
    nested_classes: List['ClassDef'] = field(default_factory=list)
    # CK Metrics - Class level
    wmc: int = 0  # Weighted Methods per Class (sum of cyclomatic complexity)
    dit: int = 0  # Depth of Inheritance Tree
    noc: int = 0  # Number of Children (direct subclasses)
    cbo: int = 0  # Coupling Between Objects
    rfc: int = 0  # Response For a Class
    lcom: int = 0  # Lack of Cohesion in Methods
    coupled_classes: Set[str] = field(default_factory=set)  # Classes this class is coupled to
    
    @property
    def _fields(self) -> tuple:
        return ('name', 'bases', 'methods', 'attributes', 'decorators', 'nested_classes')


@dataclass
class InterfaceDef(ASTNode):
    """Represents an interface (Java, TypeScript, Go, Swift protocol, Rust trait)."""
    name: str = ""
    methods: List[FunctionDef] = field(default_factory=list)
    extends: List[str] = field(default_factory=list)
    
    @property
    def _fields(self) -> tuple:
        return ('name', 'methods', 'extends')


@dataclass
class ModuleDef(ASTNode):
    """Root node representing a source file/module."""
    name: str = ""
    imports: List[ImportDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    interfaces: List[InterfaceDef] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    
    @property
    def _fields(self) -> tuple:
        return ('imports', 'classes', 'interfaces', 'functions')


# =============================================================================
# AST Utilities
# =============================================================================

def walk(node: ASTNode) -> Iterator[ASTNode]:
    """
    Recursively yield all nodes in the tree starting at node.
    Similar to Python's ast.walk().
    """
    yield node
    for field_name in node._fields:
        value = getattr(node, field_name, None)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ASTNode):
                    yield from walk(item)
        elif isinstance(value, ASTNode):
            yield from walk(value)


def iter_child_nodes(node: ASTNode) -> Iterator[ASTNode]:
    """
    Yield all direct child nodes of node.
    Similar to Python's ast.iter_child_nodes().
    """
    for field_name in node._fields:
        value = getattr(node, field_name, None)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ASTNode):
                    yield item
        elif isinstance(value, ASTNode):
            yield value


# =============================================================================
# CK Metrics Calculation Functions
# =============================================================================

def calculate_wmc(cls: ClassDef, use_complexity_weights: bool = True) -> int:
    """
    Calculate Weighted Methods per Class (WMC).
    
    WMC = Sum of complexity of all methods in a class.
    If use_complexity_weights is False, returns simple method count.
    
    Args:
        cls: ClassDef node
        use_complexity_weights: If True, sum cyclomatic complexity; else count methods
    
    Returns:
        WMC value (higher = more complex class)
    """
    if not cls.methods:
        return 0
    
    if use_complexity_weights:
        return sum(max(1, m.cyclomatic_complexity) for m in cls.methods)
    else:
        return len(cls.methods)


def calculate_dit(class_name: str, inheritance_map: Dict[str, List[str]]) -> int:
    """
    Calculate Depth of Inheritance Tree (DIT).
    
    DIT = Maximum path length from class to root of inheritance tree.
    
    Args:
        class_name: Name of the class to calculate DIT for
        inheritance_map: Dict mapping class names to their base class names
    
    Returns:
        DIT value (0 = root class, higher = deeper inheritance)
    """
    visited = set()
    depth = 0
    current = class_name
    
    while current in inheritance_map and current not in visited:
        visited.add(current)
        bases = inheritance_map[current]
        if not bases:
            break
        # Follow first base class (primary inheritance path)
        current = bases[0]
        depth += 1
        # Limit depth to avoid infinite loops in malformed data
        if depth > 100:
            break
    
    return depth


def calculate_noc(class_name: str, all_classes: List[ClassDef]) -> int:
    """
    Calculate Number of Children (NOC).
    
    NOC = Number of immediate subclasses of a class.
    
    Args:
        class_name: Name of the parent class
        all_classes: List of all ClassDef nodes in the codebase
    
    Returns:
        NOC value (higher = more reuse, but potentially fragile base class)
    """
    return sum(1 for cls in all_classes if class_name in cls.bases)


def calculate_cbo(cls: ClassDef, all_class_names: Set[str]) -> int:
    """
    Calculate Coupling Between Objects (CBO).
    
    CBO = Number of classes to which a class is coupled.
    Coupling occurs through: inheritance, method calls, attribute types, parameters.
    
    Args:
        cls: ClassDef node
        all_class_names: Set of all known class names in the codebase
    
    Returns:
        CBO value (lower = better, less coupled)
    """
    coupled = set()
    
    # Coupling via inheritance
    coupled.update(cls.bases)
    
    # Coupling via attribute types
    for attr in cls.attributes:
        if attr.type_annotation and attr.type_annotation in all_class_names:
            coupled.add(attr.type_annotation)
    
    # Coupling via method parameter types
    for method in cls.methods:
        for param_type in method.parameter_types:
            if param_type in all_class_names:
                coupled.add(param_type)
        # Coupling via return types
        if method.return_type and method.return_type in all_class_names:
            coupled.add(method.return_type)
    
    # Coupling via method calls
    for method in cls.methods:
        for called in method.called_methods:
            # Extract class name from method call (e.g., "ClassName.method" -> "ClassName")
            if '.' in called:
                class_ref = called.split('.')[0]
                if class_ref in all_class_names:
                    coupled.add(class_ref)
    
    # Remove self-reference
    coupled.discard(cls.name)
    
    cls.coupled_classes = coupled
    return len(coupled)


def calculate_rfc(cls: ClassDef) -> int:
    """
    Calculate Response For a Class (RFC).
    
    RFC = Number of methods that can be executed in response to a message.
    RFC = M + R where M = methods in class, R = unique methods called from M.
    
    Args:
        cls: ClassDef node
    
    Returns:
        RFC value (higher = more complex response, harder to test)
    """
    own_methods = len(cls.methods)
    
    # Collect all unique methods called from this class's methods
    called_methods = set()
    for method in cls.methods:
        called_methods.update(method.called_methods)
    
    return own_methods + len(called_methods)


def calculate_lcom(cls: ClassDef) -> int:
    """
    Calculate Lack of Cohesion in Methods (LCOM) using LCOM1 formula.
    
    LCOM = |P| - |Q| where:
    - P = pairs of methods that don't share instance variables
    - Q = pairs of methods that share instance variables
    If LCOM < 0, return 0 (highly cohesive)
    
    Args:
        cls: ClassDef node with accessed_attributes populated for each method
    
    Returns:
        LCOM value (0 = cohesive, higher = non-cohesive, consider splitting)
    """
    methods = cls.methods
    if len(methods) < 2:
        return 0
    
    p = 0  # Pairs with no shared attributes
    q = 0  # Pairs with shared attributes
    
    # Compare all pairs of methods
    for i in range(len(methods)):
        for j in range(i + 1, len(methods)):
            attrs_i = methods[i].accessed_attributes
            attrs_j = methods[j].accessed_attributes
            
            # Check if they share any instance variables
            if attrs_i & attrs_j:  # Intersection is non-empty
                q += 1
            else:
                p += 1
    
    lcom = p - q
    return max(0, lcom)


def calculate_lcom4(cls: ClassDef) -> int:
    """
    Calculate LCOM4 (improved LCOM using graph connectivity).
    
    LCOM4 counts the number of connected components in the method-attribute graph.
    LCOM4 = 1 means perfectly cohesive, > 1 means the class could be split.
    
    Args:
        cls: ClassDef node with accessed_attributes populated
    
    Returns:
        Number of connected components (1 = cohesive, > 1 = consider splitting)
    """
    if not cls.methods:
        return 0
    
    # Build adjacency: methods share an edge if they access common attributes
    method_names = [m.name for m in cls.methods]
    
    # Union-Find for connected components
    parent = {m.name: m.name for m in cls.methods}
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    # Connect methods that share attributes
    for i in range(len(cls.methods)):
        for j in range(i + 1, len(cls.methods)):
            if cls.methods[i].accessed_attributes & cls.methods[j].accessed_attributes:
                union(cls.methods[i].name, cls.methods[j].name)
    
    # Also connect methods that call each other
    for method in cls.methods:
        for called in method.called_methods:
            if called in parent:
                union(method.name, called)
    
    # Count unique components
    components = len(set(find(m) for m in method_names))
    return components


def apply_ck_metrics_to_class(cls: ClassDef, 
                               all_classes: List[ClassDef],
                               inheritance_map: Dict[str, List[str]],
                               all_class_names: Set[str]) -> None:
    """
    Calculate and apply all CK metrics to a ClassDef node.
    
    Args:
        cls: ClassDef to calculate metrics for
        all_classes: All classes in the codebase (for NOC)
        inheritance_map: Maps class names to their bases (for DIT)
        all_class_names: Set of all class names (for CBO)
    """
    cls.wmc = calculate_wmc(cls, use_complexity_weights=True)
    cls.dit = calculate_dit(cls.name, inheritance_map)
    cls.noc = calculate_noc(cls.name, all_classes)
    cls.cbo = calculate_cbo(cls, all_class_names)
    cls.rfc = calculate_rfc(cls)
    cls.lcom = calculate_lcom(cls)


# =============================================================================
# Tokenizer State Machine  
# =============================================================================

class TokenType(Enum):
    """Token types for the tokenizer."""
    KEYWORD = auto()
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    OPERATOR = auto()
    DELIMITER = auto()
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    COMMENT = auto()
    WHITESPACE = auto()
    EOF = auto()


@dataclass
class Token:
    """A single token from the tokenizer."""
    type: TokenType
    value: str
    lineno: int
    col_offset: int


class TokenizerState(Enum):
    """States for the tokenizer state machine."""
    NORMAL = auto()
    IN_STRING_SINGLE = auto()
    IN_STRING_DOUBLE = auto()
    IN_STRING_TRIPLE_SINGLE = auto()
    IN_STRING_TRIPLE_DOUBLE = auto()
    IN_COMMENT_SINGLE = auto()
    IN_COMMENT_MULTI = auto()
    IN_RAW_STRING = auto()
    IN_TEMPLATE_STRING = auto()


class Tokenizer:
    """
    State-machine based tokenizer that handles strings, comments, and nesting.
    """
    
    def __init__(self, source: str, language: str = 'python'):
        self.source = source
        self.language = language
        self.pos = 0
        self.lineno = 1
        self.col_offset = 0
        self.state = TokenizerState.NORMAL
        self.brace_depth = 0
        self.paren_depth = 0
        self.bracket_depth = 0
        
        # Language-specific settings
        self._setup_language(language)
    
    def _setup_language(self, language: str):
        """Configure tokenizer for specific language."""
        self.single_comment = '#' if language == 'python' else '//'
        self.multi_comment_start = None if language == 'python' else '/*'
        self.multi_comment_end = None if language == 'python' else '*/'
        self.has_triple_strings = language == 'python'
        self.has_template_strings = language in ('javascript', 'typescript')
        
        # Keywords by language
        self.keywords = self._get_keywords(language)
    
    def _get_keywords(self, language: str) -> Set[str]:
        """Get language-specific keywords."""
        common = {'if', 'else', 'for', 'while', 'return', 'break', 'continue'}
        
        lang_keywords = {
            'python': {'class', 'def', 'import', 'from', 'as', 'try', 'except', 
                      'finally', 'with', 'async', 'await', 'yield', 'lambda',
                      'pass', 'raise', 'global', 'nonlocal', 'assert', 'del',
                      'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is'},
            'java': {'class', 'interface', 'enum', 'abstract', 'final', 'static',
                    'public', 'private', 'protected', 'extends', 'implements',
                    'new', 'this', 'super', 'void', 'null', 'true', 'false',
                    'import', 'package', 'throws', 'throw', 'try', 'catch',
                    'synchronized', 'volatile', 'transient', 'native'},
            'javascript': {'class', 'function', 'const', 'let', 'var', 'import',
                          'export', 'from', 'default', 'extends', 'new', 'this',
                          'super', 'async', 'await', 'yield', 'null', 'undefined',
                          'true', 'false', 'typeof', 'instanceof', 'delete'},
            'typescript': {'class', 'function', 'const', 'let', 'var', 'import',
                          'export', 'from', 'default', 'extends', 'implements',
                          'interface', 'type', 'enum', 'abstract', 'new', 'this',
                          'super', 'async', 'await', 'public', 'private', 'protected',
                          'readonly', 'static', 'null', 'undefined'},
            'cpp': {'class', 'struct', 'enum', 'union', 'namespace', 'template',
                   'virtual', 'override', 'final', 'static', 'const', 'mutable',
                   'public', 'private', 'protected', 'friend', 'inline', 'extern',
                   'new', 'delete', 'this', 'nullptr', 'true', 'false', 'sizeof',
                   'typedef', 'using', 'typename', 'explicit', 'operator'},
            'go': {'func', 'type', 'struct', 'interface', 'package', 'import',
                  'const', 'var', 'map', 'chan', 'go', 'defer', 'select', 'case',
                  'default', 'range', 'nil', 'true', 'false', 'iota'},
            'rust': {'fn', 'struct', 'enum', 'trait', 'impl', 'mod', 'use', 'pub',
                    'crate', 'super', 'self', 'Self', 'const', 'static', 'mut',
                    'ref', 'let', 'match', 'loop', 'async', 'await', 'move',
                    'dyn', 'where', 'unsafe', 'extern'},
            'swift': {'class', 'struct', 'enum', 'protocol', 'extension', 'func',
                     'var', 'let', 'import', 'public', 'private', 'internal',
                     'fileprivate', 'open', 'static', 'final', 'override',
                     'init', 'deinit', 'self', 'Self', 'nil', 'true', 'false'}
        }
        
        return common | lang_keywords.get(language, set())
    
    def tokenize(self) -> List[Token]:
        """Tokenize the entire source code."""
        tokens = []
        while self.pos < len(self.source):
            token = self._next_token()
            if token:
                tokens.append(token)
        tokens.append(Token(TokenType.EOF, '', self.lineno, self.col_offset))
        return tokens
    
    def _next_token(self) -> Optional[Token]:
        """Get the next token."""
        if self.pos >= len(self.source):
            return None
        
        start_pos = self.pos
        start_line = self.lineno
        start_col = self.col_offset
        
        char = self.source[self.pos]
        
        # Handle different states
        if self.state == TokenizerState.NORMAL:
            return self._tokenize_normal(char, start_line, start_col)
        elif self.state in (TokenizerState.IN_STRING_SINGLE, 
                           TokenizerState.IN_STRING_DOUBLE,
                           TokenizerState.IN_STRING_TRIPLE_SINGLE,
                           TokenizerState.IN_STRING_TRIPLE_DOUBLE):
            return self._tokenize_string(char, start_line, start_col)
        elif self.state == TokenizerState.IN_COMMENT_SINGLE:
            return self._tokenize_single_comment(start_line, start_col)
        elif self.state == TokenizerState.IN_COMMENT_MULTI:
            return self._tokenize_multi_comment(start_line, start_col)
        
        return None
    
    def _advance(self, count: int = 1):
        """Advance position and update line/col tracking."""
        for _ in range(count):
            if self.pos < len(self.source):
                if self.source[self.pos] == '\n':
                    self.lineno += 1
                    self.col_offset = 0
                else:
                    self.col_offset += 1
                self.pos += 1
    
    def _peek(self, offset: int = 0) -> str:
        """Peek at character at current position + offset."""
        pos = self.pos + offset
        return self.source[pos] if pos < len(self.source) else ''
    
    def _tokenize_normal(self, char: str, start_line: int, start_col: int) -> Optional[Token]:
        """Tokenize in normal state."""
        # Whitespace
        if char in ' \t':
            self._advance()
            return None  # Skip whitespace
        
        # Newline
        if char == '\n':
            self._advance()
            return Token(TokenType.NEWLINE, '\n', start_line, start_col)
        
        # Single-line comment
        if self._check_comment_start():
            self.state = TokenizerState.IN_COMMENT_SINGLE
            return self._tokenize_single_comment(start_line, start_col)
        
        # Multi-line comment
        if self.multi_comment_start and self.source[self.pos:].startswith(self.multi_comment_start):
            self.state = TokenizerState.IN_COMMENT_MULTI
            self._advance(len(self.multi_comment_start))
            return self._tokenize_multi_comment(start_line, start_col)
        
        # String literals
        if char in '"\'':
            return self._start_string(char, start_line, start_col)
        
        # Template strings (JS/TS)
        if char == '`' and self.has_template_strings:
            self.state = TokenizerState.IN_TEMPLATE_STRING
            return self._tokenize_template_string(start_line, start_col)
        
        # Delimiters and operators
        if char in '{}()[]':
            self._update_depth(char)
            self._advance()
            return Token(TokenType.DELIMITER, char, start_line, start_col)
        
        if char in '.,;:@':
            self._advance()
            return Token(TokenType.DELIMITER, char, start_line, start_col)
        
        if char in '+-*/%=<>!&|^~?':
            return self._tokenize_operator(start_line, start_col)
        
        # Identifiers and keywords
        if char.isalpha() or char == '_':
            return self._tokenize_identifier(start_line, start_col)
        
        # Numbers
        if char.isdigit():
            return self._tokenize_number(start_line, start_col)
        
        # Unknown - skip
        self._advance()
        return None
    
    def _check_comment_start(self) -> bool:
        """Check if current position starts a single-line comment."""
        if self.language == 'python':
            return self._peek() == '#'
        else:
            return self._peek() == '/' and self._peek(1) == '/'
    
    def _start_string(self, quote: str, start_line: int, start_col: int) -> Token:
        """Start tokenizing a string literal."""
        # Check for triple quotes (Python)
        if self.has_triple_strings:
            if self.source[self.pos:self.pos+3] == quote * 3:
                if quote == '"':
                    self.state = TokenizerState.IN_STRING_TRIPLE_DOUBLE
                else:
                    self.state = TokenizerState.IN_STRING_TRIPLE_SINGLE
                self._advance(3)
                return self._tokenize_string(quote, start_line, start_col)
        
        if quote == '"':
            self.state = TokenizerState.IN_STRING_DOUBLE
        else:
            self.state = TokenizerState.IN_STRING_SINGLE
        self._advance()
        return self._tokenize_string(quote, start_line, start_col)
    
    def _tokenize_string(self, quote: str, start_line: int, start_col: int) -> Token:
        """Tokenize string content until closing quote."""
        value = []
        is_triple = self.state in (TokenizerState.IN_STRING_TRIPLE_SINGLE, 
                                   TokenizerState.IN_STRING_TRIPLE_DOUBLE)
        end_quote = quote * 3 if is_triple else quote
        
        while self.pos < len(self.source):
            if self.source[self.pos:].startswith(end_quote):
                self._advance(len(end_quote))
                self.state = TokenizerState.NORMAL
                return Token(TokenType.STRING, ''.join(value), start_line, start_col)
            
            if self._peek() == '\\' and self.pos + 1 < len(self.source):
                value.append(self._peek())
                self._advance()
                value.append(self._peek())
                self._advance()
            else:
                value.append(self._peek())
                self._advance()
        
        # Unterminated string
        self.state = TokenizerState.NORMAL
        return Token(TokenType.STRING, ''.join(value), start_line, start_col)
    
    def _tokenize_template_string(self, start_line: int, start_col: int) -> Token:
        """Tokenize JS/TS template string."""
        value = []
        self._advance()  # Skip opening `
        
        while self.pos < len(self.source):
            if self._peek() == '`':
                self._advance()
                self.state = TokenizerState.NORMAL
                return Token(TokenType.STRING, ''.join(value), start_line, start_col)
            
            if self._peek() == '\\':
                value.append(self._peek())
                self._advance()
                if self.pos < len(self.source):
                    value.append(self._peek())
                    self._advance()
            else:
                value.append(self._peek())
                self._advance()
        
        self.state = TokenizerState.NORMAL
        return Token(TokenType.STRING, ''.join(value), start_line, start_col)
    
    def _tokenize_single_comment(self, start_line: int, start_col: int) -> Token:
        """Tokenize single-line comment."""
        value = []
        while self.pos < len(self.source) and self._peek() != '\n':
            value.append(self._peek())
            self._advance()
        self.state = TokenizerState.NORMAL
        return Token(TokenType.COMMENT, ''.join(value), start_line, start_col)
    
    def _tokenize_multi_comment(self, start_line: int, start_col: int) -> Token:
        """Tokenize multi-line comment."""
        value = []
        while self.pos < len(self.source):
            if self.multi_comment_end and self.source[self.pos:].startswith(self.multi_comment_end):
                self._advance(len(self.multi_comment_end))
                self.state = TokenizerState.NORMAL
                return Token(TokenType.COMMENT, ''.join(value), start_line, start_col)
            value.append(self._peek())
            self._advance()
        
        self.state = TokenizerState.NORMAL
        return Token(TokenType.COMMENT, ''.join(value), start_line, start_col)
    
    def _tokenize_identifier(self, start_line: int, start_col: int) -> Token:
        """Tokenize identifier or keyword."""
        value = []
        while self.pos < len(self.source) and (self._peek().isalnum() or self._peek() == '_'):
            value.append(self._peek())
            self._advance()
        
        ident = ''.join(value)
        token_type = TokenType.KEYWORD if ident in self.keywords else TokenType.IDENTIFIER
        return Token(token_type, ident, start_line, start_col)
    
    def _tokenize_number(self, start_line: int, start_col: int) -> Token:
        """Tokenize number literal."""
        value = []
        while self.pos < len(self.source) and (self._peek().isalnum() or self._peek() in '._'):
            value.append(self._peek())
            self._advance()
        return Token(TokenType.NUMBER, ''.join(value), start_line, start_col)
    
    def _tokenize_operator(self, start_line: int, start_col: int) -> Token:
        """Tokenize operator."""
        value = [self._peek()]
        self._advance()
        # Handle multi-char operators like ==, !=, <=, >=, &&, ||, etc.
        if self.pos < len(self.source) and self._peek() in '=<>&|+-':
            value.append(self._peek())
            self._advance()
        return Token(TokenType.OPERATOR, ''.join(value), start_line, start_col)
    
    def _update_depth(self, char: str):
        """Update nesting depth for braces/parens/brackets."""
        if char == '{':
            self.brace_depth += 1
        elif char == '}':
            self.brace_depth = max(0, self.brace_depth - 1)
        elif char == '(':
            self.paren_depth += 1
        elif char == ')':
            self.paren_depth = max(0, self.paren_depth - 1)
        elif char == '[':
            self.bracket_depth += 1
        elif char == ']':
            self.bracket_depth = max(0, self.bracket_depth - 1)


# =============================================================================
# Language Parsers
# =============================================================================

class BaseParser:
    """Base class for language-specific parsers."""
    
    def __init__(self, tokens: List[Token], source: str):
        self.tokens = [t for t in tokens if t.type not in (TokenType.COMMENT, TokenType.WHITESPACE)]
        self.source = source
        self.pos = 0
        self.module = ModuleDef()
    
    def parse(self) -> ModuleDef:
        """Parse tokens into AST. Override in subclasses."""
        raise NotImplementedError
    
    def _current(self) -> Optional[Token]:
        """Get current token."""
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    
    def _peek(self, offset: int = 0) -> Optional[Token]:
        """Peek at token at offset from current position."""
        pos = self.pos + offset
        return self.tokens[pos] if pos < len(self.tokens) else None
    
    def _advance(self) -> Optional[Token]:
        """Advance and return current token."""
        token = self._current()
        self.pos += 1
        return token
    
    def _match(self, *values: str) -> bool:
        """Check if current token value matches any of the given values."""
        current = self._current()
        return current is not None and current.value in values
    
    def _match_type(self, token_type: TokenType) -> bool:
        """Check if current token type matches."""
        current = self._current()
        return current is not None and current.type == token_type
    
    def _consume(self, value: str) -> Optional[Token]:
        """Consume token if it matches value, return it."""
        if self._match(value):
            return self._advance()
        return None
    
    def _skip_until(self, *values: str):
        """Skip tokens until one of the values is found."""
        while self._current() and not self._match(*values):
            self._advance()
    
    def _find_matching_brace(self) -> int:
        """Find position of matching closing brace."""
        depth = 1
        start = self.pos
        while self.pos < len(self.tokens) and depth > 0:
            if self._match('{'):
                depth += 1
            elif self._match('}'):
                depth -= 1
            if depth > 0:
                self._advance()
        return self.pos


class PythonParser(BaseParser):
    """Parser for Python source code."""
    
    def parse(self) -> ModuleDef:
        """Parse Python tokens into AST."""
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('import'):
                self._parse_import()
            elif self._match('from'):
                self._parse_from_import()
            elif self._match('class'):
                self.module.classes.append(self._parse_class())
            elif self._match('def', 'async'):
                self.module.functions.append(self._parse_function())
            elif self._match('@'):
                # Decorator - peek ahead to see if it's for class or function
                decorators = self._parse_decorators()
                if self._match('class'):
                    cls = self._parse_class()
                    cls.decorators = decorators
                    self.module.classes.append(cls)
                elif self._match('def', 'async'):
                    func = self._parse_function()
                    func.decorators = decorators
                    self.module.functions.append(func)
            else:
                self._advance()
        return self.module
    
    def _parse_import(self) -> None:
        """Parse 'import X' statement."""
        self._advance()  # consume 'import'
        imp = ImportDef(lineno=self._current().lineno if self._current() else 0)
        names = []
        while self._current() and not self._match_type(TokenType.NEWLINE):
            if self._match_type(TokenType.IDENTIFIER):
                names.append(self._current().value)
            self._advance()
        imp.names = names
        imp.module = '.'.join(names)
        self.module.imports.append(imp)
    
    def _parse_from_import(self) -> None:
        """Parse 'from X import Y' statement."""
        self._advance()  # consume 'from'
        imp = ImportDef(is_from=True, lineno=self._current().lineno if self._current() else 0)
        module_parts = []
        while self._current() and not self._match('import'):
            if self._match_type(TokenType.IDENTIFIER) or self._match('.'):
                module_parts.append(self._current().value)
            self._advance()
        imp.module = ''.join(module_parts)
        self._consume('import')
        names = []
        while self._current() and not self._match_type(TokenType.NEWLINE):
            if self._match_type(TokenType.IDENTIFIER):
                names.append(self._current().value)
            self._advance()
        imp.names = names
        self.module.imports.append(imp)
    
    def _parse_decorators(self) -> List[str]:
        """Parse decorator list."""
        decorators = []
        while self._match('@'):
            self._advance()  # consume '@'
            if self._match_type(TokenType.IDENTIFIER):
                decorators.append(self._current().value)
            self._skip_until('\n', 'class', 'def', 'async', '@')
            if self._match_type(TokenType.NEWLINE):
                self._advance()
        return decorators
    
    def _parse_class(self) -> ClassDef:
        """Parse class definition."""
        token = self._advance()  # consume 'class'
        cls = ClassDef(lineno=token.lineno, col_offset=token.col_offset)
        
        if self._match_type(TokenType.IDENTIFIER):
            cls.name = self._current().value
            self._advance()
        
        # Parse bases
        if self._match('('):
            self._advance()
            bases = []
            while not self._match(')'):
                if self._match_type(TokenType.IDENTIFIER):
                    bases.append(self._current().value)
                self._advance()
            cls.bases = bases
            self._consume(')')
        
        # Check for ABC in bases
        if any(b in ('ABC', 'ABCMeta') for b in cls.bases):
            cls.is_abstract = True
        
        self._consume(':')
        
        # Parse class body (indentation-based)
        # For heuristic parsing, look for 'def' at next indentation level
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('def', 'async'):
                method = self._parse_function()
                cls.methods.append(method)
                if method.is_abstract:
                    cls.is_abstract = True
            elif self._match('@'):
                decorators = self._parse_decorators()
                if self._match('def', 'async'):
                    method = self._parse_function()
                    method.decorators = decorators
                    if 'abstractmethod' in decorators:
                        method.is_abstract = True
                        cls.is_abstract = True
                    cls.methods.append(method)
            elif self._match('class'):
                # Nested class - skip for now
                break
            elif self._match_type(TokenType.IDENTIFIER) and self._peek(1) and self._peek(1).value == '=':
                # Class attribute
                attr = AttributeDef(name=self._current().value, lineno=self._current().lineno)
                cls.attributes.append(attr)
                self._advance()
            elif self._match_type(TokenType.NEWLINE):
                self._advance()
            else:
                # End of class body heuristic - next top-level definition
                if self._current().col_offset == 0 and self._match('class', 'def', 'import', 'from'):
                    break
                self._advance()
        
        return cls
    
    def _parse_function(self) -> FunctionDef:
        """Parse function/method definition."""
        is_async = self._match('async')
        if is_async:
            self._advance()
        
        token = self._advance()  # consume 'def'
        func = FunctionDef(lineno=token.lineno, col_offset=token.col_offset)
        
        if self._match_type(TokenType.IDENTIFIER):
            func.name = self._current().value
            self._advance()
        
        # Parse arguments
        if self._match('('):
            self._advance()
            args = []
            while not self._match(')'):
                if self._match_type(TokenType.IDENTIFIER):
                    args.append(self._current().value)
                self._advance()
            func.args = args
            self._consume(')')
        
        # Parse return type annotation
        if self._match('-') and self._peek(1) and self._peek(1).value == '>':
            self._advance()  # -
            self._advance()  # >
            if self._match_type(TokenType.IDENTIFIER):
                func.return_type = self._current().value
                self._advance()
        
        self._consume(':')
        return func


class JavaParser(BaseParser):
    """Parser for Java/Kotlin/Scala source code."""
    
    def parse(self) -> ModuleDef:
        """Parse Java tokens into AST."""
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('import'):
                self._parse_import()
            elif self._match('class', 'abstract', 'public', 'private', 'protected', 'final', 'static'):
                self._parse_class_or_skip()
            elif self._match('interface'):
                self.module.interfaces.append(self._parse_interface())
            elif self._match('@'):
                self._advance()  # Skip annotation
            else:
                self._advance()
        return self.module
    
    def _parse_import(self) -> None:
        """Parse import statement."""
        self._advance()  # consume 'import'
        imp = ImportDef(lineno=self._current().lineno if self._current() else 0)
        parts = []
        while self._current() and not self._match(';'):
            if self._match_type(TokenType.IDENTIFIER) or self._match('.', '*'):
                parts.append(self._current().value)
            self._advance()
        imp.module = ''.join(parts)
        imp.names = [parts[-1]] if parts else []
        self._consume(';')
        self.module.imports.append(imp)
    
    def _parse_class_or_skip(self) -> None:
        """Parse class with modifiers or skip non-class."""
        modifiers = []
        is_abstract = False
        
        while self._match('public', 'private', 'protected', 'abstract', 'final', 'static'):
            if self._match('abstract'):
                is_abstract = True
            modifiers.append(self._current().value)
            self._advance()
        
        if self._match('class'):
            cls = self._parse_class()
            cls.is_abstract = is_abstract
            self.module.classes.append(cls)
        elif self._match('interface'):
            iface = self._parse_interface()
            self.module.interfaces.append(iface)
    
    def _parse_class(self) -> ClassDef:
        """Parse class definition."""
        token = self._advance()  # consume 'class'
        cls = ClassDef(lineno=token.lineno)
        
        if self._match_type(TokenType.IDENTIFIER):
            cls.name = self._current().value
            self._advance()
        
        # Skip generics <T>
        if self._match('<'):
            depth = 1
            self._advance()
            while depth > 0:
                if self._match('<'):
                    depth += 1
                elif self._match('>'):
                    depth -= 1
                self._advance()
        
        # Parse extends
        if self._match('extends'):
            self._advance()
            if self._match_type(TokenType.IDENTIFIER):
                cls.bases.append(self._current().value)
                self._advance()
        
        # Parse implements
        if self._match('implements'):
            self._advance()
            while not self._match('{'):
                if self._match_type(TokenType.IDENTIFIER):
                    cls.bases.append(self._current().value)
                self._advance()
        
        # Parse body
        if self._match('{'):
            self._advance()
            self._parse_class_body(cls)
        
        return cls
    
    def _parse_class_body(self, cls: ClassDef) -> None:
        """Parse class body."""
        brace_depth = 1
        while brace_depth > 0 and self._current():
            if self._match('{'):
                brace_depth += 1
                self._advance()
            elif self._match('}'):
                brace_depth -= 1
                self._advance()
            elif self._match('public', 'private', 'protected', 'abstract', 'static', 'final'):
                method = self._parse_method_or_field(cls)
            elif self._match_type(TokenType.IDENTIFIER):
                # Could be method or field
                self._parse_method_or_field(cls)
            else:
                self._advance()
    
    def _parse_method_or_field(self, cls: ClassDef) -> None:
        """Parse method or field."""
        modifiers = []
        is_abstract = False
        is_static = False
        visibility = 'package'
        
        while self._match('public', 'private', 'protected', 'abstract', 'static', 'final'):
            mod = self._current().value
            modifiers.append(mod)
            if mod == 'abstract':
                is_abstract = True
            if mod == 'static':
                is_static = True
            if mod in ('public', 'private', 'protected'):
                visibility = mod
            self._advance()
        
        # Get type and name
        if not self._match_type(TokenType.IDENTIFIER):
            return
        type_name = self._current().value
        self._advance()
        
        if not self._match_type(TokenType.IDENTIFIER):
            return
        name = self._current().value
        self._advance()
        
        if self._match('('):
            # It's a method
            func = FunctionDef(name=name, is_abstract=is_abstract, is_static=is_static, visibility=visibility)
            func.return_type = type_name
            self._advance()
            args = []
            while not self._match(')'):
                if self._match_type(TokenType.IDENTIFIER):
                    args.append(self._current().value)
                self._advance()
            func.args = args
            self._consume(')')
            cls.methods.append(func)
            if is_abstract:
                cls.is_abstract = True
            # Skip body
            if self._match('{'):
                self._skip_brace_block()
        else:
            # It's a field
            attr = AttributeDef(name=name, type_annotation=type_name, visibility=visibility)
            cls.attributes.append(attr)
    
    def _parse_interface(self) -> InterfaceDef:
        """Parse interface definition."""
        token = self._advance()  # consume 'interface'
        iface = InterfaceDef(lineno=token.lineno)
        
        if self._match_type(TokenType.IDENTIFIER):
            iface.name = self._current().value
            self._advance()
        
        if self._match('extends'):
            self._advance()
            while not self._match('{'):
                if self._match_type(TokenType.IDENTIFIER):
                    iface.extends.append(self._current().value)
                self._advance()
        
        if self._match('{'):
            self._advance()
            self._parse_interface_body(iface)
        
        return iface
    
    def _parse_interface_body(self, iface: InterfaceDef) -> None:
        """Parse interface body."""
        brace_depth = 1
        while brace_depth > 0 and self._current():
            if self._match('{'):
                brace_depth += 1
                self._advance()
            elif self._match('}'):
                brace_depth -= 1
                self._advance()
            elif self._match_type(TokenType.IDENTIFIER):
                # Parse method signature
                type_name = self._current().value
                self._advance()
                if self._match_type(TokenType.IDENTIFIER):
                    name = self._current().value
                    self._advance()
                    if self._match('('):
                        func = FunctionDef(name=name, return_type=type_name, is_abstract=True)
                        iface.methods.append(func)
                        self._skip_until(';', '{')
                        if self._match('{'):
                            self._skip_brace_block()
            else:
                self._advance()
    
    def _skip_brace_block(self) -> None:
        """Skip a brace-delimited block."""
        if not self._match('{'):
            return
        self._advance()
        depth = 1
        while depth > 0 and self._current():
            if self._match('{'):
                depth += 1
            elif self._match('}'):
                depth -= 1
            self._advance()


class JavaScriptParser(BaseParser):
    """Parser for JavaScript/TypeScript source code."""
    
    def __init__(self, tokens: List[Token], source: str, is_typescript: bool = False):
        super().__init__(tokens, source)
        self.is_typescript = is_typescript
    
    def parse(self) -> ModuleDef:
        """Parse JavaScript/TypeScript tokens into AST."""
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('import'):
                self._parse_import()
            elif self._match('class'):
                self.module.classes.append(self._parse_class())
            elif self._match('abstract') and self.is_typescript:
                self._advance()
                if self._match('class'):
                    cls = self._parse_class()
                    cls.is_abstract = True
                    self.module.classes.append(cls)
            elif self._match('interface') and self.is_typescript:
                self.module.interfaces.append(self._parse_interface())
            elif self._match('function'):
                self.module.functions.append(self._parse_function())
            elif self._match('export'):
                self._advance()  # Skip export, parse next
            else:
                self._advance()
        return self.module
    
    def _parse_import(self) -> None:
        """Parse import statement."""
        self._advance()  # consume 'import'
        imp = ImportDef(lineno=self._current().lineno if self._current() else 0)
        names = []
        
        while self._current() and not self._match('from'):
            if self._match_type(TokenType.IDENTIFIER):
                names.append(self._current().value)
            self._advance()
        
        self._consume('from')
        if self._match_type(TokenType.STRING):
            imp.module = self._current().value.strip('"\'')
            self._advance()
        
        imp.names = names
        imp.is_from = True
        self.module.imports.append(imp)
    
    def _parse_class(self) -> ClassDef:
        """Parse class definition."""
        token = self._advance()  # consume 'class'
        cls = ClassDef(lineno=token.lineno)
        
        if self._match_type(TokenType.IDENTIFIER):
            cls.name = self._current().value
            self._advance()
        
        if self._match('extends'):
            self._advance()
            if self._match_type(TokenType.IDENTIFIER):
                cls.bases.append(self._current().value)
                self._advance()
        
        if self._match('implements') and self.is_typescript:
            self._advance()
            while not self._match('{'):
                if self._match_type(TokenType.IDENTIFIER):
                    cls.bases.append(self._current().value)
                self._advance()
        
        if self._match('{'):
            self._advance()
            self._parse_class_body(cls)
        
        return cls
    
    def _parse_class_body(self, cls: ClassDef) -> None:
        """Parse class body."""
        brace_depth = 1
        while brace_depth > 0 and self._current():
            if self._match('{'):
                brace_depth += 1
                self._advance()
            elif self._match('}'):
                brace_depth -= 1
                self._advance()
            elif self._match('constructor'):
                # Constructor
                func = FunctionDef(name='constructor')
                self._advance()
                if self._match('('):
                    self._skip_until(')')
                    self._advance()
                if self._match('{'):
                    self._skip_brace_block()
                cls.methods.append(func)
            elif self._match('static', 'public', 'private', 'protected', 'abstract', 'readonly'):
                modifiers = []
                is_abstract = False
                while self._match('static', 'public', 'private', 'protected', 'abstract', 'readonly'):
                    if self._match('abstract'):
                        is_abstract = True
                    modifiers.append(self._current().value)
                    self._advance()
                if self._match_type(TokenType.IDENTIFIER):
                    name = self._current().value
                    self._advance()
                    if self._match('('):
                        func = FunctionDef(name=name, is_abstract=is_abstract)
                        cls.methods.append(func)
                        self._skip_until(')')
                        self._advance()
                        if self._match('{'):
                            self._skip_brace_block()
                    else:
                        attr = AttributeDef(name=name)
                        cls.attributes.append(attr)
            elif self._match_type(TokenType.IDENTIFIER):
                name = self._current().value
                self._advance()
                if self._match('('):
                    func = FunctionDef(name=name)
                    cls.methods.append(func)
                    self._skip_until(')')
                    self._advance()
                    if self._match('{'):
                        self._skip_brace_block()
            else:
                self._advance()
    
    def _parse_interface(self) -> InterfaceDef:
        """Parse TypeScript interface."""
        token = self._advance()  # consume 'interface'
        iface = InterfaceDef(lineno=token.lineno)
        
        if self._match_type(TokenType.IDENTIFIER):
            iface.name = self._current().value
            self._advance()
        
        if self._match('extends'):
            self._advance()
            while not self._match('{'):
                if self._match_type(TokenType.IDENTIFIER):
                    iface.extends.append(self._current().value)
                self._advance()
        
        if self._match('{'):
            self._advance()
            brace_depth = 1
            while brace_depth > 0 and self._current():
                if self._match('{'):
                    brace_depth += 1
                elif self._match('}'):
                    brace_depth -= 1
                elif self._match_type(TokenType.IDENTIFIER):
                    name = self._current().value
                    self._advance()
                    if self._match('('):
                        func = FunctionDef(name=name, is_abstract=True)
                        iface.methods.append(func)
                self._advance()
        
        return iface
    
    def _parse_function(self) -> FunctionDef:
        """Parse function definition."""
        token = self._advance()  # consume 'function'
        func = FunctionDef(lineno=token.lineno)
        
        if self._match_type(TokenType.IDENTIFIER):
            func.name = self._current().value
            self._advance()
        
        if self._match('('):
            self._skip_until(')')
            self._advance()
        
        if self._match('{'):
            self._skip_brace_block()
        
        return func
    
    def _skip_brace_block(self) -> None:
        """Skip brace-delimited block."""
        if not self._match('{'):
            return
        self._advance()
        depth = 1
        while depth > 0 and self._current():
            if self._match('{'):
                depth += 1
            elif self._match('}'):
                depth -= 1
            self._advance()


class CppParser(BaseParser):
    """Parser for C/C++ source code."""
    
    def parse(self) -> ModuleDef:
        """Parse C++ tokens into AST."""
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('class', 'struct'):
                self.module.classes.append(self._parse_class())
            elif self._match('namespace'):
                self._parse_namespace()
            else:
                self._advance()
        return self.module
    
    def _parse_class(self) -> ClassDef:
        """Parse class/struct definition."""
        is_struct = self._match('struct')
        token = self._advance()
        cls = ClassDef(lineno=token.lineno)
        
        if self._match_type(TokenType.IDENTIFIER):
            cls.name = self._current().value
            self._advance()
        
        # Parse inheritance
        if self._match(':'):
            self._advance()
            while not self._match('{', ';'):
                if self._match('public', 'private', 'protected'):
                    self._advance()
                if self._match_type(TokenType.IDENTIFIER):
                    cls.bases.append(self._current().value)
                self._advance()
        
        if self._match('{'):
            self._advance()
            self._parse_class_body(cls)
        
        return cls
    
    def _parse_class_body(self, cls: ClassDef) -> None:
        """Parse class body."""
        brace_depth = 1
        visibility = 'private'
        
        while brace_depth > 0 and self._current():
            if self._match('{'):
                brace_depth += 1
                self._advance()
            elif self._match('}'):
                brace_depth -= 1
                self._advance()
            elif self._match('public', 'private', 'protected'):
                visibility = self._current().value
                self._advance()
                self._consume(':')
            elif self._match('virtual'):
                self._advance()
                # Check for pure virtual (abstract)
                is_abstract = False
                name = None
                while not self._match(';', '{'):
                    if self._match('=') and self._peek(1) and self._peek(1).value == '0':
                        is_abstract = True
                    if self._match_type(TokenType.IDENTIFIER):
                        name = self._current().value
                    self._advance()
                if name:
                    func = FunctionDef(name=name, is_abstract=is_abstract, visibility=visibility)
                    cls.methods.append(func)
                    if is_abstract:
                        cls.is_abstract = True
            else:
                self._advance()
    
    def _parse_namespace(self) -> None:
        """Parse namespace and its contents."""
        self._advance()  # consume 'namespace'
        if self._match_type(TokenType.IDENTIFIER):
            self._advance()
        if self._match('{'):
            self._advance()
            depth = 1
            while depth > 0 and self._current():
                if self._match('{'):
                    depth += 1
                elif self._match('}'):
                    depth -= 1
                elif self._match('class', 'struct'):
                    self.module.classes.append(self._parse_class())
                    continue
                self._advance()


class GoParser(BaseParser):
    """Parser for Go source code."""
    
    def parse(self) -> ModuleDef:
        """Parse Go tokens into AST."""
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('import'):
                self._parse_import()
            elif self._match('type'):
                self._parse_type()
            elif self._match('func'):
                func = self._parse_func()
                if func:
                    self.module.functions.append(func)
            else:
                self._advance()
        return self.module
    
    def _parse_import(self) -> None:
        """Parse import statement."""
        self._advance()  # consume 'import'
        if self._match('('):
            self._advance()
            while not self._match(')'):
                if self._match_type(TokenType.STRING):
                    imp = ImportDef(module=self._current().value.strip('"'))
                    self.module.imports.append(imp)
                self._advance()
            self._consume(')')
        elif self._match_type(TokenType.STRING):
            imp = ImportDef(module=self._current().value.strip('"'))
            self.module.imports.append(imp)
            self._advance()
    
    def _parse_type(self) -> None:
        """Parse type definition (struct or interface)."""
        self._advance()  # consume 'type'
        if not self._match_type(TokenType.IDENTIFIER):
            return
        name = self._current().value
        self._advance()
        
        if self._match('struct'):
            self._advance()
            cls = ClassDef(name=name)
            if self._match('{'):
                self._advance()
                self._parse_struct_body(cls)
            self.module.classes.append(cls)
        elif self._match('interface'):
            self._advance()
            iface = InterfaceDef(name=name)
            if self._match('{'):
                self._advance()
                self._parse_interface_body(iface)
            self.module.interfaces.append(iface)
    
    def _parse_struct_body(self, cls: ClassDef) -> None:
        """Parse struct body for fields."""
        while not self._match('}') and self._current():
            if self._match_type(TokenType.IDENTIFIER):
                name = self._current().value
                self._advance()
                attr = AttributeDef(name=name)
                cls.attributes.append(attr)
            self._advance()
        self._consume('}')
    
    def _parse_interface_body(self, iface: InterfaceDef) -> None:
        """Parse interface body for method signatures."""
        while not self._match('}') and self._current():
            if self._match_type(TokenType.IDENTIFIER):
                name = self._current().value
                self._advance()
                if self._match('('):
                    func = FunctionDef(name=name, is_abstract=True)
                    iface.methods.append(func)
            self._advance()
        self._consume('}')
    
    def _parse_func(self) -> Optional[FunctionDef]:
        """Parse function definition."""
        self._advance()  # consume 'func'
        
        # Check for method receiver
        if self._match('('):
            self._advance()
            self._skip_until(')')
            self._consume(')')
        
        if not self._match_type(TokenType.IDENTIFIER):
            return None
        
        func = FunctionDef(name=self._current().value)
        self._advance()
        
        if self._match('('):
            self._skip_until(')')
            self._consume(')')
        
        # Skip return type and body
        if self._match('{'):
            depth = 1
            self._advance()
            while depth > 0 and self._current():
                if self._match('{'):
                    depth += 1
                elif self._match('}'):
                    depth -= 1
                self._advance()
        
        return func


class RustParser(BaseParser):
    """Parser for Rust source code."""
    
    def parse(self) -> ModuleDef:
        """Parse Rust tokens into AST."""
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('use'):
                self._parse_use()
            elif self._match('struct'):
                self.module.classes.append(self._parse_struct())
            elif self._match('trait'):
                self.module.interfaces.append(self._parse_trait())
            elif self._match('impl'):
                self._parse_impl()
            elif self._match('fn', 'pub'):
                if self._match('pub'):
                    self._advance()
                if self._match('fn'):
                    self.module.functions.append(self._parse_fn())
            else:
                self._advance()
        return self.module
    
    def _parse_use(self) -> None:
        """Parse use statement."""
        self._advance()  # consume 'use'
        parts = []
        while not self._match(';'):
            if self._match_type(TokenType.IDENTIFIER) or self._match(':'):
                parts.append(self._current().value)
            self._advance()
        imp = ImportDef(module=''.join(parts))
        self.module.imports.append(imp)
        self._consume(';')
    
    def _parse_struct(self) -> ClassDef:
        """Parse struct definition."""
        self._advance()  # consume 'struct'
        cls = ClassDef()
        
        if self._match_type(TokenType.IDENTIFIER):
            cls.name = self._current().value
            self._advance()
        
        if self._match('{'):
            self._advance()
            while not self._match('}') and self._current():
                if self._match_type(TokenType.IDENTIFIER):
                    attr = AttributeDef(name=self._current().value)
                    cls.attributes.append(attr)
                self._advance()
            self._consume('}')
        
        return cls
    
    def _parse_trait(self) -> InterfaceDef:
        """Parse trait definition."""
        self._advance()  # consume 'trait'
        iface = InterfaceDef()
        
        if self._match_type(TokenType.IDENTIFIER):
            iface.name = self._current().value
            self._advance()
        
        if self._match('{'):
            self._advance()
            while not self._match('}') and self._current():
                if self._match('fn'):
                    self._advance()
                    if self._match_type(TokenType.IDENTIFIER):
                        func = FunctionDef(name=self._current().value, is_abstract=True)
                        iface.methods.append(func)
                self._advance()
            self._consume('}')
        
        return iface
    
    def _parse_impl(self) -> None:
        """Parse impl block and add methods to corresponding struct."""
        self._advance()  # consume 'impl'
        
        # Get type name
        type_name = None
        trait_name = None
        
        if self._match_type(TokenType.IDENTIFIER):
            type_name = self._current().value
            self._advance()
        
        if self._match('for'):
            trait_name = type_name
            self._advance()
            if self._match_type(TokenType.IDENTIFIER):
                type_name = self._current().value
                self._advance()
        
        # Find the struct and add methods
        target_cls = None
        for cls in self.module.classes:
            if cls.name == type_name:
                target_cls = cls
                break
        
        if self._match('{'):
            self._advance()
            while not self._match('}') and self._current():
                if self._match('fn', 'pub'):
                    if self._match('pub'):
                        self._advance()
                    if self._match('fn'):
                        func = self._parse_fn()
                        if target_cls:
                            target_cls.methods.append(func)
                else:
                    self._advance()
            self._consume('}')
    
    def _parse_fn(self) -> FunctionDef:
        """Parse function definition."""
        self._advance()  # consume 'fn'
        func = FunctionDef()
        
        if self._match_type(TokenType.IDENTIFIER):
            func.name = self._current().value
            self._advance()
        
        if self._match('('):
            self._skip_until(')')
            self._consume(')')
        
        # Skip return type and body
        while not self._match('{', ';') and self._current():
            self._advance()
        
        if self._match('{'):
            depth = 1
            self._advance()
            while depth > 0 and self._current():
                if self._match('{'):
                    depth += 1
                elif self._match('}'):
                    depth -= 1
                self._advance()
        
        return func


class SwiftParser(BaseParser):
    """Parser for Swift source code."""
    
    def parse(self) -> ModuleDef:
        """Parse Swift tokens into AST."""
        while self._current() and self._current().type != TokenType.EOF:
            if self._match('import'):
                self._parse_import()
            elif self._match('class', 'struct'):
                self.module.classes.append(self._parse_class())
            elif self._match('protocol'):
                self.module.interfaces.append(self._parse_protocol())
            elif self._match('func'):
                self.module.functions.append(self._parse_func())
            else:
                self._advance()
        return self.module
    
    def _parse_import(self) -> None:
        """Parse import statement."""
        self._advance()  # consume 'import'
        if self._match_type(TokenType.IDENTIFIER):
            imp = ImportDef(module=self._current().value)
            self.module.imports.append(imp)
            self._advance()
    
    def _parse_class(self) -> ClassDef:
        """Parse class/struct definition."""
        is_struct = self._match('struct')
        self._advance()
        cls = ClassDef()
        
        if self._match_type(TokenType.IDENTIFIER):
            cls.name = self._current().value
            self._advance()
        
        if self._match(':'):
            self._advance()
            while not self._match('{'):
                if self._match_type(TokenType.IDENTIFIER):
                    cls.bases.append(self._current().value)
                self._advance()
        
        if self._match('{'):
            self._advance()
            self._parse_class_body(cls)
        
        return cls
    
    def _parse_class_body(self, cls: ClassDef) -> None:
        """Parse class body."""
        depth = 1
        while depth > 0 and self._current():
            if self._match('{'):
                depth += 1
                self._advance()
            elif self._match('}'):
                depth -= 1
                self._advance()
            elif self._match('func'):
                self._advance()
                if self._match_type(TokenType.IDENTIFIER):
                    func = FunctionDef(name=self._current().value)
                    cls.methods.append(func)
                self._skip_until('{', '}')
                if self._match('{'):
                    self._skip_brace_block()
            elif self._match('var', 'let'):
                self._advance()
                if self._match_type(TokenType.IDENTIFIER):
                    attr = AttributeDef(name=self._current().value)
                    cls.attributes.append(attr)
                self._advance()
            else:
                self._advance()
    
    def _parse_protocol(self) -> InterfaceDef:
        """Parse protocol definition."""
        self._advance()  # consume 'protocol'
        iface = InterfaceDef()
        
        if self._match_type(TokenType.IDENTIFIER):
            iface.name = self._current().value
            self._advance()
        
        if self._match('{'):
            self._advance()
            depth = 1
            while depth > 0 and self._current():
                if self._match('{'):
                    depth += 1
                elif self._match('}'):
                    depth -= 1
                elif self._match('func'):
                    self._advance()
                    if self._match_type(TokenType.IDENTIFIER):
                        func = FunctionDef(name=self._current().value, is_abstract=True)
                        iface.methods.append(func)
                self._advance()
        
        return iface
    
    def _parse_func(self) -> FunctionDef:
        """Parse function definition."""
        self._advance()  # consume 'func'
        func = FunctionDef()
        
        if self._match_type(TokenType.IDENTIFIER):
            func.name = self._current().value
            self._advance()
        
        self._skip_until('{', '}')
        if self._match('{'):
            self._skip_brace_block()
        
        return func
    
    def _skip_brace_block(self) -> None:
        """Skip brace-delimited block."""
        if not self._match('{'):
            return
        self._advance()
        depth = 1
        while depth > 0 and self._current():
            if self._match('{'):
                depth += 1
            elif self._match('}'):
                depth -= 1
            self._advance()


# =============================================================================
# Unified Parse Function
# =============================================================================

def get_language_from_extension(extension: str) -> str:
    """Map file extension to language name."""
    mapping = {
        '.py': 'python', '.pyi': 'python',
        '.java': 'java', '.scala': 'java', '.kt': 'java',
        '.js': 'javascript', '.jsx': 'javascript',
        '.ts': 'typescript', '.tsx': 'typescript',
        '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', 
        '.c': 'cpp', '.h': 'cpp', '.hpp': 'cpp', '.hxx': 'cpp',
        '.go': 'go',
        '.rs': 'rust',
        '.swift': 'swift'
    }
    return mapping.get(extension.lower(), 'unknown')


def parse(source: str, extension: str = '.py') -> ModuleDef:
    """
    Parse source code into a ModuleDef AST.
    
    Args:
        source: Source code string
        extension: File extension (e.g., '.py', '.java')
    
    Returns:
        ModuleDef containing parsed AST nodes
    """
    language = get_language_from_extension(extension)
    
    # Special case: use Python's native ast for Python files
    if language == 'python':
        try:
            return _parse_python_native(source)
        except Exception:
            pass  # Fall back to heuristic parser
    
    # Tokenize
    tokenizer = Tokenizer(source, language)
    tokens = tokenizer.tokenize()
    
    # Parse with appropriate parser
    parser_map = {
        'python': PythonParser,
        'java': JavaParser,
        'javascript': lambda t, s: JavaScriptParser(t, s, is_typescript=False),
        'typescript': lambda t, s: JavaScriptParser(t, s, is_typescript=True),
        'cpp': CppParser,
        'go': GoParser,
        'rust': RustParser,
        'swift': SwiftParser
    }
    
    parser_cls = parser_map.get(language)
    if parser_cls is None:
        return ModuleDef()
    
    if callable(parser_cls) and not isinstance(parser_cls, type):
        parser = parser_cls(tokens, source)
    else:
        parser = parser_cls(tokens, source)
    
    return parser.parse()


def _parse_python_native(source: str) -> ModuleDef:
    """Parse Python using native ast module for maximum accuracy."""
    import ast as python_ast
    
    tree = python_ast.parse(source)
    module = ModuleDef()
    
    for node in python_ast.iter_child_nodes(tree):
        if isinstance(node, python_ast.Import):
            for alias in node.names:
                imp = ImportDef(
                    module=alias.name,
                    names=[alias.asname or alias.name],
                    lineno=node.lineno
                )
                module.imports.append(imp)
        
        elif isinstance(node, python_ast.ImportFrom):
            imp = ImportDef(
                module=node.module or '',
                names=[a.name for a in node.names],
                is_from=True,
                lineno=node.lineno
            )
            module.imports.append(imp)
        
        elif isinstance(node, python_ast.ClassDef):
            cls = _convert_python_class(node)
            module.classes.append(cls)
        
        elif isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
            func = _convert_python_function(node)
            module.functions.append(func)
    
    return module


def _convert_python_class(node) -> ClassDef:
    """Convert Python ast.ClassDef to our ClassDef."""
    import ast as python_ast
    
    cls = ClassDef(
        name=node.name,
        lineno=node.lineno,
        col_offset=node.col_offset,
        end_lineno=getattr(node, 'end_lineno', 0) or 0,
        end_col_offset=getattr(node, 'end_col_offset', 0) or 0
    )
    
    # Get base classes
    for base in node.bases:
        if isinstance(base, python_ast.Name):
            cls.bases.append(base.id)
            if base.id in ('ABC', 'ABCMeta'):
                cls.is_abstract = True
        elif isinstance(base, python_ast.Attribute):
            cls.bases.append(base.attr)
    
    # Get decorators
    for dec in node.decorator_list:
        if isinstance(dec, python_ast.Name):
            cls.decorators.append(dec.id)
        elif isinstance(dec, python_ast.Attribute):
            cls.decorators.append(dec.attr)
    
    # Parse body
    for item in node.body:
        if isinstance(item, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
            method = _convert_python_function(item)
            cls.methods.append(method)
            if method.is_abstract:
                cls.is_abstract = True
        elif isinstance(item, python_ast.Assign):
            for target in item.targets:
                if isinstance(target, python_ast.Name):
                    attr = AttributeDef(name=target.id, lineno=item.lineno)
                    cls.attributes.append(attr)
        elif isinstance(item, python_ast.AnnAssign):
            if isinstance(item.target, python_ast.Name):
                type_str = None
                if item.annotation:
                    type_str = python_ast.unparse(item.annotation) if hasattr(python_ast, 'unparse') else None
                attr = AttributeDef(name=item.target.id, type_annotation=type_str, lineno=item.lineno)
                cls.attributes.append(attr)
        elif isinstance(item, python_ast.ClassDef):
            nested = _convert_python_class(item)
            cls.nested_classes.append(nested)
    
    return cls


def _convert_python_function(node) -> FunctionDef:
    """Convert Python ast.FunctionDef to our FunctionDef with CK metrics extraction."""
    import ast as python_ast
    
    func = FunctionDef(
        name=node.name,
        lineno=node.lineno,
        col_offset=node.col_offset,
        end_lineno=getattr(node, 'end_lineno', 0) or 0,
        end_col_offset=getattr(node, 'end_col_offset', 0) or 0
    )
    
    # Get arguments and parameter types
    for arg in node.args.args:
        func.args.append(arg.arg)
        if arg.annotation and hasattr(python_ast, 'unparse'):
            try:
                type_str = python_ast.unparse(arg.annotation)
                func.parameter_types.append(type_str)
            except Exception:
                pass
    
    # Get decorators
    for dec in node.decorator_list:
        if isinstance(dec, python_ast.Name):
            func.decorators.append(dec.id)
            if dec.id == 'abstractmethod':
                func.is_abstract = True
            if dec.id == 'staticmethod':
                func.is_static = True
        elif isinstance(dec, python_ast.Attribute):
            func.decorators.append(dec.attr)
    
    # Get return type
    if node.returns:
        func.return_type = python_ast.unparse(node.returns) if hasattr(python_ast, 'unparse') else None
    
    # Calculate cyclomatic complexity and extract method-level metrics
    complexity = 1  # Base complexity
    accessed_attrs = set()
    called_methods = set()
    
    for child in python_ast.walk(node):
        # Count decision points for cyclomatic complexity
        if isinstance(child, (python_ast.If, python_ast.While, python_ast.For)):
            complexity += 1
        elif isinstance(child, python_ast.BoolOp):
            # 'and' / 'or' add complexity
            complexity += len(child.values) - 1
        elif isinstance(child, python_ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, python_ast.comprehension):
            complexity += 1  # List/dict/set comprehensions with conditionals
            complexity += len(child.ifs)
        elif isinstance(child, python_ast.IfExp):
            complexity += 1  # Ternary expressions
        elif isinstance(child, python_ast.Assert):
            complexity += 1
        elif isinstance(child, python_ast.Match) if hasattr(python_ast, 'Match') else False:
            complexity += 1
        
        # Track accessed instance attributes (self.x)
        if isinstance(child, python_ast.Attribute):
            if isinstance(child.value, python_ast.Name) and child.value.id == 'self':
                accessed_attrs.add(child.attr)
        
        # Track method calls
        if isinstance(child, python_ast.Call):
            if isinstance(child.func, python_ast.Attribute):
                # obj.method() calls
                if isinstance(child.func.value, python_ast.Name):
                    caller = child.func.value.id
                    method = child.func.attr
                    if caller == 'self':
                        called_methods.add(method)  # Internal method call
                    else:
                        called_methods.add(f"{caller}.{method}")  # External call
            elif isinstance(child.func, python_ast.Name):
                # Direct function/method calls
                called_methods.add(child.func.id)
    
    func.cyclomatic_complexity = complexity
    func.accessed_attributes = accessed_attrs
    func.called_methods = called_methods
    
    return func



class OOPMetricsAnalyzer:
	"""Analyzer for Object-Oriented Programming metrics with focus on Distance from Main Sequence."""
	
	def __init__(self, use_ast: bool = True):
		"""Initialize the OOP metrics analyzer.
		
		Args:
			use_ast: If True, use AST-based parsing (more accurate). If False, use regex.
		"""
		self.packages = {}  # package_path -> metrics
		self.files = {}     # file_path -> metrics
		self.dependencies = defaultdict(set)  # file_path -> set of dependencies
		self.dependents = defaultdict(set)    # file_path -> set of dependents
		self.use_ast = use_ast  # AST always available
		
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
			'dependents': [],
			# Function-level metrics (applies to all files)
			'function_count': 0,
			'function_wmc': 0,  # Sum of all function complexities
			'functions': [],
			'classes': [],
			# CK Metrics - aggregated at file level
			'ck_metrics': {
				'wmc_total': 0,
				'avg_wmc': 0.0,
				'max_dit': 0,
				'total_noc': 0,
				'avg_cbo': 0.0,
				'avg_rfc': 0.0,
				'avg_lcom': 0.0,
			}
		}
		
		if not content.strip():
			return metrics
		
		try:
			# Try AST-based analysis first (more accurate)
			if self.use_ast:
				ast_metrics = self._analyze_with_ast(content, filepath, file_extension)
				if ast_metrics:
					metrics.update(ast_metrics)
				else:
					# Fall back to regex-based analysis
					metrics.update(self._analyze_with_regex(content, filepath, file_extension))
			else:
				# Use regex-based analysis
				metrics.update(self._analyze_with_regex(content, filepath, file_extension))
			
			# Calculate derived metrics
			metrics = self._calculate_derived_metrics(metrics)
			
			# Store for package-level analysis
			self.files[filepath] = metrics
			
		except Exception as e:
			print(f'Warning: OOP metrics calculation failed for {filepath}: {e}')
		
		return metrics
	
	def _analyze_with_ast(self, content: str, filepath: str, file_extension: str) -> Dict:
		"""
		Analyze file using AST-based parsing (more accurate than regex).
		
		Args:
			content: File content
			filepath: Path to the file
			file_extension: File extension
			
		Returns:
			Dictionary with OOP metrics or None if parsing fails
		"""
		if False:  # AST always available in combined module
			return None
		
		try:
			tree = parse(content, file_extension)
			
			metrics = {
				'classes_defined': 0,
				'abstract_classes': 0,
				'interfaces_defined': 0,
				'method_count': 0,
				'attribute_count': 0,
				'efferent_coupling': 0,
				'dependencies': [],
				# CK Metrics - aggregated at file level
				'ck_metrics': {
					'wmc_total': 0,
					'avg_wmc': 0.0,
					'max_dit': 0,
					'total_noc': 0,
					'avg_cbo': 0.0,
					'avg_rfc': 0.0,
					'avg_lcom': 0.0,
				},
				# Drill-down: per-class metrics
				'classes': [],
				# Drill-down: per-function metrics 
				'functions': []
			}
			
			# Collect all classes for CK metrics calculation
			all_classes = []
			all_class_names = set()
			inheritance_map = {}
			
			# First pass: collect class info
			for node in walk(tree):
				if isinstance(node, ClassDef):
					all_classes.append(node)
					all_class_names.add(node.name)
					inheritance_map[node.name] = node.bases
				elif isinstance(node, InterfaceDef):
					all_class_names.add(node.name)
			
			# Second pass: calculate metrics
			for node in walk(tree):
				if isinstance(node, ClassDef):
					metrics['classes_defined'] += 1
					if node.is_abstract:
						metrics['abstract_classes'] += 1
					metrics['method_count'] += len(node.methods)
					metrics['attribute_count'] += len(node.attributes)
					
					# Apply CK metrics to this class
					apply_ck_metrics_to_class(node, all_classes, inheritance_map, all_class_names)
					
					# Aggregate CK metrics at file level
					metrics['ck_metrics']['wmc_total'] += node.wmc
					metrics['ck_metrics']['max_dit'] = max(metrics['ck_metrics']['max_dit'], node.dit)
					metrics['ck_metrics']['total_noc'] += node.noc
					
					# Store per-class details for drill-down
					class_info = {
						'name': node.name,
						'lineno': node.lineno,
						'is_abstract': node.is_abstract,
						'bases': node.bases,
						'wmc': node.wmc,
						'dit': node.dit,
						'noc': node.noc,
						'cbo': node.cbo,
						'rfc': node.rfc,
						'lcom': node.lcom,
						'coupled_classes': list(node.coupled_classes),
						'method_count': len(node.methods),
						'attribute_count': len(node.attributes),
						# Per-method details for drill-down
						'methods': [
							{
								'name': m.name,
								'lineno': m.lineno,
								'cyclomatic_complexity': m.cyclomatic_complexity,
								'accessed_attributes': list(m.accessed_attributes),
								'called_methods': list(m.called_methods),
								'is_abstract': m.is_abstract,
								'is_static': m.is_static,
							}
							for m in node.methods
						]
					}
					metrics['classes'].append(class_info)
				
				elif isinstance(node, InterfaceDef):
					metrics['interfaces_defined'] += 1
					metrics['abstract_classes'] += 1  # Interfaces are abstract
					metrics['method_count'] += len(node.methods)
				
				elif isinstance(node, ImportDef):
					if node.module:
						metrics['dependencies'].append(node.module)
			
			# Calculate averages for CK metrics
			if metrics['classes_defined'] > 0:
				metrics['ck_metrics']['avg_wmc'] = metrics['ck_metrics']['wmc_total'] / metrics['classes_defined']
				total_cbo = sum(c['cbo'] for c in metrics['classes'])
				total_rfc = sum(c['rfc'] for c in metrics['classes'])
				total_lcom = sum(c['lcom'] for c in metrics['classes'])
				metrics['ck_metrics']['avg_cbo'] = total_cbo / metrics['classes_defined']
				metrics['ck_metrics']['avg_rfc'] = total_rfc / metrics['classes_defined']
				metrics['ck_metrics']['avg_lcom'] = total_lcom / metrics['classes_defined']
			
			# Store standalone function metrics for drill-down
			for func in tree.functions:
				metrics['functions'].append({
					'name': func.name,
					'lineno': func.lineno,
					'cyclomatic_complexity': func.cyclomatic_complexity,
					'accessed_attributes': list(func.accessed_attributes),
					'called_methods': list(func.called_methods),
				})
			
			# Calculate function-level metrics for all files (OOP and non-OOP)
			metrics['function_count'] = len(tree.functions)
			metrics['function_wmc'] = sum(f['cyclomatic_complexity'] for f in metrics['functions'])
			
			# Deduplicate dependencies
			metrics['dependencies'] = list(set(metrics['dependencies']))
			metrics['efferent_coupling'] = len(metrics['dependencies'])
			
			# Store dependencies for afferent coupling calculation
			self.dependencies[filepath] = set(metrics['dependencies'])
			
			return metrics
			
		except Exception:
			return None
	
	def _analyze_with_regex(self, content: str, filepath: str, file_extension: str) -> Dict:
		"""
		Analyze file using regex-based parsing (fallback method).
		
		Args:
			content: File content
			filepath: Path to the file
			file_extension: File extension
			
		Returns:
			Dictionary with OOP metrics
		"""
		# Remove comments and strings for accurate analysis
		cleaned_content = self._remove_comments_and_strings(content, file_extension)
		
		# Language-specific OOP analysis
		if file_extension in ['.java', '.scala', '.kt']:
			return self._analyze_java_oop(cleaned_content, filepath)
		elif file_extension in ['.py', '.pyi']:
			return self._analyze_python_oop(cleaned_content, filepath)
		elif file_extension in ['.cpp', '.cc', '.cxx', '.hpp', '.hxx', '.h']:
			return self._analyze_cpp_oop(cleaned_content, filepath)
		elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
			return self._analyze_javascript_oop(cleaned_content, filepath)
		elif file_extension in ['.swift']:
			return self._analyze_swift_oop(cleaned_content, filepath)
		elif file_extension in ['.go']:
			return self._analyze_go_oop(cleaned_content, filepath)
		elif file_extension in ['.rs']:
			return self._analyze_rust_oop(cleaned_content, filepath)
		
		return {}
	
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
			# Also count classes with @abstractmethod decorators
			abstractmethod_count = len(re.findall(r'@abstractmethod', content))
			if abc_classes:
				metrics['abstract_classes'] = len(abc_classes)
			elif abstractmethod_count > 0:
				# Has abstract methods but no explicit ABC inheritance detected
				# Conservative: at least 1 abstract class
				metrics['abstract_classes'] = 1
			else:
				metrics['abstract_classes'] = 0
		else:
			metrics['abstract_classes'] = 0
		
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
