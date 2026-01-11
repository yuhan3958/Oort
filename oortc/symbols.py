from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum, auto
from pathlib import Path

from . import ast
from .ast import NodeVisitor

class SymbolError(Exception):
    """Custom exception for symbol-related errors."""
    pass

class SymbolType(Enum):
    VARIABLE = auto()
    FUNCTION = auto()
    MACRO = auto()
    IMPORT = auto()
    BUILTIN = auto()

@dataclass
class Symbol:
    """Represents a named entity in a scope."""
    name: str
    symbol_type: SymbolType
    defined_at: ast.Node # The AST node where this symbol was defined
    module_path: Path # The path to the .oort file where this symbol is defined

@dataclass
class Scope:
    """A container for symbols that represents a lexical scope."""
    parent: Optional[Scope] = None
    children: List[Scope] = field(default_factory=list)
    symbols: Dict[str, Symbol] = field(default_factory=dict)

    def add(self, symbol: Symbol):
        if symbol.name in self.symbols:
            raise SymbolError(f"Name '{symbol.name}' is already defined in this scope.")
        self.symbols[symbol.name] = symbol

    def find(self, name: str, *, recursive: bool) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if recursive and self.parent:
            return self.parent.find(name, recursive=True)
        return None

class SymbolTableBuilder(NodeVisitor):
    def __init__(self):
        self.root_scope: Optional[Scope] = None
        self.current_scope: Optional[Scope] = None
        self.current_module_path: Optional[Path] = None

    def build(self, module_node: ast.Module, module_path: Path) -> Scope:
        self.current_module_path = module_path
        self.visit(module_node)
        return self.root_scope

    def enter_scope(self):
        new_scope = Scope(parent=self.current_scope)
        if self.current_scope:
            self.current_scope.children.append(new_scope)
        if not self.root_scope:
            self.root_scope = new_scope
        self.current_scope = new_scope

    def exit_scope(self):
        if self.current_scope and self.current_scope.parent:
            self.current_scope = self.current_scope.parent

    def visit_Module(self, node: ast.Module):
        self.enter_scope()
        node.scope = self.current_scope
        self.generic_visit(node)
        self.exit_scope()

    def visit_FunctionDeclaration(self, node: ast.FunctionDeclaration):
        symbol = Symbol(name=node.name.name, symbol_type=SymbolType.FUNCTION, defined_at=node, module_path=self.current_module_path)
        self.current_scope.add(symbol)
        
        self.enter_scope()
        node.body.scope = self.current_scope
        for param in node.params:
            param_symbol = Symbol(name=param.name, symbol_type=SymbolType.VARIABLE, defined_at=param, module_path=self.current_module_path)
            self.current_scope.add(param_symbol)
        self.visit(node.body)
        self.exit_scope()

    def visit_MacroDeclaration(self, node: ast.MacroDeclaration):
        symbol = Symbol(name=node.name.name, symbol_type=SymbolType.MACRO, defined_at=node, module_path=self.current_module_path)
        self.current_scope.add(symbol)
        # We don't visit the body until expansion time.

    def visit_OnBlock(self, node: ast.OnBlock):
        self.enter_scope()
        node.body.scope = self.current_scope
        self.visit(node.body)
        self.exit_scope()

    def visit_IfStatement(self, node: ast.IfStatement):
        self.visit(node.condition)
        self.enter_scope()
        node.if_body.scope = self.current_scope
        self.visit(node.if_body)
        self.exit_scope()
        if node.else_body:
            self.enter_scope()
            node.else_body.scope = self.current_scope
            self.visit(node.else_body)
            self.exit_scope()
            
    def visit_ForStatement(self, node: ast.ForStatement):
        self.visit(node.iterable)
        self.enter_scope()
        node.body.scope = self.current_scope
        var_symbol = Symbol(name=node.variable_name.name, symbol_type=SymbolType.VARIABLE, defined_at=node, module_path=self.current_module_path)
        self.current_scope.add(var_symbol)
        self.visit(node.body)
        self.exit_scope()

    def visit_WhileStatement(self, node: ast.WhileStatement):
        self.visit(node.condition)
        self.enter_scope()
        node.body.scope = self.current_scope
        self.visit(node.body)
        self.exit_scope()
        
    def visit_Block(self, node: ast.Block):
        # All statements within the block should have this same scope.
        for stmt in node.statements:
            stmt.scope = self.current_scope # Propagate scope to statements
            self.visit(stmt)

    def visit_ImportStatement(self, node: ast.ImportStatement):
        if node.is_star_import:
            # Star imports are handled by the resolver in a later pass
            pass
        else:
            for item in node.items:
                symbol_name = item.alias.name if item.alias else item.name.name
                symbol = Symbol(name=symbol_name, symbol_type=SymbolType.IMPORT, defined_at=item, module_path=self.current_module_path)
                self.current_scope.add(symbol)
    
    def visit_AssignmentStatement(self, node: ast.AssignmentStatement):
        self.visit(node.value)
        if not self.current_scope.find(node.target.name, recursive=False):
            symbol = Symbol(name=node.target.name, symbol_type=SymbolType.VARIABLE, defined_at=node, module_path=self.current_module_path)
            self.current_scope.add(symbol)
