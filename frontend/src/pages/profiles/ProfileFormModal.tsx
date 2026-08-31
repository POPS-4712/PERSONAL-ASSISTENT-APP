import { useMemo, useState } from "react";
import { Modal } from "@/components/ui";
import { Button, Input, Textarea, Field } from "@/components/ui";
import { useProfileDimensions } from "@/hooks/queries";
import type { Profile } from "@/api/types";
import type { ProfileInput } from "@/api";
import { errorMessage } from "@/components/common";

export function ProfileFormModal({
  open,
  onClose,
  onSubmit,
  initial,
  submitting,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: ProfileInput) => Promise<void>;
  initial?: Profile;
  submitting: boolean;
}) {
  const dims = useProfileDimensions();
  const editing = !!initial;

  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [makePrimary, setMakePrimary] = useState(initial?.is_primary ?? false);
  const [fields, setFields] = useState<Record<string, string>>(() => {
    const cfg = initial?.configuration ?? {};
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(cfg)) {
      out[k] = Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v ?? "");
    }
    return out;
  });
  const [advanced, setAdvanced] = useState(false);
  const [rawJson, setRawJson] = useState(() => JSON.stringify(initial?.configuration ?? {}, null, 2));
  const [error, setError] = useState<string | null>(null);

  const allKeys = useMemo(() => {
    const set = new Set<string>(dims.data?.dimensions ?? []);
    Object.keys(fields).forEach((k) => set.add(k));
    return [...set];
  }, [dims.data, fields]);

  function buildConfiguration(): Record<string, unknown> {
    if (advanced) {
      const parsed = JSON.parse(rawJson || "{}");
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        throw new Error("Configuration must be a JSON object.");
      }
      return parsed;
    }
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(fields)) {
      const trimmed = v.trim();
      if (!trimmed) continue;
      out[k] = trimmed.includes(",") ? trimmed.split(",").map((s) => s.trim()).filter(Boolean) : trimmed;
    }
    return out;
  }

  async function handleSubmit() {
    setError(null);
    let configuration: Record<string, unknown>;
    try {
      configuration = buildConfiguration();
    } catch (e) {
      setError((e as Error).message);
      return;
    }
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        configuration,
        make_primary: makePrimary,
      });
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={editing ? `Edit ${initial?.name}` : "New profile"}
      description={dims.data?.note}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!name.trim()}>
            {editing ? "Save changes" : "Create profile"}
          </Button>
        </>
      }
    >
      <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <Input label="Description" value={description} onChange={(e) => setDescription(e.target.value)} />

        {!editing && (
          <label className="flex items-center gap-2 text-sm text-fg">
            <input type="checkbox" checked={makePrimary} onChange={(e) => setMakePrimary(e.target.checked)} />
            Make this the primary profile
          </label>
        )}

        <div className="flex items-center justify-between">
          <p className="label mb-0">Personalisation</p>
          <button
            type="button"
            className="text-xs text-brand hover:underline"
            onClick={() => setAdvanced((a) => !a)}
          >
            {advanced ? "Simple fields" : "Edit as JSON"}
          </button>
        </div>

        {advanced ? (
          <Textarea
            label="configuration (JSON object)"
            value={rawJson}
            onChange={(e) => setRawJson(e.target.value)}
            rows={12}
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {allKeys.map((key) => (
              <Field key={key} label={key.replace(/_/g, " ")}>
                <input
                  className="input"
                  value={fields[key] ?? ""}
                  placeholder="value, or comma-separated list"
                  onChange={(e) => setFields((f) => ({ ...f, [key]: e.target.value }))}
                />
              </Field>
            ))}
          </div>
        )}

        {error && <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
      </div>
    </Modal>
  );
}
