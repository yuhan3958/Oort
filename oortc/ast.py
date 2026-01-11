from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

# =======================================
# Base Nodes and Visitor
# =======================================

@dataclass
class Node:
    """Base class for all AST nodes."""
    scope: Optional['Scope'] = field(init=False, default=None, repr=False)

def iter_fields(node: 'Node'):
    """Yields a tuple of (field_name, field_value) for each field in a node."""
    for field_name in node.__dataclass_fields__:
        yield (field_name, getattr(node, field_name))

class NodeVisitor:
    """A simple visitor for traversing the AST without modification."""
    def visit(self, node: Node):
        if not node: return
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        visitor(node)

    def generic_visit(self, node: Node):
        for field_name, value in iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, Node):
                        self.visit(item)
            elif isinstance(value, Node):
                self.visit(value)

class NodeTransformer:
    """A visitor that traverses and can modify the AST."""
    def visit(self, node: Node):
        if not node: return None
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: Node):
        for field_name, old_value in iter_fields(node):
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, Node):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif isinstance(value, list):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                setattr(node, field_name, new_values)
            elif isinstance(old_value, Node):
                new_node = self.visit(old_value)
                setattr(node, field_name, new_node)
        return node

@dataclass
class Statement(Node):
    """Base class for all statement nodes."""
    pass

@dataclass
class Expression(Node):
    """Base class for all expression nodes."""
    pass

# =======================================
# Expressions
# =======================================

@dataclass
class Identifier(Expression):
    """e.g., my_variable, my_function"""
    name: str

@dataclass
class StringLiteral(Expression):
    """e.g., "a string" """
    value: str

@dataclass
class NumberLiteral(Expression):
    """e.g., 123, -45"""
    value: int

@dataclass
class Variable(Expression):
    """A reference to a variable, e.g. `my_var`"""
    name: str
    
@dataclass
class BinaryExpr(Expression):
    """An expression with a left and right side and an operator."""
    left: Expression
    op: str  # e.g., '>', '==', '+', etc.
    right: Expression

@dataclass
class CallExpression(Expression):
    """e.g., foo(arg1, "hello")"""
    callee: Identifier
    arguments: List[Expression] = field(default_factory=list)

# =======================================
# Statements
# =======================================

@dataclass
class ImportItem(Node):
    """An item in an import list. e.g., 'name' or 'name as alias'"""
    name: Identifier
    alias: Optional[Identifier] = None

@dataclass
class ImportStatement(Statement):
    """from "path/to/file.oort" import item1, item2 as alias2, ..."""
    path: StringLiteral
    is_star_import: bool = field(default=False)
    items: List[ImportItem] = field(default_factory=list)

@dataclass
class Block(Node):
    """A block of statements enclosed in curly braces. e.g., { stmt1; stmt2; }"""
    statements: List[Statement] = field(default_factory=list)

@dataclass
class FunctionDeclaration(Statement):
    """fn my_func(arg1, arg2) { ... }"""
    name: Identifier
    body: Block
    params: List[Identifier] = field(default_factory=list)

@dataclass
class MacroDeclaration(Statement):
    """macro my_macro(arg1) { ... }"""
    name: Identifier
    body: Block
    params: List[Identifier] = field(default_factory=list)

@dataclass
class OnBlock(Statement):
    """on load { ... } or on tick { ... }"""
    event_type: str  # "load" or "tick"
    body: Block

@dataclass
class IfStatement(Statement):
    """if condition { ... } else { ... }"""
    condition: Expression
    if_body: Block
    else_body: Optional[Block] = None

@dataclass
class ForStatement(Statement):
    """for entity e in @a { ... }"""
    variable_type: Identifier # e.g. 'entity'
    variable_name: Identifier
    iterable: Expression # e.g. '@a'
    body: Block

@dataclass
class WhileStatement(Statement):
    """while hp > 0 { ... }"""
    condition: Expression
    body: Block

@dataclass
class AssignmentStatement(Statement):
    """var x = 10"""
    target: Identifier
    value: Expression

@dataclass
class CallStatement(Statement):
    """A statement that is just a function call. e.g., foo(); """
    expression: CallExpression

# =======================================
# Root of the AST
# =======================================

@dataclass
class Module(Node):
    """The root of the AST for a single .oort file."""
    path: Path
    statements: List[Statement] = field(default_factory=list)
