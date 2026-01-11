import copy
from typing import Dict, List, Optional

from . import ast
from .symbols import Scope, Symbol, SymbolType
from .ast import NodeTransformer

class MacroError(Exception):
    pass

class SubstitutionVisitor(NodeTransformer):
    """
    A visitor that substitutes parameter identifiers within a macro's
    AST body with the argument expressions from a call.
    """
    def __init__(self, arg_map: Dict[str, ast.Expression]):
        self.arg_map = arg_map

    def visit_Identifier(self, node: ast.Identifier) -> ast.Expression:
        # If this identifier's name is a macro parameter, return the argument expression.
        return self.arg_map.get(node.name, node)

class MacroExpander(NodeTransformer):
    """
    Walks an AST and expands all macro calls.
    Returns a new, transformed AST.
    """
    def __init__(self, modules: Dict[ast.Path, ast.Module]):
        self.modules = modules

    def expand(self, module: ast.Module) -> ast.Module:
        """
        Expands all macros in a given module. It's an iterative process
        in case macros call other macros.
        """
        return self.visit(module)

    def visit_CallStatement(self, node: ast.CallStatement) -> Optional[List[ast.Statement]]:
        callee_name = node.expression.callee.name
        
        symbol = self._find_symbol(callee_name, node.scope)
        
        if not symbol or symbol.symbol_type != SymbolType.MACRO:
            return node

        macro_decl = symbol.defined_at
        if not isinstance(macro_decl, ast.MacroDeclaration):
            raise MacroError("Symbol table points to a non-macro node for a macro symbol.")

        if len(node.expression.arguments) != len(macro_decl.params):
            raise MacroError(
                f"Macro '{callee_name}' expects {len(macro_decl.params)} arguments, "
                f"but got {len(node.expression.arguments)}."
            )
        
        arg_map = {
            param.name: arg for param, arg in zip(macro_decl.params, node.expression.arguments)
        }
        
        expanded_body = copy.deepcopy(macro_decl.body)
        
        substituter = SubstitutionVisitor(arg_map)
        substituter.visit(expanded_body)
        
        return expanded_body.statements

    def _find_symbol(self, name: str, scope: Scope) -> Optional[Symbol]:
        """Finds a symbol by walking up the scope chain, or by resolving imports."""
        if not scope:
            return None
        
        symbol = scope.find(name, recursive=True)

        if symbol:
            if symbol.symbol_type == SymbolType.IMPORT:
                for module_path, module_node in self.modules.items():
                    for stmt in module_node.statements:
                        if isinstance(stmt, ast.MacroDeclaration) and stmt.name.name == name:
                            return Symbol(name=name, symbol_type=SymbolType.MACRO, defined_at=stmt, module_path=module_path)
            return symbol
            
        return None