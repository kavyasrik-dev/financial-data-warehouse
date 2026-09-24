{{ config(materialized='table') }}

with dates as (
    select generate_series(
        '2020-01-01'::date,
        '2035-12-31'::date,
        interval '1 day'
    )::date as full_date
)

select
    to_char(full_date, 'YYYYMMDD')::integer as date_key,
    full_date,
    extract(day from full_date)::integer as day,
    extract(month from full_date)::integer as month,
    extract(quarter from full_date)::integer as quarter,
    extract(year from full_date)::integer as year,
    extract(week from full_date)::integer as week,
    extract(isodow from full_date)::integer as day_of_week,
    to_char(full_date, 'FMDay') as day_name,
    to_char(full_date, 'FMMonth') as month_name,
    extract(isodow from full_date)::integer in (6, 7) as is_weekend
from dates
