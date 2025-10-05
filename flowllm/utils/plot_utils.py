from pathlib import Path
from typing import Dict

from matplotlib import pyplot as plt


def calculate_max_drawdown(uplift: list):
    """
    A list of uplift values following a pure -1.
    """
    uplift_list = [x + 1 for x in uplift]
    cumulative_max = uplift_list[0]
    max_drawdown = 0

    for value in uplift_list:
        cumulative_max = max(cumulative_max, value)
        drawdown = value / cumulative_max - 1
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown * 100


def plot_figure(plot_dict: Dict[str, list],
                output_path: str | Path,
                xs: list = None,
                flag: bool = False,
                ticks_gap: int = None,
                enable_drawdown: bool = True,
                extra_content: str = ""):
    dt_len = len(list(plot_dict.values())[0])
    plt.figure(figsize=(12, 6))

    if xs is None:
        xs = [i for i in range(dt_len)]

    for key, ys in plot_dict.items():
        if flag:
            new_ys = ys
        else:
            new_ys = []
            for i in range(len(ys)):
                new_ys.append(sum(ys[:i + 1]))

        label = f"{key}@{new_ys[-1]:.2f}"
        if enable_drawdown:
            label += f"@{calculate_max_drawdown(new_ys):.2f}%"
        plt.plot(xs, new_ys, label=label)

    if ticks_gap is not None:
        plt.xticks(ticks=range(0, len(xs), ticks_gap), labels=xs[::ticks_gap], rotation=45)

    plt.xlabel("x")
    plt.ylabel("y")
    plt.grid()
    plt.legend()

    if extra_content:
        plt.text(x=-0.5, y=-1, s=extra_content, fontsize=8)

    plt.savefig(output_path)
    plt.close()
