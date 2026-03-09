import { NextRequest } from "next/server";
import { spawn } from "child_process";

export const maxDuration = 600; // 10 min for full pipeline
import path from "path";
import fs from "fs";

// Resolve Oasis root: cwd is either web/ or Oasis root
function getOasisRoot(): string {
  const cwd = process.cwd();
  const fromWeb = path.resolve(cwd, "..");
  if (fs.existsSync(path.join(fromWeb, "main.py"))) return fromWeb;
  if (fs.existsSync(path.join(cwd, "main.py"))) return cwd;
  return fromWeb;
}

const OASIS_ROOT = getOasisRoot();
const OUTPUT_DIR = path.join(OASIS_ROOT, "output");

function loadEnvFromRoot(): Record<string, string> {
  const envPath = path.join(OASIS_ROOT, ".env");
  if (!fs.existsSync(envPath)) return {};
  try {
    const content = fs.readFileSync(envPath, "utf-8");
    const env: Record<string, string> = {};
    for (const line of content.split("\n")) {
      const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
      if (m) env[m[1].trim()] = m[2].trim().replace(/^["']|["']$/g, "");
    }
    return env;
  } catch {
    return {};
  }
}

function slugify(name: string, maxLen = 40): string {
  const s = name
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[-\s]+/g, "-")
    .trim()
    .replace(/^-+|-+$/g, "");
  return s.slice(0, maxLen) || "reel";
}

export async function POST(req: NextRequest) {
  let body: {
    text?: string;
    name?: string;
    length?: number;
    scenes?: number;
    frames?: 1 | 4;
    noCaption?: boolean;
  };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { text, name, length = 30, scenes = 5, frames = 1, noCaption = false } = body;
  if (!text?.trim()) {
    return new Response(JSON.stringify({ error: "Text is required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const folderName = name?.trim() || text.trim().split("\n")[0].slice(0, 50) || "reel";
  const slug = slugify(folderName);
  const outputFolder = path.join(OUTPUT_DIR, slug);

  // Write text to temp file
  const tmpDir = path.join(OASIS_ROOT, ".tmp");
  fs.mkdirSync(tmpDir, { recursive: true });
  const tmpFile = path.join(tmpDir, `input-${Date.now()}.txt`);
  fs.writeFileSync(tmpFile, text.trim(), "utf-8");

  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();

      function send(event: string, data: Record<string, unknown> = {}) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ event, ...data })}\n\n`));
      }

      send("started", { message: "Pipeline started" });

      // Use venv Python if it exists (has dependencies)
      const venvPy =
        process.platform === "win32"
          ? path.join(OASIS_ROOT, ".venv", "Scripts", "python.exe")
          : path.join(OASIS_ROOT, ".venv", "bin", "python3");
      const py = fs.existsSync(venvPy) ? venvPy : process.platform === "win32" ? "py" : "python3";

      const oasisEnv = loadEnvFromRoot();
      const args = [
        path.join(OASIS_ROOT, "main.py"),
        "--text", tmpFile,
        "--name", folderName,
        "--length", String(length),
        "--scenes", String(scenes),
        "--frames", String(frames),
        "--video-gen",
      ];
      if (noCaption) args.push("--no-caption");

      const proc = spawn(py, args, {
        cwd: OASIS_ROOT,
        env: { ...process.env, ...oasisEnv },
        shell: typeof py === "string" && !path.isAbsolute(py),
      });

      let outBuffer = "";
      const fullOutput: string[] = [];

      function processChunk(chunk: Buffer, stream: "stdout" | "stderr") {
        const str = chunk.toString();
        fullOutput.push(str);
        outBuffer += str;
        const lines = outBuffer.split("\n");
        outBuffer = lines.pop() || "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed) {
            send("log", { line: trimmed, stream });
          }
          const m = line.match(/\[Phase (\d)\]/);
          if (m) {
            send("phase", { phase: parseInt(m[1], 10), message: trimmed });
          }
          if (line.includes("[Output]")) {
            send("output", { folder: slug });
          }
        }
      }

      proc.stdout?.on("data", (chunk: Buffer) => processChunk(chunk, "stdout"));
      proc.stderr?.on("data", (chunk: Buffer) => processChunk(chunk, "stderr"));

      proc.on("close", (code) => {
        try { fs.unlinkSync(tmpFile); } catch { /* ignore */ }
        const consoleOutput = fullOutput.join("");
        if (code === 0) {
          const mp4Path = path.join(outputFolder, "final.mp4");
          if (fs.existsSync(mp4Path)) {
            send("done", { folder: slug });
          } else {
            send("error", { message: "Pipeline finished but final.mp4 not found", console: consoleOutput });
          }
        } else {
          send("error", { message: `Pipeline exited with code ${code}`, console: consoleOutput });
        }
        controller.close();
      });

      proc.on("error", (err) => {
        send("error", { message: err.message });
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
