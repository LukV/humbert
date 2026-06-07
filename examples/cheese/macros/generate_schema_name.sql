{# Use custom schema names verbatim (no target-schema prefix), so models land in
   exactly `staging` / `marts` and Humbert's exposed_schemas match the manifest. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
