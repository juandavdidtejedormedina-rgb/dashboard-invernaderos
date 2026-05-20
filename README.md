# Dashboard App

Estructura modular del dashboard Streamlit de Elite Flower.

- `app.py`: flujo principal de la aplicacion y ruteo de vistas.
- `foundation.py`: imports, constantes, estilos globales, tema, logo y configuracion visual.
- `shared.py`: utilidades comunes, filtros, tarjetas, fechas, bloques y cortinas.
- `marly.py`: vistas, graficas y analisis especificos de Marly.
- `ponderosa.py`: vistas, graficas y analisis especificos de La Ponderosa.
- `greenhouse.py`: ficha tecnica, capacidad estructural y diagnostico de invernaderos.
- `analysis.py`: analisis horario, reportes, tablas y graficas estadisticas compartidas.

`dashboard.py` se mantiene como punto de entrada para Streamlit y solo llama a `dashboard_app.app.run()`.
