import type { Detail } from "./types";
import { fields } from "./types";
export function renderCard(detail: Detail, selected: string[]) {
  const canvas = document.createElement("canvas");
  canvas.width = 1000;
  const ctx = canvas.getContext("2d")!;
  ctx.font = "26px Arial";
  const rows = selected.map((key) => {
    const raw =
      key === "enquiry_time"
        ? detail.enquiry_time
        : key === "remark"
          ? detail.remark_text
          : String(detail.lead[key as keyof typeof detail.lead] ?? "");
    const value = raw || "Not recorded";
    const lines: string[] = [];
    for (const paragraph of value.split("\n")) {
      let line = "";
      for (const character of paragraph) {
        if (ctx.measureText(line + character).width > 830) {
          lines.push(line);
          line = character;
        } else line += character;
      }
      lines.push(line);
    }
    return { key, lines };
  });
  canvas.height =
    230 + rows.reduce((sum, r) => sum + 70 + r.lines.length * 34, 0);
  ctx.fillStyle = "#f3f6f8";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#173447";
  ctx.fillRect(0, 0, 1000, 150);
  ctx.fillStyle = "#8edbd6";
  ctx.font = "bold 22px Arial";
  ctx.fillText("MUNEER  /  LEAD DETAILS", 65, 55);
  ctx.fillStyle = "#fff";
  ctx.font = "bold 38px Arial";
  ctx.fillText("Sales enquiry", 65, 110);
  let y = 205;
  for (const row of rows) {
    ctx.fillStyle = "#687b89";
    ctx.font = "bold 20px Arial";
    ctx.fillText(fields[row.key].toUpperCase(), 65, y);
    y += 37;
    ctx.fillStyle = "#172f41";
    ctx.font = "26px Arial";
    for (const line of row.lines) {
      ctx.fillText(line, 65, y);
      y += 34;
    }
    y += 33;
  }
  ctx.fillStyle = "#82929d";
  ctx.font = "18px Arial";
  ctx.fillText("Shared from Muneer Lead Workspace", 65, canvas.height - 25);
  return canvas;
}
export async function cardBlob(detail: Detail, selected: string[]) {
  return new Promise<Blob>((resolve, reject) =>
    renderCard(detail, selected).toBlob(
      (blob) =>
        blob
          ? resolve(blob)
          : reject(new Error("Cannot generate the card image.")),
      "image/png",
    ),
  );
}
