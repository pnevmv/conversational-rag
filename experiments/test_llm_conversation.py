import sys
from pathlib import Path

# Add project root to sys.path so src can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import ask_llm


def main():
    question = "What documents do I need to apply for a driver's license?"
    print("QUESTION:")
    print(question)

    answer = ask_llm(question)

    print("\nANSWER:")
    print(answer)


if __name__ == "__main__":
    main()
