import os
import ast

views_path = r'c:\Users\shiva\Downloads\myproject_updated\myproject_updated\myproject\myapp\views.py'
with open(views_path, 'r', encoding='utf-8') as f:
    source = f.read()

lines = source.split('\n')

def get_node_lines(node):
    # Find the start line including decorators
    start = node.lineno
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno
    # Find end line
    end = node.end_lineno
    return start - 1, end

tree = ast.parse(source)

# Define which file gets which functions
mapping = {
    'auth_views.py': ['signup_view', 'login_view', 'logout_view', 'reset_password_view'],
    'patient_views.py': ['index', 'prediction', 'history', 'delete_history', 'download_history_csv', 'history_detail', 'history_detail_pdf', 'download_history_pdf', 'profile_view'],
    'doctor_views.py': ['doctor_apply_view', 'doctor_dashboard', 'doctor_patients_list', 'doctor_patient_history', 'doctor_history_review'],
    'admin_views.py': ['is_staff_user', 'admin_dashboard', 'admin_users', 'admin_doctors', 'admin_doctor_applications', 'admin_delete_doctor', 'admin_delete_user', 'admin_patients', 'admin_reports'],
    'chat_views.py': ['conversations_list', 'chat_view'],
    # Any other functions (like load_model, _get_model_paths) we can leave in all or put in patient_views.py.
    # Actually, let's put ML models in patient_views.py for now.
}
mapping['patient_views.py'].extend(['_get_model_paths', 'load_model'])

out_dir = r'c:\Users\shiva\Downloads\myproject_updated\myproject_updated\myproject\myapp\views'
os.makedirs(out_dir, exist_ok=True)

for filename, funcs in mapping.items():
    # We want to KEEP `funcs` and REMOVE any other FunctionDef
    lines_to_keep = [True] * len(lines)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) or hasattr(node, 'name'):
            name = getattr(node, 'name', None)
            if name and name not in funcs:
                # Remove it
                start, end = get_node_lines(node)
                for i in range(start, end):
                    lines_to_keep[i] = False

    new_source = []
    for i, line in enumerate(lines):
        if lines_to_keep[i]:
            new_source.append(line)
    
    out_path = os.path.join(out_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_source))
        
# Create __init__.py
init_path = os.path.join(out_dir, '__init__.py')
with open(init_path, 'w', encoding='utf-8') as f:
    f.write('from .auth_views import *\n')
    f.write('from .patient_views import *\n')
    f.write('from .doctor_views import *\n')
    f.write('from .admin_views import *\n')
    f.write('from .chat_views import *\n')

print("Refactoring complete.")
