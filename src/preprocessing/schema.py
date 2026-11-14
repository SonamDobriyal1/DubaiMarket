"""Column roles for the Dubai Land Department transaction extract."""

from __future__ import annotations

ARABIC_COLUMNS = [
    "trans_group_ar",
    "procedure_name_ar",
    "property_type_ar",
    "property_sub_type_ar",
    "property_usage_ar",
    "reg_type_ar",
    "area_name_ar",
    "building_name_ar",
    "project_name_ar",
    "master_project_ar",
    "nearest_landmark_ar",
    "nearest_metro_ar",
    "nearest_mall_ar",
    "rooms_ar",
]

ENGLISH_PARALLEL = {
    "trans_group_ar": "trans_group_en",
    "procedure_name_ar": "procedure_name_en",
    "property_type_ar": "property_type_en",
    "property_sub_type_ar": "property_sub_type_en",
    "property_usage_ar": "property_usage_en",
    "reg_type_ar": "reg_type_en",
    "area_name_ar": "area_name_en",
    "building_name_ar": "building_name_en",
    "project_name_ar": "project_name_en",
    "master_project_ar": "master_project_ar",
    "nearest_landmark_ar": "nearest_landmark_en",
    "nearest_metro_ar": "nearest_metro_en",
    "nearest_mall_ar": "nearest_mall_en",
    "rooms_ar": "rooms_en",
}

# master_project_ar parallels master_project_en, not itself.
ENGLISH_PARALLEL["master_project_ar"] = "master_project_en"

IDENTIFIER_COLUMNS = [
    "transaction_id",
    "procedure_id",
    "trans_group_id",
    "property_type_id",
    "property_sub_type_id",
    "reg_type_id",
    "area_id",
    "project_number",
]

# Known only after a transaction is registered, or deterministic functions of the target.
LEAKAGE_OR_UNAVAILABLE = [
    "actual_worth",
    "meter_sale_price",
    "rent_value",
    "meter_rent_price",
    "no_of_parties_role_1",
    "no_of_parties_role_2",
    "no_of_parties_role_3",
    "transaction_id",
    "procedure_id",
    "load_timestamp",
    "procedure_name_en",
    "trans_group_en",
]

TARGET_COLUMN = "actual_worth"
PSM_COLUMN = "meter_sale_price"
AREA_COLUMN = "procedure_area"

TEXT_COLUMNS = [
    "area_name_en",
    "building_name_en",
    "project_name_en",
    "master_project_en",
    "nearest_landmark_en",
    "nearest_metro_en",
    "nearest_mall_en",
    "property_type_en",
    "property_sub_type_en",
    "property_usage_en",
    "reg_type_en",
    "procedure_name_en",
    "trans_group_en",
    "rooms_en",
]
