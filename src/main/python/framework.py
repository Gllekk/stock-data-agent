from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseTool(ABC):
    """Abstract parent class for tools."""
    @property
    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    def get_declaration(self) -> Dict[str, Any]: pass

    def execute(self, registry_context: Any, **kwargs) -> str:
        try:
            return self._run_logic(registry_context, **kwargs)
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    @abstractmethod
    def _run_logic(self, context: Any, **kwargs) -> str:
        pass