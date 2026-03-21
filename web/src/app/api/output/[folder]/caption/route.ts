import { NextRequest } from "next/server";
import path from "path";
import fs from "fs";

function getOasisRoot(): string {
  const cwd = process.cwd();
  const fromWeb = path.resolve(cwd, "..");
  if (fs.existsSync(path.join(fromWeb, "main.py"))) return fromWeb;
  if (fs.existsSync(path.join(cwd, "main.py"))) return cwd;
  return fromWeb;
}

const OUTPUT_DIR = path.join(getOasisRoot(), "output");

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ folder: string }> }
) {
  const { folder } = await params;
  if (!folder || /[^a-z0-9_-]/.test(folder)) {
    return new Response("Invalid folder", { status: 400 });
  }
  const filePath = path.join(OUTPUT_DIR, folder, "caption.txt");
  if (!fs.existsSync(filePath)) {
    return new Response("Caption not found", { status: 404 });
  }
  const content = fs.readFileSync(filePath, "utf-8");
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
