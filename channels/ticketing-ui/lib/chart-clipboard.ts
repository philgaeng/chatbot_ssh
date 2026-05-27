/** Render summary charts to canvas and copy as PNG (no chart library — matches SummaryTab CSS charts). */

export const CHART_COLORS = [
  "#2563eb",
  "#dc2626",
  "#f59e0b",
  "#10b981",
  "#8b5cf6",
  "#64748b",
];

export type PieSlice = { label: string; value: number; percent: number };

export type MonthBar = {
  month: string;
  packages: { count: number }[];
};

function fillRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h);
  ctx.lineTo(x, y + h);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
  ctx.fill();
}

export function renderPieChartCanvas(
  title: string,
  slices: PieSlice[],
  width = 420,
  height = 200,
): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width * 2;
  canvas.height = height * 2;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;

  const scale = 2;
  ctx.scale(scale, scale);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = "#374151";
  ctx.font = "bold 13px system-ui, sans-serif";
  ctx.fillText(title, 12, 22);

  const total = slices.reduce((s, x) => s + x.value, 0);
  if (total === 0) {
    ctx.fillStyle = "#9ca3af";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText("No data", 12, 48);
    return canvas;
  }

  const cx = 72;
  const cy = 118;
  const r = 52;
  let start = -Math.PI / 2;
  slices.forEach((sl, i) => {
    const angle = (sl.value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, start, start + angle);
    ctx.closePath();
    ctx.fillStyle = CHART_COLORS[i % CHART_COLORS.length];
    ctx.fill();
    start += angle;
  });

  let ly = 44;
  const legendX = 150;
  slices.forEach((sl, i) => {
    ctx.fillStyle = CHART_COLORS[i % CHART_COLORS.length];
    ctx.beginPath();
    ctx.arc(legendX, ly + 5, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#374151";
    ctx.font = "11px system-ui, sans-serif";
    const text = `${sl.label}: ${sl.value} (${sl.percent}%)`;
    ctx.fillText(text.length > 42 ? `${text.slice(0, 39)}…` : text, legendX + 14, ly + 9);
    ly += 20;
  });

  return canvas;
}

export function renderBarChartCanvas(
  title: string,
  months: MonthBar[],
  width = 520,
  height = 220,
): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width * 2;
  canvas.height = height * 2;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;

  const scale = 2;
  ctx.scale(scale, scale);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = "#374151";
  ctx.font = "bold 13px system-ui, sans-serif";
  ctx.fillText(title, 12, 22);

  if (months.length === 0) {
    ctx.fillStyle = "#9ca3af";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText("No data", 12, 48);
    return canvas;
  }

  const totals = months.map((m) =>
    m.packages.reduce((s, p) => s + (p.count ?? 0), 0),
  );
  const maxTotal = Math.max(1, ...totals);
  const chartTop = 36;
  const chartBottom = 175;
  const chartH = chartBottom - chartTop;
  const barAreaLeft = 24;
  const barAreaRight = width - 12;
  const n = months.length;
  const slotW = (barAreaRight - barAreaLeft) / n;
  const barW = Math.min(28, slotW * 0.55);

  months.forEach((m, i) => {
    const total = totals[i];
    const barH = total ? Math.max(4, Math.round((total / maxTotal) * chartH)) : 2;
    const x = barAreaLeft + i * slotW + (slotW - barW) / 2;
    const y = chartBottom - barH;
    ctx.fillStyle = total ? "#3b82f6" : "#e5e7eb";
    fillRoundRect(ctx, x, y, barW, barH, 3);

    const label = m.month.length >= 7 ? m.month.slice(5) : m.month;
    ctx.fillStyle = "#6b7280";
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(label, x + barW / 2, chartBottom + 14);
    ctx.fillStyle = "#9ca3af";
    ctx.fillText(String(total), x + barW / 2, chartBottom + 26);
    ctx.textAlign = "left";
  });

  return canvas;
}

export async function copyCanvasAsPng(canvas: HTMLCanvasElement): Promise<void> {
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, "image/png");
  });
  if (!blob) throw new Error("Could not render chart image");

  if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    return;
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "chart.png";
  a.click();
  URL.revokeObjectURL(url);
  throw new Error("Clipboard unavailable — image downloaded instead");
}

export async function copyPieChart(title: string, slices: PieSlice[]): Promise<void> {
  await copyCanvasAsPng(renderPieChartCanvas(title, slices));
}

export async function copyBarChart(title: string, months: MonthBar[]): Promise<void> {
  await copyCanvasAsPng(renderBarChartCanvas(title, months));
}
