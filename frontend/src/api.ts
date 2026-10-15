let token = "";
export async function initialize() {
  const response = await fetch("/api/session");
  if (!response.ok) throw new Error("Cannot connect to the local server.");
  token = (await response.json()).token;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-CRM-Token": token },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "This action could not finish. Check your entries and try again.",
    );
  }
  return response.json();
}
export async function downloadReport(through: string) {
  const response = await fetch(
    "/api/report?through=" + encodeURIComponent(through),
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Report generation failed.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `Lead Master through ${through || "today"}.xlsx`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
