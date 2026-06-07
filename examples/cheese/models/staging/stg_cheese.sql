with raw as (
    select * from {{ ref('cheese_production') }}
)

select
    cast(area as varchar)                       as country,
    cast(item as varchar)                       as product,
    cast(year as integer)                       as year,
    make_date(cast(year as integer), 1, 1)      as production_date,
    cast(value_tonnes as double)                as production_tonnes
from raw
