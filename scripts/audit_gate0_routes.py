from app.main import app
from collections import defaultdict
import json

routes_by_method_path = defaultdict(list)
all_routes = []

for route in app.routes:
    methods = getattr(route, "methods", None)
    path = getattr(route, "path", getattr(route, "path_format", None))
    name = getattr(route, "name", "")
    endpoint = getattr(route, "endpoint", None)
    endpoint_name = getattr(endpoint, "__qualname__", str(endpoint))
    module = getattr(endpoint, "__module__", "")

    if methods:
        for m in methods:
            all_routes.append((m, path, module, endpoint_name))
            routes_by_method_path[(m, path)].append({
                "name": name,
                "endpoint": endpoint_name,
                "module": module
            })
    else:
        all_routes.append(("WS/MOUNT", path, module, endpoint_name))
        routes_by_method_path[("WS/MOUNT", path)].append({
            "name": name,
            "endpoint": endpoint_name,
            "module": module
        })

print(f"Total registered route entries (by method): {len(all_routes)}")
print(f"Total unique (method, path) endpoints: {len(routes_by_method_path)}")

duplicates = {f"{m} {path}": v for (m, path), v in routes_by_method_path.items() if len(v) > 1}
print(f"Duplicate endpoints count: {len(duplicates)}")
for route_str, entries in duplicates.items():
    print(f"  [DUPLICATE] {route_str}")
    for e in entries:
        print(f"    - {e['module']}.{e['endpoint']}")

with open("audit_gate0_routes.json", "w", encoding="utf-8") as f:
    json.dump({
        "total_routes": len(all_routes),
        "unique_endpoints": len(routes_by_method_path),
        "duplicates": duplicates
    }, f, indent=2)
