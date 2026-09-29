"""
Execute SQL batch files against Snowflake via CoCo's connection.
Reads each batch file and prints the SQL for execution.
Usage: python load_data.py <batch_file> 
       Prints the SQL content to stdout for piping to execution.
"""
import os, sys, json

BATCH_DIR = r"e:\Snowflake CoCo\retainiq\data\batches"

# Execution order (FK dependencies)
ORDER = [
    'customers',
    'policies', 
    'claims',
    'payments',
    'interactions',
]

def get_ordered_files():
    files = sorted(os.listdir(BATCH_DIR))
    ordered = []
    for prefix in ORDER:
        for f in files:
            if f.startswith(prefix) and f.endswith('.sql'):
                ordered.append(f)
    return ordered

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Print content of specific file
        fname = sys.argv[1]
        path = os.path.join(BATCH_DIR, fname)
        with open(path, 'r', encoding='utf-8') as f:
            print(f.read().rstrip())
    else:
        # List all files in order
        for f in get_ordered_files():
            size = os.path.getsize(os.path.join(BATCH_DIR, f))
            print(f"{f}: {size:,} bytes")
