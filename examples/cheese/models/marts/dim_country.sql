select distinct country
from {{ ref('stg_cheese') }}
order by country
