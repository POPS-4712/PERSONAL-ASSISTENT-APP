import { useId } from "react";
import { cn } from "@/utils/cn";
import type { CatalogField, CatalogOption } from "@/api/types";

/**
 * The controls the visual profile builder is made of.
 *
 * Every one of these writes an option id, never free text, so what lands in
 * `profiles.configuration` is the same vocabulary the n8n workflows read.
 * The single exception is the box revealed by an "Otra" option, which is the
 * only place a user types anything.
 */

/* --------------------------------- chips --------------------------------- */

function Chip({
  label,
  selected,
  onClick,
  custom,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  /** A value carried over from an older profile that is not in the catalogue. */
  custom?: boolean;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 text-sm transition",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
        selected
          ? "border-brand bg-brand text-brand-fg font-medium"
          : "border-border bg-transparent text-fg hover:border-brand/50 hover:bg-surface-2",
        custom && !selected && "border-dashed",
      )}
    >
      {selected && <span aria-hidden="true">✓ </span>}
      {label}
    </button>
  );
}

/** Multi-select. Order of selection is preserved — it reads as a priority list. */
export function ChipMultiSelect({
  options,
  value,
  onChange,
  extras = [],
}: {
  options: CatalogOption[];
  value: string[];
  onChange: (next: string[]) => void;
  /** Values already stored that the catalogue does not know about. */
  extras?: string[];
}) {
  const toggle = (id: string) =>
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <Chip key={o.id} label={o.label} selected={value.includes(o.id)} onClick={() => toggle(o.id)} />
        ))}
        {extras.map((v) => (
          <Chip key={v} label={v} custom selected={value.includes(v)} onClick={() => toggle(v)} />
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">Seleccionadas: {value.length}</p>
    </div>
  );
}

/** Single choice. Clicking the selected chip clears it — nothing is forced. */
export function ChipSingleSelect({
  options,
  value,
  onChange,
}: {
  options: CatalogOption[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={value === o.id}
          onClick={() => onChange(value === o.id ? "" : o.id)}
          className={cn(
            "rounded-full border px-3 py-1.5 text-sm transition",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
            value === o.id
              ? "border-brand bg-brand font-medium text-brand-fg"
              : "border-border text-fg hover:border-brand/50 hover:bg-surface-2",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* --------------------------------- scale --------------------------------- */

/**
 * An ordered choice (salary). A slider rather than chips because the options
 * are a scale: the user is picking a floor, not one value out of a set.
 */
export function ScaleSelect({
  options,
  value,
  onChange,
  label,
}: {
  options: CatalogOption[];
  value: string;
  onChange: (next: string) => void;
  label: string;
}) {
  const id = useId();
  const index = options.findIndex((o) => o.id === value);
  const selected = index >= 0 ? options[index] : null;

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <label className="label mb-0" htmlFor={id}>
          {label}
        </label>
        <span className="text-sm font-medium text-fg">{selected ? selected.label : "Sin preferencia"}</span>
      </div>
      <div className="flex items-center gap-3">
        <input
          id={id}
          type="range"
          min={-1}
          max={options.length - 1}
          step={1}
          value={index}
          aria-valuetext={selected ? selected.label : "Sin preferencia"}
          onChange={(e) => {
            const next = Number(e.target.value);
            onChange(next < 0 ? "" : options[next].id);
          }}
          className="w-full accent-[color:var(--brand,#2563eb)]"
        />
        {selected && (
          <button
            type="button"
            className="whitespace-nowrap text-xs text-muted underline underline-offset-2 hover:text-fg"
            onClick={() => onChange("")}
          >
            Quitar
          </button>
        )}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-muted">
        <span>{options[0]?.label}</span>
        <span>{options[options.length - 1]?.label}</span>
      </div>
    </div>
  );
}

/* -------------------------------- toggles -------------------------------- */

/** A big on/off card — used for the four automations. */
export function ToggleCard({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={title}
      onClick={() => onChange(!checked)}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border p-4 text-left transition",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
        checked ? "border-brand bg-brand/5" : "border-border hover:bg-surface-2",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition",
          checked ? "bg-brand" : "bg-border",
        )}
      >
        <span
          className={cn(
            "h-4 w-4 rounded-full bg-white transition-transform",
            checked && "translate-x-4",
          )}
        />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-fg">{title}</span>
        <span className="mt-0.5 block text-xs text-muted">{description}</span>
        <span className={cn("mt-1 block text-[11px] font-semibold uppercase", checked ? "text-ok" : "text-muted")}>
          {checked ? "ON" : "OFF"}
        </span>
      </span>
    </button>
  );
}

/* -------------------------------- progress ------------------------------- */

export function ProgressBar({ percent, label }: { percent: number; label: string }) {
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-semibold tabular-nums text-fg">{clamped}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-surface-2"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={cn("h-full rounded-full transition-all", clamped >= 100 ? "bg-ok" : "bg-brand")}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

/* ------------------------------ field router ----------------------------- */

/** Reads a value at a catalogue path out of a configuration object. */
export function readPath(configuration: Record<string, unknown>, path: string[]): unknown {
  let node: unknown = configuration;
  for (const key of path) {
    if (node == null || typeof node !== "object") return undefined;
    node = (node as Record<string, unknown>)[key];
  }
  return node;
}

/** Returns a copy of `configuration` with `path` set to `value`. */
export function writePath(
  configuration: Record<string, unknown>,
  path: string[],
  value: unknown,
): Record<string, unknown> {
  const [head, ...rest] = path;
  const next = { ...configuration };
  if (rest.length === 0) {
    next[head] = value;
    return next;
  }
  const child = next[head];
  next[head] = writePath(
    child && typeof child === "object" && !Array.isArray(child) ? (child as Record<string, unknown>) : {},
    rest,
    value,
  );
  return next;
}

export function asStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter((v) => v.trim());
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

/** Values stored on this field that the catalogue has no option for. */
export function extraValues(f: CatalogField, value: unknown): string[] {
  const known = new Set(f.options.map((o) => o.id));
  return asStringArray(value).filter((v) => !known.has(v));
}
