import os
import pandas as pd

CSV_FILE = "medicines.csv"

LABELS = {
    "name": "Medicine Name",
    "price": "Price (Rs)",
    "category": "Category",
    "generic": "Generic",
    "manufacturer": "Brand / Manufacturer",
    "pack_size": "Pack Size",
    "form": "Form",
    "availability": "Availability",
}

DISPLAY_ORDER = ["name", "price", "category", "generic", "manufacturer", "pack_size", "form", "availability"]

MISSING = "N/A"


def load_medicines(path=CSV_FILE):
    if not os.path.exists(path):
        return None, f"{path} was not found. Run 'python scraper.py' first to create it."
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return None, f"{path} is empty. Run 'python scraper.py' to fill it."
    except Exception as error:
        return None, f"{path} could not be read: {error}"
    if df.empty or "name" not in df.columns:
        return None, f"{path} has no medicine records."
    for column in df.columns:
        df[column] = df[column].str.strip()
    df = df[df["name"] != ""]
    if "product_url" in df.columns:
        df = df.drop_duplicates(subset="product_url")
    else:
        df = df.drop_duplicates()
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"].str.replace(",", ""), errors="coerce")
    for column in df.columns:
        if column != "price":
            df[column] = df[column].replace("", MISSING)
    df = df.reset_index(drop=True)
    if df.empty:
        return None, f"{path} has no medicine records."
    return df, None


def visible_columns(df):
    columns = []
    for column in DISPLAY_ORDER:
        if column not in df.columns:
            continue
        if column == "price":
            if df[column].notna().any():
                columns.append(column)
        elif (df[column] != MISSING).any():
            columns.append(column)
    return columns


def unique_values(df, column):
    if column not in df.columns:
        return []
    values = df[column][df[column] != MISSING].unique().tolist()
    return sorted(values, key=lambda value: value.lower())


def apply_filters(df, name="", category="All", manufacturer="All", min_price=None, max_price=None):
    result = df
    if name and name.strip():
        result = result[result["name"].str.contains(name.strip(), case=False, regex=False)]
    if category and category != "All" and "category" in result.columns:
        result = result[result["category"] == category]
    if manufacturer and manufacturer != "All" and "manufacturer" in result.columns:
        result = result[result["manufacturer"] == manufacturer]
    if "price" in result.columns:
        if min_price is not None:
            result = result[result["price"] >= min_price]
        if max_price is not None:
            result = result[result["price"] <= max_price]
    return result


def summary(df):
    total = len(df)
    categories = len(unique_values(df, "category"))
    available = "N/A"
    if "availability" in df.columns and (df["availability"] != MISSING).any():
        available = f"{df['availability'].str.lower().str.startswith('in stock').sum():,}"
    return {"total": f"{total:,}", "available": available, "categories": f"{categories:,}"}
