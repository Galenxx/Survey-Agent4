"""CLI 入口"""
import sys
from dotenv import load_dotenv

load_dotenv()

from src.crews.research_gap_crew import run_research_gap_analysis
from src.storage.task_storage import TaskStorage


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/cli.py <research query>")
        print("Example: python src/cli.py \"帮我分析LLM在job recommendation领域的gap\"")
        sys.exit(1)

    query = sys.argv[1]

    print(f"Starting research gap analysis...")
    print(f"Query: {query}")

    task_storage = TaskStorage(task_name=query, base_dir="outputs")
    print(f"Task ID: {task_storage.task_id}")
    print(f"Task dir: {task_storage.task_dir}")

    result = run_research_gap_analysis(
        user_input=query,
        task_storage=task_storage,
    )

    if result["status"] == "success":
        print(f"\nAnalysis completed!")
        print(f"Task ID: {result['task_id']}")
        print(f"Report: {result['report_path']}")
    else:
        print(f"\nAnalysis failed!")
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
