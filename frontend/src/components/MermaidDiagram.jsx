import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

let initialized = false;
function initMermaid() {
  if (initialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    securityLevel: "loose",
    fontFamily: "DM Sans, system-ui, sans-serif",
    themeVariables: {
      primaryColor: "#FFFFFF",
      primaryTextColor: "#0F2E4C",
      primaryBorderColor: "#0F2E4C",
      lineColor: "#0F2E4C",
      secondaryColor: "#FFE3E3",
      tertiaryColor: "#FFF4C2",
      fontSize: "14px",
    },
  });
  initialized = true;
}

let idCounter = 0;

export default function MermaidDiagram({ source }) {
  const ref = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!source) return;
    initMermaid();
    let cancelled = false;
    const id = `mmd-${++idCounter}`;

    (async () => {
      try {
        const { svg } = await mermaid.render(id, source);
        if (cancelled) return;
        if (ref.current) ref.current.innerHTML = svg;
        setError("");
      } catch (e) {
        if (cancelled) return;
        setError(e?.message || "Could not render diagram.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [source]);

  if (!source) return null;
  if (error) {
    return (
      <div className="diagram-error">
        <div style={{ fontWeight: 700, marginBottom: 6 }}>Diagram failed to render</div>
        <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>{source}</pre>
      </div>
    );
  }
  return <div className="diagram" ref={ref} aria-label="Flow diagram" />;
}
