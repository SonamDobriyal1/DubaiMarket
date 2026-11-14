# Prediction interval validation

This is a prediction interval for an individual property's potential transaction price. It is not a confidence interval for a mean price. Overall coverage near the nominal level does not guarantee the same coverage in every community.

Nominal coverage: 0.9. Method: absolute percentage residual |y-pred|/pred.

Calibration window: {"start": "2024-10-24", "end_exclusive": "2025-02-12", "n": 27436}.

Test empirical coverage: 0.8713698026348009. Mean width: 1203491.618525282 AED. Median width: 763192.7220971838 AED. Test interval rows: 81676.

Segment coverage is in the same JSON under `segments`. A nominal 90% interval does not promise 90% coverage inside every community or for an individual property.

The interval is a range for one property's potential transaction price. It is not a confidence interval for the average price of similar properties.
