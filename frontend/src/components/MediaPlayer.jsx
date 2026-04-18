import { forwardRef } from "react";

const MediaPlayer = forwardRef(function MediaPlayer({ kind, src }, ref) {
  if (kind === "video") {
    return (
      <video
        ref={ref}
        controls
        src={src}
        style={{
          width: "100%",
          borderRadius: 14,
          background: "black",
          marginTop: 12,
          border: "2px solid var(--text)",
        }}
      />
    );
  }
  return (
    <audio
      ref={ref}
      controls
      src={src}
      style={{ width: "100%", marginTop: 12 }}
    />
  );
});

export default MediaPlayer;
