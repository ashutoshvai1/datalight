# Primary testbed: Tennessee Eastman CSV

This document describes Datalight's primary testbed and demo source. Datalight
is a generic CSV data-reliability and monitoring application; the facts below
describe this export, not a required input schema or universal operating rules.
See [architecture](architecture.md) for runtime boundaries and current source
conventions, and the [roadmap](roadmap.md) for portability work.

Use this reference for offline data preparation, evaluation, and demo selection.
Do not supply it as model context or use its known labels, column identities,
run lengths, ranges, or cadence as implicit detector knowledge. Numeric channels
and behavior must be inferred from the supplied observations. Dataset-specific
metadata and sequence conventions belong in source adapters or explicit
configuration. Any future domain rules must be separately approved and versioned.

The value ranges below include faulted observations; they are descriptive
statistics, not physical limits. `sample` is a within-run ordering coordinate,
not a timestamp or a documented sampling interval. The initial analysis window
remains provisional even when this reference identifies a run as normal.

The [README](../README.md) explains how to reproduce and launch the three demonstration CSVs.
Real observations remain in ignored local CSV files; synthetic CI fixtures stay
separate.

`te_process.csv`. What is in the file: its shape, its columns, how the
rows are ordered, and what the values look like. Every figure here was measured
over all 15,330,000 rows.

---

## 1. What it is

Simulated output from the Tennessee Eastman chemical process, a standard
benchmark for fault detection. One row is one sampling instant in one
simulation run.

**6.0 GB, 15,330,000 rows, 57 columns.**

## 2. What the file contains

Three things vary across the file: which fault is active, which split a run
belongs to, and which run it is.

- **21 scenarios**, `faultNumber` 0 to 20: normal operation (0) and 20 fault types.
- **2 splits**, `source` either `train` or `test`.
- **500 runs** of each fault in each split.

That is 21 x 2 x 500 = **21,000 separate simulation runs**.

| | train | test |
|---|---|---|
| samples per run | 500 | 960 |
| runs per fault | 500 | 500 |
| rows per fault | 250,000 | 480,000 |
| run ids used | 1 to 500 | 1 to 500 |

**Run ids repeat.** Every one of the 42 fault-and-split combinations numbers
its runs from 1, so `simulationRun` value 1 appears 42 times in the file and
means a different simulation each time. A run is identified by run id, fault
number and split together.

## 3. How the rows are ordered

Row ranges in this section are zero-based data-row indices, excluding the header.
The application's row ranges and demo provenance use one-based data-row numbers.

The file is in four sections, and **the rows of a given fault are not
contiguous**.

| rows | contents | order within the section |
|---|---|---|
| 0 to 249,999 | train, fault 0 | run 1, run 2, ... run 500 |
| 250,000 to 5,249,999 | train, faults 1 to 20 | run 1 fault 1, run 1 fault 2, ... run 1 fault 20, then run 2 fault 1, ... |
| 5,250,000 to 5,729,999 | test, fault 0 | run 1, run 2, ... run 500 |
| 5,730,000 to 15,329,999 | test, faults 1 to 20 | the same cycle, 960 rows per block |

Inside the faulty sections the file cycles through all twenty faults for run 1,
then all twenty for run 2, and so on. A single fault's 500 runs are therefore
spread across the whole section in 500 separate blocks of 500 or 960 rows.

## 4. The columns

57 columns. Three are identifiers, two describe the run, 52 are signals.

### Position 1 to 3, and 56 to 57

| # | column | type | values |
|---|---|---|---|
| 1 | `faultNumber` | float | 0.0 to 20.0. Which fault this run has |
| 2 | `simulationRun` | float | 1.0 to 500.0. Which run, within its fault and split |
| 3 | `sample` | integer | 1 to 500 (train) or 1 to 960 (test). Position within the run |
| 56 | `source` | text | `train` or `test` |
| 57 | `fault_status` | text | `normal` or `faulty` |

**`fault_status` labels the run, not the row.** In a faulty test run it reads
`faulty` from sample 1 onward, even though the fault is introduced part way
through. It tells you the run is a faulty one; it does not tell you when the
fault started.

