"""
Stage 3: NILM Evaluation Metrics.
Evaluates continuous power regression and discrete appliance activation state.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, precision_recall_fscore_support


def compute_nilm_metrics(y_true, y_pred, on_threshold=20.0):
    """
    Computes standard NILM disaggregation metrics.
    Parameters:
        y_true: True appliance power series (Watts)
        y_pred: Predicted appliance power series (Watts)
        on_threshold: Power threshold (W) to classify appliance as ON
    Returns:
        dict of metric names to values
    """
    y_true = np.array(y_true, dtype=float)
    y_pred = np.clip(np.array(y_pred, dtype=float), 0, None)  # Power cannot be negative
    
    # 1. Continuous error metrics
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    # 2. Total energy estimation & Signal Aggregate Error (SAE)
    # Energy in kWh: sum(P_w * (1/60 hr)) / 1000
    true_energy_kwh = np.sum(y_true) / 60000.0
    pred_energy_kwh = np.sum(y_pred) / 60000.0
    
    if true_energy_kwh > 0:
        sae = np.abs(pred_energy_kwh - true_energy_kwh) / true_energy_kwh
        energy_error_pct = (pred_energy_kwh - true_energy_kwh) / true_energy_kwh * 100.0
    else:
        sae = np.nan
        energy_error_pct = np.nan
        
    # 3. Discrete ON/OFF classification metrics
    true_on = (y_true >= on_threshold).astype(int)
    pred_on = (y_pred >= on_threshold).astype(int)
    
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_on, pred_on, average='binary', zero_division=0
    )
    
    return {
        'MAE (W)': round(float(mae), 2),
        'RMSE (W)': round(float(rmse), 2),
        'SAE (Energy Error)': round(float(sae), 4),
        'Energy Error (%)': round(float(energy_error_pct), 2),
        'True Energy (kWh)': round(float(true_energy_kwh), 2),
        'Pred Energy (kWh)': round(float(pred_energy_kwh), 2),
        'Precision': round(float(precision), 4),
        'Recall': round(float(recall), 4),
        'F1-Score': round(float(f1), 4)
    }

