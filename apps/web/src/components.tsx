import { useQuery } from "@tanstack/react-query";
import { FileSearch, X } from "lucide-react";
import { api, type Evidence } from "./api";

export function ErrorNotice({ error }: { error: unknown }) {
  return error ? (
    <div className="notice danger" role="alert">
      {error instanceof Error ? error.message : "Something went wrong."}
    </div>
  ) : null;
}

export function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <FileSearch size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function EvidenceDrawer({
  id,
  close,
}: {
  id: string;
  close: () => void;
}) {
  const query = useQuery({
    queryKey: ["evidence", id],
    queryFn: () => api<Evidence>(`/evidence/${encodeURIComponent(id)}`),
  });
  return (
    <div className="overlay" onClick={close}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Supporting evidence"
        className="drawer"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">TRACEABLE BY DESIGN</span>
            <h2>Supporting evidence</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close evidence"
            onClick={close}
          >
            <X />
          </button>
        </div>
        <p className="muted">
          Computed locally from the indicated analysis window. Human reviews do
          not modify this record.
        </p>
        <ErrorNotice error={query.error} />
        {query.data ? (
          <>
            <Badge>{query.data.kind}</Badge>
            <p className="mono break">{query.data.id}</p>
            <pre>{JSON.stringify(query.data.details, null, 2)}</pre>
          </>
        ) : (
          <p>Loading evidence…</p>
        )}
      </section>
    </div>
  );
}
