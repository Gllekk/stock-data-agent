from abc import ABC, abstractmethod
from typing import Any, Dict


# ANSI Escape Codes for CLI Color Formatting
class Colors:
    USER = '\033[96m'     # Cyan
    AGENT = '\033[95m'    # Magenta
    SYSTEM = '\033[93m'   # Yellow
    ERROR = '\033[91m'    # Red
    RESET = '\033[0m'     # Reset


# Abstract observer class for monitoring agent events
class AgentObserver(ABC):
    @abstractmethod
    def update(self, event_type: str, data: Any): 
        pass


# Concrete observer that prints agent activity to the console
class ConsoleLogger(AgentObserver):
    def _truncate(self, text: str, max_length: int = 100) -> str:
        clean_text = str(text).replace('\n', ' ').replace('\r', '')
        return f"{clean_text[:max_length]}..." if len(clean_text) > max_length else clean_text

    def update(self, event_type: str, data: Any):
        if event_type == "ACT":
            log = self._truncate(f"Invoking: {data['name']} | Args: {data['args']}")
            print(f"{Colors.AGENT}[AGENT] {Colors.RESET}{log}")

        elif event_type == "OBSERVE":
            log = self._truncate(f"Output: {data}")
            print(f"{Colors.SYSTEM}[SYSTEM] {Colors.RESET}{log}")
            
        elif event_type == "FINAL":
            # We do not truncate the final answer so the user can read the actual report
            print(f"\n{Colors.AGENT}[AGENT] {Colors.RESET}Final Answer:\n{data}\n")


# Abstract parent class for tools
class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    def get_declaration(self) -> Dict[str, Any]: pass

    def execute(self, registry_context: Any, **kwargs) -> str:
        try:
            return self._run_logic(registry_context, **kwargs)
        except Exception as e:
            return f"Execution Error in {self.name}: {str(e)}"

    @abstractmethod
    def _run_logic(self, context: Any, **kwargs) -> str:
        pass