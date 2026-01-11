import re
from dataclasses import dataclass
from typing import List, Pattern

@dataclass
class Token:
    type: str
    value: str
    line: int
    column: int
    start_char: int
    end_char: int

class LexerError(Exception):
    pass

class Lexer:
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.tokens: List[Token] = []
        self.line = 1
        self.column = 1
        self.char_pos = 0

        # Order matters. Keywords are matched before generic identifiers.
        self.token_specification = [
            # --- Comments and Whitespace ---
            ('COMMENT', r'#.*'),
            ('WHITESPACE', r'[ \t]+'),
            ('NEWLINE', r'\n'),
            
            # --- Symbols and Operators ---
            ('LBRACE', r'\{'),
            ('RBRACE', r'\}'),
            ('LPAREN', r'\('),
            ('RPAREN', r'\)'),
            ('COMMA', r','),
            ('SEMICOLON', r';'),
            ('ASTERISK', r'\*'),
            ('EQUALS_EQUALS', r'=='),
            ('NOT_EQUALS', r'!='),
            ('GREATER_EQUALS', r'>='),
            ('LESS_EQUALS', r'<='),
            ('EQUALS', r'='),
            ('GREATER', r'>'),
            ('LESS', r'<'),
            ('PLUS', r'\+'),
            ('MINUS', r'-'),
            ('DIVIDE', r'\/'),

            # --- Keywords ---
            ('KW_FN', r'\bfn\b'),
            ('KW_ON', r'\bon\b'),
            ('KW_LOAD', r'\bload\b'),
            ('KW_TICK', r'\btick\b'),
            ('KW_IF', r'\bif\b'),
            ('KW_ELSE', r'\belse\b'),
            ('KW_FROM', r'\bfrom\b'),
            ('KW_IMPORT', r'\bimport\b'),
            ('KW_AS', r'\bas\b'),
            ('KW_MACRO', r'\bmacro\b'),
            ('KW_FOR', r'\bfor\b'),
            ('KW_IN', r'\bin\b'),
            ('KW_WHILE', r'\bwhile\b'),

            # --- Literals and Identifiers ---
            ('NUMBER', r'\d+'),
            ('STRING', r'"[^"]*"'),
            ('SELECTOR', r'@[apres]'),
            ('IDENT', r'[a-zA-Z_][a-zA-Z0-9_]*'),
            
            # --- Errors ---
            ('MISMATCH', r'.'),
        ]
        
        # Compile regexes for efficiency
        self.token_regex = re.compile('|'.join(f'(?P<{name}>{pattern})' for name, pattern in self.token_specification))

    def tokenize(self) -> List[Token]:
        pos = 0
        while pos < len(self.source_code):
            match = self.token_regex.match(self.source_code, pos)
            if not match:
                raise LexerError(f"Unexpected character at line {self.line}, column {self.column}")

            kind = match.lastgroup
            value = match.group()
            start_char = pos
            pos = match.end()
            end_char = pos

            if kind == 'NEWLINE':
                self.line += 1
                self.column = 1
            elif kind in ['WHITESPACE', 'COMMENT']:
                self.column += len(value)
            elif kind == 'MISMATCH':
                raise LexerError(f"Unexpected character '{value}' at line {self.line}, column {self.column}")
            else:
                token = Token(kind, value, self.line, self.column, start_char, end_char)
                self.tokens.append(token)
                self.column += len(value)
                
        self.tokens.append(Token('EOF', '', self.line, self.column, pos, pos))
        return self.tokens

def tokenize(source_code: str) -> List[Token]:
    """Convenience function to tokenize source code."""
    lexer = Lexer(source_code)
    return lexer.tokenize()
