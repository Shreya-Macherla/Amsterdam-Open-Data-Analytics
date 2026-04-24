"""
Amsterdam Open Data Analytics
Analyses Amsterdam Airbnb listings (Inside Airbnb) with geospatial mapping.

Data sources (all free, no API key required):
  Listings: http://insideairbnb.com/get-the-data/ → Amsterdam → listings.csv.gz
  Neighbourhoods GeoJSON: same page → neighbourhoods.geojson

Run: python amsterdam_analysis.py
Outputs: outputs/ folder with charts and an interactive Folium map.
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
os.makedirs("outputs", exist_ok=True)

# Optional geospatial imports
try:
    import geopandas as gpd
    import folium
    from folium.plugins import HeatMap
    GEO_AVAILABLE = True
except ImportError:
    GEO_AVAILABLE = False
    print("[WARN]  geopandas/folium not installed — skipping map outputs")


# ---------------------------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------------------------

def load_listings(path: str = "data/listings.csv") -> pd.DataFrame:
    if os.path.exists(path):
        df = pd.read_csv(path, low_memory=False)
    elif os.path.exists(path + ".gz"):
        df = pd.read_csv(path + ".gz", low_memory=False)
    else:
        print(f"[DATA]  {path} not found — generating synthetic data")
        return _generate_synthetic()

    # Standardise price column
    if "price" in df.columns and df["price"].dtype == object:
        df["price"] = df["price"].str.replace(r"[$,]", "", regex=True).astype(float)

    df = df[df["price"].between(5, 2000)].copy()  # remove outliers
    print(f"[DATA]  Loaded {len(df):,} listings from {path}")
    return df


def _generate_synthetic() -> pd.DataFrame:
    """Generates ~1,000 synthetic Amsterdam Airbnb listings."""
    rng = np.random.default_rng(42)
    neighbourhoods = [
        "Centrum-West", "Centrum-Oost", "De Pijp - Rivierenbuurt",
        "Westerpark", "Oud-West", "IJburg - Zeeburgereiland",
        "Noord-West", "Noord-Oost", "Bos en Lommer",
        "Geuzenveld - Slotermeer", "Watergraafsmeer", "Oost",
    ]
    n = 1000
    neigh = rng.choice(neighbourhoods, n, p=[0.15, 0.14, 0.12, 0.09, 0.09,
                                               0.08, 0.07, 0.07, 0.06, 0.05, 0.04, 0.04])
    price_base = {"Centrum-West": 140, "Centrum-Oost": 130, "De Pijp - Rivierenbuurt": 110,
                  "Westerpark": 95, "Oud-West": 105, "IJburg - Zeeburgereiland": 90}
    prices = np.array([
        rng.lognormal(np.log(price_base.get(nb, 85)), 0.4) for nb in neigh
    ]).round(0)

    return pd.DataFrame({
        "id": range(1, n + 1),
        "neighbourhood_cleansed": neigh,
        "room_type": rng.choice(
            ["Entire home/apt", "Private room", "Shared room", "Hotel room"],
            n, p=[0.62, 0.30, 0.04, 0.04]
        ),
        "price": prices,
        "availability_365": rng.integers(0, 365, n),
        "number_of_reviews": rng.integers(0, 200, n),
        "latitude": rng.uniform(52.32, 52.43, n),
        "longitude": rng.uniform(4.82, 5.00, n),
        "minimum_nights": rng.integers(1, 7, n),
    })


# ---------------------------------------------------------------------------
# 2. KEY METRICS
# ---------------------------------------------------------------------------

def compute_neighbourhood_stats(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("neighbourhood_cleansed")
        .agg(
            listings=("id", "count"),
            avg_price=("price", "mean"),
            median_price=("price", "median"),
            avg_availability=("availability_365", "mean"),
        )
        .round(2)
        .sort_values("listings", ascending=False)
        .reset_index()
        .rename(columns={"neighbourhood_cleansed": "neighbourhood"})
    )


# ---------------------------------------------------------------------------
# 3. CHARTS
# ---------------------------------------------------------------------------

def plot_price_by_neighbourhood(stats: pd.DataFrame):
    top = stats.nlargest(12, "median_price")
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(top["neighbourhood"], top["median_price"], color="#4C72B0", edgecolor="white")
    for bar, val in zip(bars, top["median_price"]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"€{val:.0f}", va="center", fontsize=9)
    ax.set_title("Median Nightly Price by Neighbourhood", fontsize=14, fontweight="bold")
    ax.set_xlabel("Median Price (€)")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig("outputs/price_by_neighbourhood.png", dpi=150)
    plt.close()
    print("[PLOT]  Saved outputs/price_by_neighbourhood.png")


def plot_room_type_mix(df: pd.DataFrame):
    mix = df["room_type"].value_counts()
    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]
    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        mix, labels=mix.index, autopct="%1.1f%%",
        colors=colors[:len(mix)], startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    ax.set_title("Amsterdam Listings by Room Type", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig("outputs/room_type_mix.png", dpi=150)
    plt.close()
    print("[PLOT]  Saved outputs/room_type_mix.png")


def plot_price_distribution(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(df["price"], bins=60, color="#4C72B0", edgecolor="white", alpha=0.8)
    axes[0].set_title("Price Distribution (all listings)", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Price per Night (€)")
    axes[0].set_ylabel("Number of Listings")

    room_order = df.groupby("room_type")["price"].median().sort_values(ascending=False).index
    sns.boxplot(data=df, x="room_type", y="price", order=room_order,
                palette="muted", ax=axes[1], showfliers=False)
    axes[1].set_title("Price Distribution by Room Type", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Price per Night (€)")
    axes[1].tick_params(axis="x", rotation=15)

    plt.tight_layout()
    plt.savefig("outputs/price_distribution.png", dpi=150)
    plt.close()
    print("[PLOT]  Saved outputs/price_distribution.png")


def create_interactive_map(df: pd.DataFrame, output_path: str = "outputs/amsterdam_map.html"):
    if not GEO_AVAILABLE:
        return
    m = folium.Map(location=[52.3676, 4.9041], zoom_start=12, tiles="CartoDB positron")

    heat_data = df[["latitude", "longitude"]].dropna().values.tolist()
    HeatMap(heat_data, radius=8, blur=10, min_opacity=0.4).add_to(m)

    m.save(output_path)
    print(f"[MAP]   Saved interactive map → {output_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n[START] Amsterdam Open Data Analytics\n")
    df = load_listings()

    print("\n[KPIs]")
    print(f"  Total listings      : {len(df):,}")
    print(f"  Median price        : €{df['price'].median():.2f}")
    print(f"  Most common type    : {df['room_type'].mode()[0]}")
    print(f"  Avg availability    : {df['availability_365'].mean():.0f} days/year\n")

    stats = compute_neighbourhood_stats(df)
    print("[STATS] Top 5 neighbourhoods by listing count:")
    print(stats.head().to_string(index=False))

    print("\n[PLOT]  Generating charts...")
    plot_price_by_neighbourhood(stats)
    plot_room_type_mix(df)
    plot_price_distribution(df)
    create_interactive_map(df)
    print("\n[DONE]  All outputs saved to outputs/")
