import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useProfile, useProfileCatalog, useProfileMutations } from "@/hooks/queries";
import { useToast } from "@/stores/toast";
import { Badge, Button, Card, CardTitle, ConfirmDialog, PageHeader } from "@/components/ui";
import { QueryBoundary, errorMessage } from "@/components/common";
import { formatDateTime } from "@/utils/format";
import { ProfileFormModal } from "./profiles/ProfileFormModal";
import { ProfileSummary } from "./profiles/ProfileSummary";

export function ProfileDetailPage() {
  const { id } = useParams<{ id: string }>();
  const profile = useProfile(id);
  const catalog = useProfileCatalog();
  const m = useProfileMutations();
  const toast = useToast();
  const navigate = useNavigate();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  return (
    <div>
      <PageHeader
        title={profile.data?.name ?? "Profile"}
        description={<Link to="/profiles" className="text-brand hover:underline">← All profiles</Link>}
        actions={
          profile.data && (
            <>
              <Button onClick={() => navigate(`/profiles/${profile.data!.id}/personalise`)}>
                Personalise
              </Button>
              <Button variant="outline" onClick={() => setEditOpen(true)}>
                Rename
              </Button>
              <Button variant="ghost" className="text-danger" onClick={() => setDeleteOpen(true)}>
                Delete
              </Button>
            </>
          )
        }
      />

      <QueryBoundary
        isLoading={profile.isLoading}
        isError={profile.isError}
        error={profile.error}
        onRetry={() => profile.refetch()}
      >
        {profile.data && (
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardTitle>Overview</CardTitle>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted">Status</dt>
                  <dd>
                    <Badge tone={profile.data.is_active ? "success" : "neutral"}>
                      {profile.data.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Primary</dt>
                  <dd>{profile.data.is_primary ? "Yes" : "No"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Created</dt>
                  <dd>{formatDateTime(profile.data.created_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Updated</dt>
                  <dd>{formatDateTime(profile.data.updated_at)}</dd>
                </div>
              </dl>
              {profile.data.description && (
                <p className="mt-3 border-t border-border pt-3 text-sm text-muted">{profile.data.description}</p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                {!profile.data.is_primary && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      m.setPrimary
                        .mutateAsync(profile.data!.id)
                        .then(() => toast.success("Primary profile set"))
                        .catch((e) => toast.error("Failed", errorMessage(e)))
                    }
                  >
                    Set primary
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    m.duplicate
                      .mutateAsync({ id: profile.data!.id })
                      .then((p) => {
                        toast.success("Duplicated");
                        navigate(`/profiles/${p.id}`);
                      })
                      .catch((e) => toast.error("Failed", errorMessage(e)))
                  }
                >
                  Duplicate
                </Button>
              </div>
            </Card>

            <Card className="lg:col-span-2">
              <CardTitle
                action={
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate(`/profiles/${profile.data!.id}/personalise`)}
                  >
                    Personalise
                  </Button>
                }
              >
                Personalisation
              </CardTitle>
              {/* The human reading of the stored options — the user never has
                  to look at the JSON to know what their profile says. */}
              <ProfileSummary
                catalog={catalog.data}
                configuration={profile.data.configuration}
                emptyMessage="No personalisation set yet. Open Personalise and pick what interests you."
              />
              <details className="mt-4 border-t border-border pt-3">
                <summary className="cursor-pointer text-xs text-muted hover:text-fg">
                  Advanced — stored data
                </summary>
                <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-surface-2 p-3 text-xs text-fg">
                  {JSON.stringify(profile.data.configuration, null, 2)}
                </pre>
              </details>
            </Card>
          </div>
        )}
      </QueryBoundary>

      {profile.data && (
        <>
          <ProfileFormModal
            open={editOpen}
            onClose={() => setEditOpen(false)}
            initial={profile.data}
            submitting={m.update.isPending}
            onSubmit={async (input) => {
              await m.update.mutateAsync({
                id: profile.data!.id,
                input: { name: input.name, description: input.description },
              });
              toast.success("Profile updated");
            }}
          />
          <ConfirmDialog
            open={deleteOpen}
            onClose={() => setDeleteOpen(false)}
            title="Delete profile"
            message={`Delete "${profile.data.name}"? This cannot be undone.`}
            confirmLabel="Delete"
            destructive
            onConfirm={async () => {
              await m.remove.mutateAsync(profile.data!.id);
              toast.success("Profile deleted");
              navigate("/profiles");
            }}
          />
        </>
      )}
    </div>
  );
}
