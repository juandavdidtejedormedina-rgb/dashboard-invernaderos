# Archivos de este paquete

Esta carpeta contiene archivos listos para subir al repositorio `dashboard-invernaderos`, dentro de `dashboard_repo_limpio`.

## Subir a GitHub

Arrastre el contenido de esta carpeta a:

```text
dashboard-invernaderos/dashboard_repo_limpio
```

## Contenido

```text
README.md
GUIA_ACTUALIZAR_DATOS.md
.gitignore
supabase_unique_variables_ambientales.sql
scripts/import_variables_ambientales.py
sample_data/README.md
sample_data/variables_ambientales_sample.csv
```

## Que no se debe subir

```text
venv/
__pycache__/
staging_supabase/
backups_supabase/
Datos/
archivos Excel reales
.streamlit/secrets.toml
```

## Nota

Los datos de `sample_data` son sinteticos. Sirven para mostrar la estructura del proyecto sin publicar datos reales de operacion.

