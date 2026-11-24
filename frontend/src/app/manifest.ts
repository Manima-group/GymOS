import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Gym-OS",
    short_name: "Gym-OS",
    description: "Check in, track your membership and payments.",
    start_url: "/me",
    display: "standalone",
    background_color: "#0f172a",
    theme_color: "#0f172a",
    icons: [{ src: "/favicon.ico", sizes: "any", type: "image/x-icon" }],
  };
}
