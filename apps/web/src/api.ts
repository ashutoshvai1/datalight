import type { components } from "./generated/api";

export type Run = components["schemas"]["RunView"];
export type System = components["schemas"]["SystemView"];
export type Report = components["schemas"]["ReportView"];
export type Profile = components["schemas"]["ChannelProfile"];
export type Finding = components["schemas"]["FindingView"];
export type Review = components["schemas"]["ReviewView"];
export type Evidence = components["schemas"]["EvidenceView"];
export type Batch = components["schemas"]["BatchView"];
export type Audit = components["schemas"]["EventView"];
export type ModelCall = components["schemas"]["ModelCallView"];
export type Control = components["schemas"]["RunControl"];

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api/v1${path}`,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      typeof error?.detail === "string"
        ? error.detail
        : `Request failed (${response.status}). Check the supplied values.`,
    );
  }
  return response.json();
}

export function uploadCsv(
  file: File,
  progress: (percent: number) => void,
): Promise<components["schemas"]["SourceView"]> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/api/v1/sources/upload");
    request.responseType = "json";
    request.upload.onprogress = (event) => {
      if (event.lengthComputable)
        progress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new Error("Upload interrupted. Please try again."));
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) resolve(request.response);
      else reject(new Error(typeof request.response?.detail === "string"
        ? request.response.detail
        : request.status === 413
          ? "This CSV exceeds the configured upload size limit."
          : "CSV upload failed. Please try again."));
    };
    const form = new FormData();
    form.append("file", file);
    request.send(form);
  });
}

export const number = (n: number | null | undefined, digits = 3) =>
  n == null
    ? "—"
    : n.toLocaleString(undefined, { maximumFractionDigits: digits });

export type PageProps = {
  run: Run;
  report?: Report;
  showEvidence: (id: string) => void;
};
