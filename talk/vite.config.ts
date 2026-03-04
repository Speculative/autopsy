import { sveltekit } from '@sveltejs/kit/vite'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

/**
 * Serve static HTML files raw, bypassing Vite's HTML transform pipeline.
 * Without this, Vite injects its HMR client into iframed .html files,
 * causing them to reload in a loop during dev.
 *
 * Uses configureServer to register middleware BEFORE Vite's own transforms.
 * The /__raw/ prefix ensures SvelteKit's router doesn't intercept the request.
 */
function rawStaticHtml(files: string[]) {
	return {
		name: 'raw-static-html',
		enforce: 'pre' as const,
		configureServer(server: any) {
			// Return a function → runs BEFORE internal middleware
			server.middlewares.use(async (req: any, res: any, next: any) => {
				if (!req.url?.startsWith('/__raw/')) return next()
				const filename = req.url.slice('/__raw/'.length)
				const match = files.find((f: string) => f === filename)
				if (!match) return next()

				// @ts-ignore -- node built-ins; svelte-check doesn't see @types/node
				const { readFileSync } = await import('node:fs')
				// @ts-ignore
				const { join } = await import('node:path')
				const content = readFileSync(join('static', match))
				res.setHeader('Content-Type', 'text/html; charset=utf-8')
				res.setHeader('Cache-Control', 'no-cache')
				res.end(content)
			})
		}
	}
}

export default defineConfig({
	plugins: [rawStaticHtml(['order_pipeline_report.html']), tailwindcss(), sveltekit()],
})
