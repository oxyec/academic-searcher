import asyncio
from src.config import OUTPUT_CSV
from src.core import search_with_diagnostics_async
from src.export import save_to_csv

async def run_cli(results_limit):
    while True:
        query = input("Research Topic/Keyword: ").strip()
        if query.lower() in ["q", "exit", "quit"]:
            print("Goodbye!")
            break
        if not query:
            continue

        print(f"\nSearching for '{query}'...")
        try:
            all_results, diagnostics = await search_with_diagnostics_async(query, results_limit)
        except ValueError as exc:
            print(f"Invalid search: {exc}")
            continue
        for stat in diagnostics:
            if stat["status"] != "OK":
                print(f"   [{stat['status']}] {stat['source']}: {stat['error']}")
        if not all_results:
            message = "All sources failed; no search results are available." if all(stat["status"] == "Error" for stat in diagnostics) else "No matches were returned."
            print(message)
            continue

        print(f"\n   -> Processing {len(all_results)} total results...")
        for row in all_results:
            save_to_csv(row)

        print(f"\nDone. Data appended to: {OUTPUT_CSV}\n")

def main():
    print("\n" + "=" * 60)
    print("   ACADEMIC RESEARCH ASSISTANT - Article Finder")
    print("   contact: oxyec in github.com ")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("How many articles per source? (Default 5): ").strip()
            if not user_input:
                results_limit = 5
            else:
                results_limit = int(user_input)
                if not 1 <= results_limit <= 100:
                    print("Choose between 1 and 100 articles per source.")
                    continue
            break
        except ValueError:
            print("Please enter a valid number.")

    print(f"\n   -> Saving to: {OUTPUT_CSV}\n")
    print("Type 'q' to exit.\n")
    asyncio.run(run_cli(results_limit))

if __name__ == "__main__":
    main()
