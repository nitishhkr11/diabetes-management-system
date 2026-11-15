import tseslint from "typescript-eslint";

export default tseslint.config(
  ...tseslint.configs.recommended,
  { ignores: [".next/**", ".next-*/**", "node_modules/**", "playwright-report/**", "test-results/**"] },
);
