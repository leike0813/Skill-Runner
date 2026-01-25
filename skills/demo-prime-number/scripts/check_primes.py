import json
import sys
import math

def is_prime(n):
    if n <= 1:
        return False, []
    if n <= 3:
        return True, [1, n]
    if n % 2 == 0:
        return False, [1, 2] # Just need one factor
    if n % 3 == 0:
        return False, [1, 3]
    i = 5
    while i * i <= n:
        if n % i == 0:
            return False, [1, i]
        if n % (i + 2) == 0:
            return False, [1, i + 2]
        i += 6
    return True, [1, n]

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_primes.py <input_json_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    
    try:
        with open(input_file, 'r') as f:
            numbers = json.load(f)
    except Exception as e:
        print(f"Error reading input: {e}")
        sys.exit(1)

    results = {}
    
    # Expecting numbers to be a list of integers
    for num in numbers:
        if not isinstance(num, int):
            results[str(num)] = {"is_prime": False, "factor": None, "error": "Not an integer"}
            continue
            
        is_p, factors = is_prime(num)
        results[str(num)] = {
            "is_prime": is_p,
            "factor": factors[1] if not is_p and len(factors) > 1 else None # Return a non-trivial factor if composite
        }

    print(json.dumps(results))

if __name__ == "__main__":
    main()
