# REFIT Smart Meter Appliance Disaggregation & Usage Analysis

A rigorous, end-to-end data science study analyzing high-resolution domestic electricity consumption, data cleaning on raw sensor streams, cross-household washing machine behavioral analytics, and non-intrusive appliance disaggregation modeling using the **REFIT: Electrical Load Measurements Dataset** (Murray et al., 2017).

---

## 1. Project Overview & Deliverables

This repository contains the complete implementation for the Flock Energy Data Scientist technical assessment:

- **Section 1: Data Cleaning & Preprocessing (House 1)**
  - Full programmatic audit of 8.5+ million raw records.
  - Chunk-wise deduplication, physical sensor validation (4 kW socket limit), uniform 1-minute grid resampling, and selective outage preservation (> 2 minutes).
- **Section 2: Washing Machine Usage Analysis (Houses 1, 2, 3, 5)**
  - Extraction and auditing of 2,212 washing machine cycles across four diverse households.
  - Characterization of operational sparsity (92–98% idle), multi-phase cycle anatomy (heating, tumbling, rinse, spin), and diurnal/weekly behavioral distributions.
- **Section 3: Appliance Disaggregation Modeling (House 2)**
  - Feature-engineered Non-Intrusive Load Monitoring (NILM) using sliding-window gradient boosted regression.
  - Strict forward chronological validation (zero temporal leakage).
  - Multi-metric benchmark against Always-Off and Usage-Profile baselines (27.3% RMSE reduction, 64.5% recall, +11.7% total energy error).
- **Section 4 & Executive Recommendations**
  - Utility executive brief, demand-flexibility potential, behavioral M&V frameworks (Difference-in-Differences), Indian household transferability analysis, and 15/30-minute smart meter scaling strategies.

