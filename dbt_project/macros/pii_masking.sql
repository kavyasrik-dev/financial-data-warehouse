{% macro mask_email(column_name) -%}
    case
        when {{ column_name }} is null then null
        when position('@' in {{ column_name }}) = 0 then '***'
        else left(split_part({{ column_name }}, '@', 1), 1) || '***@' || split_part({{ column_name }}, '@', 2)
    end
{%- endmacro %}

{% macro mask_phone(column_name) -%}
    case
        when {{ column_name }} is null then null
        else repeat('*', greatest(length({{ column_name }}) - 4, 0)) || right({{ column_name }}, 4)
    end
{%- endmacro %}

{% macro mask_card(column_name) -%}
    case
        when {{ column_name }} is null then null
        else repeat('*', greatest(length({{ column_name }}) - 4, 0)) || right({{ column_name }}, 4)
    end
{%- endmacro %}

{% macro mask_name(column_name) -%}
    case
        when {{ column_name }} is null then null
        else (
            select string_agg(left(name_part, 1) || repeat('*', greatest(length(name_part) - 1, 0)), ' ')
            from regexp_split_to_table(trim({{ column_name }}), '\s+') as name_part
        )
    end
{%- endmacro %}
