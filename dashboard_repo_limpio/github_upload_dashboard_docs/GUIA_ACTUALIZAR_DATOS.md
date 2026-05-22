# Guia para actualizar datos ambientales en Supabase

Esta guia explica como cargar nuevos datos ambientales al dashboard usando los Excel operativos. El proceso esta pensado para evitar duplicados y mantener la base de datos limpia.

## 1. Archivos necesarios

Para actualizar `variables_ambientales`, se usan estos 3 archivos:

```text
Datos_Variables.xlsx
ECOWITT Ponderosa.xlsx
Datos Final Marley.xlsx
```

Por defecto el script busca los archivos en:

```text
C:\Users\pastautomatizacion4\OneDrive - Elite Flower\Escritorio\Dashboard Variables\Datos\Datos 22-02-2026
```

Los nombres deben quedar exactamente asi:

```text
Datos_Variables.xlsx
ECOWITT Ponderosa.xlsx
Datos Final Marley.xlsx
```

Antes de correr el script, cierre esos Excel en Microsoft Excel para evitar errores de permisos.

## 2. Script de actualizacion

El script esta en:

```text
C:\Users\pastautomatizacion4\OneDrive - Elite Flower\Escritorio\Dashboard Variables\dashboard_repo_limpio\scripts\import_variables_ambientales.py
```

Este script:

- Lee los 3 Excel.
- Convierte los datos al formato de la tabla `variables_ambientales`.
- Une todos los datos en una sola estructura.
- Quita duplicados dentro de los archivos nuevos.
- Consulta Supabase.
- Separa filas nuevas de filas que ya existen.
- Puede subir automaticamente solo las filas nuevas.

## 3. Abrir terminal

Abra PowerShell o la terminal de VS Code y entre a la carpeta del proyecto:

```powershell
cd "C:\Users\pastautomatizacion4\OneDrive - Elite Flower\Escritorio\Dashboard Variables\dashboard_repo_limpio"
```

## 4. Ejecutar revision

Primero ejecute el modo revision. Este comando no sube nada a Supabase:

```powershell
.\venv\Scripts\python.exe .\scripts\import_variables_ambientales.py
```

El resultado debe mostrar algo parecido a:

```text
Total leido: 24460
Duplicados dentro de archivos removidos: 31
Ya existian en Supabase: 16186
Listos para insertar: 8243
Upload ejecutado: False
```

## 5. Revisar archivos generados

Cada revision crea una carpeta en:

```text
C:\Users\pastautomatizacion4\OneDrive - Elite Flower\Escritorio\Dashboard Variables\staging_supabase
```

Ejemplo:

```text
C:\Users\pastautomatizacion4\OneDrive - Elite Flower\Escritorio\Dashboard Variables\staging_supabase\2026-05-22_10-55-42
```

Dentro se generan estos archivos:

```text
variables_ambientales_staging_all.csv
variables_ambientales_new_rows.csv
variables_ambientales_already_existing.csv
import_report.json
```

El archivo mas importante es:

```text
variables_ambientales_new_rows.csv
```

Ese archivo contiene solo las filas nuevas que no existen en Supabase.

## 6. Subir datos automaticamente

Si la revision se ve correcta, ejecute:

```powershell
.\venv\Scripts\python.exe .\scripts\import_variables_ambientales.py --upload
```

Este comando sube solo las filas nuevas a la tabla:

```text
variables_ambientales
```

Al terminar debe aparecer:

```text
Upload ejecutado: True
```

## 7. Usar otra carpeta de Excel

Si en el futuro los Excel quedan en otra carpeta, no es necesario modificar el codigo. Use `--data-dir`:

```powershell
.\venv\Scripts\python.exe .\scripts\import_variables_ambientales.py --data-dir "C:\Ruta\A\La\Carpeta"
```

Para subir desde esa carpeta:

```powershell
.\venv\Scripts\python.exe .\scripts\import_variables_ambientales.py --data-dir "C:\Ruta\A\La\Carpeta" --upload
```

La carpeta debe contener los mismos 3 nombres de archivo:

```text
Datos_Variables.xlsx
ECOWITT Ponderosa.xlsx
Datos Final Marley.xlsx
```

## 8. Proteccion contra duplicados en Supabase

La tabla `variables_ambientales` debe tener una restriccion unica para evitar duplicados por:

```text
fecha + finca + bloque + sensor
```

El SQL esta en:

```text
supabase_unique_variables_ambientales.sql
```

Este SQL se ejecuta desde Supabase, en SQL Editor. Debe ejecutarse una vez, o nuevamente solo si se restaura o reconstruye la base.

## 9. Despues de subir datos

Despues de una carga exitosa:

1. Abrir Streamlit Cloud.
2. Entrar a la app.
3. Ir a `Manage app`.
4. Ejecutar `Reboot`.
5. Validar que las fechas nuevas aparezcan en el dashboard.

## 10. Errores comunes

### Permission denied al leer un Excel

Significa que el archivo esta abierto o bloqueado por OneDrive.

Solucion:

1. Cerrar el archivo en Excel.
2. Esperar unos segundos.
3. Ejecutar de nuevo el script.

### No encontre columna

Significa que el encabezado de una columna cambio.

Solucion:

1. Revisar el nombre de la columna en el Excel.
2. Ajustar el script en `scripts/import_variables_ambientales.py`.

### Error de duplicado en Supabase

Significa que la base detecto una fila repetida.

Solucion:

1. Ejecutar primero el modo revision.
2. Revisar `variables_ambientales_new_rows.csv`.
3. Confirmar que la restriccion unica esta activa.

## 11. Recomendacion operativa

Siempre use este orden:

```text
1. Cerrar Excel
2. Ejecutar revision
3. Revisar conteos
4. Ejecutar --upload
5. Reiniciar Streamlit
6. Validar dashboard
```