### Position 4 to 55: the signals

52 numeric columns, in two name groups:

- **`xmeas_1` to `xmeas_41`**, 41 columns, positions 4 to 44
- **`xmv_1` to `xmv_11`**, 11 columns, positions 45 to 55

## 5. Run structure

The data is a set of independent runs, not one continuous history. `sample`
restarts at 1 whenever a new run begins.

```
faultNumber  simulationRun  sample   xmeas_1   ...
    0.0           1.0          1     0.25038
    0.0           1.0          2     0.25109
   ...           ...          ...
    0.0           1.0        500     0.24980
    0.0           2.0          1     0.25050    <- new run, sample back to 1
```

The local full-file run inventory verified on 2026-09-19 contains 10,500 training
runs of exactly 500 rows and 10,500 test runs of exactly 960 rows, with no sample
gaps or duplicates. No shortened runs were found in this export. These lengths
are testbed facts, not requirements for other Datalight inputs.

## 6. How often each signal changes

Measured as the number of consecutive rows per value change, within runs, over
the whole file. The 52 signals fall into three groups:

| changes every | columns | which |
|---|---|---|
| ~1 row | 33 | `xmeas_1` to `xmeas_22`, and all 11 `xmv` columns |
| 2 rows | 14 | `xmeas_23` to `xmeas_36` |
| 5 rows | 5 | `xmeas_37` to `xmeas_41` |

A column in the 5-row group repeats its value for four rows before changing, so
it supplies one reading where the fast columns supply five.

## 7. Value ranges

Over all 15,330,000 rows, so these ranges include the faulty runs and are
wider than any single fault-free run would show.

Means span five orders of magnitude. The change rate column repeats section 6
per column.

