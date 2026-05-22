# Sample data

Estos archivos son ejemplos pequenos y sinteticos para documentar la estructura de datos del proyecto.

No corresponden a datos operativos reales de la empresa.

## Archivo incluido

```text
variables_ambientales_sample.csv
```

Representa la estructura final que se carga en Supabase en la tabla:

```text
variables_ambientales
```

Columnas:

```text
fecha
finca
bloque
sensor
temperatura
humedad_relativa
radiacion_par
gramos_agua
luz_lux
```

La llave logica para evitar duplicados es:

```text
fecha + finca + bloque + sensor
```

