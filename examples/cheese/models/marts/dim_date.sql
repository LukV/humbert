select distinct
    year,
    make_date(year, 1, 1) as production_date
from {{ ref('stg_cheese') }}
order by year
