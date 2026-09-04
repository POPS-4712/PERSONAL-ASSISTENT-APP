import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useProfile, useProfileCatalog, useProfileMutations } from "@/hooks/queries";
import { useToast } from "@/stores/toast";
import { Button, Card, CardTitle, Input, PageHeader, Textarea } from "@/components/ui";
import { QueryBoundary, errorMessage } from "@/components/common";
import { ProfileSummary } from "./profiles/ProfileSummary";
import {
  ChipMultiSelect,
  ChipSingleSelect,
  ProgressBar,
  ScaleSelect,
  ToggleCard,
  asStringArray,
  extraValues,
  readPath,
  writePath,
} from "./profiles/fields";
import { cn } from "@/utils/cn";
import type { CatalogField, CatalogSection, ProfileCatalog } from "@/api/types";

/**
 * Personalisation: a visual builder, not a form.
 *
 * The user clicks options; the `configuration` JSON is assembled from those
 * clicks and never shown. The raw editor still exists for anyone who wants it,
 * but it lives behind "Avanzado" so it is an escape hatch rather than the
 * experience.
 *
 * Sections come from `GET /api/profiles/catalog`, so adding an option is a
 * backend change and this file does not move.
 */

type Config = Record<string, unknown>;

/** How much of what the backend actually grades has been filled in. */
function completionPercent(catalog: ProfileCatalog | undefined, config: Config): number {
  if (!catalog) return 0;
  const required = catalog.required_sections;
  if (required.length === 0) return 100;
  const done = required.filter((key) => {
    const section = catalog.sections.find((s) => s.key === key);
    if (!section) return false;
    return section.fields.some((f) => {
      const value = readPath(config, f.path);
      if (f.kind === "toggle") return value === true;
      return asStringArray(value).length > 0;
    });
  });
  return (done.length / required.length) * 100;
}

function FieldControl({
  field,
  config,
  onChange,
}: {
  field: CatalogField;
  config: Config;
  onChange: (next: Config) => void;
}) {
  const value = readPath(config, field.path);
  const set = (next: unknown) => onChange(writePath(config, field.path, next));

  if (field.kind === "toggle") {
    return (
      <ToggleCard
        title={field.label}
        description={field.hint}
        checked={value === true}
        onChange={(checked) => set(checked)}
      />
    );
  }

  if (field.kind === "scale") {
    return (
      <div>
        <ScaleSelect
          label={field.label}
          options={field.options}
          value={typeof value === "string" ? value : ""}
          onChange={set}
        />
        {field.hint && <p className="mt-1 text-xs text-muted">{field.hint}</p>}
      </div>
    );
  }

  if (field.kind === "single") {
    return (
      <div>
        <p className="label">{field.label}</p>
        <ChipSingleSelect
          options={field.options}
          value={typeof value === "string" ? value : ""}
          onChange={set}
        />
        {field.hint && <p className="mt-2 text-xs text-muted">{field.hint}</p>}
      </div>
    );
  }

  // multi
  const selected = asStringArray(value);
  const showFreeText = !!field.free_text_trigger && selected.includes(field.free_text_trigger);
  const freeTextValue = field.free_text_path.length ? readPath(config, field.free_text_path) : "";

  return (
    <div>
      <p className="label">{field.label}</p>
      <ChipMultiSelect
        options={field.options}
        value={selected}
        extras={extraValues(field, value)}
        onChange={set}
      />
      {field.hint && <p className="mt-2 text-xs text-muted">{field.hint}</p>}
      {showFreeText && (
        <div className="mt-3 max-w-sm">
          <Input
            label={field.free_text_label || "Especifica"}
            value={typeof freeTextValue === "string" ? freeTextValue : ""}
            onChange={(e) => onChange(writePath(config, field.free_text_path, e.target.value))}
          />
        </div>
      )}
    </div>
  );
}

function SectionCard({
  section,
  config,
  onChange,
  required,
}: {
  section: CatalogSection;
  config: Config;
  onChange: (next: Config) => void;
  required: boolean;
}) {
  const isAutomations = section.key === "automatizaciones";
  return (
    <Card>
      <CardTitle
        action={
          required ? (
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted">
              Recomendada
            </span>
          ) : undefined
        }
      >
        {section.question}
      </CardTitle>
      {section.description && <p className="-mt-1 mb-3 text-sm text-muted">{section.description}</p>}
      <div className={cn(isAutomations ? "grid gap-3 sm:grid-cols-2" : "space-y-5")}>
        {section.fields.map((f) => (
          <FieldControl key={f.key} field={f} config={config} onChange={onChange} />
        ))}
      </div>
    </Card>
  );
}

