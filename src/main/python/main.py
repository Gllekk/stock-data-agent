from agent import StockAgent
from framework import ConsoleLogger, Colors
import os
import sys


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"{Colors.ERROR}Error: GEMINI_API_KEY environment variable not set.{Colors.RESET}")
        sys.exit(1)

    try:
        agent = StockAgent(api_key)
        agent.observers.append(ConsoleLogger())
    except Exception as e:
        print(f"{Colors.ERROR}Failed to initialize agent: {e}{Colors.RESET}")
        sys.exit(1)
    
    print(f"{Colors.SYSTEM}--- Stock Analysis System Initialized ---{Colors.RESET}")
    print("Commands: 'exit' or 'quit' to quit")
    print("          'clear' to reset history\n")

    while True:
        try:
            # Input Handling
            query = input(f"{Colors.USER}[USER] Ask about a stock:{Colors.RESET} ").strip()
            
            # Input Validation
            if not query:
                print(f"{Colors.ERROR}Input cannot be empty. Please try again.{Colors.RESET}")
                continue
                
            command = query.lower()
            if command in ['exit', 'quit']:
                print(f"{Colors.SYSTEM}Shutting down...{Colors.RESET}")
                break
            elif command == 'clear':
                agent.clear_history()
                print(f"{Colors.SYSTEM}Conversation history and cache cleared.{Colors.RESET}")
                continue

            # Execute Agent
            agent.run(query)

        # Exit with Ctrl+C
        except KeyboardInterrupt:
            print(f"\n{Colors.SYSTEM}Process interrupted by user. Shutting down...{Colors.RESET}")
            break

        # Catch all unexpected CLI crashes
        except Exception as e:
            print(f"{Colors.ERROR}An unexpected error occurred: {e}{Colors.RESET}")


if __name__ == "__main__":
    main()