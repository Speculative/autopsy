<script lang="ts">
	import { Presentation, Slide, Notes, Action, Code } from '@animotion/core'
	import { tween, all } from '@animotion/motion'

	const codeInitial = `\
for order in orders:
    shipping = shipping_options(order)
    cost = compute_cost(shipping)
    results.append(ShippedOrder(order, cost))`

	const codeWithPrint1 = `\
for order in orders:
    shipping = shipping_options(order)
    print("Shipping", shipping)
    cost = compute_cost(shipping)
    results.append(ShippedOrder(order, cost))`

	const codeWithPrints = `\
for order in orders:
    shipping = shipping_options(order)
    print("Shipping", shipping)
    cost = compute_cost(shipping)
    print("Cost", cost)
    results.append(ShippedOrder(order, cost))`

	const codeWithPrintExpanded = `\
for order in orders:
    shipping = shipping_options(order)
    print("Shipping", shipping.type, shipping.options)
    cost = compute_cost(shipping)
    print("Cost", cost)
    results.append(ShippedOrder(order, cost))`

	let code: ReturnType<typeof Code>
	let slide2Code = $state(codeInitial)
	let showTerminal = $state(false)
	let scrollTerminal = $state(false)
	let highlightBug = $state(false)
	let showExpandedTerminal = $state(false)
	let scrollExpanded = $state(false)

	const terminalLines = [
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '4.99'],
		['Shipping', 'Shipping(express, ...)'],  ['Cost', '14.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '4.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '4.99'],
		['Shipping', 'Shipping(overnight, ...)'], ['Cost', '29.99'],
		['Shipping', 'Shipping(express, ...)'],  ['Cost', '14.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '4.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '4.99'],
		['Shipping', 'Shipping(express, ...)'],  ['Cost', '14.99'],
		['Shipping', 'Shipping(overnight, ...)'], ['Cost', '29.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '4.99'],
		['Shipping', 'Shipping(express, ...)'],  ['Cost', '14.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '4.99'],
		['Shipping', 'Shipping(overnight, ...)'], ['Cost', '29.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '18.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '18.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '18.99'],
		['Shipping', 'Shipping(express, ...)'],  ['Cost', '14.99'],
		['Shipping', 'Shipping(overnight, ...)'], ['Cost', '29.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '18.99'],
		['Shipping', 'Shipping(express, ...)'],  ['Cost', '14.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '18.99'],
		['Shipping', 'Shipping(overnight, ...)'], ['Cost', '29.99'],
		['Shipping', 'Shipping(standard, ...)'], ['Cost', '18.99'],
	]

	// Expanded terminal: shipping.type + shipping.options dict
	const terminalLinesExpanded = [
		['Shipping', "standard", "{}"],  ['Cost', '4.99'],
		['Shipping', "express",  "{'base_rate': 14.99, 'zone': 'domestic'}"], ['Cost', '14.99'],
		['Shipping', "standard", "{}"],  ['Cost', '4.99'],
		['Shipping', "standard", "{}"],  ['Cost', '4.99'],
		['Shipping', "overnight","{}"], ['Cost', '29.99'],
		['Shipping', "express",  "{}"], ['Cost', '14.99'],
		['Shipping', "standard", "{}"],  ['Cost', '4.99'],
		['Shipping', "standard", "{}"],  ['Cost', '4.99'],
		['Shipping', "express",  "{}"], ['Cost', '14.99'],
		['Shipping', "overnight","{}"], ['Cost', '29.99'],
		['Shipping', "standard", "{}"],  ['Cost', '4.99'],
		['Shipping', "express",  "{}"], ['Cost', '14.99'],
		['Shipping', "standard", "{}"],  ['Cost', '4.99'],
		['Shipping', "overnight","{}"], ['Cost', '29.99'],
		['Shipping', "standard", "{'careful_handling': True}"], ['Cost', '18.99'],
		['Shipping', "standard", "{}"], ['Cost', '18.99'],
		['Shipping', "standard", "{}"], ['Cost', '18.99'],
		['Shipping', "express",  "{}"], ['Cost', '14.99'],
		['Shipping', "overnight","{}"], ['Cost', '29.99'],
		['Shipping', "standard", "{}"], ['Cost', '18.99'],
		['Shipping', "express",  "{}"], ['Cost', '14.99'],
		['Shipping', "standard", "{}"], ['Cost', '18.99'],
		['Shipping', "overnight","{}"], ['Cost', '29.99'],
		['Shipping', "standard", "{}"], ['Cost', '18.99'],
	]

	let stateTimeStep = $state(0)
	let showWhatsWrongReason1 = $state(false)
	let showWhatsWrongReason2 = $state(false)

	// ── Breakpoint debugger overlay (after breakpoint state/time plot) ──
	let showBreakpointDebugger = $state(false)
	let bpDebuggerHighlightLine = $state(-1)
	let bpDebuggerIteration = $state(0)
	const bpDebuggerLineDelay = 350
	const bpCodeLines = [
		'for order in orders:',
		'    shipping = shipping_options(order)',
		'    cost = compute_cost(shipping)',
		'    results.append(ShippedOrder(order, cost))',
	]
	const COST_LINE_IDX = 2
	const bpVariables = [
		[['order', 'Order(...)'], ['orders', '[...]'], ['shipping', 'Shipping(standard,...)'], ['cost', '4.99']],
		[['order', 'Order(...)'], ['orders', '[...]'], ['shipping', 'Shipping(express,...)'], ['cost', '14.99']],
		[['order', 'Order(...)'], ['orders', '[...]'], ['shipping', 'Shipping(overnight,...)'], ['cost', '29.99']],
	]

	function sleep(ms: number) {
		return new Promise((resolve) => setTimeout(resolve, ms))
	}

	// ── State × time build-up animation state ──
	// Code block shown during label fly-out
	let showAxisCode = $state(false)
	// Which tokens to highlight in the axis code block
	let axisCodeHighlight = $state<'state-vars' | 'cost' | null>(null)
	// Terminal (cost-only) shown during "time" label sequence
	let showCostTerminal = $state(false)

	// SVG-coordinate tweens for the axis labels (viewBox 0 0 900 520)
	const psLabel = tween({
		x: 50, y: 250, rotate: -90, fontSize: 22,
	}, { duration: 600 })

	const tLabel = tween({
		x: 460, y: 500, rotate: 0, fontSize: 22,
	}, { duration: 600 })

	// 'none' = both at rest; 'state' = program state is title; 'time' = time is title
	let titleLabel = $state<'none' | 'state' | 'time'>('none')

	const axisFade = tween({ codeOpacity: 0, terminalOpacity: 0, axisOpacity: 1 }, { duration: 400 })

	// ── State variable labels — distribute along the Y-axis ──
	// 5 variables, each tweens from center of plot to a distinct y position on the axis
	const stateVarNames = ['order', 'orders', 'shipping', 'cost', 'results']
	// Target y positions spaced along the plot height (y=90 to y=440)
	const stateVarTargetY = [110, 195, 280, 360, 430]
	const stateVarLabels = stateVarNames.map(() =>
		tween({ x: 460, y: 250, opacity: 0, fontSize: 18 }, { duration: 500 })
	)
	let showStateVarLabels = $state(false)

	// ── Cost value labels — distribute along the X-axis ──
	// Use every other Cost entry for a clean spread (12 values across x=110..810)
	const costValues = terminalLines
		.filter(([l]) => l === 'Cost')
		.map(([, v]) => v)
		.slice(0, 12)
	const costLabelTargetX = costValues.map((_, i) =>
		110 + (i / (costValues.length - 1)) * 700
	)
	const costLabels = costValues.map(() =>
		tween({ x: 460, y: 250, rotate: 0, opacity: 0, fontSize: 18 }, { duration: 500 })
	)
	let showCostLabels = $state(false)

	// Breakpoint: animated x position (slides across 3 positions)
	let bpX = tween({ x: 200 })

	// In dev, serve iframed HTML via /__raw/ to bypass Vite's HMR injection
	const iframBase = import.meta.env.DEV ? '/__raw' : ''

	// Print debugging: sawtooth dots
	function generateSawtooth(
		periods: number,
		dotsPerPeriod: number,
		xMin: number,
		xMax: number,
		yMin: number,
		yMax: number,
	): [number, number][] {
		const dots: [number, number][] = []
		const periodWidth = (xMax - xMin) / periods
		for (let p = 0; p < periods; p++) {
			const xStart = xMin + p * periodWidth
			for (let i = 0; i < dotsPerPeriod; i++) {
				const x = xStart + ((i + 0.5) / dotsPerPeriod) * periodWidth
				const y = yMax - (i / (dotsPerPeriod - 1)) * (yMax - yMin)
				dots.push([x, y])
			}
		}
		return dots
	}

	const printDots = generateSawtooth(4, 8, 110, 810, 90, 440)

	// Autopsy: 5 evenly-spaced full-height slices
	const autopsySlices = [180, 320, 460, 600, 740]
</script>

<Presentation options={{ history: true, transition: 'slide', controls: false, progress: true, slideNumber: true }}>
	<!-- ─── Slide 1: Title ─── -->
	<Slide class="h-full">
		<div class="grid h-full grid-cols-[3fr_1fr] items-center gap-8 px-16 py-12">
			<div class="flex flex-col gap-8">
				<h1 class="text-left text-[4rem] font-bold leading-tight text-black">
					Data-oriented Debugging with<br />
					<span
						class="mt-2 inline-block bg-[#0000FF] px-3 py-1 text-white"
						style="font-family: var(--r-code-font)"
					>autopsy</span>
				</h1>
				<div class="flex flex-col gap-2">
					<p class="text-left text-2xl text-black">
						<span class="font-bold text-[#0000FF]">Jeffrey Tao</span>, Xiaorui Liu, Ryan Marcus,
						Andrew Head
					</p>
					<p class="text-left text-xl text-black">PLATEAU 2026</p>
				</div>
			</div>
			<div class="flex flex-col items-center justify-center gap-8">
				<img src="/headshot.jpg" alt="Jeffrey Tao" class="h-44 w-44 rounded-full object-cover" />
				<img src="/penn-hci.svg" alt="Penn HCI Lab" class="w-40" />
			</div>
		</div>
	</Slide>

	<!-- ─── Section 1: Debugging is about checking mental models against execution data ─── -->

	<!-- Slide 2: Code example — debugging motivation -->
	<Slide class="h-full" in={() => { showTerminal = false; scrollTerminal = false; highlightBug = false; showExpandedTerminal = false; scrollExpanded = false; slide2Code = codeInitial; if (code) code.update`${codeInitial}` }}>
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16">
			<h2 class="text-left text-5xl font-bold text-black">How do you debug this?</h2>
			<div class="flex gap-6" style="align-items: stretch">
				<div
					class="rounded-xl border border-gray-200 bg-gray-50 p-6 shadow-sm overflow-hidden transition-all duration-500"
					style="flex: {showTerminal ? '2 2 66%' : '1 1 100%'}; text-align: left"
				>
					<Code
						bind:this={code}
						lang="python"
						theme="github-light"
						code={slide2Code}
						options={{ duration: 400, stagger: 0, lineNumbers: true, containerStyle: false, enhanceMatching: true, splitTokens: true }}
						class="text-2xl"
					/>
				</div>
				<div
					class="rounded-xl border border-gray-800 bg-gray-900 p-6 shadow-sm font-mono text-xl leading-relaxed text-green-400 transition-all duration-500 text-left"
					style="flex: 0 0 33%; opacity: {showTerminal ? 1 : 0}; margin-left: {showTerminal ? '0' : 'calc(-33% - 1.5rem)'}; height: 18.2rem; overflow: hidden"
				>
					<div style="animation: {scrollExpanded ? 'terminal-scroll-expanded 1s linear forwards' : scrollTerminal ? 'terminal-scroll 1s linear forwards' : 'none'}">
						{#each (showExpandedTerminal ? terminalLinesExpanded : terminalLines) as row, i}
							{@const lines = showExpandedTerminal ? terminalLinesExpanded : terminalLines}
							{#if i === lines.length - 2}
								<div
									class="transition-all duration-500"
									style="outline: {highlightBug ? '2px solid #ef4444' : '2px solid transparent'}; outline-offset: 2px; border-radius: 4px; background: {highlightBug ? 'rgba(239,68,68,0.12)' : 'transparent'}"
								>
									{#if row.length === 3}
										<p>{row[0]} <span class="text-white">{row[1]}</span> <span class="text-yellow-300">{row[2]}</span></p>
									{:else}
										<p>{row[0]} <span class="text-white">{row[1]}</span></p>
									{/if}
									{#if lines[i+1].length === 3}
										<p>{lines[i+1][0]} <span class="text-white">{lines[i+1][1]}</span> <span class="text-yellow-300">{lines[i+1][2]}</span></p>
									{:else}
										<p>{lines[i+1][0]} <span class="text-white">{lines[i+1][1]}</span></p>
									{/if}
								</div>
							{:else if i === lines.length - 1}
								<!-- rendered inside the highlight div above -->
							{:else if row.length === 3}
								<p>{row[0]} <span class="text-white">{row[1]}</span> <span class="text-yellow-300">{row[2]}</span></p>
							{:else}
								<p>{row[0]} <span class="text-white">{row[1]}</span></p>
							{/if}
						{/each}
					</div>
				</div>
			</div>
		</div>
		<Action
			do={async () => {
				await code.update`${codeWithPrint1}`
				slide2Code = codeWithPrint1
				await code.update`${codeWithPrints}`
				slide2Code = codeWithPrints
			}}
			undo={() => {
				slide2Code = codeInitial
				code.update`${codeInitial}`
			}}
		/>
		<Action do={() => { showTerminal = true }} undo={() => { showTerminal = false; scrollTerminal = false }} />
		<Action do={() => { scrollTerminal = true }} undo={() => { scrollTerminal = false; highlightBug = false }} />
		<Action do={() => { highlightBug = true }} undo={() => { highlightBug = false }} />
		<!-- Expand the Shipping print to show .type and .options -->
		<Action
			do={async () => {
				highlightBug = false
				await code.update`${codeWithPrintExpanded}`
				slide2Code = codeWithPrintExpanded
				await code.selectLines`3`
			}}
			undo={async () => {
				highlightBug = true
				await code.update`${codeWithPrints}`
				slide2Code = codeWithPrints
				await code.selectLines``
			}}
		/>
		<!-- Switch terminal to show the expanded output with the options dict -->
		<Action
			do={() => { showExpandedTerminal = true; scrollExpanded = false }}
			undo={() => { showExpandedTerminal = false; scrollExpanded = false }}
		/>
		<!-- Scroll the expanded terminal to the careful_handling line -->
		<Action
			do={() => { scrollExpanded = true }}
			undo={() => { scrollExpanded = false }}
		/>
		<Notes>
			Start with a simple motivating loop. Ask: if results look wrong, how do you figure out why?
			The natural instinct is to add print statements — advance to show what that looks like.
			Then show the output: you can see values, but it's hard to correlate them — each run is just a wall of text.
			After noticing standard shipping costs suddenly go up, expand the print to inspect .type and .options.
			The new output reveals the zone field changing to 'international' — that's the bug.
		</Notes>
	</Slide>

	<!-- Slide 3: What is happening? -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">What is happening?</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Debugging is about establishing a <em>mental model</em></li>
				<li>Observing how code executes helps with model <em>formation</em> and <em>checking</em></li>
			</ul>
		</div>
	</Slide>

	<!-- Slide 4: What's wrong? -->
	<Slide class="h-full" in={() => { showWhatsWrongReason1 = false; showWhatsWrongReason2 = false }}>
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">What's wrong?</h2>
			<ol class="flex flex-col gap-4 pl-6 text-2xl text-black list-decimal">
				<li
					class="transition-opacity duration-300"
					style="opacity: {showWhatsWrongReason1 ? 1 : 0}"
				>Debugging tools couple <em>data collection</em> and <em>data analysis</em></li>
				<li
					class="transition-opacity duration-300"
					style="opacity: {showWhatsWrongReason2 ? 1 : 0}"
				>Debugging tools have limited <em>affordances</em> for analysis</li>
			</ol>
		</div>
		<Action do={() => { showWhatsWrongReason1 = true }} undo={() => { showWhatsWrongReason1 = false }} />
		<Action do={() => { showWhatsWrongReason2 = true }} undo={() => { showWhatsWrongReason2 = false }} />
	</Slide>

	<!-- Slide 5: The state × time space -->
	<!--
		Axis labels are SVG <text> elements tweened in SVG-coordinate space (viewBox 0 0 900 520).
		Resting positions: "program state" at (50,250) rotate(-90); "time" at (460,500).
		Title position: both fly to (100,60) rotate(0) at fontSize=52.
	-->
	<Slide class="h-full" in={() => {
		stateTimeStep = 0; bpX.reset()
		titleLabel = 'none'
		showAxisCode = false; axisCodeHighlight = null; showCostTerminal = false
		showStateVarLabels = false; showCostLabels = false
		showBreakpointDebugger = false; bpDebuggerHighlightLine = -1; bpDebuggerIteration = 0
		psLabel.reset(); tLabel.reset(); axisFade.reset()
		stateVarLabels.forEach(l => l.reset())
		costLabels.forEach(l => l.reset())
	}}>
		<div class="relative flex h-full items-center justify-center overflow-hidden">

			<!-- ── Main SVG (axes, data marks, and animated axis labels) ── -->
			<svg viewBox="0 0 900 520" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="#f5f5f5" />

				<!-- Step 1: Breakpoint — animated vertical slice (solid bar) -->
				{#if stateTimeStep === 1}
					<rect x={bpX.x - 12} y="40" width="24" height="420" fill="#0000FF"
						style="opacity: 0; animation: appear 0.3s ease-out 0ms forwards" />
				{/if}

				<!-- Step 2+3: Print — single dot first, then all animate in -->
				{#if stateTimeStep === 2 || stateTimeStep === 3}
					{#if stateTimeStep === 2}
						<circle cx={printDots[0][0]} cy={printDots[0][1]} r="6" fill="#0000FF"
							style="opacity: 0; animation: appear 0.15s ease-out 0ms forwards" />
					{:else}
						<circle cx={printDots[0][0]} cy={printDots[0][1]} r="6" fill="#0000FF" />
					{/if}
					{#if stateTimeStep === 3}
						{#each printDots.slice(1) as [cx, cy], i}
							<circle cx={cx} cy={cy} r="6" fill="#0000FF"
								style="opacity: 0; animation: appear 0.15s ease-out {i * 40}ms forwards" />
						{/each}
					{/if}
				{/if}

				<!-- Step 4+5: Autopsy — first bar, then all bars -->
				{#if stateTimeStep === 4 || stateTimeStep === 5}
					{#if stateTimeStep === 4}
						<rect x={autopsySlices[0] - 11} y="40" width="22" height="420" fill="#0000FF"
							style="opacity: 0; animation: appear 0.3s ease-out 0ms forwards" />
					{:else}
						<rect x={autopsySlices[0] - 11} y="40" width="22" height="420" fill="#0000FF" />
					{/if}
					{#if stateTimeStep === 5}
						{#each autopsySlices.slice(1) as x, i}
							<rect x={x - 11} y="40" width="22" height="420" fill="#0000FF"
								style="opacity: 0; animation: appear 0.3s ease-out {i * 150}ms forwards" />
						{/each}
					{/if}
				{/if}

				<!-- Axes + other-label: fade out when a label is in title position -->
				<g opacity={axisFade.axisOpacity}>
					<!-- Y axis -->
					<line x1="100" y1="40" x2="100" y2="460" stroke="black" stroke-width="2.5" />
					<polygon points="100,33 94,47 106,47" fill="black" />
					<!-- X axis -->
					<line x1="100" y1="460" x2="836" y2="460" stroke="black" stroke-width="2.5" />
					<polygon points="843,460 829,454 829,466" fill="black" />
				</g>

				<!-- ── Axis labels (SVG text, tweened to title position) ── -->
				<text
					text-anchor="middle"
					font-family="Lato, sans-serif"
					font-size={psLabel.fontSize}
					fill="black"
					opacity={titleLabel === 'time' ? axisFade.axisOpacity : 1}
					transform="translate({psLabel.x},{psLabel.y}) rotate({psLabel.rotate})"
				>program state</text>

				<text
					text-anchor="middle"
					font-family="Lato, sans-serif"
					font-size={tLabel.fontSize}
					fill="black"
					opacity={titleLabel === 'state' ? axisFade.axisOpacity : 1}
					transform="translate({tLabel.x},{tLabel.y}) rotate({tLabel.rotate})"
				>time</text>

				<!-- ── State variable labels distributed along Y-axis ── -->
				{#if showStateVarLabels}
					{#each stateVarLabels as lbl, i}
						<text
							text-anchor="start"
							font-family="Lato, sans-serif"
							font-size={lbl.fontSize}
							fill="black"
							opacity={lbl.opacity}
							transform="translate({lbl.x},{lbl.y})"
						>{stateVarNames[i]}</text>
					{/each}
				{/if}

				<!-- ── Cost value labels distributed along X-axis ── -->
				{#if showCostLabels}
					{#each costLabels as lbl, i}
						<text
							text-anchor="middle"
							font-family="Lato, sans-serif"
							font-size={lbl.fontSize}
							fill="black"
							opacity={lbl.opacity}
							transform="translate({lbl.x},{lbl.y}) rotate({lbl.rotate})"
						>{costValues[i]}</text>
					{/each}
				{/if}
			</svg>

			<!-- ── Code overlay (and optional cost terminal) ── -->
			{#if showAxisCode}
				<div class="absolute flex items-center justify-center gap-4" style="pointer-events: none; width: 75%; left: 12.5%;">
					<!-- Code block: 2/3 width -->
					<div
						class="rounded-xl border border-gray-200 bg-white/95 px-8 py-6 shadow-xl"
						style="flex: 2 1 0; opacity: {axisFade.codeOpacity}"
					>
						<pre class="text-2xl leading-relaxed font-mono text-gray-800"><code
><span class="text-gray-500">for </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">order</span><span class="text-gray-500"> in </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">orders</span><span class="text-gray-500">:</span>
<span class="text-gray-500">    </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">shipping</span><span class="text-gray-500"> = shipping_options(order)</span>
<span class="text-gray-500">    </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' || axisCodeHighlight === 'cost' ? 'bg-yellow-200' : 'bg-transparent'}">cost</span><span class="text-gray-500"> = compute_cost(shipping)</span>
<span class="text-gray-500">    </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">results</span><span class="text-gray-500">.append(ShippedOrder(order, cost))</span></code></pre>
					</div>
					<!-- Cost terminal: 1/3 width, fixed height, only present when showCostTerminal -->
					{#if showCostTerminal}
						<div
							class="rounded-xl border border-gray-800 bg-gray-900 px-5 py-4 font-mono text-lg leading-relaxed text-green-400 overflow-y-auto text-left"
							style="flex: 1 1 0; height: 14rem; opacity: {axisFade.terminalOpacity}"
						>
							{#each terminalLines.filter(([l]) => l === 'Cost') as [label, value]}
								<p>Cost <span class="text-white">{value}</span></p>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			<!-- Step label (top-right, shown once debugging techniques are introduced) -->
			{#if stateTimeStep >= 1}
				<div class="absolute right-[8%] top-[10%] rounded-md bg-white/85 px-4 py-2 text-right">
					{#if stateTimeStep === 1}
						<p class="text-5xl font-bold text-[#0000FF]">breakpoint debugger</p>
						<p class="text-3xl text-gray-500">all state · one moment</p>
					{/if}
					{#if stateTimeStep === 2 || stateTimeStep === 3}
						<p class="text-5xl font-bold text-[#0000FF]">print debugging</p>
						<p class="text-3xl text-gray-500">some state · many moments</p>
					{/if}
					{#if stateTimeStep === 4 || stateTimeStep === 5}
						<p class="text-5xl font-bold text-[#0000FF]" style="font-family: var(--r-code-font)">autopsy</p>
						<p class="text-3xl text-gray-500">all state · many moments</p>
					{/if}
				</div>
			{/if}

			<!-- ── Breakpoint debugger overlay (code + Variables pane) ── -->
			{#if showBreakpointDebugger}
				<div class="absolute z-10 flex items-center justify-center gap-4" style="pointer-events: none; width: 75%; left: 12.5%;">
					<div
						class="rounded-xl border border-gray-200 bg-white/95 px-6 py-6 shadow-xl overflow-hidden transition-all duration-500"
						style="flex: 1 1 50%; text-align: left"
					>
						<div class="flex font-mono text-xl leading-relaxed text-gray-800">
							<div class="flex flex-col pr-3 text-right text-gray-500 select-none w-10">
								{#each bpCodeLines as _, i}
									<div class="flex items-center justify-end gap-1.5 h-[1.6em]">
										{#if i === COST_LINE_IDX}
											<div class="w-2 h-2 rounded-full bg-red-500 shrink-0"></div>
										{:else}
											<span class="w-2"></span>
										{/if}
										<span>{i + 1}</span>
									</div>
								{/each}
							</div>
							<div class="flex-1">
								{#each bpCodeLines as line, i}
									<div
										class="h-[1.6em] whitespace-pre transition-colors duration-200 rounded px-1 -mx-1 {bpDebuggerHighlightLine === i ? 'bg-yellow-200' : ''}"
									>
										{line}
									</div>
								{/each}
							</div>
						</div>
					</div>
					<div
						class="rounded-xl border border-gray-800 bg-gray-900 p-6 font-mono text-xl leading-relaxed text-green-400 text-left"
						style="flex: 0 0 50%; height: 12rem"
					>
						<p class="text-gray-400 text-sm mb-3">Variables</p>
						{#each bpVariables[bpDebuggerIteration] as [name, value]}
							<p><span class="text-gray-500">{name}</span> <span class="text-white">{value}</span></p>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		<!-- ════════════════════════════════════════════════════
		     Build-up: "program state" axis label sequence
		     ════════════════════════════════════════════════════ -->

		<!-- A1: Fly "program state" from Y-axis to title position
		     The label rests at: left≈3.2%, top=50%, rotate=-90deg.
		     Title target: appears at top-left like a slide heading.
		     We move it right by ~38% of slide width (≈500px at 1280px) and up by ~44% of slide height (≈316px at 720px),
		     then un-rotate and scale up to ~3.5rem.
		     These px values are for the slide's natural coordinate space (Reveal default ~960×700).
		-->
		<Action
			do={async () => {
				titleLabel = 'state'
				await all(
					psLabel.to({ x: 460, y: 60, rotate: 0, fontSize: 52 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 0.15 }, { duration: 400 }),
				)
			}}
			undo={async () => {
				await all(
					psLabel.to({ x: 50, y: 250, rotate: -90, fontSize: 22 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 1 }, { duration: 400 }),
				)
				titleLabel = 'none'
				showAxisCode = false
				axisFade.reset()
				axisCodeHighlight = null
			}}
		/>

		<!-- A2: Show code, highlight state variables -->
		<Action
			do={async () => {
				showAxisCode = true
				await axisFade.to({ codeOpacity: 1 }, { duration: 400 })
				axisCodeHighlight = 'state-vars'
			}}
			undo={async () => {
				axisCodeHighlight = null
				await axisFade.to({ codeOpacity: 0 }, { duration: 300 })
				showAxisCode = false
			}}
		/>

		<!-- A2b: Distribute state variable names along the Y-axis -->
		<Action
			do={async () => {
				showStateVarLabels = true
				// Fade the code overlay out while spreading the labels
				await all(
					axisFade.to({ codeOpacity: 0 }, { duration: 300 }),
					...stateVarLabels.map((lbl, i) =>
						lbl.to(
							{ x: 140, y: stateVarTargetY[i], opacity: 1 },
							{ duration: 600, delay: i * 80 },
						)
					),
				)
				showAxisCode = false
			}}
			undo={async () => {
				showAxisCode = true
				await all(
					axisFade.to({ codeOpacity: 1 }, { duration: 300 }),
					...stateVarLabels.map(lbl =>
						lbl.to({ x: 460, y: 250, opacity: 0 }, { duration: 400 })
					),
				)
				showStateVarLabels = false
				axisCodeHighlight = 'state-vars'
			}}
		/>

		<!-- A3: Fade out var labels, fly "program state" back to axis -->
		<Action
			do={async () => {
				await all(
					...stateVarLabels.map(lbl => lbl.to({ opacity: 0 }, { duration: 300 })),
					axisFade.to({ axisOpacity: 1 }, { duration: 500 }),
				)
				await psLabel.to({ x: 50, y: 250, rotate: -90, fontSize: 22 }, { duration: 700 })
				titleLabel = 'none'
			}}
			undo={async () => {
				titleLabel = 'state'
				await all(
					psLabel.to({ x: 460, y: 60, rotate: 0, fontSize: 52 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 0.15 }, { duration: 400 }),
				)
				showStateVarLabels = true
				await all(
					...stateVarLabels.map((lbl, i) =>
						lbl.to({ x: 140, y: stateVarTargetY[i], opacity: 1 }, { duration: 400 })
					),
				)
			}}
		/>

		<!-- ════════════════════════════════════════════════════
		     Build-up: "time" axis label sequence
		     ════════════════════════════════════════════════════ -->

		<!-- A4: Fly "time" from X-axis bottom to title position -->
		<Action
			do={async () => {
				titleLabel = 'time'
				await all(
					tLabel.to({ x: 460, y: 60, fontSize: 52 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 0.15 }, { duration: 400 }),
				)
			}}
			undo={async () => {
				await all(
					tLabel.to({ x: 460, y: 500, fontSize: 22 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 1 }, { duration: 400 }),
				)
				titleLabel = 'none'
				showAxisCode = false
				showCostTerminal = false
				axisFade.reset()
				axisCodeHighlight = null
			}}
		/>

		<!-- A5: Show code (highlight cost) + cost-only terminal -->
		<Action
			do={async () => {
				axisCodeHighlight = null
				showAxisCode = true
				showCostTerminal = true
				await axisFade.to({ codeOpacity: 1, terminalOpacity: 1 }, { duration: 400 })
				axisCodeHighlight = 'cost'
			}}
			undo={async () => {
				axisCodeHighlight = null
				await axisFade.to({ codeOpacity: 0, terminalOpacity: 0 }, { duration: 300 })
				showAxisCode = false
				showCostTerminal = false
			}}
		/>

		<!-- A5b: Distribute cost values along the X-axis (rotated 90°) -->
		<Action
			do={async () => {
				showCostLabels = true
				// Fade out code + terminal while spreading cost values
				await all(
					axisFade.to({ codeOpacity: 0, terminalOpacity: 0 }, { duration: 300 }),
					...costLabels.map((lbl, i) =>
						lbl.to(
							{ x: costLabelTargetX[i], y: 430, rotate: -90, opacity: 1 },
							{ duration: 600, delay: i * 50 },
						)
					),
				)
				showAxisCode = false
				showCostTerminal = false
			}}
			undo={async () => {
				showAxisCode = true
				showCostTerminal = true
				await all(
					axisFade.to({ codeOpacity: 1, terminalOpacity: 1 }, { duration: 300 }),
					...costLabels.map(lbl =>
						lbl.to({ x: 460, y: 250, rotate: 0, opacity: 0 }, { duration: 400 })
					),
				)
				showCostLabels = false
				axisCodeHighlight = 'cost'
			}}
		/>

		<!-- A6: Fade out cost labels, fly "time" back to axis -->
		<Action
			do={async () => {
				await all(
					...costLabels.map(lbl => lbl.to({ opacity: 0 }, { duration: 300 })),
					axisFade.to({ axisOpacity: 1 }, { duration: 500 }),
				)
				await tLabel.to({ x: 460, y: 500, fontSize: 22 }, { duration: 700 })
				titleLabel = 'none'
			}}
			undo={async () => {
				titleLabel = 'time'
				await all(
					tLabel.to({ x: 460, y: 60, fontSize: 52 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 0.15 }, { duration: 400 }),
				)
				showCostLabels = true
				await all(
					...costLabels.map((lbl, i) =>
						lbl.to({ x: costLabelTargetX[i], y: 430, rotate: -90, opacity: 1 }, { duration: 400 })
					),
				)
			}}
		/>

		<!-- ════════════════════════════════════════════════════
		     Debugging techniques (original actions)
		     ════════════════════════════════════════════════════ -->
		<Action do={() => { stateTimeStep = 1 }} undo={() => { stateTimeStep = 0; bpX.reset() }} />
		<!-- Breakpoint debugger: show red dot + Variables pane, yellow on cost line -->
		<Action
			do={() => {
				showBreakpointDebugger = true
				bpDebuggerHighlightLine = COST_LINE_IDX
				bpDebuggerIteration = 0
			}}
			undo={() => {
				showBreakpointDebugger = false
				bpDebuggerHighlightLine = -1
				bpDebuggerIteration = 0
			}}
		/>
		<!-- Move bar + highlight: line 3 → 4 → 1 → 2 → 3, update Variables at end -->
		<Action
			do={async () => {
				const highlightPath = [COST_LINE_IDX, 3, 0, 1, COST_LINE_IDX]
				const barDuration = highlightPath.length * bpDebuggerLineDelay
				await all(
					bpX.to({ x: 420 }, { duration: barDuration }),
					(async () => {
						for (const i of highlightPath) {
							bpDebuggerHighlightLine = i
							await sleep(bpDebuggerLineDelay)
						}
						bpDebuggerIteration = 1
					})(),
				)
			}}
			undo={async () => {
				await bpX.to({ x: 200 })
				bpDebuggerHighlightLine = COST_LINE_IDX
				bpDebuggerIteration = 0
			}}
		/>
		<!-- Repeat: same highlight path, update Variables at end -->
		<Action
			do={async () => {
				const highlightPath = [COST_LINE_IDX, 3, 0, 1, COST_LINE_IDX]
				const barDuration = highlightPath.length * bpDebuggerLineDelay
				await all(
					bpX.to({ x: 640 }, { duration: barDuration }),
					(async () => {
						for (const i of highlightPath) {
							bpDebuggerHighlightLine = i
							await sleep(bpDebuggerLineDelay)
						}
						bpDebuggerIteration = 2
					})(),
				)
			}}
			undo={async () => {
				await bpX.to({ x: 420 })
				bpDebuggerHighlightLine = COST_LINE_IDX
				bpDebuggerIteration = 1
			}}
		/>
		<!-- Dismiss breakpoint debugger before print debugging -->
		<Action
			do={() => {
				showBreakpointDebugger = false
				bpDebuggerHighlightLine = -1
			}}
			undo={() => {
				showBreakpointDebugger = true
				bpDebuggerHighlightLine = COST_LINE_IDX
				bpDebuggerIteration = 2
			}}
		/>
		<Action do={() => { stateTimeStep = 2 }} undo={() => { stateTimeStep = 1 }} />
		<Action do={() => { stateTimeStep = 3 }} undo={() => { stateTimeStep = 2 }} />
		<Action do={() => { stateTimeStep = 4 }} undo={() => { stateTimeStep = 3 }} />
		<Action do={() => { stateTimeStep = 5 }} undo={() => { stateTimeStep = 4 }} />
		<Notes>
			This is the core conceptual diagram of the talk. Return to it when discussing each tool.
			Start by showing the empty state×time space. Then pull out "program state" to explain
			what the Y axis means (all the variables in scope at a given moment). Then pull out "time"
			to explain what the X axis means (each iteration of the loop is a moment in time).
			Then walk through each debugging technique as a different sampling pattern.
		</Notes>
	</Slide>

	<!-- ─── Section 2: Evidence — what programmers actually struggle with ─── -->

	<!-- Slide 5: Formative study overview -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Formative study</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>12 professional software engineers, 3–11 years experience</li>
				<li>30-minute semi-structured interviews about debugging practices</li>
				<li>Thematic analysis through a data-oriented debugging lens</li>
			</ul>
		</div>
		<Notes>
			Recruited from personal networks and internal company postings. 4 companies, 8 from one
			company. Mix of print-preferred (7), breakpoint-preferred (2), and both (3).
		</Notes>
	</Slide>

	<!-- Slide 6: The coupling problem -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">The coupling problem</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>
					Core finding: current tools tightly <strong>couple data collection and data
					analysis</strong>
				</li>
				<li>Breakpoints: you collect and analyze simultaneously</li>
				<li>
					Print statements: plan collection upfront, then analyze — but missing data means
					rerunning
				</li>
				<li class="italic">
					"what all could I need, and then add everything in the logs...Because if I miss one
					thing, I have to wait 2 hours." — P5
				</li>
			</ul>
		</div>
		<Notes>
			P5: "what all could I need, and then add everything in the logs, and then analyze it
			later...Because if I miss one thing, I have to wait 2 hours." This is the central tension
			the whole talk builds on. The coupling is what makes both tools frustrating in different
			ways.
		</Notes>
	</Slide>

	<!-- Slide 7: The information management tension -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">The information management tension</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Want to collect <em>more</em> data (to avoid regret of missing something)</li>
				<li>But fear being <em>overwhelmed</em> by too much output</li>
				<li>Lack tools to manage data once collected → manage it by collecting less</li>
				<li class="italic">"burning up log files with unnecessary information" — P3</li>
				<li class="italic">Using a notepad to keep track of log output — P7</li>
				<li class="italic">Breakpoints on hot code paths "drive me crazy" — P10</li>
			</ul>
		</div>
		<Notes>
			This is a direct consequence of coupling. If you had tools to filter/sort/query after the
			fact, you wouldn't need to be so careful about what you collect. P4 had a strategy of
			printing both nested fields (for scanning) AND full objects (to avoid regret) — a
			workaround for the lack of post-hoc analysis tools. Multiple participants also discussed
			adding string tags to logs for filtering — a manual approximation of structured querying.
		</Notes>
	</Slide>

	<!-- Slide 8: Production debugging already solved this -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Production debugging already solved this</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>
					Industry shift: text logs → structured logging → query tools (Splunk, Datadog, ELK
					stack)
				</li>
				<li>Production debugging treats logs as a <strong>queryable dataset</strong></li>
				<li>Local debugging is decades behind: still text on a terminal</li>
			</ul>
		</div>
		<Notes>
			This is a one-slide point but it's important. It shows the transition the talk is arguing
			for has already happened in a related domain. The audience should be asking "why hasn't
			this happened for local debugging too?"
		</Notes>
	</Slide>

	<!-- ─── Section 3: Data-oriented debugging as a framework ─── -->

	<!-- Slide 9: The core proposal -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">
				The core proposal: decouple collection from analysis
			</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Treat execution data as a <strong>structured dataset</strong></li>
				<li>Decouple <em>when/what</em> you collect from <em>how</em> you analyze it</li>
				<li>Key shift: move programmer intentionality from collection to analysis</li>
			</ul>
		</div>
		<Notes>
			This is the thesis slide. Keep it crisp. The "intentionality" framing: with current tools,
			the intentional act is deciding what to log or where to set a breakpoint. With
			data-oriented debugging, the intentional act is deciding how to query, filter, sort, and
			visualize the data you already have.
		</Notes>
	</Slide>

	<!-- Slide 10: Design principles -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Design principles</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li><strong>Make collection easy:</strong> minimize friction of capturing execution data</li>
				<li>
					<strong>Manage abundant data:</strong> filter, transform, and query — don't force
					programmers to manage volume by collecting less
				</li>
				<li>
					<strong>Support exploration:</strong> help characterize execution before narrowing to
					specific hypotheses
				</li>
				<li>
					<strong>Support model confirmation:</strong> present data in ways that make it easy to
					compare against mental models
				</li>
				<li>
					<strong>Connect back to code:</strong> link analysis results to the code that produced
					them
				</li>
			</ul>
		</div>
		<Notes>
			These are derived from the formative study. Don't dwell on each one — they'll be
			illustrated in the demo. The key message is that these are design principles for a class of
			tools, not just for autopsy specifically.
		</Notes>
	</Slide>

	<!-- ─── Section 4: autopsy demo / walkthrough ─── -->

	<!-- Slide 11: autopsy overview -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">
				<span
					class="bg-[#0000FF] px-2 py-1 text-white"
					style="font-family: var(--r-code-font)"
				>autopsy</span> overview
			</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Three components: Python tracing library, web viewer, VS Code extension</li>
				<li>
					<code>import autopsy</code> / <code>autopsy.log("label", var1, var2)</code>
				</li>
				<li>Captures passed arguments + full stack trace (all frames, all variables)</li>
			</ul>
		</div>
		<Notes>
			Emphasize: the log call is intentional (you choose where to probe), but what gets captured
			goes far beyond what you explicitly asked for. This is the first step of decoupling —
			collection gives you more than you requested.
		</Notes>
	</Slide>

	<!-- Slide: Live autopsy interface (order_pipeline example) -->
	<Slide class="h-full">
		<div class="flex h-full flex-col gap-2 px-4 pt-4 pb-2">
			<h2 class="text-3xl font-bold text-black text-left">
				<span
					class="bg-[#0000FF] px-2 py-0.5 text-white"
					style="font-family: var(--r-code-font)"
				>autopsy</span> — Live Demo
			</h2>
			<!-- <iframe
				src="{iframBase}/order_pipeline_report.html"
				title="Autopsy Report — Order Pipeline"
				class="flex-1 w-full rounded-lg border border-gray-200 shadow-sm"
				style="min-height: 0"
			></iframe> -->
		</div>
		<Notes>
			This is a live, interactive autopsy report for the order_pipeline example.
			You can click into the iframe and interact with the full autopsy interface —
			streams view, history view, sorting, filtering, computed columns, etc.
			Use this to demo the workflow live during the talk.
		</Notes>
	</Slide>

	<!-- Slide 13: Demo — streams view + computed columns -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Demo: streams view + computed columns</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Logs from one call site as a <strong>structured table</strong></li>
				<li>Add a computed column from a stack variable that wasn't explicitly logged</li>
				<li>Key point: "retroactive print debugging" — no rerun needed</li>
			</ul>
			<p class="text-2xl text-black italic">[Demo: streams view, drag-and-drop computed columns]</p>
		</div>
		<Notes>
			This is the single most important feature to demonstrate. It directly shows decoupling: you
			collected data at one point, and now you're expanding what you can see from that data
			without going back to collection. Emphasize: in print debugging, realizing you need another
			variable means editing code and rerunning. Here, it's a drag-and-drop.
		</Notes>
	</Slide>

	<!-- Slide 14: Demo — sorting, filtering, cross-time comparison -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">
				Demo: sorting, filtering, cross-time comparison
			</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Sort by a column to group related entries</li>
				<li>Filter to a subset of interest</li>
				<li>Patterns across many executions become visible in the table</li>
			</ul>
			<p class="text-2xl text-black italic">[Demo: sorting and filtering]</p>
		</div>
		<Notes>
			This is the "data tools" part. Sorting and filtering are simple but they enable seeing
			patterns that are invisible in sequential log output. Point out that time is always a
			secondary sort dimension, so within groups you still see temporal ordering.
		</Notes>
	</Slide>

	<!-- Slide 15: Demo — navigation between views -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Demo: navigation between views</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Click a row in streams → jump to its location in history (sequential context)</li>
				<li>Click a row in history → jump to its stream (cross-time context)</li>
				<li>Inspect the full call stack from any row</li>
			</ul>
			<p class="text-2xl text-black italic">[Demo: cross-view navigation]</p>
		</div>
		<Notes>
			This demonstrates "connect back to code" and the ability to shift between analytical lenses
			on the same data. The navigation between streams and history is how autopsy supports both
			"what happened at this code location across time?" and "what happened around this moment in
			execution?"
		</Notes>
	</Slide>

	<!-- Slide 16: Demo — identifying the bug -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Demo: identifying the bug</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Walk through how data tools led to identifying the root cause</li>
				<li>Comparing stack traces across rows reveals the state mutation</li>
			</ul>
			<p class="text-2xl text-black italic">[Demo: bug identification moment]</p>
		</div>
		<Notes>
			Land the demo by connecting back to the model-checking framing. The programmer had a mental
			model, the data tools made it easy to find where reality diverged, and the full stack
			traces let them trace back to the code.
		</Notes>
	</Slide>

	<!-- ─── Section 5: Future vision and closing ─── -->

	<!-- Slide 17: Where this goes -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Where this goes</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Current limitation: programmer manually places log statements</li>
				<li>
					Future: full execution capture → all state at all time → intentionality moves entirely
					to analysis
				</li>
				<li>
					Agentic coding: LLM assistants currently debug via print statements — what if the agent
					could query a full execution dataset instead?
				</li>
				<li>
					Ongoing: controlled lab study comparing static logs vs. autopsy's interactive data
					manipulation
				</li>
			</ul>
		</div>
		<Notes>
			Don't oversell the agentic angle — it's speculative. But it's a good hook for this
			audience and it shows the framework has implications beyond the current tool. The lab study
			is in progress; mention it to signal that empirical validation is coming but isn't the
			focus of this talk.
		</Notes>
	</Slide>

	<!-- Slide 18: Closing -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-6xl font-bold text-black">Data-oriented debugging</h2>
			<ul class="flex flex-col gap-3 pl-6 text-2xl text-black list-disc">
				<li>Debugging = checking mental models against execution data</li>
				<li>Current tools couple collection and analysis</li>
				<li>Data-oriented debugging decouples them</li>
				<li>
					<span
						class="bg-[#0000FF] px-2 py-1 text-white"
						style="font-family: var(--r-code-font)"
					>autopsy</span> demonstrates this
				</li>
			</ul>
			<p class="text-xl text-black italic mt-4">[Link to tool / paper / contact info]</p>
		</div>
	</Slide>
</Presentation>
