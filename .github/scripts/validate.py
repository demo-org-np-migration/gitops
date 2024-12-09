#!/usr/bin/env python3
"""Valida sintaxis YAML de todos los manifests del repo y que cada Application
tenga spec.project == 'cauri'. Usado localmente y por .github/workflows/ci.yml."""
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
            if project != "cauri":
                errors.append(f"{path}: Application sin spec.project=cauri (tiene {project!r})")

print(f"Archivos YAML revisados: {len(paths)}")
print(f"Applications de Argo CD revisadas: {checked_apps}")

if errors:
    print("\nERRORES:")
    for e in errors:
        print(f" - {e}")
    sys.exit(1)

print("OK: todo el YAML parsea y todas las Applications tienen project: cauri")
