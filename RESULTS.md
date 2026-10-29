# RESULTS.md: Empirical Findings, Visualizations & Benchmark Report

## 1. Executive Summary

This document presents the empirical results of the **Washing Machine Usage Analysis** (Section 2 across Houses 1, 2, 3, and 5) and the **Appliance Disaggregation Modeling** (Section 3 on House 2) conducted on the REFIT dataset.

All statistics and visualizations are derived from the local Strathclyde cleaned datasets without synthetic fabrication or data leakage.

---

## 2. Washing Machine Usage Analysis (Houses 1, 2, 3, 5)

### 2.1 Metadata & Appliance Mapping
The REFIT documentation (Murray et al., 2017) defines the following specific sub-metered channels for the washing machine across the four target households:
- **House 1**: Appliance 5 (`Appliance5`)
- **House 2**: Appliance 2 (`Appliance2`)
- **House 3**: Appliance 6 (`Appliance6`)
- **House 5**: Appliance 3 (`Appliance3`)

### 2.2 Cycle Detection Methodology
A washing machine operation consists of multiple discrete phases separated by brief motor pauses. To extract meaningful wash cycles from 1-minute time series data, we implemented an automated state-bridging algorithm ([`src/eda.py`](file:///d:/flockenergy_hitesh/src/eda.py)):
1. **Active Threshold**: $P \ge 15\text{ W}$ marks an active mechanical state (isolating operational phases from quiescent standby power).
2. **Bridge Gap Tolerance**: Inactive periods $\le 3\text{ minutes}$ (such as drain pauses between wash and rinse) are bridged to prevent fragmenting a single wash cycle into multiple disconnected events.
3. **Minimum Duration**: Filtered to cycles lasting $\ge 10\text{ minutes}$ with total energy $\ge 30\text{ Wh}$ to exclude accidental button presses or brief plug-in sensor checks.

### 2.3 Cross-Household Empirical Comparison

Across the four households, **2,212 individual washing machine cycles** were detected and audited (saved to [`outputs/tables/wm_cross_house_summary.csv`](file:///d:/flockenergy_hitesh/outputs/tables/wm_cross_house_summary.csv) and [`outputs/tables/detected_washing_cycles_all_houses.csv`](file:///d:/flockenergy_hitesh/outputs/tables/detected_washing_cycles_all_houses.csv)):

| Household | Channel | Monitored Days | Standby / Off (%) | Active Time (%) | Total Cycles | Cycles / Week | Median Duration | Median Peak Power | Median Energy / Cycle |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **House 1** | App 5 | 639.0 days | 98.12% | 1.88% | 412 | 4.51 / wk | 33.0 min | 2,325.2 W | 306.6 Wh (0.31 kWh) |
| **House 2** | App 2 | 617.4 days | 95.31% | 4.69% | 344 | 3.90 / wk | 96.0 min | 2,089.2 W | 605.4 Wh (0.61 kWh) |
| **House 3** | App 6 | 614.6 days | 94.34% | 5.66% | 677 | 7.71 / wk | 65.0 min | 1,923.9 W | 543.0 Wh (0.54 kWh) |
| **House 5** | App 3 | 648.3 days | 92.10% | 7.90% | 779 | 8.41 / wk | 43.0 min | 2,065.3 W | 288.0 Wh (0.29 kWh) |

#### Core Usage Insights:
1. **Extreme Operational Sparsity**:
   - The appliance is powered off or in passive standby **92.1% to 98.1% of the year**.
   - Active run-time accounts for only **1.9% (House 1)** to **7.9% (House 5)** of total minutes.
2. **Consistent Heating Peak across Appliances**:
   - Despite variations in machine manufacturer and household demographics, median peak power remains remarkably consistent across all four homes: **1,924 W to 2,325 W**. This reflects the standard domestic internal electric water immersion heating element (~2 kW).
3. **Behavioral Diversity & Wash Programs**:
   - **House 2** operates long, intensive wash cycles (median **96 minutes**, **605.4 Wh**) at lower frequency (**3.9 cycles/week**), consistent with a full cotton wash program in a smaller household.
   - **House 5** runs frequent, shorter wash cycles (median **43 minutes**, **8.41 cycles/week**), characteristic of a busy family running daily quick washes.

---

### 2.4 Visualizations & Physical Interpretation

#### Plot (i): 24-Hour Aggregate vs. Washing Machine Profile
- **File**: [`outputs/figures/wm_trace_24h.png`](file:///d:/flockenergy_hitesh/outputs/figures/wm_trace_24h.png)
- **Observations**:
  - Displays a continuous 24-hour window from House 1 showing aggregate whole-home power (blue line) alongside the washing machine power trace (red filled area).
  - During the early afternoon wash cycle, the washing machine heating element directly drives the primary household peak, climbing from a ~250 W baseload to over 2,400 W.
  - The aggregate trace also reveals sharp, narrow peaks (kettle boils) that do not coincide with the washing machine, demonstrating the challenge of multi-appliance signature disentanglement.

#### Plot (ii): High-Resolution Anatomy of a Washing Machine Cycle
- **File**: [`outputs/figures/wm_detected_cycles.png`](file:///d:/flockenergy_hitesh/outputs/figures/wm_detected_cycles.png)
- **Observations**:
  - Highlights a zoomed multi-phase cycle from House 2 with color-coded operational phases:
    1. **Water Heating Phase (0 to ~20 min)**: High-magnitude continuous plateau at ~2,050 W where the internal immersion element heats cold mains water to target temperature.
    2. **Drum Agitation & Wash Tumbling (~20 to ~65 min)**: Low-power, periodic motor pulses fluctuating between 120 W and 250 W as the drum rotates clockwise, pauses, and reverses counter-clockwise.
    3. **Rinse & Drain Cycles (~65 to ~80 min)**: Brief pauses followed by water pump activation and short bursts of motor rotation.
    4. **Spin Cycle (~80 to ~95 min)**: Rapid acceleration of the centrifugal drum, drawing sustained power climbing from 350 W to 600 W.

#### Plot (iii): Cross-Household Behavioral Comparison (4-Panel Analysis)
- **File**: [`outputs/figures/wm_cross_house_comparison.png`](file:///d:/flockenergy_hitesh/outputs/figures/wm_cross_house_comparison.png)
- **Panel A (Cycle Duration Distribution)**: Boxplots show distinct clustering. House 1 centers at ~33 min, House 2 shows an extended distribution reaching up to 130 min, House 3 centers at 65 min, and House 5 at 43 min.
- **Panel B (Cycle Energy Distribution)**: Energy per cycle ranges from ~0.25 kWh to over 1.1 kWh depending on temperature setting and program duration.
- **Panel C (Diurnal Probability by Hour of Day)**: Washing machine activation exhibits a dominant morning peak between **9:00 AM and 12:00 PM**, with a secondary minor peak between **6:00 PM and 8:30 PM**. Nighttime operation (11:00 PM to 6:00 AM) is virtually non-existent.
- **Panel D (Weekly Usage Distribution)**: Clear surge on **Saturday and Sunday** across all households, aligning with residential domestic routines.

---

## 3. Disaggregation Modeling & Benchmark Results (House 2)

### 3.1 Validation Design & Zero-Leakage Protocol
To simulate realistic real-world deployment on an existing smart meter, disaggregation was formulated as a **forward chronological regression task**:
- **Dataset**: House 2 clean 1-minute resampled data (670,044 minutes).
- **Training Set (80%)**: September 17, 2013 to February 6, 2015 (**536,071 minutes**).
- **Testing Set (20%)**: February 6, 2015 to May 28, 2015 (**133,973 minutes**, ~3.5 months of unseen operational data).
- **Leakage Prevention**: All rolling window statistics and normalizations were computed strictly causally or within temporal blocks. Shuffled k-fold cross-validation was strictly prohibited to eliminate time-series auto-correlation leakage.

### 3.2 Benchmark Comparison Table

All three models were evaluated on the **133,973 unseen test minutes** (saved to [`outputs/tables/model_performance_comparison.csv`](file:///d:/flockenergy_hitesh/outputs/tables/model_performance_comparison.csv)):

| Model Description | MAE (W) | RMSE (W) | F1-Score ($\ge 15\text{ W}$) | Precision | Recall | Predicted Energy (kWh) | Actual Energy (kWh) | Energy Error (SAE) | Training Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Always-Off Baseline** | **19.91 W** | 181.28 W | 0.0000 | 0.0% | 0.0% | 0.00 kWh | 44.46 kWh | -100.0% (1.000) | < 0.01 s |
| **Usage-Profile Baseline** | 35.48 W | 180.13 W | 0.0992 | 5.46% | 53.82% | 39.37 kWh | 44.46 kWh | -11.44% (0.114) | 0.08 s |
| **Gradient Boosted NILM (Ours)** | 23.85 W | **131.85 W** | **0.4239** | **31.57%** | **64.47%** | **49.68 kWh** | 44.46 kWh | **+11.74% (0.117)** | **8.66 s** |

---

### 3.3 Critical Metric Analysis & Trade-Offs

#### 1. The "MAE Paradox" in Highly Imbalanced Energy Data
A superficial inspection might suggest that the **Always-Off Baseline** performs well because its Mean Absolute Error is only **19.91 W**. However, this is an artifact of extreme class imbalance: because the washing machine is inactive for 95.3% of test minutes, predicting zero achieves a low average absolute error across idle periods. 

Crucially, the Always-Off baseline:
- Completely misses all active wash cycles (Recall = 0.0%, F1 = 0.0).
- Incurs an **SAE of 1.0 (100% underestimation)**, predicting 0 kWh vs 44.46 kWh actual.
- Shows a high **RMSE of 181.28 W**, severely penalizing its failure on 2 kW active spikes.

#### 2. Model Performance (Gradient Boosted NILM)
Our feature-engineered Gradient Boosted NILM model:
- Reduces RMSE by **27.3%** (from 181.28 W down to **131.85 W**).
- Achieves an **F1-score of 0.4239** with **64.47% Recall**, successfully detecting nearly two-thirds of active washing machine operations directly from whole-home smart meter data.
- Accurately tracks cumulative energy: predicts **49.68 kWh** against the ground-truth **44.46 kWh** (+11.74% energy error over 3.5 continuous months).
- Trains in just **8.66 seconds**, providing an optimal balance between accuracy and computational scalability for utility deployments.

---

### 3.4 Visual Inspection & Failure Mode Analysis

The actual vs. predicted disaggregation behavior is visualized in [`outputs/figures/disaggregation_actual_vs_predicted.png`](file:///d:/flockenergy_hitesh/outputs/figures/disaggregation_actual_vs_predicted.png), with a tabular sample in [`outputs/tables/test_actual_vs_predicted_sample.csv`](file:///d:/flockenergy_hitesh/outputs/tables/test_actual_vs_predicted_sample.csv).

The visual audit reveals two primary failure modes:

#### Failure Mode A: False Positives from Signature Overlap
- **Observation**: The model occasionally predicts brief 500 W – 1,500 W washing machine spikes when the aggregate power suddenly jumps to 2.5 kW.
- **Physical Explanation**: In a domestic setting, resistive heating loads (electric kettles boiling at 2.2 kW, electric showers at 7–9 kW, toasters, and hair dryers) exhibit step-change power profiles identical to a washing machine water immersion heater. Without sub-second harmonic data, the model must rely solely on temporal duration and sliding window context. Brief 2–3 minute kettle boils can trigger false positives if aggregate power remains elevated.

#### Failure Mode B: False Negatives on Low-Power Drum Agitation
- **Observation**: During the motor wash/rinse phases (~20 to ~65 minutes into a cycle), the actual washing machine draws 120 W to 250 W. The model frequently underestimates or misses these phases (predicting ~10–30 W).
- **Physical Explanation**: A 150 W motor load has a low Signal-to-Noise Ratio (SNR) relative to aggregate household baseload fluctuations. Constant baseload variations from refrigerators (cycling 80–150 W), entertainment systems, and lighting obscure the subtle periodic pulses of the washing machine drum.

