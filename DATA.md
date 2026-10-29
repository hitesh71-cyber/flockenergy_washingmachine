# DATA.md: Data Quality & Preprocessing Report

## 1. Dataset Overview & Scope

This report documents the empirical data coverage, raw quality anomalies, and preprocessing methodologies applied to the **REFIT: Electrical Load Measurements Dataset** (Murray et al., 2017, Loughborough & Strathclyde Universities). 

As specified in the assignment constraints:
- **Raw House 1 data** (`RAW_House1_Part1.csv` and `RAW_House1_Part2.csv`) was used exclusively for the Section 1 data cleaning exercise.
- **Strathclyde Official Cleaned Data** (`CLEAN_House1.csv` through `CLEAN_House5.csv`) was used for Section 2 (Washing Machine Usage Analysis) and Section 3 (Disaggregation Modeling).

---

## 2. Raw House 1 Coverage & Characteristics

The raw House 1 dataset records domestic electricity consumption captured via:
1. **Current Cost Envi CC128 Current Transformer (CT) clamp** measuring aggregate whole-home active power (Watts).
2. **Current Cost Individual Appliance Monitors (IAMs)** measuring active power (Watts) across 9 individual appliance circuits.

### Empirical Data Scope
- **Part 1 File**: `RAW_House1_Part1.csv` (October 9, 2013 13:48:47 to October 1, 2014 00:23:40, 4,377,294 rows).
- **Part 2 File**: `RAW_House1_Part2.csv` (June 27, 2014 11:10:04 to July 10, 2015 08:18:14, 4,141,469 rows).
- **Total Combined Raw Records**: **8,518,763 rows**.
- **Nominal Sampling Frequency**: Variable, event-triggered with periodic reporting roughly every 6 to 8 seconds.

---

## 3. Data Quality Issues Identified

A rigorous programmatic audit across all 8.5+ million rows revealed four major classes of raw data degradation:

### 3.1 3-Month File Overlap & Duplicate Timestamps
- **File Overlap**: Part 1 and Part 2 overlap between **June 27, 2014** and **October 1, 2014** (a 96-day overlap period containing hundreds of thousands of redundant sensor events).
- **Duplicate Timestamps**: **1,412,513 rows (16.58% of the raw dataset)** share an identical second-level timestamp with another record.
- **Cause**: Dual data logger uploads, asynchronous transmitter buffers, and transmission re-tries during the overlap period.

### 3.2 Sensor Transmission Corruption & Physically Impossible Spikes
A standard UK domestic plug socket operates at 230 V on a 13 A fuse, permitting a theoretical maximum continuous load of $230\text{ V} \times 13\text{ A} = 2,990\text{ W}$ (with short transient tolerances up to ~3,200 W – 3,600 W on standard 16 A ring circuits).

Our raw audit discovered severe multi-kilowatt sensor corruption spikes on individual plug monitors:
- **Appliance 2**: Maximum recorded raw power reached **98,301 W** (impossible for a domestic appliance).
- **Appliance 4**: Maximum recorded raw power reached **98,301 W**.
- **Appliance 8**: Maximum recorded raw power reached **98,301 W**.
- **Appliance 1**: Maximum recorded raw power reached **76,677 W**.
- **Appliance 3 & 5**: Maximum recorded raw power reached **73,725 W**.
- **Aggregate**: Maximum recorded raw spike reached **29,159 W** (41,054 raw readings exceeded 4,000 W).

*Root Cause*: RF bit-flips, wireless buffer corruption, or 16-bit integer sign overflows occurring during Current Cost wireless transmission to the base station.

### 3.3 Large Missing Intervals & Outages
- Smart meter loggers experienced disconnections, basestation crashes, and homeowner unplugging events.
- On a 1-minute uniform grid spanning October 9, 2013 to July 10, 2015 (920,031 total minutes), **114,547 minutes (12.45% of total time)** represent extended data gaps exceeding 2 consecutive minutes.

### 3.4 Delayed Appliance Installation
- **Appliance 9** contained **1,911,811 NaN values** in raw Part 1 because the sub-meter monitor was not deployed during the first few months of the REFIT study.

---

## 4. Cleaning Policies & Preprocessing Pipeline

