#!/usr/bin/env python3
"""Valida sintaxis YAML de todos los manifests del repo, que cada Application
tenga spec.project == 'cauri', que no haya YAML sin apiVersion/kind dentro de
apps/** salvo los values-*.yaml (eso es justo lo que Argo NO tolera en un
source tipo Directory: intenta decodificar todo *.yaml como manifest de
Kubernetes), y que bootstrap/root.yaml excluya esos values del recorrido.
Usado localmente y por .github/workflows/ci.yml."""
import fnmatch
import sys
import glob
import yaml

errors = []
checked_apps = 0

paths = sorted(
    p for p in glob.glob("**/*.yaml", recursive=True)
    if not p.startswith(".git/")
)

for path in paths:
    with open(path) as f:
        try:
            docs = list(yaml.safe_load_all(f))
        except yaml.YAMLError as e:
            errors.append(f"{path}: YAML inválido: {e}")
            continue

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if doc.get("kind") == "Application" and doc.get("apiVersion", "").startswith("argoproj.io"):
            checked_apps += 1
            project = doc.get("spec", {}).get("project")
            if str(path).startswith("bootstrap/"):
                continue  # las apps raíz viven en el proyecto default: son las que crean el proyecto cauri
            if project != "cauri":
                errors.append(f"{path}: Application sin spec.project=cauri (tiene {project!r})")

        # Cualquier YAML dentro de apps/** que no sea un values-*.yaml tiene que ser
        # un manifest de verdad (apiVersion + kind): es lo que el source Directory de
        # root.yaml va a intentar aplicar. Un archivo sin eso rompe la sync entera de
        # "root", no solo esa app (ver bootstrap/root.yaml).
        if path.startswith("apps/") and not fnmatch.fnmatch(path.split("/")[-1], "values-*.yaml"):
            if "apiVersion" not in doc or "kind" not in doc:
                errors.append(
                    f"{path}: dentro de apps/** sin ser values-*.yaml, pero no tiene "
                    f"apiVersion/kind — el source Directory de root.yaml fallaría al parsearlo"
                )

# root.yaml tiene que declarar cómo se saca los values-*.yaml del recorrido de directory,
# porque si alguien lo borra sin querer, root vuelve a romper en silencio hasta el próximo sync.
with open("bootstrap/root.yaml") as f:
    root_docs = list(yaml.safe_load_all(f))

root_app = next(
    (d for d in root_docs if isinstance(d, dict) and d.get("metadata", {}).get("name") == "root"),
    None,
)
if root_app is None:
    errors.append("bootstrap/root.yaml: no encontré el Application 'root'")
else:
    directory = root_app.get("spec", {}).get("source", {}).get("directory", {})
    if not directory.get("exclude") and not directory.get("include"):
        errors.append(
            "bootstrap/root.yaml: el Application 'root' no tiene directory.exclude ni "
            "directory.include — va a intentar parsear los values-*.yaml como manifests"
        )

print(f"Archivos YAML revisados: {len(paths)}")
print(f"Applications de Argo CD revisadas: {checked_apps}")

if errors:
    print("\nERRORES:")
    for e in errors:
        print(f" - {e}")
    sys.exit(1)

print("OK: todo el YAML parsea, todas las Applications tienen project: cauri,")
print("no hay YAML sin apiVersion/kind en apps/** fuera de los values, y root.yaml excluye los values.")
