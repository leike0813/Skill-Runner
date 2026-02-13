import sys
import pandas as pd
import json

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: python analyze.py <csv_file> <column>"}))
        sys.exit(1)

    csv_file = sys.argv[1]
    column = sys.argv[2]

    try:
        df = pd.read_csv(csv_file)
        if column not in df.columns:
             print(json.dumps({"error": f"Column '{column}' not found"}))
             sys.exit(1)
        
        mean_val = df[column].mean()
        # Round for consistency in testing
        result = {"mean": round(float(mean_val), 2)}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
