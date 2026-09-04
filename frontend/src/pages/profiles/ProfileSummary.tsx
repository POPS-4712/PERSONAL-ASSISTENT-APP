import { useMemo } from "react";
import { asStringArray, readPath } from "./fields";
import type { CatalogField, ProfileCatalog } from "@/api/types";

/**
 * The human reading of a profile.
 *
 * This is what replaces showing the user their own JSON. It translates option
 * ids back into labels using the same catalogue the picker renders from, so a
 * value can never appear here under a name the picker does not use.
 */

function labelsFor(f: CatalogField, value: unknown): string[] {
  const byId = new Map(f.options.map((o) => [o.id, o.label]));
  if (f.kind === "toggle") return value ? [f.label] : [];
  // Unknown ids (an older profile) are shown as-is rather than hidden: the user
  // should see everything that is actually stored about them.
  return asStringArray(value).map((v) => byId.get(v) ?? v);
}

export interface SummaryLine {
  key: string;
  title: string;
  values: string[];
}

export function summarise(
  catalog: ProfileCatalog | undefined,
  configuration: Record<string, unknown>,
): SummaryLine[] {
  if (!catalog) return [];
  const lines: SummaryLine[] = [];
  for (const section of catalog.sections) {
    const values: string[] = [];
    for (const f of section.fields) {
      values.push(...labelsFor(f, readPath(configuration, f.path)));
      // a free-text answer behind an "Otra" option
      if (f.free_text_path.length) {
        const extra = readPath(configuration, f.free_text_path);
        if (typeof extra === "string" && extra.trim()) values.push(extra.trim());
      }
    }
    if (values.length) lines.push({ key: section.key, title: section.title, values });
  }
  return lines;
}

export function ProfileSummary({
  catalog,
  configuration,
  emptyMessage = "Todavía no has elegido nada. Abre Personalizar y selecciona lo que te interesa.",
}: {
  catalog: ProfileCatalog | undefined;
  configuration: Record<string, unknown>;
  emptyMessage?: string;
}) {
  const lines = useMemo(() => summarise(catalog, configuration), [catalog, configuration]);

  if (lines.length === 0) {
    return <p className="text-sm text-muted">{emptyMessage}</p>;
  }

  return (
    <dl className="space-y-3">
      {lines.map((line) => (
        <div key={line.key}>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">{line.title}</dt>
          <dd className="mt-0.5 text-sm text-fg">{line.values.join(" · ")}</dd>
        </div>
      ))}
    </dl>
  );
}
