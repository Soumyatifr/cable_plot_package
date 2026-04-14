#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


AWG_CONFIG = {
    "AWG18": {
        "area_m2": 1.9e-6,
        "rho20_ohm_m": 1.767e-8,
        "alpha_per_c": 2.70e-3,
        "ins_threshold_mohm": 100.0,
        "ins_ylim": (1.0, 1.0e4),
    },
    "AWG28": {
        "area_m2": 9.291e-8,
        "rho20_ohm_m": 1.84e-8,
        "alpha_per_c": 3.58e-3,
        "ins_threshold_mohm": 1000.0,
        "ins_ylim": (1.0, 4.0e5),
    },
}


def extract_pair_from_filename(filename: str) -> Tuple[str, str]:
    m = re.search(r"TIF[_-]?LIC[-_]?(\d+)[-_](\d+)", filename, re.IGNORECASE)
    if not m:
        raise ValueError(f"Could not extract cable pair from filename: {filename}")
    return m.group(1), m.group(2)


def find_txt_files(base_dir: Path) -> List[Path]:
    return sorted(p for p in base_dir.rglob("*.txt") if p.is_file())


def find_tif_files(base_dir: Path) -> List[Path]:
    return sorted(
        p for p in base_dir.rglob("*.txt")
        if re.search(r"TIF[_-]?LIC[-_]?\d+[-_]\d+", p.name, re.IGNORECASE)
    )


def build_ot_index(base_dir: Path) -> Dict[str, List[Path]]:
    index: Dict[str, List[Path]] = {}

    for p in find_txt_files(base_dir):
        name_lower = p.name.lower()
        if not name_lower.startswith("ot_lic") and not name_lower.startswith("ot-lic"):
            continue

        lic = None

        for parent in [p.parent] + list(p.parents):
            m = re.search(r"LIC[-_](\d+)", parent.name, re.IGNORECASE)
            if m:
                lic = m.group(1)
                break

        if lic is None:
            m = re.search(r"OT[_-]?LIC[-_]?(\d+)", p.name, re.IGNORECASE)
            if m:
                lic = m.group(1)

        if lic is not None:
            index.setdefault(lic, []).append(p)

    return index


def choose_ot_file_for_lic(lic: str, ot_index: Dict[str, List[Path]]) -> Path:
    if lic not in ot_index or not ot_index[lic]:
        raise FileNotFoundError(f"No OT_LIC file found for LIC {lic}")

    candidates = ot_index[lic]

    def score(p: Path) -> Tuple[int, int]:
        score = 0
        s = str(p).lower()

        if f"lic-{lic}".lower() in s or f"lic_{lic}".lower() in s:
            score += 5
        if "lab15" in s:
            score += 2
        if p.suffix.lower() == ".txt":
            score += 2
        if p.name.lower().startswith("ot_lic") or p.name.lower().startswith("ot-lic"):
            score += 1

        return (-score, len(str(p)))

    return sorted(candidates, key=score)[0]


