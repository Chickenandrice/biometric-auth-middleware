(function (global) {
  const palette = {
    grid: "rgba(255, 255, 255, 0.06)",
    text: "#8b95a8",
    accentSoft: "rgba(108, 142, 239, 0.25)",
    success: "#34D399",
    danger: "#E05555",
    warn: "#EAB308",
  };

  const defaultOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: { color: palette.text, font: { family: "'Inter', sans-serif" } },
      },
    },
  };

  function destroyChart(chart) {
    if (chart && typeof chart.destroy === "function") chart.destroy();
  }

  function createAttemptsChart(canvas, labels, success, failure) {
    if (!canvas || !global.Chart) return null;
    const ctx = canvas.getContext("2d");
    return new global.Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Success",
            data: success,
            borderColor: palette.success,
            backgroundColor: palette.accentSoft,
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: "Failure",
            data: failure,
            borderColor: palette.danger,
            backgroundColor: "rgba(224, 85, 85, 0.08)",
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        ...defaultOpts,
        interaction: { mode: "index", intersect: false },
        plugins: {
          ...defaultOpts.plugins,
          legend: {
            ...defaultOpts.plugins.legend,
            position: "top",
            align: "end",
          },
        },
        scales: {
          x: {
            grid: { color: palette.grid },
            ticks: { color: palette.text, maxRotation: 0 },
          },
          y: {
            beginAtZero: true,
            grid: { color: palette.grid },
            ticks: { color: palette.text, precision: 0 },
          },
        },
      },
    });
  }

  function createOutcomeChart(canvas, values) {
    if (!canvas || !global.Chart) return null;
    const ctx = canvas.getContext("2d");
    const total = values.success + values.failure + values.challenge;
    const data =
      total === 0 ? [1, 0, 0] : [values.success, values.failure, values.challenge];
    return new global.Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Success", "Failure", "Other"],
        datasets: [
          {
            data,
            backgroundColor: [palette.success, palette.danger, palette.warn],
            borderWidth: 0,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: palette.text,
              boxWidth: 10,
              padding: 14,
              font: { family: "'Inter', sans-serif", size: 12 },
            },
          },
        },
      },
    });
  }

  global.BioAuthCharts = {
    destroyChart,
    createAttemptsChart,
    createOutcomeChart,
  };
})(typeof window !== "undefined" ? window : globalThis);
