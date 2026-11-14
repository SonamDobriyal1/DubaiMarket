# Preprocessing report

The eligibility policy keeps arm's-length residential dwelling sales and leaves every other row in the cleaned file with a reason.

Primary procedures are `Sell` and `Sell - Pre registration`. `Delayed Sell` is retained only in the extended file because it is a real consideration with deferred registration, not an ordinary spot sale. Development registrations, sale-on-payment-plan, lease-to-own, gifts, grants, and every mortgage procedure are out of the valuation population.

Property scope is Residential usage and Unit or Villa. Subtypes kept are Flat, Villa, Stacked Townhouses, Hotel Apartment, and missing subtype. Office, shop, and other non-dwelling subtypes are excluded even if the usage field says Residential.

Domain screens remove unit area outside [20, 2000] sqm, villa area outside [50, 10000] sqm, and AED per sqm outside [200, 250000]. The upper AED/sqm bound is an inconsistency ceiling. High prices below it stay in the model.

                                 step  rows_before  rows_removed  rows_after
                             raw_load      1593464             0     1593464
        drop_redundant_arabic_columns      1593464             0     1593464
           deduplicate_transaction_id      1593464        592184     1001280
normalize_text_dates_bedrooms_parking      1001280             0     1001280
             assign_eligibility_flags      1001280             0     1001280
     select_primary_residential_sales      1001280        456808      544472
         primary_domain_outlier_rules       544472          1280      543192
        extended_domain_outlier_rules       586856          1429      585427

Primary date span: 1993-01-27 to 2025-11-07.

Whitespace was collapsed. Case-only label variants were not merged, because a case difference can be a different project. User input matching is case-insensitive and returns an error when it is ambiguous.

Bedroom labels: Studio is 0. `N B/R` is N. Penthouse, single room, office, shop, and other non-count labels stay missing, with a penthouse flag when the label is PENTHOUSE.
