import { defineConfig } from "eslint/config";
import globals from "globals";
import js from "@eslint/js";

export default defineConfig([
    {
        // Define the globally ignored directories; no other properties permitted
        ignores: [".venv/", "docs/build/"]
    },
    {
        name: "boardwalkd static javascript",
        basePath: "src/boardwalkd/static/",
        files: ["**/*.js"],
        ignores: [
            "**/*.min.js",
        ],
        languageOptions: {
            sourceType: "script",
            globals: {
                // Tell ESLint we're running this in the context of a web browser
                ...globals.browser,
            },
        },
		plugins: {
			js,
		},
		extends: ["js/recommended"],
	},
    {
        name: "boardwalkd static javascript test suite",
        basePath: "test/boardwalkd/",
        files: ["**/*.mjs"],
        languageOptions: {
            sourceType: "module",
            globals: {
                // Tell ESLint we're running this in the context of a web browser
                ...globals.browser,
            },
        },
		plugins: {
			js,
		},
		extends: ["js/recommended"],
	},
]);

