import { cpSync, existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const distDir = process.env.NEXT_DIST_DIR || ".next";
const standalone = resolve(root, `${distDir}/standalone`);
const staticSource = resolve(root, `${distDir}/static`);
const staticTarget = resolve(standalone, `${distDir}/static`);

mkdirSync(staticTarget, { recursive: true });
cpSync(staticSource, staticTarget, { recursive: true });
if (existsSync(resolve(root, "public"))) {
  cpSync(resolve(root, "public"), resolve(standalone, "public"), { recursive: true });
}
