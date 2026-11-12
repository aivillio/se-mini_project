// ESLint flat config for the browser UI in web/static (plain scripts, no bundler).
import js from "@eslint/js";
import globals from "globals";

// helpers defined in app.js and shared by every page script
const shared = Object.fromEntries(
  ["$", "$$", "store", "ApiError", "api", "toast", "showErr", "inr", "fmtTime", "h", "segmented",
   "renderNav", "setSession", "clearSession"].map((n) => [n, "readonly"]),
);

export default [
  js.configs.recommended,
  {
    files: ["web/static/**/*.js"],
    languageOptions: { ecmaVersion: 2022, sourceType: "script", globals: { ...globals.browser, ...shared } },
    rules: {
      "no-unused-vars": ["error", { vars: "local", args: "none", caughtErrors: "none" }],
      eqeqeq: ["error", "smart"],
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-script-url": "error",
    },
  },
  {
    // app.js defines the shared helpers, so its top-level names are "unused" inside the file
    files: ["web/static/app.js"],
    languageOptions: { globals: { ...globals.browser } },
    rules: { "no-unused-vars": ["error", { vars: "local", args: "none", caughtErrors: "none" }], "no-redeclare": "off" },
  },
];
