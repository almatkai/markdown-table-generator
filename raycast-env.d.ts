/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `generate-markdown-table` command */
  export type GenerateMarkdownTable = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `generate-markdown-table` command */
  export type GenerateMarkdownTable = {
  /** # of Rows */
  "rows": string,
  /** # of Columns */
  "columns": string
}
}

