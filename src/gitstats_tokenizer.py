"""
State-machine based tokenizer for multi-language parsing.

Handles strings, comments, and nesting for Python, Java, JavaScript/TypeScript,
C++, Go, Rust, and Swift.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Set


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


# Language-specific keywords
LANGUAGE_KEYWORDS = {
    'python': {'class', 'def', 'import', 'from', 'as', 'try', 'except', 
              'finally', 'with', 'async', 'await', 'yield', 'lambda',
              'pass', 'raise', 'global', 'nonlocal', 'assert', 'del',
              'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
              'if', 'else', 'elif', 'for', 'while', 'return', 'break', 'continue'},
    'java': {'class', 'interface', 'enum', 'abstract', 'final', 'static',
            'public', 'private', 'protected', 'extends', 'implements',
            'new', 'this', 'super', 'void', 'null', 'true', 'false',
            'import', 'package', 'throws', 'throw', 'try', 'catch',
            'synchronized', 'volatile', 'transient', 'native',
            'if', 'else', 'for', 'while', 'return', 'break', 'continue'},
    'javascript': {'class', 'function', 'const', 'let', 'var', 'import',
                  'export', 'from', 'default', 'extends', 'new', 'this',
                  'super', 'async', 'await', 'yield', 'null', 'undefined',
                  'true', 'false', 'typeof', 'instanceof', 'delete',
                  'if', 'else', 'for', 'while', 'return', 'break', 'continue'},
    'typescript': {'class', 'function', 'const', 'let', 'var', 'import',
                  'export', 'from', 'default', 'extends', 'implements',
                  'interface', 'type', 'enum', 'abstract', 'new', 'this',
                  'super', 'async', 'await', 'public', 'private', 'protected',
                  'readonly', 'static', 'null', 'undefined',
                  'if', 'else', 'for', 'while', 'return', 'break', 'continue'},
    'cpp': {'class', 'struct', 'enum', 'union', 'namespace', 'template',
           'virtual', 'override', 'final', 'static', 'const', 'mutable',
           'public', 'private', 'protected', 'friend', 'inline', 'extern',
           'new', 'delete', 'this', 'nullptr', 'true', 'false', 'sizeof',
           'typedef', 'using', 'typename', 'explicit', 'operator',
           'if', 'else', 'for', 'while', 'return', 'break', 'continue'},
    'go': {'func', 'type', 'struct', 'interface', 'package', 'import',
          'const', 'var', 'map', 'chan', 'go', 'defer', 'select', 'case',
          'default', 'range', 'nil', 'true', 'false', 'iota',
          'if', 'else', 'for', 'return', 'break', 'continue'},
    'rust': {'fn', 'struct', 'enum', 'trait', 'impl', 'mod', 'use', 'pub',
            'crate', 'super', 'self', 'Self', 'const', 'static', 'mut',
            'ref', 'let', 'match', 'loop', 'async', 'await', 'move',
            'dyn', 'where', 'unsafe', 'extern',
            'if', 'else', 'for', 'while', 'return', 'break', 'continue'},
    'swift': {'class', 'struct', 'enum', 'protocol', 'extension', 'func',
             'var', 'let', 'import', 'public', 'private', 'internal',
             'fileprivate', 'open', 'static', 'final', 'override',
             'init', 'deinit', 'self', 'Self', 'nil', 'true', 'false',
             'if', 'else', 'for', 'while', 'return', 'break', 'continue'}
}


class Tokenizer:
    """
    State-machine based tokenizer that handles strings, comments, and nesting.
    
    Supports multiple programming languages with language-specific handling
    for comments, string literals, and keywords.
    """
    
    def __init__(self, source: str, language: str = 'python'):
        """
        Initialize the tokenizer.
        
        Args:
            source: Source code to tokenize
            language: Programming language ('python', 'java', 'javascript', 
                      'typescript', 'cpp', 'go', 'rust', 'swift')
        """
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
    
    def _setup_language(self, language: str) -> None:
        """Configure tokenizer for specific language."""
        self.single_comment = '#' if language == 'python' else '//'
        self.multi_comment_start = None if language == 'python' else '/*'
        self.multi_comment_end = None if language == 'python' else '*/'
        self.has_triple_strings = language == 'python'
        self.has_template_strings = language in ('javascript', 'typescript')
        
        # Keywords by language
        self.keywords = LANGUAGE_KEYWORDS.get(language, set())
    
    def tokenize(self) -> List[Token]:
        """
        Tokenize the entire source code.
        
        Returns:
            List of tokens
        """
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
        elif self.state == TokenizerState.IN_TEMPLATE_STRING:
            return self._tokenize_template_string(start_line, start_col)
        
        return None
    
    def _advance(self, count: int = 1) -> None:
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
    
    def _update_depth(self, char: str) -> None:
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
