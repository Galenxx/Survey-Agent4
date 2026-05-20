"""主程序入口"""
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

from src.crews.research_gap_crew import run_research_gap_analysis
from src.storage.task_storage import TaskStorage


def main():
    parser = argparse.ArgumentParser(description="Research Gap Analysis System")
    parser.add_argument("query", type=str, help="Research gap analysis query")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="Output directory for task results",
    )
    args = parser.parse_args()

    print(f"Starting research gap analysis...")
    print(f"Query: {args.query}")
    print(f"Output dir: {args.output_dir}")

    task_storage = TaskStorage(task_name=args.query, base_dir=args.output_dir)
    print(f"Task ID: {task_storage.task_id}")
    print(f"Task dir: {task_storage.task_dir}")

    result = run_research_gap_analysis(
        user_input=args.query,
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
