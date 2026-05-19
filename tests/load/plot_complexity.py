"""Построение графиков зависимости времени и памяти от управляющего параметра.

Рисует четыре PNG-файла в backend/app/resources/figures/:
  - complexity_param_generator_time.png   — время ParamGeneratorService(r)
  - complexity_param_generator_memory.png — память ParamGeneratorService(r)
  - complexity_orchestrator_time.png      — время TaskOrchestrator(m)
  - complexity_orchestrator_memory.png    — память TaskOrchestrator(m)

Данные забиты в скрипт явно — обновляйте константы PARAM_DATA / ORCH_DATA
после каждого запуска бенчмарков.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Результаты bench_param_generator.py: (r, время мкс, пиковая память KB).
PARAM_DATA: list[tuple[int, float, float]] = [
    (1, 3.283, 1.59),
    (2, 30.411, 6.53),
    (3, 63.638, 11.38),
    (4, 108.491, 16.12),
    (5, 117.066, 20.85),
]

# Результаты bench_orchestrator.py: (m, время мс, пиковая память KB).
ORCH_DATA: list[tuple[int, float, float]] = [
    (1, 124.942, 1.60),
    (2, 249.812, 1.79),
    (3, 374.403, 1.79),
]

OUT_DIR = Path(__file__).resolve().parents[2] / "backend" / "app" / "resources" / "figures"


def _plot_linear(
    xs: np.ndarray,
    ys: np.ndarray,
    xlabel: str,
    ylabel: str,
    title: str,
    out_path: Path,
    fit_format: str,
) -> None:
    """Рисует точки + аппроксимирующую прямую методом наименьших квадратов."""
    slope, intercept = np.polyfit(xs, ys, 1)
    fit_xs = np.linspace(xs.min() - 0.2, xs.max() + 0.2, 100)
    fit_ys = slope * fit_xs + intercept

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    ax.plot(
        fit_xs, fit_ys, "--", color="tab:gray",
        label=fit_format.format(slope=slope, intercept=intercept),
    )
    ax.plot(xs, ys, "o", color="tab:blue", markersize=8, label="измерение")

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(xs.astype(int))
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", framealpha=0.95)

    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Сохранено: {out_path}")


def main() -> None:
    # ParamGenerator — время.
    rs = np.array([d[0] for d in PARAM_DATA], dtype=float)
    pg_times = np.array([d[1] for d in PARAM_DATA], dtype=float)
    pg_mems = np.array([d[2] for d in PARAM_DATA], dtype=float)

    _plot_linear(
        rs, pg_times,
        xlabel="Число попыток r",
        ylabel="Среднее время, мкс",
        title="Зависимость времени работы ParamGeneratorService от r",
        out_path=OUT_DIR / "complexity_param_generator_time.png",
        fit_format="y = {slope:.2f}·r + {intercept:.2f} мкс",
    )
    _plot_linear(
        rs, pg_mems,
        xlabel="Число попыток r",
        ylabel="Пиковая память, KB",
        title="Зависимость пиковой памяти ParamGeneratorService от r",
        out_path=OUT_DIR / "complexity_param_generator_memory.png",
        fit_format="y = {slope:.2f}·r + {intercept:.2f} KB",
    )

    # TaskOrchestrator — время и память.
    ms = np.array([d[0] for d in ORCH_DATA], dtype=float)
    orch_times = np.array([d[1] for d in ORCH_DATA], dtype=float)
    orch_mems = np.array([d[2] for d in ORCH_DATA], dtype=float)

    _plot_linear(
        ms, orch_times,
        xlabel="Число итераций m",
        ylabel="Среднее время, мс",
        title="Зависимость времени работы TaskOrchestrator от m",
        out_path=OUT_DIR / "complexity_orchestrator_time.png",
        fit_format="y = {slope:.2f}·m + {intercept:.2f} мс",
    )
    _plot_linear(
        ms, orch_mems,
        xlabel="Число итераций m",
        ylabel="Пиковая память, KB",
        title="Зависимость пиковой памяти TaskOrchestrator от m",
        out_path=OUT_DIR / "complexity_orchestrator_memory.png",
        fit_format="y = {slope:.2f}·m + {intercept:.2f} KB",
    )


if __name__ == "__main__":
    main()
