import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { viteSingleFile } from 'vite-plugin-singlefile'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const isLiveBuild = mode === 'live';

  return {
    plugins: [svelte(), viteSingleFile()],
    build: {
      outDir: 'dist',
      emptyOutDir: false,
      // Don't copy public assets since we're inlining everything
      copyPublicDir: false,
      rollupOptions: {
        output: {
          entryFileNames: '[name].js',
          chunkFileNames: '[name].js',
          assetFileNames: '[name].[ext]',
        },
      },
    },
    define: {
      __LIVE_MODE_ENABLED__: isLiveBuild,
    },
  }
})