def parse_temperature_c(text: str) -> Optional[float]:
    m = re.search(r"Temperature:\s*([0-9]+(?:[.,][0-9]+)?)", text, re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def clean_channel_for_group(channel: str, group: str) -> str:
    c = channel.strip()

    if group == "AWG18_INS":
        c = c.replace("LVreturn", "LVR")
        c = c.replace("PHreturn", "PHR")

    return c


def channel_group(channel: str, section: str) -> Optional[str]:
    c = channel.strip()

    if section == "continuity":
        if re.fullmatch(r"LV\d+", c) or re.fullmatch(r"LVreturn\d+", c):
            return "AWG18_CONT"
        if c in {"PH", "PHreturn"}:
            return "AWG18_CONT"
        if re.fullmatch(r"H\d+", c) or re.fullmatch(r"HR\d+", c):
            return "AWG28_CONT"
        if re.fullmatch(r"Tsensor\d+", c):
            return "AWG28_CONT"
        return None

    if section == "insulation":
        if re.fullmatch(r"LV\d+", c) or re.fullmatch(r"LVR\d+", c):
            return "AWG18_INS"
        if c in {"PH", "PHR"}:
            return "AWG18_INS"
        if re.fullmatch(r"HV\d+", c) or re.fullmatch(r"HVreturn\d+", c):
            return "AWG28_INS"
        if re.fullmatch(r"Tsensor\d+", c):
            return "AWG28_INS"
        return None

    return None


def parse_measurement_txt(txt_path: Path) -> Dict[str, object]:
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    temperature_c = parse_temperature_c(text)

    out = {
        "temperature_c": temperature_c,
        "AWG18_cont": {},
        "AWG28_cont": {},
        "AWG18_ins": {},
        "AWG28_ins": {},
    }

    section = None

    for raw in lines:
        line = raw.strip()

        if "CONTINUITY AND RESISTANCE MEASUREMENTS" in line:
            section = "continuity"
            continue

        if "INSULATION TEST 1 VS all" in line:
            section = "insulation"
            continue

        if "INSULATION GROUP TEST" in line:
            section = None
            continue

        if not line.startswith("Passed"):
            continue

        parts = [p.strip() for p in raw.split(";")]
        if len(parts) < 3:
            continue

        channel = parts[1]
        value_str = parts[2].replace(",", ".").strip()

        try:
            value = float(value_str)
        except ValueError:
            continue

        group = channel_group(channel, section) if section else None
        if group is None:
            continue

        clean_ch = clean_channel_for_group(channel, group)

        if group == "AWG18_CONT":
            out["AWG18_cont"][clean_ch] = value
        elif group == "AWG28_CONT":
            out["AWG28_cont"][clean_ch] = value
        elif group == "AWG18_INS":
            out["AWG18_ins"][clean_ch] = value / 1.0e6
        elif group == "AWG28_INS":
            out["AWG28_ins"][clean_ch] = value / 1.0e6

    return out


def read_jumper_resistance(csv_path: Path) -> Dict[str, float]:
    jumper: Dict[str, float] = {}

    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = [x.strip() for x in line.split(";")]
            if len(parts) < 2:
                continue

            ch = parts[0]
            val = parts[1].replace(",", ".")

            try:
                jumper[ch] = float(val)
            except ValueError:
                continue

    print(f"[INFO] Loaded {len(jumper)} jumper resistances from {csv_path}")
    return jumper


def correct_resistance_to_reference_temp(
    r_meas: float,
    temp_meas: float,
    temp_ref: float,
    awg: str,
) -> float:
    alpha = AWG_CONFIG[awg]["alpha_per_c"]
    return r_meas / (1.0 + alpha * (temp_meas - temp_ref))


def process_continuity(
    values: Dict[str, float],
    awg: str,
    temp_c: Optional[float],
    reference_temp: float,
    label: str = "",
    jumper_map: Optional[Dict[str, float]] = None,
    subtract_jumper: bool = False,
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    alpha = AWG_CONFIG[awg]["alpha_per_c"]

    if temp_c is None:
        print(f"[TEMP] {label} | {awg}: no temperature found -> no correction applied")
    else:
        corr_factor = 1.0 / (1.0 + alpha * (temp_c - reference_temp))
        print(
            f"[TEMP] {label} | {awg}: "
            f"T_meas = {temp_c:.2f} °C, T_ref = {reference_temp:.2f} °C, "
            f"alpha = {alpha:.5e} 1/°C, factor = {corr_factor:.6f}"
        )

    for ch, val in values.items():
        corrected = val

        if temp_c is not None:
            corrected = correct_resistance_to_reference_temp(
                corrected,
                temp_c,
                reference_temp,
                awg,
            )

        if subtract_jumper and jumper_map is not None:
            if ch in jumper_map:
                before = corrected
                corrected -= jumper_map[ch]
                print(
                    f"[JUMPER] {label} | {awg} | {ch}: "
                    f"R_corr = {before:.6f} Ω, "
                    f"R_jumper = {jumper_map[ch]:.6f} Ω, "
                    f"R_final = {corrected:.6f} Ω"
                )
            else:
                print(f"[JUMPER WARNING] {label} | {awg}: no jumper value for channel {ch}")

        out[ch] = corrected

    return out


def combine_sum(d1: Dict[str, float], d2: Dict[str, float]) -> Dict[str, float]:
    keys = [k for k in d1 if k in d2]
    return {k: d1[k] + d2[k] for k in keys}


def combine_average(d1: Dict[str, float], d2: Dict[str, float]) -> Dict[str, float]:
    keys = [k for k in d1 if k in d2]
    return {k: 0.5 * (d1[k] + d2[k]) for k in keys}


def align_series(d1: Dict[str, float], d2: Dict[str, float]) -> Tuple[List[str], np.ndarray, np.ndarray]:
    keys = [k for k in d1 if k in d2]
    if not keys:
        keys = sorted(set(d1).intersection(d2))

    y1 = np.array([d1[k] for k in keys], dtype=float)
    y2 = np.array([d2[k] for k in keys], dtype=float)
    return keys, y1, y2


def setup_common_axes_style(ax):
    ax.grid(True, axis="y", alpha=0.35)
    ax.tick_params(axis="x", rotation=80)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)


def plot_continuity_panel(
    ax,
    awg: str,
    channels: List[str],
    y_comp: np.ndarray,
    y_together: np.ndarray,
    lic1: str,
    lic2: str,
):
    pair_label = f"{lic1}+{lic2}"
    legend_comp = f"OT_LIC {pair_label} COMPOSITION of single measurements at Lab 15"
    legend_together = f"OT_LIC {pair_label} together at Lab15"

    x = np.arange(len(channels))

    ax.plot(x, y_comp, linestyle="--", marker="s", label=legend_comp)
    ax.plot(x, y_together, linestyle="--", marker="^", label=legend_together)

    ax.set_title(f"{awg} - Electrical Resistance per channel", fontsize=17, weight="bold")
    ax.set_ylabel("Resistance [Ω]", fontsize=20, weight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(channels)
    ax.legend(loc="upper left", fontsize=10, frameon=False, handlelength=3.0)
    setup_common_axes_style(ax)


def plot_insulation_panel(
    ax,
    awg: str,
    channels: List[str],
    y_comp: np.ndarray,
    y_together: np.ndarray,
    lic1: str,
    lic2: str,
):
    pair_label = f"{lic1}+{lic2}"
    legend_comp = f"OT_LIC {pair_label} COMPOSITION of single measurements at Lab 15"
    legend_together = f"OT_LIC {pair_label} together at Lab15"

    x = np.arange(len(channels))

    ax.plot(x, y_comp, label=legend_comp)
    ax.plot(x, y_together, label=legend_together)

    ax.set_title(f"{awg} - Insulation Resistance of all channels", fontsize=17, weight="bold")
    ax.set_ylabel("Insulation Resistance [MΩ]", fontsize=20, weight="bold", color="red")
    ax.set_xticks(x)
    ax.set_xticklabels(channels)

    ax.set_yscale("log")
    ax.set_ylim(*AWG_CONFIG[awg]["ins_ylim"])

    thr = AWG_CONFIG[awg]["ins_threshold_mohm"]
    ax.axhline(thr, linestyle="--", linewidth=1.0)
    ax.text(
        0.06,
        thr * 1.15,
        "Threshold",
        fontsize=11,
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.25", fc="0.92", ec="0.4"),
    )

    ax.legend(loc="lower center", fontsize=10, frameon=False, handlelength=3.0)
    setup_common_axes_style(ax)


def make_plot(
    tif_file: Path,
    tif_data: Dict[str, object],
    ot1_data: Dict[str, object],
    ot2_data: Dict[str, object],
    lic1: str,
    lic2: str,
    output_dir: Path,
    jumper_map: Dict[str, float],
    reference_temp: float,
):
    tif_awg18_cont = process_continuity(
        tif_data["AWG18_cont"],
        "AWG18",
        tif_data["temperature_c"],
        reference_temp,
        label=f"TIF {lic1}+{lic2}",
        jumper_map=jumper_map,
        subtract_jumper=True,
    )
    tif_awg28_cont = process_continuity(
        tif_data["AWG28_cont"],
        "AWG28",
        tif_data["temperature_c"],
        reference_temp,
        label=f"TIF {lic1}+{lic2}",
        jumper_map=jumper_map,
        subtract_jumper=True,
    )

    ot1_awg18_cont = process_continuity(
        ot1_data["AWG18_cont"],
        "AWG18",
        ot1_data["temperature_c"],
        reference_temp,
        label=f"OT {lic1}",
        jumper_map=None,
        subtract_jumper=False,
    )
    ot2_awg18_cont = process_continuity(
        ot2_data["AWG18_cont"],
        "AWG18",
        ot2_data["temperature_c"],
        reference_temp,
        label=f"OT {lic2}",
        jumper_map=None,
        subtract_jumper=False,
    )
    ot1_awg28_cont = process_continuity(
        ot1_data["AWG28_cont"],
        "AWG28",
        ot1_data["temperature_c"],
        reference_temp,
        label=f"OT {lic1}",
        jumper_map=None,
        subtract_jumper=False,
    )
    ot2_awg28_cont = process_continuity(
        ot2_data["AWG28_cont"],
        "AWG28",
        ot2_data["temperature_c"],
        reference_temp,
        label=f"OT {lic2}",
        jumper_map=None,
        subtract_jumper=False,
    )

    comp_awg18_cont = combine_sum(ot1_awg18_cont, ot2_awg18_cont)
    comp_awg28_cont = combine_sum(ot1_awg28_cont, ot2_awg28_cont)

    comp_awg18_ins = combine_average(ot1_data["AWG18_ins"], ot2_data["AWG18_ins"])
    comp_awg28_ins = combine_average(ot1_data["AWG28_ins"], ot2_data["AWG28_ins"])

    ch18c, y18c_comp, y18c_tif = align_series(comp_awg18_cont, tif_awg18_cont)
    ch28c, y28c_comp, y28c_tif = align_series(comp_awg28_cont, tif_awg28_cont)
    ch18i, y18i_comp, y18i_tif = align_series(comp_awg18_ins, tif_data["AWG18_ins"])
    ch28i, y28i_comp, y28i_tif = align_series(comp_awg28_ins, tif_data["AWG28_ins"])

    fig, axes = plt.subplots(2, 2, figsize=(18, 10))
    fig.subplots_adjust(hspace=0.35, wspace=0.22, left=0.08, right=0.98, top=0.82, bottom=0.14)

    pair_label = f"{lic1}+{lic2}"

    fig.text(
        0.5,
        0.965,
        f"CABLE {pair_label}",
        fontsize=30,
        weight="bold",
        ha="center",
        va="top",
    )
    fig.text(
        0.5,
        0.925,
        f"Resistance corrected to {reference_temp:.0f}°C",
        fontsize=18,
        ha="center",
        va="top",
    )

    plot_continuity_panel(axes[0, 0], "AWG18", ch18c, y18c_comp, y18c_tif, lic1, lic2)
    plot_continuity_panel(axes[0, 1], "AWG28", ch28c, y28c_comp, y28c_tif, lic1, lic2)
    plot_insulation_panel(axes[1, 0], "AWG18", ch18i, y18i_comp, y18i_tif, lic1, lic2)
    plot_insulation_panel(axes[1, 1], "AWG28", ch28i, y28i_comp, y28i_tif, lic1, lic2)

    png_out = output_dir / f"{tif_file.stem}_four_panel.png"
    pdf_out = output_dir / f"{tif_file.stem}_four_panel.pdf"

    fig.savefig(png_out, dpi=180)
    fig.savefig(pdf_out)
    plt.close(fig)

    print(f"[OK] Wrote {png_out}")
    print(f"[OK] Wrote {pdf_out}")


def parse_args():
    parser = argparse.ArgumentParser(description="Produce four-panel cable plots from TXT files only")
    parser.add_argument("--input-dir", required=True, help="Directory containing the txt files")
    parser.add_argument("--jumper-file", required=True, help="CSV file containing jumper resistances")
    parser.add_argument(
        "--reference-temp",
        type=float,
        default=20.0,
        help="Reference temperature for resistance correction (default: 20°C)",
    )
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--pair", default=None, help='Optional pair, e.g. "042-043"')
    return parser.parse_args()


def main():
    args = parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tif_files = find_tif_files(input_dir)
    if not tif_files:
        raise FileNotFoundError(f"No TIF_LIC txt files found in {input_dir}")

    if args.pair:
        pair_norm = args.pair.replace("_", "-")
        tif_files = [p for p in tif_files if pair_norm in p.name]
        if not tif_files:
            raise FileNotFoundError(f"No TIF file found for pair {args.pair}")

    ot_index = build_ot_index(input_dir)
    jumper_map = read_jumper_resistance(Path(args.jumper_file).expanduser().resolve())

    for tif_file in tif_files:
        try:
            lic1, lic2 = extract_pair_from_filename(tif_file.name)

            ot1_file = choose_ot_file_for_lic(lic1, ot_index)
            ot2_file = choose_ot_file_for_lic(lic2, ot_index)

            print(f"\n[PAIR] Processing {lic1}+{lic2}")
            print(f"[INFO] Reference temperature: {args.reference_temp:.2f} °C")
            print(f"[FILE] TIF: {tif_file}")
            print(f"[FILE] OT1: {ot1_file}")
            print(f"[FILE] OT2: {ot2_file}")

            tif_data = parse_measurement_txt(tif_file)
            ot1_data = parse_measurement_txt(ot1_file)
            ot2_data = parse_measurement_txt(ot2_file)

            make_plot(
                tif_file=tif_file,
                tif_data=tif_data,
                ot1_data=ot1_data,
                ot2_data=ot2_data,
                lic1=lic1,
                lic2=lic2,
                output_dir=output_dir,
                jumper_map=jumper_map,
                reference_temp=args.reference_temp,
            )
        except Exception as e:
            print(f"[FAIL] {tif_file.name}: {e}")


if __name__ == "__main__":
    main()