### Deliverable Documents:
1. [`DATA.md`](file:///d:/flockenergy_hitesh/DATA.md): Comprehensive data coverage, sensor quality findings, cleaning policies, and outage trade-offs.
2. [`RESULTS.md`](file:///d:/flockenergy_hitesh/RESULTS.md): Cross-household usage statistics, high-resolution plots, model benchmark comparisons, and failure mode analysis.
3. [`Recommendation.md`](file:///d:/flockenergy_hitesh/Recommendation.md): 1-page utility executive brief with Section 4 strategic and engineering answers.
4. [`README.md`](file:///d:/flockenergy_hitesh/README.md): System architecture, execution guide, design decisions, and future extensions.

---

## 2. Directory Structure

```text
d:/flockenergy_hitesh/
├── data/                                # Cached 1-minute resampled datasets
│   ├── House1_1min.csv
│   ├── House2_1min.csv
│   ├── House3_1min.csv
│   ├── House5_1min.csv
│   └── House1_cleaned_1min_sample.csv
├── notebooks/                           # Interactive Jupyter notebooks for all sections
│   ├── 01_raw_cleaning.ipynb            # Section 1: Raw House 1 cleaning audit
│   ├── 02_washing_machine_eda.ipynb     # Section 2: Washing machine behavioral EDA
│   └── 03_disaggregation_modeling.ipynb # Section 3: Disaggregation model training & evaluation
├── outputs/                             # Verified figures and empirical tables
│   ├── figures/
│   │   ├── house1_cleaning_before_after.png
│   │   ├── wm_trace_24h.png
│   │   ├── wm_detected_cycles.png
│   │   ├── wm_cross_house_comparison.png
│   │   └── disaggregation_actual_vs_predicted.png
│   └── tables/
│       ├── raw_house1_inspection_summary.csv
│       ├── house1_cleaned_1min_summary.csv
│       ├── wm_cross_house_summary.csv
│       ├── detected_washing_cycles_all_houses.csv
│       ├── model_performance_comparison.csv
│       └── test_actual_vs_predicted_sample.csv
├── src/                                 # Modular Python source modules
│   ├── cleaning.py                      # Raw cleaning & resampling pipeline
│   ├── eda.py                           # Washing machine cycle extraction & statistics
│   ├── features.py                      # Sliding window feature engineering
│   ├── metrics.py                       # NILM evaluation metrics (MAE, RMSE, F1, SAE)
│   └── model.py                         # Baseline models and Gradient Boosted NILM
├── DATA.md                              # Data quality and preprocessing report
├── RESULTS.md                           # Empirical findings and model benchmark report
├── Recommendation.md                    # Utility executive brief & Section 4 answers
└── README.md                            # Project overview & documentation
```

---

## 3. Setup & Reproduction Guide

### Environment Requirements
- Python 3.10+ (Tested on Python 3.13.2 64-bit on Windows)
- Required Python libraries:
  ```bash
  pip install pandas numpy scikit-learn matplotlib
  ```

### Running the Complete Pipeline via Python Modules
The modular source scripts can be executed directly from the command line:

```bash
# 1. Clean raw House 1 data and generate before/after diagnostic figures
python src/cleaning.py

# 2. Run washing machine cycle detection and cross-household EDA (Houses 1, 2, 3, 5)
python src/eda.py

# 3. Train and evaluate disaggregation models on House 2 with forward temporal split
python src/model.py
```

### Running the Interactive Notebooks
The notebooks in `notebooks/` provide step-by-step visualizations and commentary:
- `jupyter notebook notebooks/01_raw_cleaning.ipynb`
- `jupyter notebook notebooks/02_washing_machine_eda.ipynb`
- `jupyter notebook notebooks/03_disaggregation_modeling.ipynb`

---

## 4. Key Assumptions & Engineering Trade-Offs

1. **Active State Threshold ($P \ge 15\text{ W}$)**:
   - *Rationale*: Isolates mechanical drum agitation, water pumping, and heating phases from quiescent standby/off power (typically 0.5–2.0 W).
2. **Selective Outage Preservation (> 2 Minutes)**:
   - *Trade-off*: Rather than forward-filling missing smart meter records across communication dropouts, all gaps $>2\text{ minutes}$ are preserved strictly as `NaN`. Forward filling an outage following a 2.2 kW heating spike would fabricate enormous phantom energy. Short jitter ($\le 2$ min) is linearly interpolated.
3. **Physical Socket Limit (4,000 W)**:
   - *Trade-off*: UK 13A wall sockets trip near 3 kW continuous load. Raw sensor spikes reaching 98 kW represent RF bit corruption and were clamped to prevent severe squared-error skew during training.
4. **Feature-Engineered Gradient Boosting vs. Complex Deep Learning**:
   - *Trade-off*: While deep architectures (Seq2Point / WaveNet) can model complex sequence shapes, they require substantial GPU resources and longer training times. Our feature-engineered histogram gradient boosting model trains in **under 9 seconds on CPU**, achieves an **RMSE of 131.85 W** (27.3% error reduction), and tracks total energy within **+11.7%**, making it suitable for utility deployment.

---

## 5. Validation Strategy & Zero Data Leakage

Time series disaggregation models are exceptionally vulnerable to artificial performance inflation if validated improperly. Our pipeline enforces strict protocols to ensure zero data leakage:

1. **Chronological Forward Train/Test Split**:
   - Evaluated on House 2 clean data:
     - **Training Set (80%)**: September 17, 2013 to February 6, 2015 (**536,071 minutes**).
     - **Testing Set (20%)**: February 6, 2015 to May 28, 2015 (**133,973 minutes**, ~3.5 continuous months).
2. **No Shuffled K-Fold Cross-Validation**:
   - Shuffling consecutive 1-minute samples leaks past and future power states into the validation set, creating artificially inflated metrics.
3. **Causal Rolling Statistics**:
   - Window statistics (rolling means, rolling min/max, rolling standard deviations) are computed strictly across historical/causal windows without peeking into future aggregate load.

---

## 6. AI Tools Disclosure

As required by the assignment guidelines, this project utilized **Google Antigravity (powered by Gemini)** as an interactive AI pair-programming assistant. 

### How AI Was Used:
- Rapid prototyping of data cleaning scripts and exploratory visualization templates.
- Vectorizing cycle extraction algorithms in [`src/eda.py`](file:///d:/flockenergy_hitesh/src/eda.py) to replace slow Python iteration.
- Structuring mathematical evaluation functions for Sub-metered Appliance Energy (SAE) error and F1 active state classification.

### Human Verification & Rigor:
- **No Hallucinated Results**: All numbers, tables, and figures reported across the codebase and documentation reflect real computations executed locally against the physical REFIT files.
- **Physical Plausibility Checks**: Electrical engineering principles (socket fuse ratings, nominal voltages, thermal heating element physics) were manually verified.


