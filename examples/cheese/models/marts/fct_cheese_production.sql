select
    country,
    product,
    year,
    production_date,
    production_tonnes
from {{ ref('stg_cheese') }}
