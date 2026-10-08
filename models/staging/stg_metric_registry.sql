select metric_key, status, has_zero_guard, note from {{ ref('metric_registry') }}
