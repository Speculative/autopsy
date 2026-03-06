<script lang="ts">
	interface Marker {
		line: number
		type: 'print' | 'breakpoint'
	}

	interface Props {
		lines: string[]
		highlightLine?: number
		/** Lines to accent with a yellow token-level highlight (e.g. newly added print lines). */
		accentLines?: number[]
		markers?: Marker[]
		instant?: boolean
		class?: string
		style?: string
	}

	let { lines, highlightLine = -1, accentLines = [], markers = [], instant = false, class: className = '', style: styleStr = '' }: Props = $props()

	function markerAt(line: number): Marker | undefined {
		return markers.find((m) => m.line === line)
	}
</script>

<div
	class="rounded-xl border border-gray-200 bg-white/95 px-6 py-6 shadow-xl overflow-hidden transition-all duration-500 shrink-0 {className}"
	style="text-align: left; {styleStr}"
>
	<div class="flex font-mono text-2xl leading-relaxed text-gray-800">
		<div class="flex flex-col pr-3 text-right text-gray-500 select-none w-10">
			{#each lines as _, i}
				{@const marker = markerAt(i)}
				<div class="flex items-center justify-end gap-1.5 h-[1.6em]">
					{#if marker?.type === 'breakpoint'}
						<div class="w-2 h-2 rounded-full bg-red-500 shrink-0"></div>
					{:else}
						<span class="w-2"></span>
					{/if}
					<span>{i + 1}</span>
				</div>
			{/each}
		</div>
		<div class="flex-1">
			{#each lines as line, i}
				<div
					class="h-[1.6em] whitespace-pre rounded px-1 -mx-1 {instant ? '' : 'transition-colors duration-200'} {highlightLine === i ? 'bg-yellow-200' : ''}"
				>
					{#if accentLines.includes(i)}
						<span class="rounded px-0.5 bg-yellow-200">{line}</span>
					{:else}
						{line}
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>
