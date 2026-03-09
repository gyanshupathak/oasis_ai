"use client";

import { useState } from "react";

const PHASES = [
  { id: 1, label: "Scene Planning", desc: "Gemini: hook rewrite + scene structure" },
  { id: 2, label: "Images", desc: "Flux: keyframe images per scene" },
  { id: 3, label: "Voiceover", desc: "Gemini TTS: speech from scene text" },
  { id: 4, label: "Video Generation", desc: "Seedance Lite: AI video (FFmpeg fallback)" },
  { id: 5, label: "Assembly", desc: "Clips + voiceover + subtitles" },
  { id: 6, label: "Packaging", desc: "Caption & hashtags" },
];

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <div className="w-8 h-8 bg-black dark:bg-white rounded-full flex items-center justify-center">
        <div className="w-3 h-3 bg-white dark:bg-black rounded-sm rotate-45" />
      </div>
      <span className="font-display font-bold text-xl tracking-tighter">OASIS</span>
    </div>
  );
}

export default function Home() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentPhase, setCurrentPhase] = useState(0);
  const [phaseMessage, setPhaseMessage] = useState("");
  const [error, setError] = useState("");
  const [consoleLog, setConsoleLog] = useState<string[]>([]);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [caption, setCaption] = useState<string | null>(null);
  const [hashtags, setHashtags] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;

    setLoading(true);
    setError("");
    setVideoUrl(null);
    setCaption(null);
    setHashtags(null);
    setConsoleLog([]);
    setCurrentPhase(0);
    setPhaseMessage("Starting...");

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          length: 30,
          scenes: 5,
          frames: 1,
          noCaption: false,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(res.statusText || "Request failed");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.event === "started") {
              setConsoleLog((prev) => [...prev, data.message || "Pipeline started"]);
            } else if (data.event === "log") {
              setConsoleLog((prev) => [...prev, data.line]);
            } else if (data.event === "phase") {
              setCurrentPhase(data.phase);
              setPhaseMessage(data.message || "");
            } else if (data.event === "done") {
              setCurrentPhase(6);
              setPhaseMessage("Done!");
              const folder = data.folder as string;
              setVideoUrl(`/api/video/${encodeURIComponent(folder)}?t=${Date.now()}`);
              Promise.all([
                fetch(`/api/output/${encodeURIComponent(folder)}/caption`).then((r) => r.ok ? r.text() : null),
                fetch(`/api/output/${encodeURIComponent(folder)}/hashtags`).then((r) => r.ok ? r.text() : null),
              ]).then(([c, h]) => {
                setCaption(c ?? null);
                setHashtags(h ?? null);
              });
            } else if (data.event === "error") {
              setError(data.message || "Unknown error");
              if (data.console) {
                setConsoleLog(data.console.split("\n"));
              }
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-white text-black">
      {/* Header */}
      <header className="border-b border-black/10">
        <div className="mx-auto max-w-2xl px-6 py-4">
          <Logo />
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-12">
        <div className="mb-10">
          <h1 className="text-2xl font-display font-bold tracking-tight text-black mb-2">
            Turn your post into a reel
          </h1>
          <p className="text-black/60 text-sm max-w-md">
            Paste any LinkedIn/Twitter post or any thought script you have. OASIS creates a 30-second Instagram Reel with AI visuals, voiceover, and subtitles.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="text" className="block text-xs font-semibold text-black/70 uppercase tracking-wider mb-2">
              Your post
            </label>
            <textarea
              id="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste your LinkedIn or Twitter post here..."
              rows={10}
              disabled={loading}
              className="w-full rounded-lg border-2 border-black/20 bg-white px-4 py-4 text-black placeholder-black/30 focus:border-black focus:outline-none disabled:opacity-50 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="w-full rounded-lg bg-black text-white px-6 py-4 font-semibold hover:bg-black/90 focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {loading ? "Creating Reel..." : "Create Reel"}
          </button>
        </form>

        {(loading || consoleLog.length > 0) && (
          <div className="mt-12 space-y-8">
            {loading && (
              <div className="rounded-lg border-2 border-black/10 bg-black/[0.02] p-6">
                <h3 className="text-xs font-semibold text-black/60 uppercase tracking-wider mb-4">Pipeline</h3>
                <div className="space-y-3">
                  {PHASES.map((p) => (
                    <div
                      key={p.id}
                      className={`flex items-center gap-3 text-sm ${
                        currentPhase >= p.id ? "text-black" : "text-black/40"
                      }`}
                    >
                      <span
                        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                          currentPhase >= p.id
                            ? "bg-black text-white"
                            : "bg-black/10 text-black/40"
                        }`}
                      >
                        {currentPhase > p.id ? "✓" : p.id}
                      </span>
                      <span>{p.label}</span>
                      {currentPhase === p.id && phaseMessage && (
                        <span className="text-black/50 truncate">— {phaseMessage}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {consoleLog.length > 0 && (
              <div className="rounded-lg border-2 border-black/10 overflow-hidden">
                <h3 className="text-xs font-semibold text-black/60 uppercase tracking-wider px-4 py-3 border-b border-black/10">
                  Log
                </h3>
                <pre className="p-4 text-xs text-black/60 font-mono overflow-x-auto max-h-56 overflow-y-auto whitespace-pre-wrap break-words bg-black/[0.02]">
                  {consoleLog.join("\n")}
                </pre>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="mt-10 rounded-lg border-2 border-red-200 bg-red-50 p-4 text-red-800 text-sm">
            {error}
          </div>
        )}

        {videoUrl && !loading && (
          <div className="mt-12 space-y-8">
            <div className="rounded-lg border-2 border-black/10 overflow-hidden bg-black/[0.02]">
              <h3 className="text-xs font-semibold text-black/60 uppercase tracking-wider px-6 pt-6 pb-2">Your Reel</h3>
              <video
                key={videoUrl}
                src={videoUrl}
                controls
                playsInline
                autoPlay
                muted
                className="w-full aspect-[9/16] max-h-[70vh] object-contain bg-black"
              />
            </div>
            {(caption || hashtags) && (
              <div className="rounded-lg border-2 border-black/10 bg-black/[0.02] p-6 space-y-5">
                {caption && (
                  <div>
                    <h3 className="text-xs font-semibold text-black/60 uppercase tracking-wider mb-2">Caption</h3>
                    <p className="text-sm text-black/80 whitespace-pre-wrap">{caption}</p>
                  </div>
                )}
                {hashtags && (
                  <div>
                    <h3 className="text-xs font-semibold text-black/60 uppercase tracking-wider mb-2">Hashtags</h3>
                    <p className="text-sm text-black/70 font-mono">{hashtags}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
