import os
import re

def update_file(filepath, header_content):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'Source References:' in content:
        return # already updated

    # Find the end of the module docstring
    match = re.search(r'^\"\"\"[\s\S]*?\"\"\"', content)
    if match:
        old_docstring = match.group(0)
        # remove the closing quotes
        new_docstring = old_docstring[:-3] + '\n\n' + header_content + '\n\"\"\"'
        content = content.replace(old_docstring, new_docstring, 1)
    else:
        content = f'\"\"\"\n{header_content}\n\"\"\"\n\n' + content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

base_dir = r'c:\Users\ADMIN\Desktop\Flood\flowshield\src\flowshield'

general_header = '''Source References:
- [REF-001] Python standard library
- [REF-002] NumPy documentation
- [REF-003] Pydantic documentation

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.'''

flow_header = '''Source References:
- [REF-002] NumPy documentation
- [REF-004] D4 / von Neumann cellular automaton flow routing approximation
- [REF-007] Hydrological mass conservation principles

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.'''

forecasting_header = '''Source References:
- [REF-002] NumPy documentation
- [REF-005] Linear least squares regression (np.polyfit)

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.'''

generator_header = '''Source References:
- [REF-002] NumPy documentation
- [REF-006] Synthetic terrain generation mathematics

Implementation:
Original FLOWSHIELD implementation.

External Code:
No external code copied.

Dataset:
Synthetic FLOWSHIELD-generated data. No external dataset used.'''

for dirpath, _, filenames in os.walk(base_dir):
    for filename in filenames:
        if filename.endswith('.py'):
            filepath = os.path.join(dirpath, filename)
            if 'flow.py' in filename:
                update_file(filepath, flow_header)
            elif 'forecasting.py' in filename:
                update_file(filepath, forecasting_header)
            elif 'generator.py' in filename:
                update_file(filepath, generator_header)
            else:
                update_file(filepath, general_header)

print("Done updating module docstrings.")
