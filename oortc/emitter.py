import json
import shutil
from pathlib import Path
from typing import Dict, List, Set, Optional

from .config import ProjectConfig
from . import ast
from .symbols import SymbolType, Scope

class EmitterError(Exception):
    pass

VARS_OBJECTIVE = "oort_vars"

# A set of recognized built-in commands. A real compiler would have a much more
# sophisticated system with argument types and formatting rules.
BUILTIN_COMMANDS: Set[str] = {
    "say", "give", "kill", "scoreboard", "execute", "schedule", "function", "tag"
}

class Emitter(ast.NodeVisitor):
    def __init__(self, config: ProjectConfig, modules: Dict[Path, ast.Module]):
        self.config = config
        if self.config.build.debug_message:
            print("DEBUG: Initializing Emitter...")
        self.modules = modules
        self.datapack_root: Path = self.config.build.output / self.config.build.datapack_name
        self.functions_dir: Path = self.datapack_root / "data" / self.config.package.namespace / "functions"
        
        self.current_module_path: Path = None
        self.output_lines: List[str] = []
        self.function_count = 0

    def emit_all(self):
        if self.config.build.debug_message:
            print("DEBUG: Emitter.emit_all() called.")
        self._setup_directories()
        self._emit_pack_mcmeta()
        self._emit_tags()

        for path, module in self.modules.items():
            if self.config.build.debug_message:
                print(f"DEBUG: Emitter processing module: {path}")
            self.current_module_path = path
            self.visit(module)
            
    def _setup_directories(self):
        if self.config.build.clean and self.datapack_root.exists():
            shutil.rmtree(self.datapack_root)
        self.functions_dir.mkdir(parents=True, exist_ok=True)

    def _emit_pack_mcmeta(self):
        mcmeta_path = self.datapack_root / "pack.mcmeta"
        content = {"pack": {"pack_format": self.config.minecraft.pack_format, "description": self.config.package.description or f"A datapack generated for {self.config.package.name}"}}
        with open(mcmeta_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=4)

    def _emit_tags(self):
        tags_dir = self.datapack_root / "data/minecraft/tags/functions"
        tags_dir.mkdir(parents=True, exist_ok=True)
        ns = self.config.package.namespace
        
        load_rel_path = self.config.entrypoints.load.relative_to(self.config.project_dir)
        tick_rel_path = self.config.entrypoints.tick.relative_to(self.config.project_dir)
        load_func_name = f"{ns}:{self._oort_path_to_function_base(load_rel_path)}/on_load"
        tick_func_name = f"{ns}:{self._oort_path_to_function_base(tick_rel_path)}/on_tick"

        with open(tags_dir / "load.json", 'w', encoding='utf-8') as f:
            json.dump({"values": [load_func_name]}, f, indent=4)
        with open(tags_dir / "tick.json", 'w', encoding='utf-8') as f:
            json.dump({"values": [tick_func_name]}, f, indent=4)

    def _oort_path_to_function_base(self, oort_path: Path) -> str:
        return str(oort_path.with_suffix('')).replace('\\', '/')

    def _write_mcfunction(self, function_path: str, lines: List[str]):
        full_path = self.functions_dir / f"{function_path}.mcfunction"
        if self.config.build.debug_message:
            print(f"DEBUG: Emitter is writing to {full_path.resolve()}")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
            
    def _generate_function(self, base_name: str, node_body: ast.Block) -> str:
        """Generates a function for a block of code and returns its namespaced name."""
        self.function_count += 1
        func_path = f"{base_name}_{self.function_count}"
        
        original_lines = self.output_lines
        self.output_lines = []
        self.visit(node_body)
        self._write_mcfunction(func_path, self.output_lines)
        self.output_lines = original_lines
        
        return f"{self.config.package.namespace}:{func_path}"

    def _format_expr(self, expr: ast.Expression) -> str:
        if isinstance(expr, ast.StringLiteral):
            return expr.value # mcfunctions don't use quotes for string args
        elif isinstance(expr, ast.NumberLiteral):
            return str(expr.value)
        elif isinstance(expr, (ast.Identifier, ast.Variable)):
            return expr.name
        elif isinstance(expr, ast.BinaryExpr):
            return f"{self._format_expr(expr.left)} {expr.op} {self._format_expr(expr.right)}"
        return ""

    def generic_visit(self, node: ast.Node):
        for field_name, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Node):
                        self.visit(item)
            elif isinstance(value, ast.Node):
                self.visit(value)
        return node

    # =======================================
    # Visitor Methods (Code Generation)
    # =======================================

    def visit_FunctionDeclaration(self, node: ast.FunctionDeclaration):
        if self.config.build.debug_message:
            print(f"DEBUG: Visiting FunctionDeclaration: {node.name.name}")
        rel_path = self.current_module_path.relative_to(self.config.project_dir)
        function_base = self._oort_path_to_function_base(rel_path)
        function_path = f"{function_base}/{node.name.name}"
        
        self.output_lines.append(f"# Function: {node.name.name}")
        self.visit(node.body)
        self._write_mcfunction(function_path, self.output_lines)
        self.output_lines = []

    def visit_OnBlock(self, node: ast.OnBlock):
        if self.config.build.debug_message:
            print(f"DEBUG: Visiting OnBlock: {node.event_type}")
        rel_path = self.current_module_path.relative_to(self.config.project_dir)
        function_base = self._oort_path_to_function_base(rel_path)
        function_path = f"{function_base}/on_{node.event_type}"

        self.output_lines.append(f"# Event: on {node.event_type}")

        if node.event_type == 'load':
            self.output_lines.append(f"scoreboard objectives add {VARS_OBJECTIVE} dummy")

        self.visit(node.body)
        self._write_mcfunction(function_path, self.output_lines)
        self.output_lines = []

    def visit_CallStatement(self, node: ast.CallStatement):
        callee = node.expression.callee.name
        
        if callee in BUILTIN_COMMANDS:
            args = " ".join(self._format_expr(arg) for arg in node.expression.arguments)
            self.output_lines.append(f"{callee} {args}")
        else:
            # Find user-defined function
            func_path = self._find_function_path(callee, node.scope)
            if func_path:
                self.output_lines.append(f"function {func_path}")
            else:
                self.output_lines.append(f"# ERROR: Unresolved function call to '{callee}'")

    def visit_IfStatement(self, node: ast.IfStatement):
        # Generate a separate function for the 'if' body
        rel_path = self.current_module_path.relative_to(self.config.project_dir)
        if_base_name = f"{self._oort_path_to_function_base(rel_path)}/if_body"
        body_func_name = self._generate_function(if_base_name, node.if_body)

        # Generate the 'execute if' command
        condition_cmd = self._format_condition(node.condition, body_func_name)
        self.output_lines.append(condition_cmd)

        # TODO: else and else-if are not handled yet.

    def visit_ForStatement(self, node: ast.ForStatement):
        iterable = self._format_expr(node.iterable)
        rel_path = self.current_module_path.relative_to(self.config.project_dir)
        loop_base_name = f"{self._oort_path_to_function_base(rel_path)}/for_loop_{node.variable_name.name}"
        body_func_name = self._generate_function(loop_base_name, node.body)
        self.output_lines.append(f"execute as {iterable} at @s run function {body_func_name}")

    def visit_WhileStatement(self, node: ast.WhileStatement):
        rel_path = self.current_module_path.relative_to(self.config.project_dir)
        self.function_count += 1
        while_base_name = f"{self._oort_path_to_function_base(rel_path)}/while_{self.function_count}"
        
        check_func_path = f"{while_base_name}_check"
        body_func_path = f"{while_base_name}_body"
        
        ns = self.config.package.namespace
        namespaced_check_func = f"{ns}:{check_func_path}"
        namespaced_body_func = f"{ns}:{body_func_path}"

        # 1. Generate the body function's content
        original_lines = self.output_lines
        self.output_lines = []
        self.visit(node.body)
        # After the body, schedule the check function for the next tick
        self.output_lines.append(f"schedule function {namespaced_check_func} 1t")
        self._write_mcfunction(body_func_path, self.output_lines)
        self.output_lines = original_lines
        
        # 2. Generate the check function's content
        check_lines = [
            f"# While loop check for: {self._format_expr(node.condition)}",
            self._format_condition(node.condition, namespaced_body_func),
        ]
        self._write_mcfunction(check_func_path, check_lines)
        
        # 3. The initial call site just starts the check function once
        self.output_lines.append(f"function {namespaced_check_func}")


    def visit_AssignmentStatement(self, node: ast.AssignmentStatement):
        var_name = node.target.name
        
        # Case 1: Simple assignment from a literal
        if isinstance(node.value, ast.NumberLiteral):
            self.output_lines.append(f"scoreboard players set {var_name} {VARS_OBJECTIVE} {node.value.value}")
        
        # Case 2: Assignment from another variable
        elif isinstance(node.value, (ast.Identifier, ast.Variable)):
             self.output_lines.append(f"scoreboard players operation {var_name} {VARS_OBJECTIVE} = {node.value.name} {VARS_OBJECTIVE}")

        # Case 3: Assignment from an expression
        elif isinstance(node.value, ast.BinaryExpr):
            expr = node.value
            left_var = self._format_expr(expr.left)
            right_var = self._format_expr(expr.right)
            op = expr.op
            
            # First, set the variable to the left side
            self.output_lines.append(f"scoreboard players operation {var_name} {VARS_OBJECTIVE} = {left_var} {VARS_OBJECTIVE}")
            
            # Then, perform the operation with the right side
            op_map = { '+': 'add', '-': 'remove' } # extend this
            if op in op_map and isinstance(expr.right, ast.NumberLiteral):
                self.output_lines.append(f"scoreboard players {op_map[op]} {var_name} {VARS_OBJECTIVE} {right_var}")
            else:
                 # Generic operation for var-var operations
                 op_map_op = { '+': '+=', '-': '-=', '*': '*=', '/': '/=', '%': '%=' }
                 if op in op_map_op:
                    self.output_lines.append(f"scoreboard players operation {var_name} {VARS_OBJECTIVE} {op_map_op[op]} {right_var} {VARS_OBJECTIVE}")
                 else:
                    self.output_lines.append(f"# ERROR: Unsupported binary operator '{op}' in assignment")

        else:
            self.output_lines.append(f"# ERROR: Unsupported assignment for value of type {type(node.value)}")

    def _format_condition(self, condition: ast.BinaryExpr, func_to_run: str) -> str:
        """Formats a BinaryExpr into an `execute if score` command."""
        if not isinstance(condition, ast.BinaryExpr):
            return f"# ERROR: Unsupported condition type {type(condition)}"
            
        left = self._format_expr(condition.left)
        op = condition.op
        right = self._format_expr(condition.right)

        # We need to handle both `var op literal` and `var op var`
        if isinstance(condition.right, ast.NumberLiteral):
            op_map = {
                '<': '..',
                '<=': '..',
                '>': '..',
                '>=': '..',
                '==': 'matches',
            }
            # This is a simplification. A full implementation would be more robust.
            if op == '==':
                return f"execute if score {left} {VARS_OBJECTIVE} matches {right} run function {func_to_run}"
            elif op == '<':
                return f"execute if score {left} {VARS_OBJECTIVE} matches ..{int(right)-1} run function {func_to_run}"
            elif op == '<=':
                return f"execute if score {left} {VARS_OBJECTIVE} matches ..{right} run function {func_to_run}"
            elif op == '>':
                return f"execute if score {left} {VARS_OBJECTIVE} matches {int(right)+1}.. run function {func_to_run}"
            elif op == '>=':
                return f"execute if score {left} {VARS_OBJECTIVE} matches {right}.. run function {func_to_run}"
            else:
                return f"# ERROR: Unsupported operator '{op}' for literal comparison"
        else:
            # Comparison between two variables
            return f"execute if score {left} {VARS_OBJECTIVE} {op} {right} {VARS_OBJECTIVE} run function {func_to_run}"

    def _find_function_path(self, name: str, scope: Scope) -> Optional[str]:
        """Finds a user-defined function using the symbol table."""
        if not scope:
            return None
        
        symbol = scope.find(name, recursive=True)
        if symbol and symbol.symbol_type == SymbolType.FUNCTION:
            rel_path = symbol.module_path.relative_to(self.config.project_dir)
            base = self._oort_path_to_function_base(rel_path)
            return f"{self.config.package.namespace}:{base}/{name}"
        return None


    def visit_Block(self, node: ast.Block):
        self.generic_visit(node)
        
    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        
    # We don't want to visit things we don't emit
    def visit_ImportStatement(self, node: ast.ImportStatement): pass
    def visit_MacroDeclaration(self, node: ast.MacroDeclaration): pass