# Data quality report

The supplied file has **1,593,464 rows** and **47 columns**, using about 3902 MiB in memory. The project brief's figure of 52,216 rows does not describe this file.

Parsed transaction dates run from 1975-07-28 to 2025-11-07. 3 date strings did not parse as Gregorian dates. Their raw values are ['1420-01-30', '1422-11-23', '1417-02-04']. They are mortgage records and are excluded from the residential sale population.

## Duplicates

There are 1,001,280 distinct `transaction_id` values and 592,184 extra exact copies. Conflicting ids on price, area, procedure, and date: {'actual_worth': 0, 'procedure_area': 0, 'procedure_name_en': 0, 'instance_date': 0, 'area_name_en': 0}. Extra rows are exact copies of the same transaction_id. Economic fields do not conflict inside an id. Deduplication keeps one copy and is recorded in the filter log.

## Target and units

meter_sale_price matches actual_worth / procedure_area within rounding for virtually every row. It is a derived field, not an independent measurement. Using it as a feature to predict actual_worth would leak the target.
Rows with a relative difference above 1%: 25. Maximum absolute difference: 8.6633.

The file has no separate unit-of-measure column. meter_sale_price matches actual_worth / procedure_area, and the joint magnitudes (median area near a typical dwelling size, median worth in the low millions, median meter price in the thousands) are the Dubai Land Department convention of square meters and AED. This is an interpretation of the supplied fields, not a second measurement.

actual_worth is populated for sales, mortgages, and gifts. On mortgages it is a financing amount. On gifts and grants it is not an arm's-length market price. It is an appropriate transaction-price target only after the eligibility policy restricts rows to residential dwelling sales. meter_sale_price is the same information divided by area.

## What a user cannot supply at prediction time

These fields are excluded from the market-value model: `actual_worth`, `meter_sale_price`, `rent_value`, `meter_rent_price`, `no_of_parties_role_1`, `no_of_parties_role_2`, `no_of_parties_role_3`, `transaction_id`, `procedure_id`, `load_timestamp`, `procedure_name_en`, `trans_group_en`, `asking price (not in the file; must not be used as a model input)`.

`meter_sale_price` is a restatement of the target divided by area. Asking price is not in the file and is not a feature.

## Rental fields

After deduplication, 22,748 rows have `rent_value`. Transaction groups: {'Mortgages': 22748}.
Non-null rent fields are attached to lease-to-own and related mortgage procedures, not to a general set of rental contracts. They are not used to estimate market rent or yield. Sales rows carrying rent_value after deduplication: 0.

## Filters

                                 step  rows_before  rows_removed  rows_after
                             raw_load      1593464             0     1593464
        drop_redundant_arabic_columns      1593464             0     1593464
           deduplicate_transaction_id      1593464        592184     1001280
normalize_text_dates_bedrooms_parking      1001280             0     1001280
             assign_eligibility_flags      1001280             0     1001280
     select_primary_residential_sales      1001280        456808      544472
         primary_domain_outlier_rules       544472          1280      543192
        extended_domain_outlier_rules       586856          1429      585427

Cleaned rows: 1,001,280. Primary residential sales: 543,192. Primary plus delayed sales: 585,427.

Non-residential usages, mortgages, gifts, land, and buildings remain in `cleaned_transactions.parquet` with an exclusion reason. They are not silently deleted from the analytical file.
