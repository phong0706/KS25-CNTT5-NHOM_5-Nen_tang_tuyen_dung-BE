import os
import py_compile
import importlib
import sys
import traceback

def scan_imports():
    errors = []
    compiled = 0
    imported = 0
    
    app_dir = os.path.abspath("app")
    sys.path.insert(0, os.path.abspath("."))
    
    modules_to_test = []
    for root, _, files in os.walk(app_dir):
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                # 1. py_compile
                try:
                    py_compile.compile(full_path, doraise=True)
                    compiled += 1
                except py_compile.PyCompileError as e:
                    errors.append({"type": "syntax", "file": full_path, "error": str(e)})
                
                # prepare module path
                rel = os.path.relpath(full_path, os.path.abspath(".")).replace("\\", "/")
                mod_name = rel[:-3].replace("/", ".")
                modules_to_test.append((mod_name, full_path))
                
    print(f"Compiled {compiled} python files in app/")
    
    # 2. Try importing each module
    for mod_name, fpath in modules_to_test:
        try:
            importlib.import_module(mod_name)
            imported += 1
        except Exception as e:
            errors.append({
                "type": "import_error",
                "module": mod_name,
                "file": fpath,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()
            })
            
    print(f"Imported {imported}/{len(modules_to_test)} modules in app/")
    print(f"Total scan errors found: {len(errors)}")
    for err in errors:
        print(f"  [{err['type']}] {err.get('module') or err.get('file')}: {err['error']}")

if __name__ == "__main__":
    scan_imports()
