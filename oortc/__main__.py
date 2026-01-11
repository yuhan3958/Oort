import argparse
import sys
from pathlib import Path

from .config import ProjectConfig, ConfigError
from .resolver import Resolver, ResolverError
from .macros import MacroExpander, MacroError
from .emitter import Emitter, EmitterError
from .parser import ParserError
from .symbols import SymbolTableBuilder, SymbolError


def main():
    """The main entrypoint for the Oort compiler CLI."""
    parser = argparse.ArgumentParser(description="Oort Compiler for Minecraft Datapacks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Build Command ---
    build_parser = subparsers.add_parser("build", help="Build a datapack from an Oort project.")
    build_parser.add_argument(
        "project_dir",
        type=str,
        help="The path to the Oort project directory (containing properties.json)."
    )
    build_parser.add_argument(
        "--out",
        type=str,
        help="Override the output directory specified in properties.json."
    )

    args = parser.parse_args()

    if args.command == "build":
        project_path = Path(args.project_dir)
        try:
            print(f"Building Oort project at: {project_path.resolve()}")

            # 1. Load Configuration
            print("Step 1/5: Loading configuration...")
            config = ProjectConfig.from_project_dir(project_path)
            
            if args.out:
                config.build.output = Path(args.out).resolve()
            
            print(f"  - Project: {config.package.name}")
            print(f"  - Namespace: {config.package.namespace}")
            print(f"  - Output Datapack: {config.build.output / config.build.datapack_name}")

            # 2. Resolve and Parse Modules
            print("Step 2/6: Resolving and parsing modules...")
            resolver = Resolver(config)
            modules = resolver.discover_and_parse_all()
            print(f"  - Discovered {len(modules)} modules.")
            
            # 3. Build initial Symbol Tables for unexpanded modules
            print("Step 3/6: Building initial symbol tables...")
            for path, module in modules.items():
                symbol_builder = SymbolTableBuilder()
                symbol_builder.build(module, path)
            print("  - Initial symbol tables built.")

            # 4. Expand Macros
            print("Step 4/6: Expanding macros...")
            expander = MacroExpander(modules) # Expander needs modules with initial symbols
            expanded_modules = {path: expander.expand(mod) for path, mod in modules.items()}
            print(f"  - Macro expansion complete.")

            # 5. Build final Symbol Tables for expanded modules
            print("Step 5/6: Building final symbol tables for expanded modules...")
            for path, module in expanded_modules.items():
                symbol_builder = SymbolTableBuilder()
                symbol_builder.build(module, path) # Rebuild symbols after expansion
            print("  - Final symbol tables built.")

            # 6. Emit Datapack
            print("Step 6/6: Emitting datapack files...")
            emitter = Emitter(config, expanded_modules) # Pass expanded modules with scopes
            emitter.emit_all()
            
            print("\nBuild successful!")
            print(f"Datapack generated at: {emitter.datapack_root.resolve()}")

        except (ConfigError, ResolverError, EmitterError, ParserError, SymbolError, MacroError, FileNotFoundError) as e:
            print(f"\nBuild failed: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
            raise e
            # sys.exit(1)

if __name__ == "__main__":
    main()
