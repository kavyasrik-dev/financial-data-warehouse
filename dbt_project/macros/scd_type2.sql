{% macro customer_scd_record_hash(
    email_column='email',
    phone_column='phone',
    address_column='address',
    city_column='city',
    state_column='state',
    country_column='country',
    status_column='customer_status'
) -%}
    md5(concat_ws('|',
        coalesce({{ email_column }}, ''),
        coalesce({{ phone_column }}, ''),
        coalesce({{ address_column }}, ''),
        coalesce({{ city_column }}, ''),
        coalesce({{ state_column }}, ''),
        coalesce({{ country_column }}, ''),
        coalesce({{ status_column }}, '')
    ))
{%- endmacro %}
