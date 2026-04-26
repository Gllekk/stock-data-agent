from agent import StockAgent
from framework import ConsoleLogger, Colors
import os
import sys


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"{Colors.ERROR}[ERROR] {Colors.RESET}GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    try:
        agent = StockAgent(api_key)
        agent.observers.append(ConsoleLogger())
    except Exception as e:
        print(f"{Colors.ERROR}[ERROR] {Colors.RESET}Failed to initialize agent: {e}")
        sys.exit(1)
    
    print(f"{Colors.SYSTEM}--- Stock Analysis System Initialized ---{Colors.RESET}")
    print("Commands: 'exit' or 'quit' to quit")
    print("          'clear' to reset history\n")

    while True:
        try:
            # Input Handling
            query = input(f"{Colors.USER}[USER] {Colors.RESET}Ask about a stock: ").strip()
            
            # Input Validation
            if not query:
                print(f"{Colors.SYSTEM}[SYSTEM] {Colors.RESET}Input cannot be empty. Please try again.")
                continue
                
            command = query.lower()
            if command in ['exit', 'quit']:
                print(f"{Colors.SYSTEM}[SYSTEM] {Colors.RESET}Shutting down...")
                break
            elif command == 'clear':
                agent.clear_history()
                print(f"{Colors.SYSTEM}[SYSTEM] {Colors.RESET}Conversation history and cache cleared.")
                continue

            # Execute Agent
            agent.run(query)

        # Exit with Ctrl+C
        except KeyboardInterrupt:
            print(f"\n{Colors.SYSTEM}[SYSTEM] {Colors.RESET}Process interrupted by user. Shutting down...")
            break

        # Catch all unexpected CLI crashes
        except Exception as e:
            print(f"{Colors.ERROR}[ERROR] {Colors.RESET}An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()