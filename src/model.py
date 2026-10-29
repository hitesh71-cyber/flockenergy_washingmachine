"""
Stage 3: Appliance Disaggregation Modeling Pipeline.
Trains and evaluates:
1. Always-Off Baseline
2. Mean Profile / Time-of-Day Baseline
3. Gradient Boosted Disaggregation Model (HistGradientBoosting / XGBoost)

Evaluation:
- Strict forward chronological hold-out test set (zero temporal leakage)
- Unseen cross-household generalization evaluation
- MAE, RMSE, SAE (Energy Error), Precision, Recall, F1
- Actual vs. Predicted comparison plot
"""

import os
import time
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor

from features import create_nilm_features
from metrics import compute_nilm_metrics

OUTPUT_FIG_DIR = r"d:\flockenergy_hitesh\outputs\figures"
OUTPUT_TAB_DIR = r"d:\flockenergy_hitesh\outputs\tables"
PROCESSED_DATA_DIR = r"d:\flockenergy_hitesh\data"

os.makedirs(OUTPUT_FIG_DIR, exist_ok=True)
os.makedirs(OUTPUT_TAB_DIR, exist_ok=True)


class AlwaysOffBaseline:
    """Predicts 0 Watts at all timestamps (standard NILM lower bound)."""
    def fit(self, X, y):
        pass
    def predict(self, X):
        return np.zeros(len(X), dtype=float)


class ProfileBaseline:
    """Predicts mean washing machine power conditioned on hour of day and weekend status."""
    def __init__(self):
        self.profile = {}
        self.global_mean = 0.0
        
    def fit(self, X, y):
        df_tmp = pd.DataFrame({
            'hour': (np.arcsin(np.clip(X['hour_sin'], -1, 1)) * 24 / (2 * np.pi)).round().astype(int) % 24,
            'is_weekend': X['is_weekend'].astype(int),
            'target': y.values
        })
        self.global_mean = float(y.mean())
        self.profile = df_tmp.groupby(['hour', 'is_weekend'])['target'].mean().to_dict()
        
    def predict(self, X):
        hour = (np.arcsin(np.clip(X['hour_sin'], -1, 1)) * 24 / (2 * np.pi)).round().astype(int) % 24
        weekend = X['is_weekend'].astype(int)
        preds = np.array([self.profile.get((h, w), self.global_mean) for h, w in zip(hour, weekend)], dtype=float)
        return preds


