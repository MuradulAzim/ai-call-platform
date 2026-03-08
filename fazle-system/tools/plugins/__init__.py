# ============================================================
# Fazle Plugin System — Dynamic plugin loader
# Plugins are isolated modules that extend Fazle's capabilities
# ============================================================
import importlib
import os
import json
import logging
from typing import Any, Callable

logger = logging.getLogger("fazle-plugins")


class Plugin:
    """Base class for all Fazle plugins."""

    name: str = "unnamed"
    description: str = ""
    version: str = "1.0.0"

    def get_input_schema(self) -> dict:
        """Return JSON schema for plugin input."""
        return {}

    async def execute(self, **kwargs) -> dict:
        """Execute the plugin logic. Must be overridden."""
        raise NotImplementedError


class PluginRegistry:
    """Manages loading and execution of plugins."""

    def __init__(self):
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin):
        """Register a plugin instance."""
        self._plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "description": p.description,
                "version": p.version,
                "input_schema": p.get_input_schema(),
            }
            for p in self._plugins.values()
        ]

    async def execute(self, name: str, **kwargs) -> dict:
        plugin = self._plugins.get(name)
        if not plugin:
            raise ValueError(f"Plugin not found: {name}")
        return await plugin.execute(**kwargs)

    def load_from_directory(self, directory: str):
        """Load all plugins from a directory."""
        if not os.path.isdir(directory):
            logger.warning(f"Plugin directory not found: {directory}")
            return

        for filename in os.listdir(directory):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, os.path.join(directory, filename)
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Look for a class that inherits from Plugin
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, Plugin)
                            and attr is not Plugin
                        ):
                            instance = attr()
                            self.register(instance)
                except Exception as e:
                    logger.error(f"Failed to load plugin {filename}: {e}")


# Global registry instance
registry = PluginRegistry()
