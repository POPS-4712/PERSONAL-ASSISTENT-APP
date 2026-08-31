import { useMemo } from "react";

/**
 * Dependency-free area/line chart for a single metric series. Renders real
 * sampled values — no synthetic data.
 */
export function Sparkline({
  values,
  width = 480,
  height = 120,
  max = 100,
  unit = "%",
  label,
}: {
  values: number[];
  width?: number;
  height?: number;
  max?: number;
  unit?: string;
  label?: string;
}) {
  const { linePath, areaPath, last } = useMemo(() => {
    if (values.length === 0) return { linePath: "", areaPath: "", last: null as number | null };
    const n = values.length;
    const stepX = n > 1 ? width / (n - 1) : width;
    const clamp = (v: number) => Math.max(0, Math.min(max, v));
    const toY = (v: number) => height - (clamp(v) / max) * (height - 6) - 3;
    const pts = values.map((v, i) => [i * stepX, toY(v)] as const);
    const line = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const area = `${line} L${width},${height} L0,${height} Z`;
    return { linePath: line, areaPath: area, last: values[n - 1] };
  }, [values, width, height, max]);

  return (
    <figure className="w-full">
      {label && (
        <figcaption className="mb-1 flex items-baseline justify-between">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
          <span className="font-mono text-sm text-fg">
            {last == null ? "—" : `${last.toFixed(last < 10 ? 1 : 0)}${unit}`}
          </span>
        </figcaption>
      )}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-28 w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label={`${label ?? "metric"} over time`}
      >
        {values.length > 0 ? (
          <>
            <path d={areaPath} fill="rgb(var(--c-brand) / 0.15)" />
            <path d={linePath} fill="none" stroke="rgb(var(--c-brand))" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          </>
        ) : (
          <text x="50%" y="50%" textAnchor="middle" className="fill-muted text-xs">
            waiting for data…
          </text>
        )}
      </svg>
    </figure>
  );
}
