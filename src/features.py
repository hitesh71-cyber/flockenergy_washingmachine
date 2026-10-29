"""
Stage 3: Feature Engineering for Appliance Disaggregation.
Constructs sliding window context and rolling statistics from aggregate mains power:
- Bidirectional window: Lags (t - k) and Leads (t + k) up to 30 minutes
- Rolling statistics: Mean, Std, Max, Min over 5, 15, 30, and 60 minutes
- Time-of-day cyclical features (sin/cos encoding)
"""

import numpy as np
import pandas as pd


def create_nilm_features(df, agg_col='Aggregate', target_col='WashingMachine', window_minutes=30):
    """
    Generates time-series context features from 1-minute aggregate power.
    Parameters:
        df: DataFrame with DateTime index and aggregate power column
        window_minutes: Max lag/lead window in minutes (e.g. 30)
    Returns:
        X: Feature matrix
        y: Washing machine power target (if target_col in df)
    """
    df_feat = pd.DataFrame(index=df.index)
    agg = df[agg_col]
    
    # 1. Base power
    df_feat['agg_current'] = agg
    
    # 2. Lags and Leads (Bidirectional receptive field like Seq2Point)
    offsets = [1, 2, 3, 5, 10, 15, 20, 30]
    for k in offsets:
        if k <= window_minutes:
            df_feat[f'agg_lag_{k}'] = agg.shift(k)
            df_feat[f'agg_lead_{k}'] = agg.shift(-k)
            # Power differences
            df_feat[f'agg_diff_lag_{k}'] = agg - agg.shift(k)
            df_feat[f'agg_diff_lead_{k}'] = agg.shift(-k) - agg
            
    # 3. Rolling statistics (backward-looking and centered)
    for w in [5, 15, 30, 60]:
        df_feat[f'agg_roll_mean_{w}'] = agg.rolling(w, min_periods=1).mean()
        df_feat[f'agg_roll_std_{w}'] = agg.rolling(w, min_periods=1).std().fillna(0)
        df_feat[f'agg_roll_max_{w}'] = agg.rolling(w, min_periods=1).max()
        df_feat[f'agg_roll_min_{w}'] = agg.rolling(w, min_periods=1).min()
        
    # 4. Temporal encodings
    hour = df.index.hour + df.index.minute / 60.0
    df_feat['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
    df_feat['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
    
    dayofweek = df.index.dayofweek
    df_feat['day_sin'] = np.sin(2 * np.pi * dayofweek / 7.0)
    df_feat['day_cos'] = np.cos(2 * np.pi * dayofweek / 7.0)
    df_feat['is_weekend'] = (dayofweek >= 5).astype(float)
    
    # Drop rows with NaNs caused by shift/rolling
    valid_idx = df_feat.notna().all(axis=1)
    if target_col in df.columns:
        valid_idx = valid_idx & df[target_col].notna()
        return df_feat.loc[valid_idx], df.loc[valid_idx, target_col]
    
    return df_feat.loc[valid_idx], None

