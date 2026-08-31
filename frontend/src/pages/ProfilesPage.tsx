import { useState } from "react";
import { Link } from "react-router-dom";
import { useProfileMutations, useProfiles } from "@/hooks/queries";
import { useToast } from "@/stores/toast";
import { Badge, Button, Card, ConfirmDialog, EmptyState, PageHeader } from "@/components/ui";
import { QueryBoundary, errorMessage } from "@/components/common";
import { relativeTime } from "@/utils/format";
import type { Profile } from "@/api/types";
import { ProfileFormModal } from "./profiles/ProfileFormModal";

export function ProfilesPage() {
  const profiles = useProfiles();
  const m = useProfileMutations();
  const toast = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Profile | undefined>();
  const [deleting, setDeleting] = useState<Profile | undefined>();

  const busy =
    m.create.isPending ||
    m.update.isPending ||
    m.duplicate.isPending ||
    m.activate.isPending ||
    m.deactivate.isPending ||
    m.setPrimary.isPending;

  function runAction<T>(p: Promise<T>, ok: string) {
    p.then(() => toast.success(ok)).catch((e) => toast.error("Action failed", errorMessage(e)));
  }

  return (
    <div>
      <PageHeader
        title="Profiles"
        description="Personalisation profiles that drive your automations."
        actions={
          <Button
            onClick={() => {
              setEditing(undefined);
              setFormOpen(true);
            }}
          >
            New profile
          </Button>
        }
      />

      <QueryBoundary
        isLoading={profiles.isLoading}
        isError={profiles.isError}
        error={profiles.error}
        onRetry={() => profiles.refetch()}
      >
        {profiles.data && profiles.data.length === 0 ? (
          <EmptyState
            title="No profiles yet."
            description="Create your first profile to personalise how automations run."
            action={
              <Button onClick={() => setFormOpen(true)}>Create your first profile</Button>
            }
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {profiles.data?.map((p) => (
              <Card key={p.id} className="flex flex-col">
                <div className="flex items-start justify-between gap-2">
                  <Link to={`/profiles/${p.id}`} className="text-base font-semibold text-fg hover:text-brand">
                    {p.name}
                  </Link>
                  <div className="flex shrink-0 gap-1">
                    {p.is_primary && <Badge tone="brand">Primary</Badge>}
                    <Badge tone={p.is_active ? "success" : "neutral"}>{p.is_active ? "Active" : "Inactive"}</Badge>
                  </div>
                </div>
                {p.description && <p className="mt-1 text-sm text-muted">{p.description}</p>}

                <div className="mt-3 flex flex-wrap gap-1">
                  {Object.entries(p.configuration).slice(0, 6).map(([k, v]) => (
                    <span key={k} className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">
                      {k}: {Array.isArray(v) ? v.join(", ") : String(v)}
                    </span>
                  ))}
                </div>

                <p className="mt-3 text-[11px] text-muted">updated {relativeTime(p.updated_at)}</p>

                <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-3">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setEditing(p);
                      setFormOpen(true);
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => runAction(m.duplicate.mutateAsync({ id: p.id }), "Profile duplicated")}
                  >
                    Duplicate
                  </Button>
                  {p.is_active ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy || p.is_primary}
                      onClick={() => runAction(m.deactivate.mutateAsync(p.id), "Profile deactivated")}
                    >
                      Deactivate
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy}
                      onClick={() => runAction(m.activate.mutateAsync(p.id), "Profile activated")}
                    >
                      Activate
                    </Button>
                  )}
                  {!p.is_primary && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy}
                      onClick={() => runAction(m.setPrimary.mutateAsync(p.id), "Primary profile set")}
                    >
                      Set primary
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-danger"
                    disabled={busy}
                    onClick={() => setDeleting(p)}
                  >
                    Delete
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </QueryBoundary>

      <ProfileFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        initial={editing}
        submitting={m.create.isPending || m.update.isPending}
        onSubmit={async (input) => {
          if (editing) {
            await m.update.mutateAsync({
              id: editing.id,
              input: { name: input.name, description: input.description, configuration: input.configuration },
            });
            toast.success("Profile updated");
          } else {
            await m.create.mutateAsync(input);
            toast.success("Profile created");
          }
        }}
      />

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(undefined)}
        title="Delete profile"
        message={`Delete "${deleting?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await m.remove.mutateAsync(deleting.id);
            toast.success("Profile deleted");
          } catch (e) {
            toast.error("Delete failed", errorMessage(e));
            throw e;
          }
        }}
      />
    </div>
  );
}
