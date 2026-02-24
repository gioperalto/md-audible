import { useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_VOICES = ["alloy", "nova", "onyx", "echo", "fable", "shimmer"];
const DEFAULT_NARRATORS = [
  "The Reluctant Confessor",
  "The Naive Observer",
  "The Ancient Sentinel",
  "The Heavy-Hearted Veteran",
];

type ConvertResponse = {
  filename: string;
  audio_url: string;
};

type SampleResponse = {
  filename: string;
  audio_url: string;
};

type ErrorResponse = {
  detail: string;
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [voice, setVoice] = useState<string>("alloy");
  const [narrators, setNarrators] = useState<string[]>(DEFAULT_NARRATORS);
  const [narrator, setNarrator] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [sampleLoading, setSampleLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [audioPath, setAudioPath] = useState<string>("");
  const [audioFilename, setAudioFilename] = useState<string>("");
  const [sampleText, setSampleText] = useState<string>("");
  const playerRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadNarrators() {
      try {
        const response = await fetch(`${apiBase}/api/narrators`);
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as { narrators?: string[] };
        if (mounted && Array.isArray(payload.narrators) && payload.narrators.length > 0) {
          setNarrators(payload.narrators);
        }
      } catch {
        // Keep defaults when narrator list cannot be loaded.
      }
    }
    void loadNarrators();
    return () => {
      mounted = false;
    };
  }, []);

  const playableUrl = useMemo(() => {
    if (!audioPath) {
      return "";
    }
    if (audioPath.startsWith("http")) {
      return audioPath;
    }
    return `${apiBase}${audioPath}`;
  }, [audioPath]);

  async function handleConvert(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setAudioPath("");
    setAudioFilename("");

    if (!selectedFile) {
      setError("Select a markdown file first.");
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith(".md")) {
      setError("Only .md files are supported.");
      return;
    }

    const formData = new FormData();
    formData.append("markdown_file", selectedFile);
    formData.append("voice", voice);
    if (narrator) {
      formData.append("narrator", narrator);
    }

    try {
      setLoading(true);
      const response = await fetch(`${apiBase}/api/convert`, {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json()) as ConvertResponse | ErrorResponse;

      if (!response.ok) {
        throw new Error("detail" in payload ? payload.detail : "Conversion failed");
      }

      const result = payload as ConvertResponse;
      setAudioPath(result.audio_url);
      setAudioFilename(result.filename);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Conversion failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSample() {
    setError("");
    setAudioPath("");
    setAudioFilename("");

    const formData = new FormData();
    formData.append("voice", voice);
    if (narrator) {
      formData.append("narrator", narrator);
    }
    if (sampleText.trim()) {
      formData.append("sample_text", sampleText.trim());
    }

    try {
      setSampleLoading(true);
      const response = await fetch(`${apiBase}/api/voice-sample`, {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json()) as SampleResponse | ErrorResponse;

      if (!response.ok) {
        throw new Error("detail" in payload ? payload.detail : "Sample generation failed");
      }

      const result = payload as SampleResponse;
      setAudioPath(result.audio_url);
      setAudioFilename(result.filename);
      queueMicrotask(() => {
        if (playerRef.current) {
          void playerRef.current.play();
        }
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Sample generation failed";
      setError(message);
    } finally {
      setSampleLoading(false);
    }
  }

  function handlePlay() {
    if (playerRef.current) {
      void playerRef.current.play();
    }
  }

  return (
    <main className="page">
      <section className="card">
        <h1>Markdown to Audio</h1>
        <p>Select a chapter .md file and convert it to speech using OpenRouter.</p>

        <form onSubmit={handleConvert} className="form">
          <label>
            Markdown file
            <input
              type="file"
              accept=".md,text/markdown"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <label>
            Voice
            <select value={voice} onChange={(e) => setVoice(e.target.value)}>
              {DEFAULT_VOICES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label>
            Narrator style
            <select value={narrator} onChange={(e) => setNarrator(e.target.value)}>
              <option value="">None</option>
              {narrators.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <button type="submit" disabled={loading || sampleLoading}>
            {loading ? "Converting..." : "Convert to Audio"}
          </button>
        </form>

        <div className="sampleBox">
          <label>
            Sample text (optional)
            <input
              type="text"
              value={sampleText}
              onChange={(e) => setSampleText(e.target.value)}
              placeholder="Leave blank for the default sample"
            />
            <span className="helper">Max 500 characters.</span>
          </label>
          <button type="button" onClick={handleSample} disabled={loading || sampleLoading}>
            {sampleLoading ? "Sampling..." : "Sample Voice"}
          </button>
        </div>

        {error ? <p className="error">{error}</p> : null}

        {playableUrl ? (
          <div className="audioBox">
            <p>Created: {audioFilename}</p>
            <audio ref={playerRef} controls src={playableUrl} preload="metadata" />
            <button type="button" onClick={handlePlay}>
              Play
            </button>
          </div>
        ) : null}
      </section>
    </main>
  );
}
