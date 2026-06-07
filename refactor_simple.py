import os
import re

with open(r'c:\Users\shiva\Downloads\myproject_updated\myproject_updated\myproject\myapp\views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

blocks = []
current_block = []
current_func_name = None

# Identify globals vs functions
globals_lines = []
is_global = True

for line in lines:
    if line.startswith('def ') or (line.startswith('@') and not line.startswith(' ')):
        is_global = False
        
    if is_global:
        globals_lines.append(line)
    else:
        # If line is def or @ at top level, it might be a new block
        if (line.startswith('def ') or line.startswith('@')) and not current_block:
            current_block.append(line)
            m = re.match(r'^def\s+([a-zA-Z_0-9]+)\(', line)
            if m:
                current_func_name = m.group(1)
        elif (line.startswith('def ') or line.startswith('@')) and current_block and current_block[-1] == '\n':
            # Actually, just looking at indentation is better.
            # Python functions must be unindented.
            pass

# Let's use a simpler approach. We know the functions we want in each file.
# We will use ast to get start/end lines, but correctly!
import ast
source = "".join(lines)
tree = ast.parse(source)

# Build a map of function name to (start_line, end_line)
func_lines = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        start = node.lineno
        if node.decorator_list:
            start = node.decorator_list[0].lineno
        end = node.end_lineno
        func_lines[node.name] = (start - 1, end)  # 0-indexed

# We also want to keep globals. Let's find the first function's start line.
first_func_start = min(start for start, end in func_lines.values())
globals_text = "".join(lines[:first_func_start])

mapping = {
    'auth_views.py': ['signup_view', 'login_view', 'logout_view', 'reset_password_view'],
    'patient_views.py': ['index', 'prediction', 'history', 'delete_history', 'download_history_csv', 'history_detail', 'history_detail_pdf', 'download_history_pdf', 'profile_view', '_get_model_paths', 'load_model'],
    'doctor_views.py': ['doctor_apply_view', 'doctor_dashboard', 'doctor_patients_list', 'doctor_patient_history', 'doctor_history_review'],
    'admin_views.py': ['is_staff_user', 'admin_dashboard', 'admin_users', 'admin_doctors', 'admin_doctor_applications', 'admin_delete_doctor', 'admin_delete_user', 'admin_patients', 'admin_reports'],
    'chat_views.py': ['conversations_list', 'chat_view'],
}

out_dir = r'c:\Users\shiva\Downloads\myproject_updated\myproject_updated\myproject\myapp\views'
os.makedirs(out_dir, exist_ok=True)

for filename, funcs in mapping.items():
    out_lines = [globals_text]
    for func in funcs:
        if func in func_lines:
            start, end = func_lines[func]
            out_lines.append("".join(lines[start:end]) + "\n")
    
    with open(os.path.join(out_dir, filename), 'w', encoding='utf-8') as f:
        f.write("".join(out_lines))

with open(os.path.join(out_dir, '__init__.py'), 'w', encoding='utf-8') as f:
    for filename in mapping.keys():
        f.write(f"from .{filename[:-3]} import *\n")

print("Done")