| column | min | max | mean | std | changes every |
|---|---|---|---|---|---|
| `xmeas_1` | -0.004986 | 1.018 | 0.2578 | 0.1409 | 1.1 |
| `xmeas_2` | 3,308 | 3,907 | 3,665 | 42.91 | 1.1 |
| `xmeas_3` | 3,541 | 5,176 | 4,509 | 107 | 1.1 |
| `xmeas_4` | 6.64 | 12.24 | 9.381 | 0.3672 | 1.1 |
| `xmeas_5` | 25.35 | 28.57 | 26.9 | 0.2282 | 1.1 |
| `xmeas_6` | 39.66 | 44.65 | 42.37 | 0.3165 | 1.1 |
| `xmeas_7` | 2,414 | 3,000 | 2,723 | 76.37 | 1.1 |
| `xmeas_8` | 61.13 | 87.19 | 74.87 | 1.281 | 1.1 |
| `xmeas_9` | 119.6 | 121 | 120.4 | 0.06853 | 1.2 |
| `xmeas_10` | 0.0184 | 0.8207 | 0.3447 | 0.0808 | 1.1 |
| `xmeas_11` | 68.1 | 87.59 | 79.73 | 1.773 | 1.1 |
| `xmeas_12` | 44.63 | 55.48 | 49.99 | 0.9999 | 1.1 |
| `xmeas_13` | 2,317 | 2,945 | 2,652 | 77.27 | 1.1 |
| `xmeas_14` | 18.44 | 33.09 | 25.11 | 1.107 | 1.1 |
| `xmeas_15` | 44.31 | 55.91 | 49.96 | 1.014 | 1.1 |
| `xmeas_16` | 2,870 | 3,453 | 3,121 | 77.7 | 1.1 |
| `xmeas_17` | 19.14 | 27.24 | 22.93 | 0.6472 | 1.1 |
| `xmeas_18` | 52.12 | 74.7 | 66 | 1.728 | 1.1 |
| `xmeas_19` | -3.537 | 466.7 | 246.1 | 67.13 | 1.1 |
| `xmeas_20` | 230.2 | 400.7 | 340.8 | 11.14 | 1.1 |
| `xmeas_21` | 79.9 | 100.3 | 94.44 | 1.238 | 1.1 |
| `xmeas_22` | 62.64 | 83.81 | 77.06 | 1.318 | 1.1 |
| `xmeas_23` | 23.23 | 40.21 | 32.02 | 1.74 | 2.0 |
| `xmeas_24` | 7.444 | 10.35 | 8.871 | 0.2255 | 2.0 |
| `xmeas_25` | 16.91 | 36.47 | 26.77 | 1.883 | 2.0 |
| `xmeas_26` | 5.899 | 7.885 | 6.871 | 0.135 | 2.0 |
| `xmeas_27` | 12.05 | 26.92 | 18.68 | 0.9945 | 2.0 |
| `xmeas_28` | 0.8848 | 2.165 | 1.629 | 0.1268 | 2.0 |
| `xmeas_29` | 20 | 45.41 | 32.71 | 2.619 | 2.0 |
| `xmeas_30` | 11.79 | 15.82 | 13.79 | 0.2892 | 2.0 |
| `xmeas_31` | 10.3 | 39.24 | 24.56 | 2.893 | 2.0 |
| `xmeas_32` | 0.2469 | 2.651 | 1.248 | 0.1495 | 2.0 |
| `xmeas_33` | 9.663 | 29.76 | 18.42 | 1.395 | 2.0 |
| `xmeas_34` | 1.255 | 2.973 | 2.222 | 0.1729 | 2.0 |
| `xmeas_35` | 3.039 | 6.497 | 4.776 | 0.343 | 2.0 |
| `xmeas_36` | 1.34 | 3.119 | 2.263 | 0.1817 | 2.0 |
| `xmeas_37` | -0.03097 | 0.06693 | 0.01787 | 0.0102 | 5.0 |
| `xmeas_38` | 0.3891 | 1.71 | 0.8365 | 0.09163 | 5.0 |
| `xmeas_39` | 0.02031 | 0.1737 | 0.09734 | 0.0133 | 5.0 |
| `xmeas_40` | 50.03 | 57.12 | 53.74 | 0.5858 | 5.0 |
| `xmeas_41` | 40.02 | 47.34 | 43.8 | 0.6116 | 5.0 |
| `xmv_1` | 28.12 | 100 | 63.86 | 4.756 | 1.0 |
| `xmv_2` | 7.348 | 100 | 54.56 | 6.753 | 1.0 |
| `xmv_3` | -0.3587 | 100.2 | 29.48 | 19.4 | 1.1 |
| `xmv_4` | -0.005223 | 100 | 63.46 | 8.219 | 1.0 |
| `xmv_5` | -0.1069 | 100.1 | 23.13 | 11.92 | 1.1 |
| `xmv_6` | 0 | 97.53 | 39.51 | 12.8 | 1.0 |
| `xmv_7` | 22.29 | 54.23 | 38.06 | 2.943 | 1.1 |
| `xmv_8` | 33.37 | 60.22 | 46.43 | 2.348 | 1.1 |
| `xmv_9` | -0.6834 | 100.6 | 49.88 | 17.14 | 1.1 |
| `xmv_10` | -0.5157 | 100.6 | 41.96 | 11 | 1.0 |
| `xmv_11` | -0.006774 | 100 | 19.16 | 7.643 | 1.0 |

## 8. Completeness

| | |
|---|---|
| rows | 15,330,000 |
| missing values | **0** |
| non-numeric values in a signal column | **0** |
| gaps in the `sample` index | **none** |

Every cell is populated and every signal column parses as a number. There are
no nulls, no blanks and no placeholder tokens anywhere in the file.

## 9. Quick reference

| question | answer |
|---|---|
| how many rows | 15,330,000 |
| how many columns | 57: 3 identifiers, 2 run labels, 52 signals |
| how many runs | 21,000 |
| how long is a run | 500 rows (train) or 960 (test) |
| what identifies a run | `faultNumber` + `source` + `simulationRun` together |
| which column orders observations | `sample`, restarting each run; no timestamp or sampling interval is supplied |
| how many fault types | 20, numbered 1 to 20, plus fault-free scenario 0 |
| is anything missing | no |
