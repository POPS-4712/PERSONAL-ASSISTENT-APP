import { useState } from "react";
import { Modal, Button, Input, Select, Textarea, Field } from "@/components/ui";
import type { Credential, CredentialType } from "@/api/types";
import type { CredentialInput } from "@/api";
import { errorMessage } from "@/components/common";

const TYPES: { value: CredentialType; label: string }[] = [
  { value: "api_key", label: "API Key" },
  { value: "bearer", label: "Bearer token" },
  { value: "basic_auth", label: "Basic auth" },
  { value: "oauth2", label: "OAuth2" },
  { value: "custom", label: "Custom" },
];

export function CredentialFormModal({
  open,
  onClose,
  onSubmit,
  initial,
  submitting,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: CredentialInput | { id: string; patch: Record<string, unknown> }) => Promise<void>;
  initial?: Credential;
  submitting: boolean;
}) {
  const editing = !!initial;
  const [provider, setProvider] = useState(initial?.provider ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [type, setType] = useState<CredentialType>((initial?.type as CredentialType) ?? "api_key");
  const [apiKey, setApiKey] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [refreshToken, setRefreshToken] = useState("");
  const [customJson, setCustomJson] = useState("{\n  \n}");
  const [testUrl, setTestUrl] = useState(String(initial?.meta?.test_url ?? ""));
  const [headerName, setHeaderName] = useState(String(initial?.meta?.header_name ?? ""));
  const [error, setError] = useState<string | null>(null);

  function buildSecret(): Record<string, string> | null {
    switch (type) {
      case "api_key":
      case "bearer":
        return apiKey.trim() ? { api_key: apiKey.trim() } : null;
      case "basic_auth":
        return username && password ? { username, password } : null;
      case "oauth2":
        return accessToken.trim()
          ? { access_token: accessToken.trim(), ...(refreshToken.trim() ? { refresh_token: refreshToken.trim() } : {}) }
          : null;
      case "custom": {
        const parsed = JSON.parse(customJson || "{}");
        const flat: Record<string, string> = {};
        for (const [k, v] of Object.entries(parsed)) flat[k] = String(v);
        return Object.keys(flat).length ? flat : null;
      }
    }
  }

  async function handleSubmit() {
    setError(null);
    const meta: Record<string, unknown> = {};
    if (testUrl.trim()) meta.test_url = testUrl.trim();
    if (headerName.trim()) meta.header_name = headerName.trim();

    let secret: Record<string, string> | null;
    try {
      secret = buildSecret();
    } catch {
      setError("Custom secret must be valid JSON.");
      return;
    }

    try {
      if (editing) {
        const patch: Record<string, unknown> = { name: name.trim(), meta };
        if (secret) patch.secret = secret;
        await onSubmit({ id: initial!.id, patch });
      } else {
        if (!secret) {
          setError("Enter the secret material for this credential.");
          return;
        }
        await onSubmit({ provider: provider.trim(), name: name.trim(), type, secret, meta });
      }
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={editing ? `Edit ${initial?.provider}/${initial?.name}` : "Add credential"}
      description={editing ? "Leave secret fields blank to keep the current value." : undefined}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!name.trim() || (!editing && !provider.trim())}>
            {editing ? "Save" : "Add"}
          </Button>
        </>
      }
    >
      <div className="max-h-[60vh] space-y-3 overflow-y-auto pr-1">
        {!editing && (
          <>
            <Input label="Provider" placeholder="openai, google, telegram…" value={provider} onChange={(e) => setProvider(e.target.value)} />
            <Select label="Type" value={type} onChange={(e) => setType(e.target.value as CredentialType)}>
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </>
        )}
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} />

        {(type === "api_key" || type === "bearer") && (
          <Input label="Secret / API key" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="off" />
        )}
        {type === "basic_auth" && (
          <>
            <Input label="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
            <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" />
          </>
        )}
        {type === "oauth2" && (
          <>
            <Input label="Access token" type="password" value={accessToken} onChange={(e) => setAccessToken(e.target.value)} autoComplete="off" />
            <Input label="Refresh token (optional)" type="password" value={refreshToken} onChange={(e) => setRefreshToken(e.target.value)} autoComplete="off" />
          </>
        )}
        {type === "custom" && (
          <Textarea label="Secret (JSON object)" value={customJson} onChange={(e) => setCustomJson(e.target.value)} rows={5} />
        )}

        <div className="grid grid-cols-2 gap-3 border-t border-border pt-3">
          <Field label="Test URL (optional)">
            <input className="input" value={testUrl} onChange={(e) => setTestUrl(e.target.value)} placeholder="https://api.example.com/v1/me" />
          </Field>
          <Field label="Header name (optional)">
            <input className="input" value={headerName} onChange={(e) => setHeaderName(e.target.value)} placeholder="X-Api-Key" />
          </Field>
        </div>

        {error && <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
      </div>
    </Modal>
  );
}
