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

const OASIS_ROOT = getOasisRoot();
const OUTPUT_DIR = path.join(OASIS_ROOT, "output");

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ folder: string }> }
) {
  const { folder } = await params;
  if (!folder || /[^a-z0-9_-]/.test(folder)) {
    return new Response("Invalid folder", { status: 400 });
  }
  const mp4Path = path.join(OUTPUT_DIR, folder, "final.mp4");
  if (!fs.existsSync(mp4Path)) {
    return new Response("Video not found", { status: 404 });
  }
  const stat = fs.statSync(mp4Path);
  const file = fs.readFileSync(mp4Path);
  return new Response(file, {
    headers: {
      "Content-Type": "video/mp4",
      "Content-Length": stat.size.toString(),
    },
  });
}
