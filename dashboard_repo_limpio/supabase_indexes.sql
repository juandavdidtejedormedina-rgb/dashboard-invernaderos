-- Optional but recommended for faster dashboard loads from Supabase.
-- Run this once in Supabase SQL Editor.

create index if not exists idx_variables_ambientales_finca_sensor_fecha
on public.variables_ambientales (finca, sensor, fecha);

create index if not exists idx_variables_ambientales_finca_bloque_sensor_fecha
on public.variables_ambientales (finca, bloque, sensor, fecha);

create index if not exists idx_registros_cortinas_bloque_fecha
on public.registros_cortinas (bloque, fecha);

analyze public.variables_ambientales;
analyze public.registros_cortinas;
