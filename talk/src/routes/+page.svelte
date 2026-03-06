<script lang="ts">
	import { Presentation, Slide, Notes, Action, Code } from '@animotion/core'
	import { tween, all } from '@animotion/motion'
	import { AlertTriangle, CircleUserRound, Info } from '@lucide/svelte'
	import { trace } from '$lib/tracing'
	import CodeOverlay from '$lib/components/CodeOverlay.svelte'
	import VariablesPane from '$lib/components/VariablesPane.svelte'

	// ── Configurable parameters ──
	const SEED = 3
	const ITEM_COUNT = 16
	const SLOW_LINE_DELAY = 200      // ms per line for the first (slow) iteration (~1s total)
	const FAST_LINE_DELAY = 50       // ms per line for remaining (fast) iterations

	// ── Generate all traced data ──
	const tr = trace(SEED, ITEM_COUNT)

	// ── Derived code strings (for Animotion <Code> component on slide 2) ──
	const codeInitial = tr.codeVariants.base.lines.join('\n')
	const codeWithPrint1 = tr.codeVariants.printV1.lines.join('\n')
	const codeWithPrints = tr.codeVariants.printV2.lines.join('\n')
	// Expanded variant: same as V2 but with qty added to the price print
	const codeWithPrintExpanded = [
		'for item in cart:',
		'    if item.qty >= 9:',
		'        item.price *= 0.9',
		'        print("Price", item.price, item.qty)',
		'    ...',
		'    if item.price < 4.00:',
		'        item.free_shipping = True',
		'        print("Free", item.free_shipping)',
	].join('\n')

	let code: ReturnType<typeof Code>
	let slide2Code = $state(codeInitial)
	let showTerminal = $state(false)
	let scrollTerminal = $state(false)
	let highlightBug = $state(false)
	let showExpandedTerminal = $state(false)
	let scrollExpanded = $state(false)
	let slide2Todo = $state<0 | 1 | 2>(0)

	// Terminal output from traced execution
	const terminalLines = tr.terminalLines
	const terminalLinesExpanded = tr.terminalLinesExpanded

	let stateTimeStep = $state(0)

	// ── Breakpoint debugger overlay ──
	let showBreakpointDebugger = $state(false)
	let bpDebuggerHighlightLine = $state(-1)
	let bpDebuggerIteration = $state(0)
	const COST_LINE_IDX = 2

	// ── Execution paths from trace (all iterations) ──
	const printExecPathV1 = tr.traces.printV1.map((t) => t.path)
	const printExecPathV2 = tr.traces.printV2.map((t) => t.path)
	const FIRST_PRINT_LINE = tr.codeVariants.printV1.printLines[0]
	const SECOND_PRINT_LINE = tr.codeVariants.printV2.printLines[1]

	// Breakpoint "continue" paths: from the breakpoint line, through rest of loop, back to breakpoint.
	// This simulates clicking "Continue" in a debugger paused at COST_LINE_IDX.
	const baseLineCount = tr.codeVariants.base.lines.length
	function bpContinuePath(): number[] {
		// From breakpoint, step through remaining lines, loop back to top, stop at breakpoint
		const path: number[] = []
		for (let i = COST_LINE_IDX; i < baseLineCount; i++) path.push(i)
		for (let i = 0; i <= COST_LINE_IDX; i++) path.push(i)
		return path
	}
	const bpHighlightPath = bpContinuePath()

	function sleep(ms: number) {
		return new Promise((resolve) => setTimeout(resolve, ms))
	}

	// ── State × time build-up animation state ──
	let showAxisCode = $state(false)
	let axisCodeHighlight = $state<'state-vars' | 'cost' | null>(null)
	let showCostTerminal = $state(false)

	// SVG-coordinate tweens for the axis labels (viewBox 0 0 900 520)
	const psLabel = tween({
		x: 50, y: 250, rotate: -90, fontSize: 36,
	}, { duration: 600 })

	const tLabel = tween({
		x: 460, y: 500, rotate: 0, fontSize: 36,
	}, { duration: 600 })

	let titleLabel = $state<'none' | 'state' | 'time'>('none')

	const axisFade = tween({ codeOpacity: 0, terminalOpacity: 0, axisOpacity: 1 }, { duration: 400 })

	// ── State variable labels — distribute along the Y-axis ──
	const stateVarNames = tr.stateVarNames
	const stateVarTargetY = stateVarNames.map((_, i) =>
		110 + (i / (stateVarNames.length - 1)) * 320
	)
	const stateVarLabels = stateVarNames.map(() =>
		tween({ x: 460, y: 250, opacity: 0, fontSize: 36 }, { duration: 500 })
	)
	let showStateVarLabels = $state(false)

	// ── Cost value labels — distribute along the X-axis ──
	const costValues = tr.costValues
	const costLabelTargetX = costValues.map((_, i) =>
		110 + (i / Math.max(costValues.length - 1, 1)) * 700
	)
	const costLabels = costValues.map(() =>
		tween({ x: 460, y: 250, rotate: 0, opacity: 0, fontSize: 36 }, { duration: 500 })
	)
	let showCostLabels = $state(false)

	// Breakpoint: animated x position
	let bpX = tween({ x: tr.breakpointXPositions[0] ?? 200 })

	// In dev, serve iframed HTML via /__raw/ to bypass Vite's HMR injection
	const iframBase = import.meta.env.DEV ? '/__raw' : ''

	// ── Print debugging state ──
	let showPrintDebugger = $state(false)
	let printDebuggerHighlightLine = $state(-1)
	let printCodeVersion = $state(0) // 0: no print, 1: first only, 2: both
	let instantHighlight = $state(false) // disable transition during fast animation

	// Dot positions from traced data
	const printDotsRow1 = tr.printDots.row1
	const printDotsRow2 = tr.printDots.row2
	const printDotsRow1Indices = tr.printDots.row1Indices
	const printDotsRow2Indices = tr.printDots.row2Indices

	let printDotsVisibleRow1 = $state(0)
	let printDotsVisibleRow2 = $state(0)

	// Autopsy slices from traced data
	const autopsySlices = tr.autopsySliceXPositions
	let autopsyVisibleCount = $state(0)
