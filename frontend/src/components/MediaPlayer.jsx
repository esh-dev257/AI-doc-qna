import { forwardRef } from "react";

const MediaPlayer = forwardRef(function MediaPlayer({ kind, src }, ref) {
  if (kind === "video") {
    return (
      <video
        ref={ref}
        controls
        src={src}
        style={{ width: "100%", borderRadius: 8, background: "black", marginTop: 8 }}
      />
    );
  }
  return (
    <audio
      ref={ref}
      controls
      src={src}
      style={{ width: "100%", marginTop: 8 }}
    />
  );
});

export default MediaPlayer;
