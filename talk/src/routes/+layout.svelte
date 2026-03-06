<script lang="ts">
	import '../styles/app.css'

	let { children } = $props()
</script>

<svelte:head>
	<title>Data-oriented Debugging with autopsy</title>
</svelte:head>

{@render children()}