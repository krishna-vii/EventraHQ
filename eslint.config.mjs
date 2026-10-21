import js from "@eslint/js";
import ts from "typescript-eslint";

export default ts.config(
  { ignores: ["**/node_modules/**", "**/.next/**", "**/next-env.d.ts", ".runtime/**", "test-results/**", "playwright-report/**"] },
  { files: ["apps/web/src/**/*.{ts,tsx}", "tests/browser/**/*.ts"], extends: [js.configs.recommended, ...ts.configs.recommended],
    rules: { "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }], "no-undef": "off" } }
);
