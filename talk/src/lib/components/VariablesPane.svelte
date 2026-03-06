<script lang="ts">
	import type { VarSnapshot } from '$lib/types'

	interface Props {
		variables: VarSnapshot
		title?: string
		class?: string
		style?: string
	}

	let { variables, title = 'Variables', class: className = '', style: styleStr = '' }: Props = $props()
</script>

<div
	class="rounded-xl border border-gray-800 bg-gray-900 p-6 font-mono text-2xl leading-relaxed text-green-400 text-left flex-1 min-h-0 {className}"
	style={styleStr}
>
	<p class="text-gray-400 text-lg mb-2">{title}</p>
	{#each Object.entries(variables) as [name, value]}
		<p><span class="text-gray-500">{name}</span> <span class="text-white">{value}</span></p>
	{/each}
</div>
