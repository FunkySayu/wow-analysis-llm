import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Library build, IIFE, everything inlined. The output is dropped verbatim into a
// report's <script> block by build_report.py, and a published report runs under the
// Artifact CSP, which blocks every external host - so React is bundled rather than
// externalised, and there are no .css assets: styles live in src/theme.ts as a
// string this bundle injects itself. One file in, one file out.
export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: "src/mount.tsx",
      name: "WCLViz",
      formats: ["iife"],
      fileName: () => "viz.iife.js",
    },
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: false,
    target: "es2019",
  },
  // React reads this at module scope; without it the bundle throws on `process`.
  define: { "process.env.NODE_ENV": '"production"' },
});
