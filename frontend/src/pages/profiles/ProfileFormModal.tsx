import { useState } from "react";
import { Modal } from "@/components/ui";
import { Button, Input } from "@/components/ui";
import type { Profile } from "@/api/types";
import type { ProfileInput } from "@/api";
import { errorMessage } from "@/components/common";

/**
 * Identity only: what the profile is called and whether it is the primary one.
 *
 * Personalisation used to live here as a grid of free-text inputs and a raw
 * JSON box. It moved to the visual builder at
 * `/profiles/:id/personalise`, which writes the same `configuration` object
 * from picked options. Keeping a second, typed way to edit the same field would
 * be two sources of truth for one piece of data.
 *
 * A newly created profile starts with an empty configuration and the caller
 * sends the user straight to the builder.
 */
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
  const editing = !!initial;

  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [makePrimary, setMakePrimary] = useState(initial?.is_primary ?? false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        // Never sent from here: the builder owns `configuration`, and omitting
        // it means an edit to the name cannot wipe someone's selections.
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
      title={editing ? `Edit ${initial?.name}` : "New profile"}
      description={
        editing
          ? "Personalisation is edited in the visual builder."
          : "Name it first — you will pick your options next."
      }
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
      <div className="space-y-4">
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <Input
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

        {!editing && (
          <label className="flex items-center gap-2 text-sm text-fg">
            <input
              type="checkbox"
              checked={makePrimary}
              onChange={(e) => setMakePrimary(e.target.checked)}
            />
            Make this the primary profile
          </label>
        )}

        {error && <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
      </div>
    </Modal>
  );
}
