"""Split large INSERT SQL files into smaller batches for execution."""
import os, re, sys

DATA_DIR = r"e:\Snowflake CoCo\retainiq\data"
BATCH_DIR = os.path.join(DATA_DIR, "batches")
os.makedirs(BATCH_DIR, exist_ok=True)

# Max rows per batch — keeps each INSERT under ~50KB
MAX_ROWS = {
    'customers': 500,   # 75KB total, 1 batch is fine
    'policies': 400,    # 158KB total, split into 2
    'claims': 300,      # 53KB total, 1 batch
    'payments': 500,    # 224KB total, split into ~5
    'interactions': 150 # 719KB total, split into ~10
}

def split_sql_file(filepath, table_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    statements = [s.strip() for s in content.split(';') if s.strip()]
    batch_num = 0
    
    for stmt in statements:
        # Find the VALUES keyword
        match = re.search(r'(INSERT INTO .+?VALUES\s*\n?)', stmt, re.DOTALL)
        if not match:
            continue
        
        header = match.group(1)
        values_part = stmt[match.end():]
        
        # Split into individual row tuples
        rows = []
        depth = 0
        current = ""
        for char in values_part:
            current += char
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    rows.append(current.strip().rstrip(',').strip())
                    current = ""
            elif char == ',' and depth == 0:
                current = ""  # skip comma between rows
        
        max_rows = MAX_ROWS.get(table_name, 200)
        for i in range(0, len(rows), max_rows):
            batch = rows[i:i+max_rows]
            batch_num += 1
            batch_sql = header + ',\n'.join(batch) + ';'
            
            outpath = os.path.join(BATCH_DIR, f"{table_name}_{batch_num:02d}.sql")
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(batch_sql)
            
            print(f"  {os.path.basename(outpath)}: {len(batch)} rows, {len(batch_sql):,} chars")

files = [
    ('insert_customers.sql', 'customers'),
    ('insert_policies.sql', 'policies'),
    ('insert_claims.sql', 'claims'),
    ('insert_payments.sql', 'payments'),
    ('insert_interactions.sql', 'interactions'),
]

for filename, table in files:
    filepath = os.path.join(DATA_DIR, filename)
    print(f"\n{table.upper()}:")
    split_sql_file(filepath, table)

# List all batch files
print(f"\n--- Total batch files ---")
batches = sorted(os.listdir(BATCH_DIR))
print(f"{len(batches)} files ready for execution")
for b in batches:
    size = os.path.getsize(os.path.join(BATCH_DIR, b))
    print(f"  {b}: {size:,} bytes")
