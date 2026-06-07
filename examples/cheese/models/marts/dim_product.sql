-- Milk source: cow / sheep / goat / buffalo, derived from the FAOSTAT item name.
select distinct
    product,
    case
        when product ilike '%sheep%' then 'sheep'
        when product ilike '%goat%' then 'goat'
        when product ilike '%buffalo%' then 'buffalo'
        else 'cow'
    end as milk_source
from {{ ref('stg_cheese') }}
order by product
