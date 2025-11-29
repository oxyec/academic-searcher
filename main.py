from src.config import OUTPUT_CSV
from src.core import search_all_sources
from src.export import save_to_csv

def main():
    print("\n" + "="*60)
    print("   ACADEMIC RESEARCH ASSISTANT - Article Finder")
    print("   contact: oxyec in github.com ")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("How many articles per source? (Default 5): ").strip()
            if not user_input:
                results_limit = 5
            else:
                results_limit = int(user_input)
                if results_limit < 1: results_limit = 1
            break
        except ValueError:
            print("Please enter a valid number.")

    print(f"\n   -> Saving to: {OUTPUT_CSV}\n")
    print("Type 'q' to exit.\n")

    while True:
        query = input("Research Topic/Keyword: ").strip()
        if query.lower() in ['q', 'exit', 'quit']:
            print("Goodbye!")
            break
        if not query: continue

        print(f"\n🔎 Searching for '{query}'...")

        # Use the core logic (returns a combined list of results)
        all_results = search_all_sources(query, results_limit)

        # Save all results
        print(f"\n   -> Processing {len(all_results)} total results...")
        for row in all_results:
            save_to_csv(row)
        
        print(f"\n✅ Data appended to: {OUTPUT_CSV}\n")

if __name__ == "__main__":
    main()
