import sys
from pathlib import Path

# Add project root to sys.path so src can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import ask_llm


def main():
    prompt = "What is the capital of France?"
    print(f"Prompt: {prompt}")
    answer = ask_llm(prompt)
    print(f"Response: {answer}")


if __name__ == "__main__":
    main()
