# Community analytics

Growth rates use median AED per sqm and are reported only when both periods have at least 20 sales. Blank growth is an insufficient sample, not a zero change.

Cross-sectional dispersion is the median absolute deviation of AED per sqm divided by the median. It describes how spread out prices are in the sample. Time-series volatility is the standard deviation of quarter-to-quarter changes in the quarterly median, and it is blank when there are fewer than six usable changes. A high price level is not labeled as high volatility.

Activity, stability, growth, and data-confidence scores are percentile or log-sample descriptions. They are not investment recommendations.

## Requested names

- master_project `Dubai Marina`: 38,897 primary residential sales out of 59,653 deduplicated rows. Property types across all procedures: {'Building': 173, 'Land': 111, 'Unit': 59265, 'Villa': 104}.
- master_project `DownTown Dubai`: 23,740 primary residential sales out of 43,577 deduplicated rows. Property types across all procedures: {'Building': 54, 'Land': 103, 'Unit': 43420}.
- master_project `The Greens`: 8,458 primary residential sales out of 16,312 deduplicated rows. Property types across all procedures: {'Building': 18, 'Land': 7, 'Unit': 16287}.
- master_project `Al Furjan`: 7,719 primary residential sales out of 19,886 deduplicated rows. Property types across all procedures: {'Building': 39, 'Land': 3732, 'Unit': 12343, 'Villa': 3772}.
- master_project `The Gardens`: 0 primary residential sales out of 3 deduplicated rows. Property types across all procedures: {'Land': 3}.

The Gardens has 0 primary residential dwelling sales across its registry rows. The valuation API refuses communities below 30 such sales instead of returning an unsupported estimate.

Community summary rows: 269 across official areas and master projects. Latest complete quarter on those rows: 2025Q3.

Detail is in `data/analytics/community_summary.parquet` and the monthly, quarterly, property-type, and bedroom metric files.