The automated cleaning pipeline implemented in [`src/cleaning.py`](file:///d:/flockenergy_hitesh/src/cleaning.py) adheres to strict physical and statistical principles:

```
+-----------------------------------------------------------------------------------+
| RAW HOUSE 1 DATA (Part 1 + Part 2: 8,518,763 rows)                                |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 1. Timestamp Normalization & Chunk-Wise Deduplication                             |
|    - Parse timestamps to datetime64[ns]                                           |
|    - Aggregate duplicate timestamps using mean power per channel                  |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 2. Physical Validation & Outlier Capping                                          |
|    - Sub-metered IAM channels (Appliance 1-9): Clamped / nulled above 4,000 W      |
|    - Physical lower bound: Clamped negative values to 0 W                         |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 3. Uniform 1-Minute Grid Resampling                                               |
|    - Resample to complete continuous 1-minute DatetimeIndex                       |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 4. Selective Gap Handling Policy                                                  |
|    - Short gaps (<= 2 minutes): Linear interpolation (596 minutes)                |
|    - Long gaps (> 2 minutes): Preserved strictly as NaN (114,547 minutes)         |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| CLEANED HOUSE 1 DATASET (Outputs: outputs/tables/house1_cleaned_1min_summary.csv) |
+-----------------------------------------------------------------------------------+
```

### Preprocessing Policy Decisions & Justifications

1. **Deduplication via Mean Aggregation**:
   - Rather than dropping duplicate records arbitrarily (which would discard real energy measurements if two readings occurred within the same second), duplicate timestamps are averaged. This preserves the mean active power during that timestamp.

2. **Physical Socket Capping (4,000 W)**:
   - A threshold of 4,000 W was applied to all sub-metered channels. This is comfortably above the highest legitimate appliance draw (e.g. electric kettles and washing machine heating elements peak at 2,000 W – 3,000 W) while eliminating corrupted multi-kilowatt RF artifacts.

3. **Strict Preservation of Long Missing Gaps (> 2 Minutes)**:
   - **Why NOT forward-fill or back-fill?** If an outage lasts 6 hours or 3 days, forward-filling the last known power reading (e.g., 2,200 W during a wash cycle) would fabricate hundreds of kilowatt-hours of non-existent electricity. 
   - Linear interpolation was strictly capped at **2 minutes** (to bridge trivial 1-sample sensor jitter). All gaps longer than 2 minutes are preserved as `NaN` (unrecorded/missing).

---

## 5. Cleaned Dataset Summary

The resulting 1-minute cleaned dataset for House 1 spans **920,031 minutes** (saved to [`outputs/tables/house1_cleaned_1min_summary.csv`](file:///d:/flockenergy_hitesh/outputs/tables/house1_cleaned_1min_summary.csv)):

| Channel | Valid Minutes | Missing/Outage Minutes | Outage % | Mean Power (W) | Max Power (W) | Median Power (W) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Aggregate** | 805,484 | 114,547 | 12.45% | 477.37 | 13,763.29 | 245.78 |
| **Appliance 1 (Fridge)** | 804,106 | 115,925 | 12.60% | 17.69 | 3,072.00 | 0.00 |
| **Appliance 2 (Chest Freezer)** | 803,415 | 116,616 | 12.68% | 16.66 | 2,094.00 | 0.00 |
| **Appliance 3 (Upright Freezer)** | 804,063 | 115,968 | 12.60% | 29.18 | 532.11 | 0.00 |
| **Appliance 4 (Tumble Dryer)** | 804,591 | 115,440 | 12.55% | 1.92 | 2,670.00 | 0.00 |
| **Appliance 5 (Washing Machine)** | 799,463 | 120,568 | 13.10% | 10.82 | 2,461.25 | 0.00 |
| **Appliance 6 (Dishwasher)** | 804,539 | 115,492 | 12.55% | 11.16 | 2,377.09 | 0.00 |
| **Appliance 7 (Computer)** | 805,444 | 114,587 | 12.45% | 2.47 | 2,049.00 | 0.00 |
| **Appliance 8 (Television)** | 804,528 | 115,503 | 12.55% | 5.87 | 597.33 | 0.00 |
| **Appliance 9 (Electric Heater)** | 708,668 | 211,363 | 22.97% | 76.37 | 2,086.89 | 1.00 |

A visual before-and-after audit verifying raw spike elimination and gap preservation is available in [`outputs/figures/house1_cleaning_before_after.png`](file:///d:/flockenergy_hitesh/outputs/figures/house1_cleaning_before_after.png).

---

## 6. Remaining Data Quality Considerations

1. **Unmonitored Sub-Circuits**:
   - In REFIT, the sum of monitored appliances does not equal the whole-home aggregate. Unmonitored circuits (lighting, electric shower, oven/hob, auxiliary wall sockets) account for roughly 40–60% of aggregate energy consumption.
2. **Sub-Minute Switching Transients**:
   - Resampling from ~8 seconds to 1-minute averages rapid motor-starting spikes. This is desirable for energy disaggregation and grid-level smart meter simulation, but sub-cycle harmonic characteristics are absent.
3. **Appliance Mapping Variations**:
   - Appliance IDs differ between households (e.g. Washing Machine is Appliance 5 in House 1, Appliance 2 in House 2, Appliance 6 in House 3, and Appliance 3 in House 5). Any cross-household pipeline must strictly verify metadata mappings.

