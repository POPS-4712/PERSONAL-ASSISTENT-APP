import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useLogsWebSocket } from "@/hooks/useLogsWebSocket";
import { Badge, Button, Card, Input, PageHeader, Select } from "@/components/ui";
import { cn } from "@/utils/cn";
import { formatTime } from "@/utils/format";

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"];

const levelColor: Record<string, string> = {
  DEBUG: "text-muted",
  INFO: "text-info",
  WARNING: "text-warn",
  ERROR: "text-danger",
  CRITICAL: "text-danger",
};

export function LogsPage() {
  const [level, setLevel] = useState("INFO");
  const [source, setSource] = useState("");
  const [search, setSearch] = useState("");
  const stream = useLogsWebSocket(level);

  const scrollRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return stream.logs.filter(
      (l) =>
        (!source || l.source.toLowerCase().includes(source.toLowerCase())) &&
        (!q || l.message.toLowerCase().includes(q) || l.source.toLowerCase().includes(q)),
    );
  }, [stream.logs, source, search]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setStickToBottom(nearBottom);
  }

  useLayoutEffect(() => {
    if (stickToBottom && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered, stickToBottom]);

  useEffect(() => {
    setStickToBottom(true);
  }, [level]);

  const sources = useMemo(
    () => [...new Set(stream.logs.map((l) => l.source))].sort(),
    [stream.logs],
  );

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      <PageHeader
        title="Logs"
        description="Live structured log stream. Secrets are scrubbed server-side."
        actions={
          <Badge tone={stream.live ? "success" : "warning"}>
            <span className={cn("mr-1 inline-block h-2 w-2 rounded-full", stream.live ? "animate-pulse bg-ok" : "bg-warn")} />
            {stream.live ? "LIVE" : stream.status === "reconnecting" ? "RECONNECTING" : "CONNECTING"}
          </Badge>
        }
      />

      <div className="mb-3 grid gap-2 sm:grid-cols-4">
        <Select label="Min level" value={level} onChange={(e) => setLevel(e.target.value)}>
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </Select>
        <Select label="Source" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <div className="sm:col-span-2">
          <Input label="Search" placeholder="filter messages…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      <Card className="flex min-h-0 flex-1 flex-col p-0">
        <div className="flex items-center justify-between border-b border-border px-3 py-2 text-xs text-muted">
          <span>
            {filtered.length} / {stream.logs.length} lines
          </span>
          <div className="flex items-center gap-2">
            {!stickToBottom && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setStickToBottom(true);
                  if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }}
              >
                Jump to latest
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={stream.clear}>
              Clear
            </Button>
          </div>
        </div>
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="min-h-0 flex-1 overflow-auto bg-surface-2/40 p-3 font-mono text-xs leading-relaxed"
        >
          {filtered.length === 0 ? (
            <p className="text-muted">No log lines yet.</p>
          ) : (
            filtered.map((l) => (
              <div key={l._id} className="flex gap-3 whitespace-pre-wrap break-all py-0.5">
                <span className="shrink-0 text-muted">{formatTime(l.timestamp)}</span>
                <span className={cn("w-16 shrink-0 font-semibold", levelColor[l.level] ?? "text-fg")}>{l.level}</span>
                <span className="w-32 shrink-0 truncate text-muted">{l.source}</span>
                <span className="text-fg">{l.message}</span>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
