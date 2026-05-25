# Dashboard Invernaderos Elite Flower

Dashboard ejecutivo desarrollado en Python y Streamlit para visualizar variables ambientales, comparativas de sensores y analisis operativo por bloques de invernadero.

## Objetivo

Centralizar la lectura de datos ambientales desde Supabase y presentar informacion clara para seguimiento tecnico y operativo. El proyecto reemplaza la lectura directa de archivos Excel por una base de datos estructurada, manteniendo un flujo controlado para actualizar nuevos datos.

## Tecnologias

- Python
- Streamlit
- Pandas
- Plotly
- Supabase
- SQL

## Estructura principal

```text
dashboard.py
dashboard_app/
data_loaders.py
data_transforms.py
supabase_client.py
scripts/import_variables_ambientales.py
requirements.txt
```

## Ejecutar localmente

Antes de ejecutar, configure la conexion a Supabase en variables de entorno o en un archivo local que no se sube a GitHub:

```text
.streamlit/secrets.toml
```

Ejemplo:

```toml
SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_KEY = "sb_publishable_tu_llave"
```

```powershell
cd "C:\Users\pastautomatizacion4\OneDrive - Elite Flower\Escritorio\Dashboard Variables\dashboard_repo_limpio"
.\venv\Scripts\python.exe -m streamlit run dashboard.py
```

## Actualizar datos

La actualizacion de datos ambientales se hace con el script:

```text
scripts/import_variables_ambientales.py
```

El proceso completo esta documentado en:

```text
GUIA_ACTUALIZAR_DATOS.md
```

## Proteccion contra duplicados

La tabla `variables_ambientales` debe tener una restriccion unica por:

```text
fecha + finca + bloque + sensor
```

El SQL para crear esa proteccion esta en:

```text
supabase_unique_variables_ambientales.sql
```