export function PersonalisePage() {
  const { id } = useParams<{ id: string }>();
  const profile = useProfile(id);
  const catalog = useProfileCatalog();
  const m = useProfileMutations();
  const toast = useToast();
  const navigate = useNavigate();

  const [config, setConfig] = useState<Config>({});
  const [dirty, setDirty] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [rawJson, setRawJson] = useState("{}");
  const [jsonError, setJsonError] = useState<string | null>(null);

  // Load the stored configuration once it arrives. Values the catalogue does
  // not know are kept in state untouched, so an older profile round-trips
  // without losing anything.
  useEffect(() => {
    if (profile.data && !dirty) {
      const stored = (profile.data.configuration ?? {}) as Config;
      setConfig(stored);
      setRawJson(JSON.stringify(stored, null, 2));
    }
  }, [profile.data, dirty]);

  const update = (next: Config) => {
    setConfig(next);
    setRawJson(JSON.stringify(next, null, 2));
    setDirty(true);
  };

  const percent = useMemo(() => completionPercent(catalog.data, config), [catalog.data, config]);
  const isEmpty = useMemo(
    () => Object.values(config).every((v) => asStringArray(v).length === 0 && !v),
    [config],
  );

  async function save() {
    if (!profile.data) return;
    let payload = config;
    if (advanced) {
      try {
        const parsed = JSON.parse(rawJson || "{}");
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("La configuración debe ser un objeto JSON.");
        }
        payload = parsed;
        setJsonError(null);
      } catch (e) {
        setJsonError((e as Error).message);
        return;
      }
    }
    try {
      await m.update.mutateAsync({ id: profile.data.id, input: { configuration: payload } });
      setDirty(false);
      toast.success("Perfil guardado");
    } catch (e) {
      toast.error("No se pudo guardar", errorMessage(e));
    }
  }

  return (
    <div>
      <PageHeader
        title="Personalisation"
        description={
          <>
            Elige lo que te interesa. Las automatizaciones filtran contra esto.{" "}
            <Link to={`/profiles/${id}`} className="text-brand hover:underline">
              ← Volver al perfil
            </Link>
          </>
        }
        actions={
          <Button onClick={save} loading={m.update.isPending} disabled={!dirty || isEmpty}>
            {dirty ? "Guardar cambios" : "Guardado"}
          </Button>
        }
      />

      <QueryBoundary
        isLoading={profile.isLoading || catalog.isLoading}
        isError={profile.isError || catalog.isError}
        error={profile.error ?? catalog.error}
        onRetry={() => {
          profile.refetch();
          catalog.refetch();
        }}
        skeletonRows={6}
      >
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            {(catalog.data?.sections ?? []).map((section) => (
              <SectionCard
                key={section.key}
                section={section}
                config={config}
                onChange={update}
                required={(catalog.data?.required_sections ?? []).includes(section.key)}
              />
            ))}

            <Card>
              <button
                type="button"
                className="text-sm font-medium text-muted hover:text-fg"
                onClick={() => setAdvanced((a) => !a)}
                aria-expanded={advanced}
              >
                {advanced ? "▾" : "▸"} Avanzado
              </button>
              {advanced && (
                <div className="mt-3">
                  <p className="mb-2 text-xs text-muted">
                    El editor JSON existe por si necesitas una clave que el selector todavía no
                    cubre. No hace falta para el uso normal.
                  </p>
                  <Textarea
                    label="configuration (objeto JSON)"
                    value={rawJson}
                    rows={14}
                    onChange={(e) => {
                      setRawJson(e.target.value);
                      setDirty(true);
                    }}
                  />
                  {jsonError && <p className="mt-1 text-xs text-danger">{jsonError}</p>}
                </div>
              )}
            </Card>
          </div>

          {/* Summary: the human reading of what has been picked. */}
          <div className="lg:col-span-1">
            <Card className="lg:sticky lg:top-4">
              <CardTitle>Tu perfil</CardTitle>
              <div className="mb-4">
                <ProgressBar percent={percent} label="Perfil completado" />
              </div>
              <ProfileSummary catalog={catalog.data} configuration={config} />
              {isEmpty && (
                <p className="mt-4 border-t border-border pt-3 text-xs text-warn">
                  Selecciona al menos una opción para poder guardar.
                </p>
              )}
              <div className="mt-4 border-t border-border pt-3">
                <Button
                  className="w-full"
                  onClick={save}
                  loading={m.update.isPending}
                  disabled={!dirty || isEmpty}
                >
                  {dirty ? "Guardar cambios" : "Guardado"}
                </Button>
                <button
                  type="button"
                  className="mt-2 w-full text-xs text-muted hover:text-fg"
                  onClick={() => navigate(`/profiles/${id}`)}
                >
                  Volver al perfil
                </button>
              </div>
            </Card>
          </div>
        </div>
      </QueryBoundary>
    </div>
  );
}
