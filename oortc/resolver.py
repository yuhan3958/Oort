from pathlib import Path
from typing import Set, Dict, List

from .config import ProjectConfig, ConfigError
from .parser import parse_file, ParserError
from .ast import Module, ImportStatement
from . import ast
from .symbols import SymbolTableBuilder, SymbolError

class ResolverError(Exception):
    pass

class ImportFinder(ast.NodeVisitor):
    """A NodeVisitor that collects all ImportStatement nodes in an AST."""
    def __init__(self):
        self.imports: List[ast.ImportStatement] = []

    def visit_ImportStatement(self, node: ast.ImportStatement):
        self.imports.append(node)
        # Do not visit children of import statements
    
    def find(self, node: ast.Module) -> List[ast.ImportStatement]:
        self.visit(node)
        return self.imports

class Resolver:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.project_dir = config.project_dir
        self.processed_files: Set[Path] = set()
        self.modules: Dict[Path, ast.Module] = {}

    def discover_and_parse_all(self) -> Dict[Path, ast.Module]:
        """
        Starting from the entrypoints, discovers all imported .oort files,
        parses them, and builds their symbol tables.
        """
        files_to_process: List[Path] = [
            self.config.entrypoints.load.resolve(),
            self.config.entrypoints.tick.resolve()
        ]
        
        while files_to_process:
            file_path = files_to_process.pop(0)

            if file_path in self.processed_files:
                continue

            if not file_path.is_file():
                raise ResolverError(f"Imported file not found: {file_path}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                
                module_ast = parse_file(file_path, source_code)
                
                self.modules[file_path] = module_ast
                self.processed_files.add(file_path)

                new_files = self._discover_imports(module_ast, file_path.parent)
                files_to_process.extend(new_files)

            except (IOError, ParserError, SymbolError) as e:
                raise ResolverError(f"Error processing file {file_path.name}: {e}")

        self._validate_entrypoints()
        return self.modules

    def _discover_imports(self, module: ast.Module, base_dir: Path) -> List[Path]:
        """Finds all import statements in a module and returns a list of new file paths to parse."""
        finder = ImportFinder()
        import_nodes = finder.find(module)
        
        new_files = []
        for import_stmt in import_nodes:
            imported_path = (base_dir / import_stmt.path.value).resolve()
            if imported_path not in self.processed_files:
                new_files.append(imported_path)
        return new_files
        
    def _validate_entrypoints(self):
        """Checks if the required on load/tick blocks exist in the entrypoint files."""
        load_path = self.config.entrypoints.load.resolve()
        tick_path = self.config.entrypoints.tick.resolve()

        if load_path not in self.modules:
             raise ResolverError(f"Entrypoint file {self.config.entrypoints.load} was not resolved.")
        if tick_path not in self.modules:
            raise ResolverError(f"Entrypoint file {self.config.entrypoints.tick} was not resolved.")

        load_module = self.modules[load_path]
        tick_module = self.modules[tick_path]

        has_on_load = any(isinstance(stmt, ast.OnBlock) and stmt.event_type == 'load' for stmt in load_module.statements)
        if not has_on_load:
            raise ResolverError(f"Entrypoint file '{self.config.entrypoints.load.name}' must contain an 'on load {{ ... }}' block.")

        has_on_tick = any(isinstance(stmt, ast.OnBlock) and stmt.event_type == 'tick' for stmt in tick_module.statements)
        if not has_on_tick:
            raise ResolverError(f"Entrypoint file '{self.config.entrypoints.tick.name}' must contain an 'on tick {{ ... }}' block.")

