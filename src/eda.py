"""
Stage 2: Exploratory Analysis of Washing-Machine Use (Clean REFIT Data).
Optimized for fast processing and caching.
Across at least 4 households at 1-minute resolution:
- House 1 (Appliance 5)
- House 2 (Appliance 2)
- House 3 (Appliance 6)
- House 5 (Appliance 3)
"""

import os
import time
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CLEAN_DIR = r"D:\REFIT\CLEAN_REFIT_081116"
OUTPUT_FIG_DIR = r"d:\flockenergy_hitesh\outputs\figures"
OUTPUT_TAB_DIR = r"d:\flockenergy_hitesh\outputs\tables"
PROCESSED_DATA_DIR = r"d:\flockenergy_hitesh\data"

os.makedirs(OUTPUT_FIG_DIR, exist_ok=True)
os.makedirs(OUTPUT_TAB_DIR, exist_ok=True)
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

HOUSE_CONFIG = {
    'House 1': {'file': 'CLEAN_House1.csv', 'wm_col': 'Appliance5'},
    'House 2': {'file': 'CLEAN_House2.csv', 'wm_col': 'Appliance2'},
    'House 3': {'file': 'CLEAN_House3.csv', 'wm_col': 'Appliance6'},
    'House 5': {'file': 'CLEAN_House5.csv', 'wm_col': 'Appliance3'}
}

ON_POWER_THRESHOLD = 20.0     # Watts
MAX_INTERNAL_GAP_MIN = 5      # Consecutive minutes of pause allowed within a cycle
MIN_CYCLE_DURATION_MIN = 15   # Minimum total minutes for a valid wash cycle


