# Autopsy HTML Report Generator

Svelte application for generating self-contained HTML reports for the Autopsy debugging library.

## Development

```bash
npm install
npm run dev
```

## Building

Build the application to generate `autopsy/template.html`:

```bash
npm run build
```

This will create a self-contained HTML file with all CSS and JavaScript inlined, ready for Python to inject report data.

## Project Structure

- `src/App.svelte` - Main application component
- `src/types.ts` - TypeScript type definitions for report data
- `src/main.ts` - Application entry point
- `index.html` - Development entry point
- `vite.config.ts` - Build configuration for self-contained output
