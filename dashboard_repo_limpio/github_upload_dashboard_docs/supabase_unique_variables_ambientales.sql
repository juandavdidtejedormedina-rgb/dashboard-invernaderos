-- Safe duplicate cleanup and unique protection for variables_ambientales only.
-- This is the only table updated by the three Excel files:
-- Datos_Variables.xlsx, ECOWITT Ponderosa.xlsx, Datos Final Marley.xlsx.

-- 1) Audit duplicates before changing anything.
select
    'variables_ambientales' as table_name,
    count(*) as duplicate_rows_before
from (
    select
        id,
        count(*) over (
            partition by
                fecha,
                coalesce(finca, ''),
                coalesce(bloque, ''),
                coalesce(sensor, '')
        ) as duplicate_count
    from public.variables_ambientales
) audit
where duplicate_count > 1;

-- 2) Backup repeated copies before deleting them.
create table if not exists public.backup_variables_ambientales_duplicados_20260522 as
with ranked as (
    select
        *,
        row_number() over (
            partition by
                fecha,
                coalesce(finca, ''),
                coalesce(bloque, ''),
                coalesce(sensor, '')
            order by id
        ) as duplicate_rank
    from public.variables_ambientales
)
select *
from ranked
where duplicate_rank > 1;

-- 3) Delete only repeated copies, keeping the first id.
with ranked as (
    select
        id,
        row_number() over (
            partition by
                fecha,
                coalesce(finca, ''),
                coalesce(bloque, ''),
                coalesce(sensor, '')
            order by id
        ) as duplicate_rank
    from public.variables_ambientales
)
delete from public.variables_ambientales target
using ranked
where target.id = ranked.id
  and ranked.duplicate_rank > 1;

-- 4) Prevent future duplicates.
create unique index if not exists uq_variables_ambientales_fecha_finca_bloque_sensor
on public.variables_ambientales (
    fecha,
    (coalesce(finca, '')),
    (coalesce(bloque, '')),
    (coalesce(sensor, ''))
);

analyze public.variables_ambientales;

-- 5) Final verification. This should return 0.
select
    'variables_ambientales' as table_name,
    count(*) as duplicate_rows_after
from (
    select
        id,
        count(*) over (
            partition by
                fecha,
                coalesce(finca, ''),
                coalesce(bloque, ''),
                coalesce(sensor, '')
        ) as duplicate_count
    from public.variables_ambientales
) audit
where duplicate_count > 1;
