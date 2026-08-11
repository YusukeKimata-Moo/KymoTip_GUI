"""Core utilities for computing and visualizing cell-elongation growth curves."""
from __future__ import annotations

import csv

import numpy as np


def compute_cell_lengths(centerline_base_path, num_frames, pixel_per_micron=1.0):
    """各フレームのcenterlineデータ(x, y)から、弧長ベースの細胞長(um)を計算する。"""
    lengths = []
    for i in range(num_frames):
        data = np.loadtxt(f"{centerline_base_path}_{i:03d}.txt")
        distances = np.sqrt(np.diff(data[:, 0]) ** 2 + np.diff(data[:, 1]) ** 2)
        lengths.append(np.sum(distances) / pixel_per_micron)
    return np.array(lengths)


def compute_growth_rate(cell_lengths_um, time_interval_sec):
    """細胞長の時系列から伸長速度(nm/min)を計算する(各フレーム位置での中心差分)。"""
    dt_min = time_interval_sec / 60.0
    return np.gradient(np.asarray(cell_lengths_um, dtype=float), dt_min) * 1000.0


def smooth_series_loess(values, degree=2, fraction=0.3):
    """1次元時系列をLOESS(LOWESS)平滑化する。

    trajectory.smooth_loessと同じ`loess`パッケージを使い、プロジェクト内の
    平滑化実装を統一する。
    """
    from loess.loess_1d import loess_1d

    x = np.arange(len(values), dtype=float)
    _, smoothed, _ = loess_1d(x, np.asarray(values, dtype=float), degree=degree, frac=fraction)
    return smoothed


def save_growth_csv(
    out_path, frame_x, time_min, cell_length_um, cell_length_smooth, growth_rate, growth_rate_smooth
):
    """フレームごとの細胞長・伸長速度(生値・平滑化値)をCSVに保存する。

    Excelでの文字化けを避けるためUTF-8 BOM付き(utf-8-sig)で保存する。
    """
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "frame",
                "time_min",
                "cell_length_um",
                "cell_length_um_smooth",
                "growth_rate_nm_min",
                "growth_rate_nm_min_smooth",
            ]
        )
        for row in zip(
            frame_x,
            time_min,
            cell_length_um,
            cell_length_smooth if cell_length_smooth is not None else [""] * len(frame_x),
            growth_rate,
            growth_rate_smooth if growth_rate_smooth is not None else [""] * len(frame_x),
        ):
            writer.writerow(row)


def _new_figure(fig_size, labsize):
    from matplotlib.figure import Figure

    fig = Figure(figsize=fig_size)
    axs = fig.add_subplot(111)
    axs.tick_params(labelsize=labsize)
    return fig, axs


def plot_cell_length(x, cell_length_um, smoothed_um, xlabel, out_path, fig_size=(8, 5), labsize=12):
    fig, axs = _new_figure(fig_size, labsize)
    axs.plot(x, cell_length_um, "o-", markersize=3, color="tab:blue", label="Cell length")
    if smoothed_um is not None:
        axs.plot(x, smoothed_um, "-", color="tab:red", linewidth=2, label="LOWESS")
        axs.legend(fontsize=labsize * 0.8)
    axs.set_xlabel(xlabel, fontsize=labsize)
    axs.set_ylabel("Cell length (um)", fontsize=labsize)
    fig.tight_layout()
    fig.savefig(out_path, format="png")
    return str(out_path)


def plot_growth_rate(x, growth_rate, smoothed, xlabel, out_path, fig_size=(8, 5), labsize=12):
    fig, axs = _new_figure(fig_size, labsize)
    axs.plot(x, growth_rate, "o-", markersize=3, color="tab:green", label="Growth rate")
    if smoothed is not None:
        axs.plot(x, smoothed, "-", color="tab:red", linewidth=2, label="LOWESS")
        axs.legend(fontsize=labsize * 0.8)
    axs.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    axs.set_xlabel(xlabel, fontsize=labsize)
    axs.set_ylabel("Growth rate (nm/min)", fontsize=labsize)
    fig.tight_layout()
    fig.savefig(out_path, format="png")
    return str(out_path)


def plot_overlay(
    x, cell_length_um, cell_length_smooth, growth_rate, growth_rate_smooth, xlabel, out_path,
    fig_size=(8, 5), labsize=12,
):
    fig, axs = _new_figure(fig_size, labsize)
    axs2 = axs.twinx()

    length_series = cell_length_smooth if cell_length_smooth is not None else cell_length_um
    rate_series = growth_rate_smooth if growth_rate_smooth is not None else growth_rate

    line1, = axs.plot(x, length_series, "-", color="tab:blue", linewidth=2, label="Cell length")
    line2, = axs2.plot(x, rate_series, "-", color="tab:orange", linewidth=2, label="Growth rate")

    axs.set_xlabel(xlabel, fontsize=labsize)
    axs.set_ylabel("Cell length (um)", fontsize=labsize, color="tab:blue")
    axs2.set_ylabel("Growth rate (nm/min)", fontsize=labsize, color="tab:orange")
    axs.tick_params(axis="y", labelcolor="tab:blue", labelsize=labsize)
    axs2.tick_params(axis="y", labelcolor="tab:orange", labelsize=labsize)
    axs.tick_params(axis="x", labelsize=labsize)
    # twinxで2本の線が別々のAxesに属するため、locの自動選択(best)は片方の
    # データしか考慮できずプロットに重なりうる。プロット枠の外側(上)に固定配置する。
    axs.legend(
        handles=[line1, line2], fontsize=labsize * 0.8,
        loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2, frameon=False,
    )
    fig.tight_layout()
    fig.savefig(out_path, format="png", bbox_inches="tight")
    return str(out_path)