def load_and_resample_house(house_name, config):
    """Loads a clean house CSV with fast date parsing and caches the 1-minute resampled series."""
    cache_path = os.path.join(PROCESSED_DATA_DIR, f"{house_name.replace(' ', '')}_1min.csv")
    
    if os.path.exists(cache_path):
        print(f"Loading {house_name} from 1-min cache: {cache_path}...", flush=True)
        df_1min = pd.read_csv(cache_path, index_col='DateTime', parse_dates=True)
        return df_1min

    file_path = os.path.join(CLEAN_DIR, config['file'])
    print(f"Reading {house_name} from {config['file']} (first time, caching to CSV)...", flush=True)
    t0 = time.time()
    
    cols = ['Time', 'Aggregate', config['wm_col']]
    df = pd.read_csv(file_path, usecols=cols)
    df.rename(columns={config['wm_col']: 'WashingMachine'}, inplace=True)
    
    # Fast date parsing with explicit format
    df['DateTime'] = pd.to_datetime(df['Time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df = df.dropna(subset=['DateTime']).set_index('DateTime').sort_index()
    
    df_1min = df[['Aggregate', 'WashingMachine']].resample('1min').mean()
    df_1min.to_csv(cache_path)
    print(f"  {house_name} cached to {cache_path} ({len(df_1min):,} minutes, {time.time() - t0:.2f}s)", flush=True)
    return df_1min


def detect_washing_cycles(wm_series, p_thresh=ON_POWER_THRESHOLD, max_gap=MAX_INTERNAL_GAP_MIN, min_dur=MIN_CYCLE_DURATION_MIN):
    """Vectorized detection of washing machine cycles."""
    is_active = (wm_series >= p_thresh) & wm_series.notna()
    if not is_active.any():
        return pd.DataFrame(), pd.Series(False, index=wm_series.index)
    
    active_ff = is_active.replace(False, np.nan).ffill(limit=max_gap).fillna(False)
    active_bf = is_active.replace(False, np.nan).bfill(limit=max_gap).fillna(False)
    bridged_active = (active_ff & active_bf).astype(bool)
    
    cycle_id = (bridged_active != bridged_active.shift()).cumsum()
    cycle_id = cycle_id.where(bridged_active, np.nan)
    
    df_active = pd.DataFrame({
        'power': wm_series[bridged_active],
        'cycle_id': cycle_id[bridged_active],
        'time': wm_series.index[bridged_active]
    })
    
    stats = df_active.groupby('cycle_id').agg(
        start_time=('time', 'first'),
        end_time=('time', 'last'),
        duration_min=('power', 'count'),
        peak_power_w=('power', 'max'),
        energy_wh=('power', lambda s: (s.fillna(0).sum()) / 60.0),
        mean_active_power_w=('power', 'mean')
    )
    
    valid_cycles = stats[(stats['duration_min'] >= min_dur) & (stats['peak_power_w'] >= 100.0)].copy()
    valid_cycles['duration_min'] = valid_cycles['duration_min'].astype(int)
    valid_cycles['peak_power_w'] = valid_cycles['peak_power_w'].round(1)
    valid_cycles['energy_wh'] = valid_cycles['energy_wh'].round(2)
    valid_cycles['mean_active_power_w'] = valid_cycles['mean_active_power_w'].round(1)
    valid_cycles['start_hour'] = valid_cycles['start_time'].dt.hour
    valid_cycles['start_weekday'] = valid_cycles['start_time'].dt.day_name()
    
    valid_cycle_ids = set(valid_cycles.index)
    final_cycle_mask = cycle_id.isin(valid_cycle_ids)
    
    return valid_cycles.reset_index(drop=True), final_cycle_mask


def run_eda_pipeline():
    house_data = {}
    house_cycles = {}
    eda_summary = []
    
    for h_name, cfg in HOUSE_CONFIG.items():
        df_1m = load_and_resample_house(h_name, cfg)
        house_data[h_name] = df_1m
        
        cycles_df, cycle_mask = detect_washing_cycles(df_1m['WashingMachine'])
        house_cycles[h_name] = cycles_df
        
        total_minutes = len(df_1m)
        missing_minutes = df_1m['WashingMachine'].isna().sum()
        valid_minutes = total_minutes - missing_minutes
        
        off_standby_minutes = ((df_1m['WashingMachine'] < ON_POWER_THRESHOLD) & df_1m['WashingMachine'].notna()).sum()
        active_minutes = (df_1m['WashingMachine'] >= ON_POWER_THRESHOLD).sum()
        
        start_date = df_1m.index[0].strftime('%Y-%m-%d')
        end_date = df_1m.index[-1].strftime('%Y-%m-%d')
        days_covered = round((df_1m.index[-1] - df_1m.index[0]).total_seconds() / 86400, 1)
        
        eda_summary.append({
            'Household': h_name,
            'WM Channel': cfg['wm_col'],
            'Start Date': start_date,
            'End Date': end_date,
            'Total Days': days_covered,
            'Missing / NaN (%)': round(missing_minutes / total_minutes * 100, 2),
            'Standby / Off (%)': round(off_standby_minutes / valid_minutes * 100, 2),
            'Active Time (%)': round(active_minutes / valid_minutes * 100, 2),
            'Detected Cycles': len(cycles_df),
            'Cycles/Week': round(len(cycles_df) / (days_covered / 7.0), 2),
            'Median Duration (min)': round(cycles_df['duration_min'].median(), 1) if len(cycles_df) else 0,
            'Median Peak Power (W)': round(cycles_df['peak_power_w'].median(), 1) if len(cycles_df) else 0,
            'Median Energy (Wh)': round(cycles_df['energy_wh'].median(), 1) if len(cycles_df) else 0
        })
        print(f"  {h_name}: Detected {len(cycles_df)} valid washing machine cycles.", flush=True)
        
    summary_df = pd.DataFrame(eda_summary)
    summary_path = os.path.join(OUTPUT_TAB_DIR, "wm_cross_house_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print("\nCross-Household Washing Machine EDA Summary:", flush=True)
    print(summary_df.to_string(index=False), flush=True)
    
    # -------------------------------------------------------------
    # PLOT (i): Representative 24-Hour Aggregate + Washing Machine Trace
    # -------------------------------------------------------------
    print("\nGenerating Plot (i): 24-Hour Representative Trace...", flush=True)
    h2_df = house_data['House 2']
    sample_day = pd.Timestamp("2014-04-12")
    day_df = h2_df[(h2_df.index >= sample_day) & (h2_df.index < sample_day + pd.Timedelta(days=1))]
    
    fig, ax1 = plt.subplots(figsize=(14, 5))
    ax1.plot(day_df.index, day_df['Aggregate'], color='#1f77b4', lw=1.2, label='Aggregate Mains Power (W)', alpha=0.85)
    ax1.plot(day_df.index, day_df['WashingMachine'], color='#d62728', lw=1.8, label='Washing Machine Power (W)')
    ax1.fill_between(day_df.index, 0, day_df['WashingMachine'], color='#d62728', alpha=0.25)
    
    ax1.set_title("Plot (i): Representative 24-Hour Household Aggregate vs. Washing Machine Trace (House 2: 2014-04-12)", 
                  fontsize=12, fontweight='bold', pad=10)
    ax1.set_ylabel("Power (Watts)", fontsize=11)
    ax1.set_xlabel("Time of Day", fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right', frameon=True, fontsize=10)
    
    plot1_path = os.path.join(OUTPUT_FIG_DIR, "wm_trace_24h.png")
    fig.savefig(plot1_path, dpi=200)
    plt.close(fig)
    print(f"Saved Plot (i) to {plot1_path}", flush=True)
    
    # -------------------------------------------------------------
    # PLOT (ii): Detected Washing-Machine Cycle Zoom-In
    # -------------------------------------------------------------
    print("\nGenerating Plot (ii): Zoom-In of Detected Cycles...", flush=True)
    zoom_start = pd.Timestamp("2014-04-12 08:30:00")
    zoom_end = pd.Timestamp("2014-04-12 11:30:00")
    zoom_df = h2_df[(h2_df.index >= zoom_start) & (h2_df.index <= zoom_end)]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    
    ax1.plot(zoom_df.index, zoom_df['Aggregate'], color='#003366', lw=1.2, label='Aggregate Power (W)', alpha=0.7)
    ax1.plot(zoom_df.index, zoom_df['WashingMachine'], color='#d62728', lw=2.0, label='Washing Machine Power (W)')
    ax1.axhline(ON_POWER_THRESHOLD, color='gray', linestyle='--', lw=1.0, label=f'Active Threshold ({ON_POWER_THRESHOLD}W)')
    ax1.set_title("Zoomed View: Aggregate vs. Washing Machine Load Profile During Active Cycle", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Power (W)", fontsize=10)
    ax1.legend(loc='upper right', frameon=True)
    ax1.grid(True, alpha=0.3)
    
    ax2.plot(zoom_df.index, zoom_df['WashingMachine'], color='#d62728', lw=2.2, label='Washing Machine Signal')
    ax2.fill_between(zoom_df.index, 0, zoom_df['WashingMachine'], color='#d62728', alpha=0.2)
    
    # Operational phases text callouts
    ax2.text(0.18, 0.85, 'Phase 1: Water Heating (~2,200 W)\nResistive element draws high active power', 
             transform=ax2.transAxes, fontsize=9, fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    ax2.text(0.45, 0.45, 'Phase 2: Drum Tumbling (100-300 W)\nMotor agitates wash load', 
             transform=ax2.transAxes, fontsize=9, bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    ax2.text(0.70, 0.65, 'Phase 3: Spin Cycle & Pump (400-800 W)\nHigh-speed drum extraction', 
             transform=ax2.transAxes, fontsize=9, bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    ax2.set_title("Plot (ii): Detected Washing Machine Cycle Signature and Identified Physical Operational Phases", 
                  fontsize=11, fontweight='bold')
    ax2.set_ylabel("Power (W)", fontsize=10)
    ax2.set_xlabel("Time (HH:MM)", fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right', frameon=True)
    
    fig.subplots_adjust(top=0.93, bottom=0.08, left=0.08, right=0.96, hspace=0.25)
    plot2_path = os.path.join(OUTPUT_FIG_DIR, "wm_detected_cycles.png")
    fig.savefig(plot2_path, dpi=200)
    plt.close(fig)
    print(f"Saved Plot (ii) to {plot2_path}", flush=True)
    
    # -------------------------------------------------------------
    # PLOT (iii): Cross-House Comparison
    # -------------------------------------------------------------
    print("\nGenerating Plot (iii): Cross-House Comparison...", flush=True)
    all_cycles_list = []
    for h_name, c_df in house_cycles.items():
        if len(c_df) > 0:
            c_df = c_df.copy()
            c_df['Household'] = h_name
            all_cycles_list.append(c_df)
    combined_cycles = pd.concat(all_cycles_list, ignore_index=True)
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    colors = ['#66c2a5', '#fc8d62', '#8da0cb', '#e78ac3']
    houses = list(HOUSE_CONFIG.keys())
    
    # Subplot A: Cycle Duration Boxplot
    dur_data = [combined_cycles[combined_cycles['Household'] == h]['duration_min'].values for h in houses]
    bplot1 = axes[0, 0].boxplot(dur_data, labels=houses, patch_artist=True, showmeans=True)
    for patch, color in zip(bplot1['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    axes[0, 0].set_title("A: Washing Machine Cycle Duration (Minutes)", fontsize=11, fontweight='bold')
    axes[0, 0].set_ylabel("Duration (Minutes)", fontsize=10)
    axes[0, 0].grid(True, alpha=0.3)
    
    # Subplot B: Total Energy Boxplot (Wh)
    energy_data = [combined_cycles[combined_cycles['Household'] == h]['energy_wh'].values for h in houses]
    bplot2 = axes[0, 1].boxplot(energy_data, labels=houses, patch_artist=True, showmeans=True)
    for patch, color in zip(bplot2['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    axes[0, 1].set_title("B: Total Energy Consumption per Cycle (Wh)", fontsize=11, fontweight='bold')
    axes[0, 1].set_ylabel("Energy (Watt-hours)", fontsize=10)
    axes[0, 1].grid(True, alpha=0.3)
    
    # Subplot C: Usage by Hour of Day
    for i, h_name in enumerate(houses):
        h_c = combined_cycles[combined_cycles['Household'] == h_name]
        hour_counts = h_c['start_hour'].value_counts(normalize=True).sort_index() * 100
        axes[1, 0].plot(hour_counts.index, hour_counts.values, marker='o', lw=1.8, label=h_name, color=colors[i])
    axes[1, 0].set_title("C: Cycle Start-Time Probability by Hour of Day", fontsize=11, fontweight='bold')
    axes[1, 0].set_xlabel("Hour of Day (0 - 23)", fontsize=10)
    axes[1, 0].set_ylabel("Probability of Cycle Start (%)", fontsize=10)
    axes[1, 0].set_xticks(range(0, 24, 2))
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend(frameon=True, fontsize=9)
    
    # Subplot D: Usage by Day of Week
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    x_indices = np.arange(len(weekday_order))
    bar_width = 0.2
    
    for i, h_name in enumerate(houses):
        h_c = combined_cycles[combined_cycles['Household'] == h_name]
        day_counts = h_c['start_weekday'].value_counts(normalize=True).reindex(weekday_order).fillna(0) * 100
        axes[1, 1].bar(x_indices + i * bar_width, day_counts.values, width=bar_width, label=h_name, color=colors[i], alpha=0.85)
        
    axes[1, 1].set_title("D: Cycle Start Distribution by Day of Week (%)", fontsize=11, fontweight='bold')
    axes[1, 1].set_xlabel("Day of Week", fontsize=10)
    axes[1, 1].set_ylabel("Share of Weekly Cycles (%)", fontsize=10)
    axes[1, 1].set_xticks(x_indices + bar_width * 1.5)
    axes[1, 1].set_xticklabels([d[:3] for d in weekday_order])
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend(frameon=True, fontsize=9)
    
    fig.subplots_adjust(top=0.93, bottom=0.08, left=0.08, right=0.96, hspace=0.3, wspace=0.25)
    plot3_path = os.path.join(OUTPUT_FIG_DIR, "wm_cross_house_comparison.png")
    fig.savefig(plot3_path, dpi=200)
    plt.close(fig)
    print(f"Saved Plot (iii) to {plot3_path}", flush=True)
    
    cycles_csv_path = os.path.join(OUTPUT_TAB_DIR, "detected_washing_cycles_all_houses.csv")
    combined_cycles.to_csv(cycles_csv_path, index=False)
    print(f"Saved all detected cycles to: {cycles_csv_path}", flush=True)

    return summary_df, combined_cycles


if __name__ == "__main__":
    run_eda_pipeline()
