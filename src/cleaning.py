"""
Stage 1: Raw House 1 Inspection and Cleaning Pipeline.
Handles:
- Timestamp parsing & sorting
- Deduplication with stated policy (mean of readings at identical timestamps)
- Sensor limit handling (clamping / setting impossible spikes > 4,000 W to NaN for IAMs)
- Resampling to 1-minute intervals ('1min' mean)
- Short-gap interpolation (<= 2 min) vs. Long outage preservation (> 2 min)
- Before/after visualization for Aggregate and appliance channels
"""

import os
import time
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RAW_DIR = r"D:\REFIT\REFIT_RAW_081116"
OUTPUT_FIG_DIR = r"d:\flockenergy_hitesh\outputs\figures"
OUTPUT_TAB_DIR = r"d:\flockenergy_hitesh\outputs\tables"
PROCESSED_DATA_DIR = r"d:\flockenergy_hitesh\data"

os.makedirs(OUTPUT_FIG_DIR, exist_ok=True)
os.makedirs(OUTPUT_TAB_DIR, exist_ok=True)
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)


def clean_house1_pipeline():
    """Runs the full cleaning pipeline on raw House 1 data and exports cleaned 1-min data and plots."""
    p1 = os.path.join(RAW_DIR, "RAW_House1_Part1.csv")
    p2 = os.path.join(RAW_DIR, "RAW_House1_Part2.csv")

    print("Step 1: Loading raw datasets...")
    t0 = time.time()
    df1 = pd.read_csv(p1)
    df2 = pd.read_csv(p2)
    df_raw = pd.concat([df1, df2], ignore_index=True)
    print(f"Loaded {len(df_raw):,} combined rows in {time.time() - t0:.2f}s")

    print("\nStep 2: Parsing timestamps and sorting...")
    df_raw['DateTime'] = pd.to_datetime(df_raw['Time'], errors='coerce')
    df_raw = df_raw.dropna(subset=['DateTime'])
    df_raw = df_raw.sort_values('DateTime').reset_index(drop=True)

    print("\nStep 3: Removing impossible sensor spikes...")
    # Physical sensor limits: UK IAM plugs rated max 4000 W (13A * 230V ~ 3000 W)
    appliance_cols = [f"Appliance{i}" for i in range(1, 10)]
    for app in appliance_cols:
        # Flag and replace values > 4000 W or < 0 W with NaN
        invalid_mask = (df_raw[app] > 4000) | (df_raw[app] < 0)
        invalid_count = invalid_mask.sum()
        if invalid_count > 0:
            print(f"  {app}: {invalid_count:,} sensor spike values (>4000W) set to NaN")
            df_raw.loc[invalid_mask, app] = np.nan

    # Aggregate mains: clamp extreme artifacts (> 15,000 W or < 0 W)
    invalid_agg = (df_raw['Aggregate'] > 15000) | (df_raw['Aggregate'] < 0)
    print(f"  Aggregate: {invalid_agg.sum():,} extreme spikes (>15,000W) set to NaN")
    df_raw.loc[invalid_agg, 'Aggregate'] = np.nan

    print("\nStep 4: Handling duplicates (Rule: Mean aggregation at identical timestamps)...")
    power_cols = ['Aggregate'] + appliance_cols
    # Deduplicate by grouping on DateTime and calculating mean of available readings
    df_dedup = df_raw.groupby('DateTime')[power_cols].mean()
    print(f"Deduplicated to {len(df_dedup):,} unique timestamps")

    print("\nStep 5: Resampling to regular 1-minute intervals ('1min' grid)...")
    # Resample to 1-minute frequency using mean
    df_1min = df_dedup.resample('1min').mean()
    print(f"Resampled 1-minute grid: {len(df_1min):,} total minutes from {df_1min.index[0]} to {df_1min.index[-1]}")

    print("\nStep 6: Handling gaps (Rule: Interpolate short gaps <= 2 min; preserve long outages > 2 min)...")
    # Mark boolean mask of missing minutes before interpolation
    was_missing = df_1min['Aggregate'].isna()

    # Calculate gap lengths using run-length encoding
    is_na = was_missing.astype(int)
    blocks = (is_na != is_na.shift()).cumsum()
    gap_lengths = is_na.groupby(blocks).transform('sum') * is_na

    # Flag outages: gaps strictly > 2 consecutive minutes
    is_outage = gap_lengths > 2
    df_1min['Is_Outage'] = is_outage

    print(f"  Total missing 1-min intervals in grid: {was_missing.sum():,} ({was_missing.mean()*100:.2f}%)")
    print(f"  Missing intervals flagged as long outages (>2 min): {is_outage.sum():,} ({is_outage.mean()*100:.2f}%)")
    short_gap_count = was_missing.sum() - is_outage.sum()
    print(f"  Missing intervals within short gaps (<=2 min): {short_gap_count:,}")

    # Interpolate short gaps (limit=2 forward fill / linear interpolation)
    df_cleaned = df_1min[power_cols].interpolate(method='time', limit=2)
    # Re-apply NaN to long outages to guarantee they are strictly preserved
    for col in power_cols:
        df_cleaned.loc[is_outage, col] = np.nan

    df_cleaned['Is_Outage'] = is_outage

    # Summary table of cleaned dataset
    clean_stats = []
    for c in power_cols:
        clean_stats.append({
            'Channel': c,
            'Valid 1-min Points': df_cleaned[c].notna().sum(),
            'Outage (NaN) Points': df_cleaned[c].isna().sum(),
            'Mean (W)': round(df_cleaned[c].mean(), 2),
            'Max (W)': round(df_cleaned[c].max(), 2),
            'Median (W)': round(df_cleaned[c].median(), 2)
        })
    clean_summary_df = pd.DataFrame(clean_stats)
    clean_summary_df.to_csv(os.path.join(OUTPUT_TAB_DIR, "house1_cleaned_1min_summary.csv"), index=False)
    print("\nCleaned 1-minute dataset summary:")
    print(clean_summary_df.to_string(index=False))

    print("\nStep 7: Generating Before vs. After Cleaning Plots...")
    # Select a 48-hour representative window with appliance usage, sensor noise, and a short gap
    # Window: 2014-03-05 to 2014-03-07
    start_ts = pd.Timestamp("2014-03-05 00:00:00")
    end_ts = pd.Timestamp("2014-03-07 00:00:00")

    raw_window = df_raw[(df_raw['DateTime'] >= start_ts) & (df_raw['DateTime'] <= end_ts)].set_index('DateTime')
    clean_window = df_cleaned[(df_cleaned.index >= start_ts) & (df_cleaned.index <= end_ts)]

    fig, axes = plt.subplots(3, 2, figsize=(16, 10), sharex='col')

    # Channel 1: Aggregate Power
    axes[0, 0].plot(raw_window.index, raw_window['Aggregate'], color='darkblue', alpha=0.7, lw=0.8)
    axes[0, 0].set_title("Before Cleaning: Raw Aggregate Power (~8s)", fontsize=11, fontweight='bold')
    axes[0, 0].set_ylabel("Power (W)", fontsize=10)
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].plot(clean_window.index, clean_window['Aggregate'], color='navy', lw=1.2)
    axes[0, 1].set_title("After Cleaning: Resampled Aggregate Power (1-min)", fontsize=11, fontweight='bold')
    axes[0, 1].set_ylabel("Power (W)", fontsize=10)
    axes[0, 1].grid(True, alpha=0.3)

    # Channel 2: Appliance 1 (Fridge)
    axes[1, 0].plot(raw_window.index, raw_window['Appliance1'], color='crimson', alpha=0.7, lw=0.8)
    axes[1, 0].set_title("Before Cleaning: Raw Appliance 1 (Fridge)", fontsize=11, fontweight='bold')
    axes[1, 0].set_ylabel("Power (W)", fontsize=10)
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(clean_window.index, clean_window['Appliance1'], color='darkred', lw=1.2)
    axes[1, 1].set_title("After Cleaning: Resampled Appliance 1 (Fridge)", fontsize=11, fontweight='bold')
    axes[1, 1].set_ylabel("Power (W)", fontsize=10)
    axes[1, 1].grid(True, alpha=0.3)

    # Channel 3: Appliance 5 (Washing Machine)
    axes[2, 0].plot(raw_window.index, raw_window['Appliance5'], color='forestgreen', alpha=0.7, lw=0.8)
    axes[2, 0].set_title("Before Cleaning: Raw Appliance 5 (Washing Machine)", fontsize=11, fontweight='bold')
    axes[2, 0].set_ylabel("Power (W)", fontsize=10)
    axes[2, 0].set_xlabel("Timestamp", fontsize=10)
    axes[2, 0].grid(True, alpha=0.3)

    axes[2, 1].plot(clean_window.index, clean_window['Appliance5'], color='darkgreen', lw=1.2)
    axes[2, 1].set_title("After Cleaning: Resampled Appliance 5 (Washing Machine)", fontsize=11, fontweight='bold')
    axes[2, 1].set_ylabel("Power (W)", fontsize=10)
    axes[2, 1].set_xlabel("Timestamp", fontsize=10)
    axes[2, 1].grid(True, alpha=0.3)

    plt.suptitle("House 1: Before vs. After Cleaning & 1-Minute Resampling (Representative 48h Window)", 
                 fontsize=13, fontweight='bold', y=0.99)
    plt.tight_layout()

    plot_path = os.path.join(OUTPUT_FIG_DIR, "house1_cleaning_before_after.png")
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\nSaved before/after plot to: {plot_path}")

    # Save a sample of cleaned data for House 1
    sample_clean_path = os.path.join(PROCESSED_DATA_DIR, "House1_cleaned_1min_sample.csv")
    df_cleaned.head(50000).to_csv(sample_clean_path)
    print(f"Saved sample cleaned data to: {sample_clean_path}")

    return df_cleaned


if __name__ == "__main__":
    clean_house1_pipeline()