</script>

<Presentation options={{ history: true, transition: 'slide', controls: false, progress: true, slideNumber: true }}>
	<!-- ─── Slide 1: Title ─── -->
	<Slide class="h-full">
		<div class="grid h-full grid-cols-[3fr_1fr] items-center gap-8 px-16 py-12">
			<div class="flex flex-col gap-8">
				<h1 class="text-left text-[6rem] font-bold leading-tight text-black">
					Data-oriented Debugging with
					<span
						class="mt-2 inline-block bg-[#1E40AF] px-3 py-1 text-white"
						style="font-family: var(--r-code-font)"
					>autopsy</span>
				</h1>
				<div class="flex flex-col gap-2">
					<p class="text-left text-5xl text-black">
						<span class="font-bold text-[#1E40AF]">Jeffrey Tao</span>, Xiaorui Liu, Ryan Marcus,
						Andrew Head
					</p>
					<p class="text-left text-3xl text-black">PLATEAU 2026</p>
				</div>
			</div>
			<div class="flex flex-col items-center justify-center gap-8">
				<img src="/headshot.jpg" alt="Jeffrey Tao" class="h-44 w-44 rounded-full object-cover" />
				<img src="/penn-hci.svg" alt="Penn HCI Lab" class="w-40" />
			</div>
		</div>
	</Slide>

	<!-- Slide: About me -->
	<Slide class="h-full">
		<div class="flex h-full w-full flex-col justify-center gap-8 px-20 py-16">
			<h2 class="text-left text-8xl font-bold text-black">Why I Care About Debugging</h2>
			<div class="flex w-full items-center justify-between gap-16">
				<ul class="flex flex-col gap-4 text-left text-5xl text-black list-disc pl-6">
					<li>Previously: Senior SWE @ Microsoft & MongoDB</li>
					<li>Auth, Notifications, Client/Server Sync, Dev Tools</li>
					<li>Highly stateful code, complex logic</li>
					<li>Now: DB & HCI @ Penn: tools for programmers</li>
					<li>Shameless <code class="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-4xl">print()</code> debugger</li>
				</ul>
				<img src="/headshot.jpg" alt="Jeffrey Tao" class="h-72 w-72 shrink-0 rounded-full object-cover" />
			</div>
		</div>
		<Notes>
			First, a bit of background about me and why I care about debugging.
			I'm currently a PhD student at Penn, researching tools for programmers.
			But I used to be a senior software engineer in the industry, where I worked on auth, notifications, client/server sync.
			All things that are highly stateful, highly complex, prone to bugs, and really annoying to debug.
			And in all that time I was one of those programmers who always used print statements to debug.
		</Notes>
	</Slide>

	<!-- ─── Section 1: Debugging is about checking mental models against execution data ─── -->

	<!-- Slide 2: Code example — debugging motivation -->
	<Slide class="h-full" in={() => { showTerminal = false; scrollTerminal = false; highlightBug = false; showExpandedTerminal = false; scrollExpanded = false; slide2Todo = 0; slide2Code = codeInitial; if (code) code.update`${codeInitial}` }}>
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16">
			<h2 class="text-left text-8xl font-bold text-black">How do you debug this?</h2>
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
						class="text-5xl"
					/>
				</div>
				<div
					class="rounded-xl border border-gray-800 bg-gray-900 p-6 shadow-sm font-mono text-3xl leading-relaxed text-green-400 transition-all duration-500 text-left"
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
		{#if slide2Todo >= 1}
			<div class="absolute inset-0 flex items-center justify-center z-20" style="background: rgba(255,255,255,0.92)">
				<div class="rounded-2xl border-4 border-dashed border-amber-400 bg-amber-50 px-12 py-10 shadow-lg max-w-2xl">
					<p class="text-7xl font-bold text-amber-600 mb-4">TODO: Print Debugging</p>
					<ul class="text-5xl text-amber-800 list-disc pl-6 flex flex-col gap-2">
						<li>Animate adding print statements to the code</li>
						<li>Show terminal panel with extremely long scrolling output</li>
						<li>Wall-of-text feeling — Price/Qty values streaming by</li>
						<li>Point: output is overwhelming and hard to correlate</li>
					</ul>
				</div>
			</div>
		{/if}
		{#if slide2Todo >= 2}
			<div class="absolute inset-0 flex items-center justify-center z-30" style="background: rgba(255,255,255,0.92)">
				<div class="rounded-2xl border-4 border-dashed border-blue-400 bg-blue-50 px-12 py-10 shadow-lg max-w-2xl">
					<p class="text-7xl font-bold text-blue-600 mb-4">TODO: Breakpoint Stepping</p>
					<ul class="text-5xl text-blue-800 list-disc pl-6 flex flex-col gap-2">
						<li>Show breakpoint debugger overlay on code</li>
						<li>Yellow highlight line steps through each line (like state/time chart)</li>
						<li>Variables pane shows item.price and item.free_shipping drifting by</li>
						<li>Point: see everything at one moment, but lose the cross-time view</li>
					</ul>
				</div>
			</div>
		{/if}
		<Action do={() => { slide2Todo = 1 }} undo={() => { slide2Todo = 0 }} />
		<Action do={() => { slide2Todo = 2 }} undo={() => { slide2Todo = 1 }} />
		<!-- REWORK: print/terminal actions commented out — reworking this narrative -->
		<!--
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
		<Action
			do={async () => {
				highlightBug = false
				await code.update`${codeWithPrintExpanded}`
				slide2Code = codeWithPrintExpanded
				await code.selectLines`4`
			}}
			undo={async () => {
				highlightBug = true
				await code.update`${codeWithPrints}`
				slide2Code = codeWithPrints
				await code.selectLines``
			}}
		/>
		<Action
			do={() => { showExpandedTerminal = true; scrollExpanded = false }}
			undo={() => { showExpandedTerminal = false; scrollExpanded = false }}
		/>
		<Action
			do={() => { scrollExpanded = true }}
			undo={() => { scrollExpanded = false }}
		/>
		-->
		<Notes>
			REWORK: Two animations needed here:
			1) Print debugging: add prints, show overwhelming terminal output scrolling by
			2) Breakpoint stepping: yellow highlight line walks through code, price/free_shipping values drift by in variables pane
		</Notes>
	</Slide>


	<!-- Slide: The state × time space -->
	<!--
		Axis labels are SVG <text> elements tweened in SVG-coordinate space (viewBox 0 0 900 520).
		Resting positions: "program state" at (50,250) rotate(-90); "time" at (460,500).
		Title position: both fly to (100,60) rotate(0) at fontSize=104.
	-->
	<Slide class="h-full" in={() => {
		stateTimeStep = 0; bpX.reset()
		titleLabel = 'none'
		showAxisCode = false; axisCodeHighlight = null; showCostTerminal = false
		showStateVarLabels = false; showCostLabels = false
		showBreakpointDebugger = false; bpDebuggerHighlightLine = -1; bpDebuggerIteration = 0
		showPrintDebugger = false; printDebuggerHighlightLine = -1; printCodeVersion = 0
		printDotsVisibleRow1 = 0; printDotsVisibleRow2 = 0; autopsyVisibleCount = 0
		psLabel.reset(); tLabel.reset(); axisFade.reset()
		stateVarLabels.forEach(l => l.reset())
		costLabels.forEach(l => l.reset())
	}}>
		<div class="relative flex h-full items-center justify-center overflow-hidden">

			<!-- ── Main SVG (axes, data marks, and animated axis labels) ── -->
			<svg viewBox="0 0 900 520" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="white" />

				<!-- Step 1: Breakpoint — animated vertical slice (solid bar) -->
				{#if stateTimeStep === 1}
					<rect x={bpX.x - 12} y="40" width="24" height="420" fill="#1E40AF"
						style="opacity: 0; animation: appear 0.3s ease-out 0ms forwards" />
				{/if}

				<!-- Step 2–4: Print — single dot (conceptual: "you have one data point") -->
				{#if stateTimeStep >= 2 && stateTimeStep < 5 && printDotsRow1.length > 0}
					<circle cx={printDotsRow1[0][0]} cy={printDotsRow1[0][1]} r="6" fill="#991B1B"
						style="opacity: 0; animation: appear 0.15s ease-out 0ms forwards" />
				{/if}

				<!-- Step 5–7: Print — row 1 dots (appear during V1 yellow bar animation) -->
				{#if stateTimeStep >= 5 && stateTimeStep <= 7}
					{#each printDotsRow1.slice(0, printDotsVisibleRow1) as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsRow1[i-1][0]} y1={printDotsRow1[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B"
							style="opacity: 0; animation: appear 0.15s ease-out 0ms forwards" />
					{/each}
				{/if}

				<!-- Step 7: Print — row 2 dots (appear during V2 yellow bar animation) -->
				{#if stateTimeStep === 7}
					{#each printDotsRow2.slice(0, printDotsVisibleRow2) as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsRow2[i-1][0]} y1={printDotsRow2[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B"
							style="opacity: 0; animation: appear 0.15s ease-out 0ms forwards" />
					{/each}
				{/if}

				<!-- Step 8+: Autopsy bars + print dots reappearing per-iteration -->
				{#if stateTimeStep >= 8}
					{#each autopsySlices.slice(0, autopsyVisibleCount) as x}
						<rect x={x - 11} y="40" width="22" height="420" fill="#1E40AF" />
					{/each}
					<!-- Row 1 dots (red dots on top of blue bars) -->
					{@const r1Count = printDotsRow1Indices.filter((idx: number) => idx < autopsyVisibleCount).length}
					{#each printDotsRow1.slice(0, r1Count) as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsRow1[i-1][0]} y1={printDotsRow1[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B" />
					{/each}
					<!-- Row 2 dots (red dots on top of blue bars) -->
					{@const r2Count = printDotsRow2Indices.filter((idx: number) => idx < autopsyVisibleCount).length}
					{#each printDotsRow2.slice(0, r2Count) as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsRow2[i-1][0]} y1={printDotsRow2[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B" />
					{/each}
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
						<pre class="text-5xl leading-relaxed font-mono text-gray-800"><code
><span class="text-gray-500">for </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">item</span><span class="text-gray-500"> in </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">cart</span><span class="text-gray-500">:</span>
<span class="text-gray-500">    if </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">item.qty</span><span class="text-gray-500"> >= 9:</span>
<span class="text-gray-500">        </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' || axisCodeHighlight === 'cost' ? 'bg-yellow-200' : 'bg-transparent'}">item.price</span><span class="text-gray-500"> *= 0.9</span>
<span class="text-gray-500">    ...</span>
<span class="text-gray-500">    if </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' || axisCodeHighlight === 'cost' ? 'bg-yellow-200' : 'bg-transparent'}">item.price</span><span class="text-gray-500"> &lt; 4.00:</span>
<span class="text-gray-500">        </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">item.free_shipping</span><span class="text-gray-500"> = True</span></code></pre>
					</div>
					<!-- Cost terminal: 1/3 width, fixed height, only present when showCostTerminal -->
					{#if showCostTerminal}
						<div
							class="rounded-xl border border-gray-800 bg-gray-900 px-5 py-4 font-mono text-2xl leading-relaxed text-green-400 overflow-y-auto text-left"
							style="flex: 1 1 0; height: 14rem; opacity: {axisFade.terminalOpacity}"
						>
							{#each terminalLines as [label, value]}
								<p>{label} <span class="text-white">{value}</span></p>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			<!-- Step label (top-right, shown once debugging techniques are introduced) -->
			{#if stateTimeStep >= 1}
				<div class="absolute right-[8%] top-[10%] rounded-md bg-white/85 px-4 py-2 text-right">
					{#if stateTimeStep === 1}
						<p class="text-7xl font-bold text-[#1E40AF]">breakpoint debugger</p>
						<p class="text-5xl text-gray-500">all state · one moment</p>
					{/if}
					{#if stateTimeStep >= 2 && stateTimeStep <= 7}
						<p class="text-7xl font-bold text-[#1E40AF]">print debugging</p>
						<p class="text-5xl text-gray-500">some state · many moments</p>
					{/if}
					{#if stateTimeStep === 8 || stateTimeStep === 9}
						<p class="text-7xl font-bold text-[#1E40AF]" style="font-family: var(--r-code-font)">autopsy</p>
						<p class="text-5xl text-gray-500">all state · many moments</p>
					{/if}
				</div>
			{/if}

			<!-- ── Print debugger overlay (code + yellow bar) ── -->
			{#if showPrintDebugger}
				<div class="absolute z-10 flex justify-center" style="pointer-events: none; width: 75%; left: 12.5%;">
					<CodeOverlay
						lines={printCodeVersion === 0 ? tr.codeVariants.base.lines : printCodeVersion === 1 ? tr.codeVariants.printV1.lines : tr.codeVariants.printV2.lines}
						highlightLine={printDebuggerHighlightLine}
						instant={instantHighlight}
					/>
				</div>
			{/if}

			<!-- ── Breakpoint debugger overlay (code + Variables pane) ── -->
			{#if showBreakpointDebugger}
				<div class="absolute z-10 flex items-stretch justify-center gap-4" style="pointer-events: none; width: 75%; left: 12.5%;">
					<CodeOverlay
						lines={tr.codeVariants.base.lines}
						highlightLine={bpDebuggerHighlightLine}
						markers={[{ line: COST_LINE_IDX, type: 'breakpoint' }]}
						instant={instantHighlight}
						class="flex-1"
						style="flex: 1 1 50%"
					/>
					<VariablesPane
						variables={tr.breakpointSnapshots[bpDebuggerIteration]}
						class="flex-1"
						style="flex: 1 1 50%"
					/>
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
					psLabel.to({ x: 460, y: 60, rotate: 0, fontSize: 72 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 0.15 }, { duration: 400 }),
				)
			}}
			undo={async () => {
				await all(
					psLabel.to({ x: 50, y: 250, rotate: -90, fontSize: 36 }, { duration: 700 }),
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
				await psLabel.to({ x: 50, y: 250, rotate: -90, fontSize: 36 }, { duration: 700 })
				titleLabel = 'none'
			}}
			undo={async () => {
				titleLabel = 'state'
				await all(
					psLabel.to({ x: 460, y: 60, rotate: 0, fontSize: 72 }, { duration: 700 }),
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
					tLabel.to({ x: 460, y: 60, fontSize: 72 }, { duration: 700 }),
					axisFade.to({ axisOpacity: 0.15 }, { duration: 400 }),
				)
			}}
			undo={async () => {
				await all(
					tLabel.to({ x: 460, y: 500, fontSize: 36 }, { duration: 700 }),
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
				await tLabel.to({ x: 460, y: 500, fontSize: 36 }, { duration: 700 })
				titleLabel = 'none'
			}}
			undo={async () => {
				titleLabel = 'time'
				await all(
					tLabel.to({ x: 460, y: 60, fontSize: 72 }, { duration: 700 }),
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
		<!-- Breakpoint: one slow "Continue" — step from breakpoint through loop, back to breakpoint -->
		<Action
			do={async () => {
				const barDuration = bpHighlightPath.length * SLOW_LINE_DELAY
				await all(
					bpX.to({ x: tr.breakpointXPositions[1] ?? 420 }, { duration: barDuration }),
					(async () => {
						for (const line of bpHighlightPath) {
							bpDebuggerHighlightLine = line
							await sleep(SLOW_LINE_DELAY)
						}
						bpDebuggerIteration = 1
					})(),
				)
			}}
			undo={async () => {
				await bpX.to({ x: tr.breakpointXPositions[0] ?? 200 })
				bpDebuggerHighlightLine = COST_LINE_IDX
				bpDebuggerIteration = 0
			}}
		/>
		<!-- Breakpoint: fast-forward remaining iterations (cap at 8 to keep animation short) -->
		<Action
			do={async () => {
				instantHighlight = true
				const maxBpIter = Math.min(tr.breakpointXPositions.length, 8)
				for (let iter = 2; iter < maxBpIter; iter++) {
					const barDuration = bpHighlightPath.length * FAST_LINE_DELAY
					await all(
						bpX.to({ x: tr.breakpointXPositions[iter] }, { duration: barDuration }),
						(async () => {
							for (const line of bpHighlightPath) {
								bpDebuggerHighlightLine = line
								await sleep(FAST_LINE_DELAY)
							}
							bpDebuggerIteration = iter
						})(),
					)
				}
				instantHighlight = false
			}}
			undo={async () => {
				instantHighlight = false
				await bpX.to({ x: tr.breakpointXPositions[1] ?? 420 })
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
				bpDebuggerIteration = Math.min(tr.breakpointXPositions.length, 8) - 1
			}}
		/>
		<Action do={() => { stateTimeStep = 2 }} undo={() => { stateTimeStep = 1 }} />
		<!-- Print: show code -->
		<Action
			do={() => {
				showPrintDebugger = true
				printCodeVersion = 0
				printDebuggerHighlightLine = -1
				stateTimeStep = 3
			}}
			undo={() => {
				showPrintDebugger = false
				printCodeVersion = 0
				printDebuggerHighlightLine = -1
				stateTimeStep = 2
			}}
		/>
		<!-- Print: add print to first condition -->
		<Action
			do={() => { printCodeVersion = 1; stateTimeStep = 4 }}
			undo={() => { printCodeVersion = 0; stateTimeStep = 3 }}
		/>
		<!-- Print V1: one slow iteration -->
		<Action
			do={async () => {
				stateTimeStep = 5
				printDotsVisibleRow1 = 0
				for (const line of printExecPathV1[0]) {
					printDebuggerHighlightLine = line
					if (line === FIRST_PRINT_LINE) {
						printDotsVisibleRow1 += 1
					}
					await sleep(SLOW_LINE_DELAY)
				}
			}}
			undo={() => {
				stateTimeStep = 4
				printDotsVisibleRow1 = 0
				printDebuggerHighlightLine = -1
			}}
		/>
		<!-- Print V1: fast-forward remaining iterations -->
		<Action
			do={async () => {
				instantHighlight = true
				for (let iter = 1; iter < printExecPathV1.length; iter++) {
					for (const line of printExecPathV1[iter]) {
						printDebuggerHighlightLine = line
						if (line === FIRST_PRINT_LINE) {
							printDotsVisibleRow1 += 1
						}
						await sleep(FAST_LINE_DELAY)
					}
				}
				printDebuggerHighlightLine = -1
				instantHighlight = false
			}}
			undo={() => {
				instantHighlight = false
				printDotsVisibleRow1 = printExecPathV1[0].includes(FIRST_PRINT_LINE) ? 1 : 0
				printDebuggerHighlightLine = -1
			}}
		/>
		<!-- Print: add print to second condition -->
		<Action
			do={() => { printCodeVersion = 2; stateTimeStep = 6 }}
			undo={() => { printCodeVersion = 1; stateTimeStep = 5 }}
		/>
		<!-- Print V2: one slow iteration -->
		<Action
			do={async () => {
				stateTimeStep = 7
				printDotsVisibleRow2 = 0
				for (const line of printExecPathV2[0]) {
					printDebuggerHighlightLine = line
					if (line === SECOND_PRINT_LINE) {
						printDotsVisibleRow2 += 1
					}
					await sleep(SLOW_LINE_DELAY)
				}
			}}
			undo={() => {
				stateTimeStep = 6
				printDotsVisibleRow2 = 0
				printDebuggerHighlightLine = -1
			}}
		/>
		<!-- Print V2: fast-forward remaining iterations -->
		<Action
			do={async () => {
				instantHighlight = true
				for (let iter = 1; iter < printExecPathV2.length; iter++) {
					for (const line of printExecPathV2[iter]) {
						printDebuggerHighlightLine = line
						if (line === SECOND_PRINT_LINE) {
							printDotsVisibleRow2 += 1
						}
						await sleep(FAST_LINE_DELAY)
					}
				}
				printDebuggerHighlightLine = -1
				instantHighlight = false
			}}
			undo={() => {
				instantHighlight = false
				printDotsVisibleRow2 = printExecPathV2[0].includes(SECOND_PRINT_LINE) ? 1 : 0
				printDebuggerHighlightLine = -1
			}}
		/>
		<!-- Dismiss print debugger before autopsy -->
		<Action
			do={() => {
				showPrintDebugger = false
				printDebuggerHighlightLine = -1
			}}
			undo={() => {
				showPrintDebugger = true
				printCodeVersion = 2
			}}
		/>
		<!-- Autopsy: show first bar -->
		<Action
			do={() => { stateTimeStep = 8; autopsyVisibleCount = 1 }}
			undo={() => { stateTimeStep = 7; autopsyVisibleCount = 0 }}
		/>
		<!-- Autopsy: animate remaining bars one-by-one with print dots -->
		<Action
			do={async () => {
				stateTimeStep = 9
				for (let i = 2; i <= autopsySlices.length; i++) {
					autopsyVisibleCount = i
					await sleep(100)
				}
			}}
			undo={() => {
				stateTimeStep = 8
				autopsyVisibleCount = 1
			}}
		/>
		<Notes>
			This is the core conceptual diagram of the talk. Return to it when discussing each tool.
			Start by showing the empty state×time space. Then pull out "program state" to explain
			what the Y axis means (all the variables in scope at a given moment). Then pull out "time"
			to explain what the X axis means (each iteration of the loop is a moment in time).
			Then walk through each debugging technique as a different sampling pattern.
		</Notes>
	</Slide>

	<!-- Slide: Formative study — too much / too little information -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16 text-left">
			<div class="flex flex-col gap-6">
				<div class="flex items-center gap-4">
					<AlertTriangle class="h-14 w-14 shrink-0 text-amber-600" />
					<h2 class="text-8xl font-bold text-black">Too Much Information</h2>
				</div>
				<div class="flex items-center gap-4 pl-2">
					<CircleUserRound class="h-14 w-14 shrink-0 text-amber-500" />
					<p class="text-5xl text-black">P3: "you don't want to burn up your log files with unnecessary information…otherwise, you will lose out the meaningful logs"</p>
				</div>
				<div class="flex items-center gap-4 pl-2">
					<CircleUserRound class="h-14 w-14 shrink-0 text-amber-500" />
					<p class="text-5xl text-black">P10: "if it is something that's gonna get called a ton…putting a breakpoint inside that is gonna kind of drive me crazy"</p>
				</div>
			</div>
			<div class="flex flex-col gap-6">
				<div class="flex items-center gap-4">
					<Info class="h-14 w-14 shrink-0 text-blue-600" />
					<h2 class="text-8xl font-bold text-black">Too Little Information</h2>
				</div>
				<div class="flex items-center gap-4 pl-2">
					<CircleUserRound class="h-14 w-14 shrink-0 text-blue-500" />
					<p class="text-5xl text-black">P5: "oh, okay, this is happening. Okay, then what was the state before this? And you don't have a log for that…"</p>
				</div>
				<div class="flex items-center gap-4 pl-2">
					<CircleUserRound class="h-14 w-14 shrink-0 text-blue-500" />
					<p class="text-5xl text-black">P12: "I just print out everything. As much information as possible."</p>
				</div>
			</div>
		</div>
		<Notes>
			We conducted interviews with 12 experienced industry software engineers to understand their debugging practices and why they preferred certain tools and techniques.
		</Notes>
	</Slide>

	<!-- Slide: Information needs in tension (2) -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Two information needs in tension</h2>
			<div class="flex gap-12">
				<div class="flex-1 rounded-xl border-2 border-amber-200 bg-amber-50 p-6">
					<p class="text-7xl font-bold text-amber-800 mb-2">Collection</p>
					<p class="text-4xl text-amber-900">Collect <em>more</em> data — it may be useful in future analysis</p>
				</div>
				<div class="flex-1 rounded-xl border-2 border-blue-200 bg-blue-50 p-6">
					<p class="text-7xl font-bold text-blue-800 mb-2">Analysis</p>
					<p class="text-4xl text-blue-900">Make sense of data and avoid being <em>overwhelmed</em> by it</p>
				</div>
			</div>
		</div>
	</Slide>

	<!-- Slide: Design principles — intro (3) -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Design principles</h2>
			<p class="text-5xl text-black">This tension motivated a new design. Principles:</p>
			<ol class="flex flex-col gap-3 pl-6 text-5xl text-black list-decimal">
				<li><strong>Separate collection and analysis</strong></li>
				<li><strong>Better affordances for analysis</strong></li>
				<li><strong>Connection back to code</strong></li>
			</ol>
		</div>
		<Notes>
			Original impetus: "Why do people still do print debugging if breakpoint debuggers exist?" and looking at rows of print output thinking "I wish I could do more with that now that I have it."
		</Notes>
	</Slide>

	<!-- Slide: Principle 3b — separate collection and analysis -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Principle: separate collection and analysis</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Collect lots of data without impeding analysis</li>
				<li>Extra data available for use <em>at-will</em></li>
			</ul>
		</div>
	</Slide>

	<!-- Slide: Principle 3c — better affordances for analysis -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Principle: better affordances for analysis</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Project new analysis from collected state</li>
				<li>Group and aggregate across logs — distributions, boundaries, outliers</li>
				<li>Associate logs with each other; focus to a region of interest</li>
				<li>Make comparisons across points in the log</li>
				<li class="mt-4 text-3xl text-gray-600">Omniscient debuggers don't get you all the way there: they replay deterministically and let you jump in time, but don't present across-log analysis tools</li>
			</ul>
		</div>
		<Notes>
			Industry already does this with structured logging in production (Splunk, Datadog, ELK).
		</Notes>
	</Slide>

	<!-- Slide: Principle 3d — connection back to code -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Principle: connection back to code</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Execution data is generated by a precise, computational process</li>
				<li>We know the exact <em>provenance</em> of all data</li>
				<li>This is leveraged in the analysis process</li>
			</ul>
		</div>
	</Slide>

	<!-- Slide: Demo — pricing example -->
	<Slide class="h-full">
		<div class="flex h-full flex-col gap-2 px-4 pt-4 pb-2">
			<h2 class="text-6xl font-bold text-black text-left">
				<span
					class="bg-[#1E40AF] px-2 py-0.5 text-white"
					style="font-family: var(--r-code-font)"
				>autopsy</span> — Demo: pricing example
			</h2>
			<!-- <iframe
				src="{iframBase}/price_calculator_report.html"
				title="Autopsy Report — Price Calculator"
				class="flex-1 w-full rounded-lg border border-gray-200 shadow-sm"
				style="min-height: 0"
			></iframe> -->
			<p class="text-3xl text-gray-500 italic flex-1 flex items-center justify-center">[Live demo: price calculator with autopsy]</p>
		</div>
		<Notes>
			Demo the autopsy interface with the pricing example: streams view, computed columns, sorting, filtering, cross-view navigation.
		</Notes>
	</Slide>

	<!-- ─── Section 3: Data-oriented debugging as a framework ─── -->

	<!-- Slide: The core proposal -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">
				The core proposal: decouple collection from analysis
			</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
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

	<!-- ─── Section 4: autopsy demo / walkthrough ─── -->

	<!-- Slide 11: autopsy overview -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">
				<span
					class="bg-[#1E40AF] px-2 py-1 text-white"
					style="font-family: var(--r-code-font)"
				>autopsy</span> overview
			</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
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
			<h2 class="text-6xl font-bold text-black text-left">
				<span
					class="bg-[#1E40AF] px-2 py-0.5 text-white"
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
			<h2 class="text-8xl font-bold text-black">Demo: streams view + computed columns</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Logs from one call site as a <strong>structured table</strong></li>
				<li>Add a computed column from a stack variable that wasn't explicitly logged</li>
				<li>Key point: "retroactive print debugging" — no rerun needed</li>
			</ul>
			<p class="text-5xl text-black italic">[Demo: streams view, drag-and-drop computed columns]</p>
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
			<h2 class="text-8xl font-bold text-black">
				Demo: sorting, filtering, cross-time comparison
			</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Sort by a column to group related entries</li>
				<li>Filter to a subset of interest</li>
				<li>Patterns across many executions become visible in the table</li>
			</ul>
			<p class="text-5xl text-black italic">[Demo: sorting and filtering]</p>
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
			<h2 class="text-8xl font-bold text-black">Demo: navigation between views</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Click a row in streams → jump to its location in history (sequential context)</li>
				<li>Click a row in history → jump to its stream (cross-time context)</li>
				<li>Inspect the full call stack from any row</li>
			</ul>
			<p class="text-5xl text-black italic">[Demo: cross-view navigation]</p>
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
			<h2 class="text-8xl font-bold text-black">Demo: identifying the bug</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Walk through how data tools led to identifying the root cause</li>
				<li>Comparing stack traces across rows reveals the state mutation</li>
			</ul>
			<p class="text-5xl text-black italic">[Demo: bug identification moment]</p>
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
			<h2 class="text-8xl font-bold text-black">Where this goes</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
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
			<h2 class="text-8xl font-bold text-black">Data-oriented debugging</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Debugging = checking mental models against execution data</li>
				<li>Current tools couple collection and analysis</li>
				<li>Data-oriented debugging decouples them</li>
				<li>
					<span
						class="bg-[#1E40AF] px-2 py-1 text-white"
						style="font-family: var(--r-code-font)"
					>autopsy</span> demonstrates this
				</li>
			</ul>
			<p class="text-3xl text-black italic mt-4">[Link to tool / paper / contact info]</p>
		</div>
	</Slide>
</Presentation>
