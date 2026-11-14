# Exploratory analysis

All figures below use the primary residential sale population after the documented screens. Associations are descriptive.

Transactions: 543,192. Total value: 1,048,707,555,928 AED. Median price: 1,268,440 AED. Mean price: 1,930,639 AED. Median AED per sqm: 13,552.

Dates: 1993-01-27 to 2025-11-07. The latest complete quarter used for growth is 2025Q3, because the file ends before the end of the following quarter.

Official-area concentration: top 10 areas account for 52.7% of primary sales. The Herfindahl index of area transaction shares is 0.040.

Registration mix:

                       size     median
reg_type_en                           
Existing Properties  236572  1132835.0
Off-Plan Properties  306620  1339000.0

Year counts for the primary population are in the modeling table and the monthly chart data at `reports/figures/data/monthly_market.csv`.

Earliest primary-sale year in this frame: 1993 (1 sales). Latest year: 2025 (91,186 sales).

Interactive charts, when generated, are HTML files in `reports/figures/`. Scatter and box charts use random samples and say so in the title. Rankings of median AED per sqm require at least 50 sales so a handful of transactions cannot define the top or bottom of the market.

Price rises with size, but not linearly, and AED per sqm differs by community, type, and existing versus off-plan. Those are associations in the registered sales, not effects of changing one attribute while holding the market constant.
