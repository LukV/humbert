-- Daily time spine MetricFlow requires for time-based metrics.
-- Range covers full FAOSTAT history (1961→) with headroom.
select cast(generate_series as date) as date_day
from generate_series(timestamp '1960-01-01', timestamp '2027-12-31', interval 1 day)
