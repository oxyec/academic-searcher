import concurrent.futures
from src.config import OUTPUT_CSV, GOOGLE_API_KEY, CSE_ID
from src.search import process_crossref, process_semanticscholar, process_google
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

        # Using ThreadPoolExecutor for parallel execution
        # We have 3 sources: CrossRef, Semantic Scholar, Google
        all_results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Schedule the tasks
            futures = []
            
            # 1. CrossRef
            futures.append(executor.submit(process_crossref, query, results_limit))
            
            # 2. Semantic Scholar
            futures.append(executor.submit(process_semanticscholar, query, results_limit))

            # 3. Google (only if configured)
            if GOOGLE_API_KEY and CSE_ID:
                futures.append(executor.submit(process_google, query, results_limit, GOOGLE_API_KEY, CSE_ID))
            
            # Wait for all to complete and gather results
            for future in concurrent.futures.as_completed(futures):
                try:
                    data = future.result()
                    all_results.extend(data)
                except Exception as exc:
                    print(f"   [!] Generated an exception: {exc}")

        # Save all results
        print(f"\n   -> Processing {len(all_results)} total results...")
        for row in all_results:
            save_to_csv(row)
        
        print(f"\n✅ Data appended to: {OUTPUT_CSV}\n")

if __name__ == "__main__":
    main()
