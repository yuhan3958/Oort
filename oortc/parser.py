from pathlib import Path
from typing import List, Dict

from . import ast
from .lexer import Token, LexerError

class ParserError(Exception):
    pass

# A simple map for operator precedence for the expression parser.
PRECEDENCE: Dict[str, int] = {
    'EQUALS': 1,
    'EQUALS_EQUALS': 2, 'NOT_EQUALS': 2, 'LESS': 2, 'GREATER': 2, 'LESS_EQUALS': 2, 'GREATER_EQUALS': 2,
    'PLUS': 3, 'MINUS': 3,
    'ASTERISK': 4, 'DIVIDE': 4,
    'LPAREN': 5, # For call expressions
}

class Parser:
    def __init__(self, tokens: List[Token], file_path: Path, source_code: str):
        self.tokens = tokens
        self.file_path = file_path
        self.source_code = source_code
        self.current = 0

    def parse(self) -> ast.Module:
        module = ast.Module(path=self.file_path)
        while not self.is_at_end():
            if self.match('SEMICOLON'):
                continue
            module.statements.append(self.parse_statement())
        return module

    # =======================================
    # Statement Parsers
    # =======================================

    def parse_statement(self) -> ast.Statement:
        if self.match('KW_FROM'):
            return self.parse_import_statement()
        if self.match('KW_FN'):
            return self.parse_function_declaration()
        if self.match('KW_MACRO'):
            return self.parse_macro_declaration()
        if self.match('KW_ON'):
            return self.parse_on_block()
        if self.match('KW_IF'):
            return self.parse_if_statement()
        if self.match('KW_FOR'):
            return self.parse_for_statement()
        if self.match('KW_WHILE'):
            return self.parse_while_statement()
        
        # Check for assignment or a call statement
        if self.check('IDENT') and self.check_next('EQUALS'):
            return self.parse_assignment_statement()
        
        return self.parse_call_statement()

    def parse_import_statement(self) -> ast.ImportStatement:
        path_token = self.consume('STRING', "Expected a file path string after 'from'.")
        path_literal = ast.StringLiteral(value=path_token.value.strip('"'))
        self.consume('KW_IMPORT', "Expected 'import' keyword.")
        
        if self.match('ASTERISK'):
            return ast.ImportStatement(path=path_literal, is_star_import=True)
        
        items = []
        while True:
            name = self.consume('IDENT', "Expected an identifier to import.")
            ident = ast.Identifier(name=name.value)
            alias = None
            if self.match('KW_AS'):
                alias_token = self.consume('IDENT', "Expected an alias identifier after 'as'.")
                alias = ast.Identifier(name=alias_token.value)
            items.append(ast.ImportItem(name=ident, alias=alias))
            if not self.match('COMMA'):
                break
        return ast.ImportStatement(path=path_literal, items=items)

    def parse_param_list(self) -> List[ast.Identifier]:
        params = []
        self.consume('LPAREN', "Expected '(' after function/macro name.")
        if not self.check('RPAREN'):
            while True:
                param_token = self.consume('IDENT', "Expected parameter name.")
                params.append(ast.Identifier(name=param_token.value))
                if not self.match('COMMA'):
                    break
        self.consume('RPAREN', "Expected ')' after parameters.")
        return params

    def parse_function_declaration(self) -> ast.FunctionDeclaration:
        name_token = self.consume('IDENT', "Expected function name.")
        name = ast.Identifier(name=name_token.value)
        params = self.parse_param_list()
        body = self.parse_block()
        return ast.FunctionDeclaration(name=name, body=body, params=params)

    def parse_macro_declaration(self) -> ast.MacroDeclaration:
        name_token = self.consume('IDENT', "Expected macro name.")
        name = ast.Identifier(name=name_token.value)
        params = self.parse_param_list()
        body = self.parse_block()
        return ast.MacroDeclaration(name=name, body=body, params=params)

    def parse_on_block(self) -> ast.OnBlock:
        event_type = self.consume_one_of(['KW_LOAD', 'KW_TICK'], "Expected 'load' or 'tick'.").value
        body = self.parse_block()
        return ast.OnBlock(event_type=event_type, body=body)

    def parse_if_statement(self) -> ast.IfStatement:
        condition = self.parse_expression()
        if_body = self.parse_block()
        else_body = None
        if self.match('KW_ELSE'):
            else_body = self.parse_block()
        return ast.IfStatement(condition=condition, if_body=if_body, else_body=else_body)
    
    def parse_for_statement(self) -> ast.ForStatement:
        var_type = ast.Identifier(name=self.consume('IDENT', "Expected type in for loop.").value)
        var_name = ast.Identifier(name=self.consume('IDENT', "Expected variable name in for loop.").value)
        self.consume('KW_IN', "Expected 'in' keyword in for loop.")
        iterable = self.parse_expression()
        body = self.parse_block()
        return ast.ForStatement(variable_type=var_type, variable_name=var_name, iterable=iterable, body=body)
    
    def parse_while_statement(self) -> ast.WhileStatement:
        condition = self.parse_expression()
        body = self.parse_block()
        return ast.WhileStatement(condition=condition, body=body)

    def parse_assignment_statement(self) -> ast.AssignmentStatement:
        target = ast.Identifier(name=self.consume('IDENT', 'Expected variable name.').value)
        self.consume('EQUALS', "Expected '=' for assignment.")
        value = self.parse_expression()
        self.match('SEMICOLON')
        return ast.AssignmentStatement(target=target, value=value)

    def parse_call_statement(self) -> ast.CallStatement:
        expr = self.parse_expression()
        if not isinstance(expr, ast.CallExpression):
            raise self._error(self.peek(), "Invalid statement. Expected a function call.")
        self.match('SEMICOLON')
        return ast.CallStatement(expression=expr)

    def parse_block(self) -> ast.Block:
        self.consume('LBRACE', "Expected '{' to start a block.")
        statements = []
        while not self.check('RBRACE') and not self.is_at_end():
            if self.match('SEMICOLON'):
                continue
            statements.append(self.parse_statement())
        self.consume('RBRACE', "Expected '}' to end a block.")
        return ast.Block(statements=statements)

    # =======================================
    # Expression Parsers (Pratt Parser style)
    # =======================================

    def parse_expression(self, precedence=0) -> ast.Expression:
        left_expr = self.parse_prefix()

        while not self.is_at_end() and precedence < self.get_precedence(self.peek()):
            left_expr = self.parse_infix(left_expr)
            
        return left_expr

    def parse_prefix(self) -> ast.Expression:
        if self.match('IDENT'):
            return ast.Identifier(name=self.previous().value)
        if self.match('NUMBER'):
            return ast.NumberLiteral(value=int(self.previous().value))
        if self.match('STRING'):
            return ast.StringLiteral(value=self.previous().value.strip('"'))
        if self.match('SELECTOR'):
            return ast.StringLiteral(value=self.previous().value)
        
        if self.match('LPAREN'):
            expr = self.parse_expression()
            self.consume('RPAREN', "Expected ')' after expression.")
            return expr

        raise self._error(self.peek(), "Expected an expression.")

    def parse_infix(self, left: ast.Expression) -> ast.Expression:
        op_token = self.peek()
        precedence = self.get_precedence(op_token)
        
        if op_token.type == 'LPAREN':
            return self.parse_call_expression(left)

        # It's a binary operator
        self.advance() # Consume operator
        op_str = op_token.value
        right = self.parse_expression(precedence)
        return ast.BinaryExpr(left=left, op=op_str, right=right)

    def parse_call_expression(self, callee: ast.Expression) -> ast.CallExpression:
        if not isinstance(callee, ast.Identifier):
            raise self._error(self.previous(), "Expected a function name before '('.")
        
        self.consume('LPAREN', "Expected '(' to start a call.")
        args = []
        if not self.check('RPAREN'):
            while True:
                args.append(self.parse_expression())
                if not self.match('COMMA'):
                    break
        self.consume('RPAREN', "Expected ')' after arguments.")
        return ast.CallExpression(callee=callee, arguments=args)

    def get_precedence(self, token: Token) -> int:
        return PRECEDENCE.get(token.type, 0)

    # =======================================
    # Parser Utils (unchanged from before)
    # =======================================

    def match(self, *types: str) -> bool:
        if self.is_at_end(): return False
        if self.peek().type in types:
            self.advance()
            return True
        return False

    def consume(self, type: str, message: str) -> Token:
        if self.check(type): return self.advance()
        raise self._error(self.peek(), message)
    
    def consume_one_of(self, types: List[str], message: str) -> Token:
        for type in types:
            if self.check(type): return self.advance()
        raise self._error(self.peek(), message)

    def check(self, type: str) -> bool:
        if self.is_at_end(): return False
        return self.peek().type == type
    
    def check_next(self, type: str) -> bool:
        if self.is_at_end() or self.tokens[self.current + 1].type == 'EOF': return False
        return self.tokens[self.current + 1].type == type

    def advance(self) -> Token:
        if not self.is_at_end(): self.current += 1
        return self.previous()

    def is_at_end(self) -> bool:
        return self.peek().type == 'EOF'

    def peek(self) -> Token:
        return self.tokens[self.current]

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def _error(self, token: Token, message: str) -> ParserError:
        if token.type == 'EOF':
            return ParserError(f"Parser error at end of file in {self.file_path.name}: {message}")
        else:
            return ParserError(
                f"Parser error in {self.file_path.name} at line {token.line}, column {token.column} near '{token.value}': {message}"
            )

def parse_file(file_path: Path, source_code: str) -> ast.Module:
    from .lexer import tokenize
    tokens = tokenize(source_code)
    parser = Parser(tokens, file_path, source_code)
    return parser.parse()