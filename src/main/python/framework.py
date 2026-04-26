from abc import ABC, abstractmethod
from typing import Any, Dict


class AgentObserver(ABC):
    """Abstract observer class for monitoring agent events."""
    @abstractmethod
    def update(self, event_type: str, data: Any): 
        pass


class ConsoleLogger(AgentObserver):
    """Concrete observer that prints agent activity to the console."""
    def update(self, event_type: str, data: Any):
        if event_type == "ACT":
            print(f"\n[AGENT] Invoking Tool: '{data['name']}'")
            print(f"        Arguments: {data['args']}")

        elif event_type == "OBSERVE":
            # We truncate long outputs to keep the console clean
            summary = str(data)[:150] + "..." if len(str(data)) > 150 else data
            print(f"[SYSTEM] Tool Output: {summary}")

        elif event_type == "FINAL":
            print(f"\n[AGENT] Final Answer: {data}\n")


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