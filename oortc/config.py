import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

# As per the specification, a mapping from Minecraft version to pack format.
# This can be extended as new versions are released.
VERSION_TO_PACK_FORMAT = {
    "1.21": 48,
    "1.20.6": 41,
    "1.20.5": 41,
    "1.20.4": 26,
    "1.20.3": 26,
    "1.20.2": 18,
    "1.20.1": 15,
    "1.20": 15,
    "1.19.4": 13,
    "1.19.3": 12,
    "1.19.2": 9,
    "1.19.1": 9,
    "1.19": 9,
    "1.18.2": 8,
    "1.18.1": 8,
    "1.18": 8,
}


class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass


@dataclass
class PackageConfig:
    name: str
    namespace: str
    description: Optional[str] = None


@dataclass
class MinecraftConfig:
    version: str
    pack_format: int


@dataclass
class EntrypointsConfig:
    load: Path
    tick: Path


@dataclass
class BuildConfig:
    output: Path
    datapack_name: str
    clean: bool = True


@dataclass
class ProjectConfig:
    project_dir: Path
    package: PackageConfig
    minecraft: MinecraftConfig
    entrypoints: EntrypointsConfig
    build: BuildConfig

    @classmethod
    def from_project_dir(cls, project_dir: Path) -> 'ProjectConfig':
        abs_project_dir = project_dir.resolve()
        properties_path = abs_project_dir / "properties.json"
        if not properties_path.is_file():
            raise ConfigError(f"'properties.json' not found in project directory: {abs_project_dir}")

        try:
            with open(properties_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Error decoding 'properties.json': {e}")
        except IOError as e:
            raise ConfigError(f"Error reading 'properties.json': {e}")

        # --- Package ---
        package_data = data.get("package")
        if not isinstance(package_data, dict):
            raise ConfigError("'package' section is missing or not an object in properties.json")
        
        pkg_name = package_data.get("name")
        pkg_namespace = package_data.get("namespace")
        if not pkg_name or not pkg_namespace:
            raise ConfigError("'package.name' and 'package.namespace' are required")

        package = PackageConfig(
            name=pkg_name,
            namespace=pkg_namespace,
            description=package_data.get("description")
        )

        # --- Minecraft ---
        minecraft_data = data.get("minecraft")
        if not isinstance(minecraft_data, dict):
            raise ConfigError("'minecraft' section is missing or not an object in properties.json")
        
        mc_version = minecraft_data.get("version")
        if not mc_version:
            raise ConfigError("'minecraft.version' is required")

        pack_format = minecraft_data.get("pack_format")
        if pack_format is None:
            if mc_version not in VERSION_TO_PACK_FORMAT:
                raise ConfigError(
                    f"Unknown Minecraft version '{mc_version}'. "
                    f"Please specify 'minecraft.pack_format' directly."
                )
            pack_format = VERSION_TO_PACK_FORMAT[mc_version]
        
        minecraft = MinecraftConfig(version=mc_version, pack_format=int(pack_format))

        # --- Entrypoints ---
        entrypoints_data = data.get("entrypoints")
        if not isinstance(entrypoints_data, dict):
            raise ConfigError("'entrypoints' section is missing or not an object in properties.json")
        
        load_path_str = entrypoints_data.get("load")
        tick_path_str = entrypoints_data.get("tick")
        if not load_path_str or not tick_path_str:
            raise ConfigError("'entrypoints.load' and 'entrypoints.tick' are required")

        entrypoints = EntrypointsConfig(
            load=abs_project_dir / Path(load_path_str),
            tick=abs_project_dir / Path(tick_path_str)
        )

        # --- Build ---
        build_data = data.get("build", {})
        if not isinstance(build_data, dict):
            raise ConfigError("'build' section must be an object in properties.json")
            
        datapack_name = build_data.get("datapack_name", f"{package.name}-datapack")
        output_dir = build_data.get("output", "build")
        
        build = BuildConfig(
            output=abs_project_dir / Path(output_dir),
            datapack_name=datapack_name,
            clean=bool(build_data.get("clean", True))
        )

        return cls(
            project_dir=abs_project_dir,
            package=package,
            minecraft=minecraft,
            entrypoints=entrypoints,
            build=build
        )

