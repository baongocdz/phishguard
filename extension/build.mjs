import { build, context } from "esbuild";
import { cpSync, mkdirSync } from "node:fs";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: {
    background: "src/background.ts",
    content: "src/content.ts",
    popup: "src/popup.ts",
    gmail: "src/gmail.ts",
  },
  bundle: true,
  format: "iife",
  target: "chrome110",
  outdir: "dist",
  sourcemap: true,
  logLevel: "info",
};

function copyStatic() {
  mkdirSync("dist", { recursive: true });
  for (const f of ["manifest.json", "popup.html", "popup.css"]) {
    cpSync(f, `dist/${f}`);
  }
}

copyStatic();
if (watch) {
  const ctx = await context(options);
  await ctx.watch();
  console.log("Watching... (sửa file rồi bấm Reload extension trong chrome://extensions)");
} else {
  await build(options);
}
