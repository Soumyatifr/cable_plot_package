# Cable Resistance Comparison Plot Package (Lab15)

This package produces **four-panel comparison plots** for cable measurements performed at **Lab15**, combining:

* pairwise **TIF measurements** (cables measured together)
* individual **OT measurements** (single cable measurements)

The script automatically:

* reads Lab15 `.txt` measurement files
* applies **temperature correction** to a configurable reference temperature
* subtracts **jumper resistance** from **TIF continuity measurements**
* builds **composition curves** from individual OT measurements
* produces publication-quality **four-panel comparison plots**

---

# Installation

Create and activate a Python virtual environment:

```bash
python3 -m venv cable_env
source cable_env/bin/activate
```

Install required packages:

```bash
pip install matplotlib numpy pandas
```

---

# Check available options

To see all runtime options:

```bash
python3 plot_cable_report.py --help
```

To install the package
```bash
git clone https://github.com/Soumyatifr/cable_plot_package 
```

Example output:

```text
usage: plot_cable_report.py [-h] --input-dir INPUT_DIR --jumper-file JUMPER_FILE
                           [--reference-temp REFERENCE_TEMP]
                           [--output-dir OUTPUT_DIR]
                           [--pair PAIR]

Produce four-panel cable plots from TXT files only

options:
  -h, --help            show this help message and exit
  --input-dir INPUT_DIR
                        Directory containing the txt files
  --jumper-file JUMPER_FILE
                        CSV file containing jumper resistances
  --reference-temp REFERENCE_TEMP
                        Reference temperature for resistance correction (default: 20°C)
  --output-dir OUTPUT_DIR
                        Output directory
  --pair PAIR           Optional pair, e.g. "042-043"
```

---

# Run the script (single cable pair)

Example:

```bash
python3 plot_cable_report.py \
  --input-dir ../PS_PP1_test/ \
  --jumper-file jumper_resistance.csv \
  --reference-temp 20 \
  --output-dir output \
  --pair 042-043
```

This produces:

```
output/TIF_LIC-042-043_*_four_panel.png
output/TIF_LIC-042-043_*_four_panel.pdf
```

---

# Run the script (all available cable pairs)

To process **all TIF files automatically**, simply omit the `--pair` argument:

```bash
python3 plot_cable_report.py \
  --input-dir ../PS_PP1_test/ \
  --jumper-file jumper_resistance.csv \
  --reference-temp 20 \
  --output-dir output
```

The script will detect and process all files matching:

```
TIF_LIC-XXX-YYY*.txt
```

---

# Expected input directory structure

Example:

```
PS_PP1_test/
│
├── TIF_LIC-042-043_2026_03_26_14_03_50.txt
├── TIF_LIC-044-045_2026_03_27_10_22_01.txt
│
├── Lab15_LIC-042/
│   └── OT_LIC-3020839_06_08_2025_15_48_59.txt
│
├── Lab15_LIC-043/
│   └── OT_LIC-3020840_05_08_2025_17_53_40.txt
│
└── Lab15_LIC-044/
    └── OT_LIC-xxxxx.txt
```

---

# Input file requirements

## TIF files

Must:

* start with `TIF`
* contain pair number `XXX-YYY`

Example:

```
TIF_LIC-042-043_*.txt
```

These represent:

```
pairwise Lab15 measurements
```

---

## OT files

Must exist inside directories:

```
Lab15_LIC-042/
Lab15_LIC-043/
```

Example:

```
Lab15_LIC-042/OT_LIC-*.txt
Lab15_LIC-043/OT_LIC-*.txt
```

These represent:

```
single cable measurements
```

---

# Jumper resistance file format

Example:

```
LV1 ;0.034866422
LVreturn1 ;0.035438078
LV2 ;0.034517548
...
H12 ;0.020883278
HR3 ;0.027934136
```

Rules:

* separator must be `;`
* channel names must match Lab15 channel naming
* units must be **Ohm**

Applied automatically to:

```
TIF continuity measurements only
```

Not applied to:

```
OT composition measurements
```

---

# Temperature correction

Continuity resistance values are corrected to a reference temperature:

Default:

```
20°C
```

Formula used:

```
R_ref = R_measured / (1 + α (T_measured − T_ref))
```

Temperature coefficients:

| Cable type | α (°C⁻¹)    |
| ---------- | ----------- |
| AWG18      | 2.70 × 10⁻³ |
| AWG28      | 3.58 × 10⁻³ |

Change reference temperature:

```bash
--reference-temp 25
```

Example plot header:

```
Resistance corrected to 25°C
```

---

# Continuity correction logic (upper plots)

Composition curve:

```
OT_042 + OT_043
```

with temperature correction applied.

Together curve:

```
TIF measurement
− jumper resistance
+ temperature correction
```

applied channel-by-channel.

---

# Insulation plots (lower plots)

Composition curve:

```
average(OT_042 , OT_043)
```

Together curve:

```
TIF measurement
```

Threshold lines:

| Cable | Threshold |
| ----- | --------- |
| AWG18 | 100 MΩ    |
| AWG28 | 1000 MΩ   |

Plots are shown on:

```
log scale starting from 1 MΩ
```

---

# Output

Each cable pair produces:

```
PNG figure
PDF figure
```

Example:

```
output/
└── TIF_LIC-042-043_2026_03_26_14_03_50_four_panel.png
```

Each figure contains:

```
AWG18 continuity comparison
AWG28 continuity comparison
AWG18 insulation comparison
AWG28 insulation comparison
```

with:

```
temperature correction applied
jumper correction applied
Lab15 composition comparison
```

---

# Example workflow

```bash
python3 -m venv cable_env
source cable_env/bin/activate

pip install matplotlib numpy pandas

python3 plot_cable_report.py \
  --input-dir ../PS_PP1_test/ \
  --jumper-file jumper_resistance.csv \
  --reference-temp 20 \
  --output-dir output
```

Plots will be written to:

```
output/
```

---