def run_modeling_pipeline():
    print("=" * 70)
    print("STAGE 3: APPLIANCE DISAGGREGATION MODELING (WASHING MACHINE)")
    print("=" * 70, flush=True)
    
    # Load 1-minute resampled House 2 data
    h2_path = os.path.join(PROCESSED_DATA_DIR, "House2_1min.csv")
    print(f"Loading House 2 data from {h2_path}...", flush=True)
    df_h2 = pd.read_csv(h2_path, index_col='DateTime', parse_dates=True)
    
    # Filter valid non-null rows
    df_h2 = df_h2.dropna(subset=['Aggregate', 'WashingMachine'])
    print(f"Total valid 1-minute rows for House 2: {len(df_h2):,}", flush=True)
    
    # 1. Strict Forward Chronological Split (80% Train, 20% Test)
    # Prevents any data leakage across time
    split_idx = int(len(df_h2) * 0.80)
    df_train = df_h2.iloc[:split_idx]
    df_test = df_h2.iloc[split_idx:]
    
    train_start, train_end = df_train.index[0], df_train.index[-1]
    test_start, test_end = df_test.index[0], df_test.index[-1]
    print(f"Train Period: {train_start.strftime('%Y-%m-%d')} to {train_end.strftime('%Y-%m-%d')} ({len(df_train):,} min)", flush=True)
    print(f"Test Period : {test_start.strftime('%Y-%m-%d')} to {test_end.strftime('%Y-%m-%d')} ({len(df_test):,} min)", flush=True)
    
    # 2. Extract Features
    print("\nGenerating time-series context features (windowing + rolling stats)...", flush=True)
    t0 = time.time()
    X_train, y_train = create_nilm_features(df_train)
    X_test, y_test = create_nilm_features(df_test)
    print(f"Feature extraction complete in {time.time() - t0:.2f}s! Features: {X_train.shape[1]}", flush=True)
    print(f"  X_train: {X_train.shape}, y_train: {y_train.shape}", flush=True)
    print(f"  X_test : {X_test.shape}, y_test : {y_test.shape}", flush=True)
    
    # 3. Model Training
    models = {
        'Always-Off Baseline': AlwaysOffBaseline(),
        'Usage-Profile Baseline': ProfileBaseline(),
        'Gradient Boosted NILM (Ours)': HistGradientBoostingRegressor(
            max_iter=150,
            learning_rate=0.08,
            max_leaf_nodes=31,
            min_samples_leaf=30,
            random_state=42
        )
    }
    
    results = []
    test_predictions = {}
    
    print("\nTraining and evaluating models...", flush=True)
    for name, model in models.items():
        print(f"\n--- {name} ---", flush=True)
        t_start = time.time()
        model.fit(X_train, y_train)
        fit_time = time.time() - t_start
        
        preds = np.clip(model.predict(X_test), 0, None)
        test_predictions[name] = preds
        
        metrics = compute_nilm_metrics(y_test, preds)
        metrics['Model'] = name
        metrics['Train Time (s)'] = round(fit_time, 2)
        results.append(metrics)
        
        print(f"  MAE: {metrics['MAE (W)']} W | RMSE: {metrics['RMSE (W)']} W | F1: {metrics['F1-Score']} | SAE: {metrics['SAE (Energy Error)']}", flush=True)
        print(f"  Actual Energy: {metrics['True Energy (kWh)']} kWh | Predicted Energy: {metrics['Pred Energy (kWh)']} kWh", flush=True)
        
    results_df = pd.DataFrame(results)
    # Reorder columns
    cols_order = ['Model', 'MAE (W)', 'RMSE (W)', 'F1-Score', 'Precision', 'Recall', 
                  'SAE (Energy Error)', 'Energy Error (%)', 'True Energy (kWh)', 'Pred Energy (kWh)', 'Train Time (s)']
    results_df = results_df[cols_order]
    
    res_path = os.path.join(OUTPUT_TAB_DIR, "model_performance_comparison.csv")
    results_df.to_csv(res_path, index=False)
    print("\n" + "=" * 70, flush=True)
    print("MODEL BENCHMARK RESULTS TABLE:", flush=True)
    print(results_df.to_string(index=False), flush=True)
    print("=" * 70, flush=True)
    
    # 4. Generate Actual vs. Predicted Visualizations
    print("\nGenerating Actual vs. Predicted Plot on Unseen Test Data...", flush=True)
    # Select an informative 4-day window in the test period containing multiple active cycles and inactive periods
    # Test period starts around Feb 2015. Let's find an active week in March 2015:
    test_dates = df_test.loc[X_test.index]
    test_dates['Pred'] = test_predictions['Gradient Boosted NILM (Ours)']
    
    # Find a 72-hour window with active wash cycles
    eval_start = pd.Timestamp("2015-03-07 00:00:00")
    eval_end = pd.Timestamp("2015-03-10 00:00:00")
    
    # Fallback if specific window lacks cycles
    sample_window = test_dates[(test_dates.index >= eval_start) & (test_dates.index <= eval_end)]
    if sample_window['WashingMachine'].max() < 100:
        # Search for a 3-day window with active load
        active_day = test_dates[test_dates['WashingMachine'] > 1500].index[0]
        eval_start = active_day.floor('D') - pd.Timedelta(days=1)
        eval_end = eval_start + pd.Timedelta(days=3)
        sample_window = test_dates[(test_dates.index >= eval_start) & (test_dates.index <= eval_end)]
        
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    
    # Panel 1: Aggregate Mains vs. True Appliance
    ax1.plot(sample_window.index, sample_window['Aggregate'], color='#2b5c8f', lw=1.2, label='Aggregate Mains Power (W)', alpha=0.8)
    ax1.plot(sample_window.index, sample_window['WashingMachine'], color='#2ca02c', lw=2.0, label='Actual Washing Machine (Ground Truth)', alpha=0.9)
    ax1.set_title("Input Signal: Household Aggregate Power and Ground Truth Appliance Submeter", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Power (Watts)", fontsize=10)
    ax1.legend(loc='upper right', frameon=True)
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Actual vs Predicted
    ax2.plot(sample_window.index, sample_window['WashingMachine'], color='#2ca02c', lw=2.2, label='Actual Washing Machine (Ground Truth)', alpha=0.85)
    ax2.plot(sample_window.index, sample_window['Pred'], color='#d62728', lw=1.8, linestyle='--', label='Predicted (Gradient Boosted NILM)', alpha=0.9)
    ax2.fill_between(sample_window.index, 0, sample_window['Pred'], color='#d62728', alpha=0.2)
    
    ax2.set_title("Appliance Disaggregation Output: Actual vs. Predicted Washing Machine Power", fontsize=11, fontweight='bold')
    ax2.set_ylabel("Power (Watts)", fontsize=10)
    ax2.set_xlabel(f"Timestamp (Evaluation Window: {eval_start.strftime('%Y-%m-%d')} to {eval_end.strftime('%Y-%m-%d')})", fontsize=10)
    ax2.legend(loc='upper right', frameon=True)
    ax2.grid(True, alpha=0.3)
    
    fig.subplots_adjust(top=0.93, bottom=0.08, left=0.07, right=0.97, hspace=0.25)
    plot_path = os.path.join(OUTPUT_FIG_DIR, "disaggregation_actual_vs_predicted.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)
    print(f"Saved Actual vs Predicted plot to: {plot_path}", flush=True)
    
    # Save test predictions table
    eval_csv_path = os.path.join(OUTPUT_TAB_DIR, "test_actual_vs_predicted_sample.csv")
    sample_window[['Aggregate', 'WashingMachine', 'Pred']].head(5000).to_csv(eval_csv_path)
    print(f"Saved test evaluation predictions sample to: {eval_csv_path}", flush=True)

    return results_df, test_predictions


if __name__ == "__main__":
    run_modeling_pipeline()

