import { build, context } from "esbuild";
import { cpSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: {
    background: "src/background.ts",
    content: "src/content.ts",
    popup: "src/popup.ts",
    gmail: "src/gmail.ts",
    blocked: "src/blocked.ts",
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
  for (const f of ["popup.html", "popup.css", "blocked.html"]) {
    cpSync(f, `dist/${f}`);
  }
  // Chuyển hướng (redirect) cần quyền trên tên miền quảng cáo: sinh từ danh sách.
  const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
  const ads = JSON.parse(readFileSync("src/ad-domains.json", "utf8")).domains;
  manifest.host_permissions = [...manifest.host_permissions, ...ads.map((d) => `*://*.${d}/*`)];
  writeFileSync("dist/manifest.json", JSON.stringify(manifest, null, 2));
}

copyStatic();
if (watch) {
  const ctx = await context(options);
  await ctx.watch();
  console.log("Watching... (sửa file rồi bấm Reload extension trong chrome://extensions)");
} else {
  await build(options);
}
