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

	// Interleaved dot sequence (execution order across both print rows)
	// Each entry: [x, y] coordinate from the appropriate row
	const printDotsInterleaved: [number, number][] = (() => {
		const seq: [number, number][] = []
		let r1 = 0, r2 = 0
		for (const t of tr.traces.printV2) {
			const hitsFirst = t.printOutputs.some(o => o.line === tr.codeVariants.printV2.printLines[0])
			const hitsSecond = t.printOutputs.some(o => o.line === tr.codeVariants.printV2.printLines[1])
			if (hitsFirst && r1 < printDotsRow1.length) {
				seq.push(printDotsRow1[r1])
				r1++
			}
			if (hitsSecond && r2 < printDotsRow2.length) {
				seq.push(printDotsRow2[r2])
				r2++
			}
		}
		return seq
	})()

	// Autopsy slices from traced data
	const autopsySlices = tr.autopsySliceXPositions
	let autopsyVisibleCount = $state(0)

	// ── Formative study slide ──
	let showTooLittle = $state(false)

	// ── Looping analysis slide ──
	type LoopMode = 'none' | 'breakpoint' | 'print'
	let loopMode = $state<LoopMode>('none')
	let loopHighlightLine = $state(-1)
	let loopBpIteration = $state(0)
	let loopBpX = tween({ x: tr.breakpointXPositions[0] ?? 200 }, { duration: 300 })
	let loopVars = $state<Record<string, string>>({})
	let loopTerminalLines = $state<string[]>([])
	let loopPrintDotsR1 = $state(0)
	let loopPrintDotsR2 = $state(0)
	let loopCancel: (() => void) | null = null

	function stopLoop() {
		if (loopCancel) { loopCancel(); loopCancel = null }
	}

	async function runBreakpointLoop() {
		let cancelled = false
		loopCancel = () => { cancelled = true }
		while (!cancelled) {
			for (let iter = 0; iter < ITEM_COUNT && !cancelled; iter++) {
				// Animate to this iteration's X position
				loopBpX.to({ x: tr.breakpointXPositions[iter] })
				loopBpIteration = iter
				loopVars = tr.breakpointSnapshots[iter]
				// Step through highlight path
				for (const line of bpHighlightPath) {
					if (cancelled) return
					loopHighlightLine = line
					await sleep(80)
				}
			}
		}
	}

	async function runPrintLoop() {
		let cancelled = false
		loopCancel = () => { cancelled = true }
		while (!cancelled) {
			loopPrintDotsR1 = 0
			loopPrintDotsR2 = 0
			loopTerminalLines = []
			for (let iter = 0; iter < printExecPathV2.length && !cancelled; iter++) {
				for (const line of printExecPathV2[iter]) {
					if (cancelled) return
					loopHighlightLine = line
					if (line === FIRST_PRINT_LINE) {
						loopPrintDotsR1 += 1
						const out = tr.traces.printV2[iter].printOutputs.find(o => o.line === FIRST_PRINT_LINE)
						if (out) loopTerminalLines = [...loopTerminalLines, out.text]
					}
					if (line === SECOND_PRINT_LINE) {
						loopPrintDotsR2 += 1
						const out = tr.traces.printV2[iter].printOutputs.find(o => o.line === SECOND_PRINT_LINE)
						if (out) loopTerminalLines = [...loopTerminalLines, out.text]
					}
					await sleep(iter === 0 ? 120 : 40)
				}
			}
			// Brief pause before restarting
			if (!cancelled) await sleep(500)
		}
	}

	// ── Comparison chart (post-tension slide) ──
	// 0: blank, 1: breakpoint bar, 2: print zigzag (2 rows),
	// 3: autopsy zigzag only, 4: + horizontal row lines, 5: + bars
	let compChartStep = $state(0)

	// ── Merged slide layout phases ──
	// 'code': full-screen code with heading
	// 'chart': code shrinks to corner, axes appear
	// 'breakpoint': 3-panel (chart left 2/3, code top-right, variables bottom-right)
	// 'print': 3-panel (chart left 2/3, code top-right, terminal bottom-right)
	// 'autopsy': chart-focused (code + panels dismissed)
	type Phase = 'code' | 'chart' | 'breakpoint' | 'print' | 'autopsy'
	let phase = $state<Phase>('code')

	// Tween for code editor position/size
	// In 'code' phase: fills screen. In 'chart' phase: small in top-right corner.
	// In 'breakpoint'/'print' phase: top-right panel in 3-panel layout.
	const codeTransform = tween({
		// These represent percentage-based positioning via CSS
		scale: 1, opacity: 1,
	}, { duration: 500 })

	// Whether to show the heading "How do you debug this?"
	let showHeading = $state(true)

	// Which panel to show in the bottom-right during 3-panel mode
	let rightPanel = $state<'none' | 'variables' | 'terminal'>('none')

	// Which code lines to show in the unified CodeOverlay
	let unifiedCodeLines = $derived(
		printCodeVersion === 0 ? tr.codeVariants.base.lines
		: printCodeVersion === 1 ? tr.codeVariants.printV1.lines
		: tr.codeVariants.printV2.lines
	)

	// Breakpoint markers for the unified CodeOverlay
	let unifiedMarkers = $derived(
		phase === 'breakpoint'
			? [{ line: COST_LINE_IDX, type: 'breakpoint' as const }]
			: []
	)

	// Unified highlight line (used for both breakpoint and print stepping)
	let unifiedHighlightLine = $derived(
		phase === 'breakpoint' ? bpDebuggerHighlightLine : printDebuggerHighlightLine
	)

	// Accent lines: momentary yellow token highlight when print lines are added
	let unifiedAccentLines = $state<number[]>([])

	// Print terminal output lines for the bottom-right terminal panel
	let printTerminalLines = $state<string[]>([])
</script>

<Presentation options={{ history: true, transition: 'slide', controls: false, progress: true, slideNumber: true }}>
	<!-- ─── Slide 1: Title ─── -->
	<Slide class="h-full">
		<div class="grid h-full grid-cols-[3fr_1fr] items-center gap-8 px-16 py-12">
			<div class="flex flex-col gap-8">
				<h1 class="text-left text-[6rem] font-bold leading-tight text-black">
					Data-oriented Debugging with
					<span
						class="mt-2 inline-block bg-[#0000FF] px-3 py-1 text-white"
						style="font-family: var(--r-code-font)"
					>autopsy</span>
				</h1>
				<div class="flex flex-col gap-2">
					<p class="text-left text-5xl text-black">
						<span class="font-bold text-[#0000FF]">Jeffrey Tao</span>, Xiaorui Liu, Ryan Marcus,
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

	<!-- ─── Merged Slide: Code → State×Time Chart → Debugging Techniques ─── -->
	<!--
		This single slide combines the "How do you debug this?" code intro with the
		state×time chart and debugging technique animations.

		Layout phases (controlled by `phase` state):
		- 'code': Full-screen code with "How do you debug this?" heading
		- 'chart': Code shrinks to top-right corner, state×time axes appear + build-up
		- 'breakpoint': 3-panel — chart (left 2/3), code (top-right), variables (bottom-right)
		- 'print': 3-panel — chart (left 2/3), code (top-right), terminal (bottom-right)
		- 'autopsy': Chart with bars filling in, right panels dismissed
	-->
	<Slide class="h-full" in={() => {
		phase = 'code'
		showHeading = true
		rightPanel = 'none'
		printCodeVersion = 0
		bpDebuggerHighlightLine = -1
		bpDebuggerIteration = 0
		printDebuggerHighlightLine = -1
		instantHighlight = false
		printTerminalLines = []
		stateTimeStep = 0; bpX.reset()
		titleLabel = 'none'
		showAxisCode = false; axisCodeHighlight = null; showCostTerminal = false
		showStateVarLabels = false; showCostLabels = false
		printDotsVisibleRow1 = 0; printDotsVisibleRow2 = 0; autopsyVisibleCount = 0
		psLabel.reset(); tLabel.reset(); axisFade.reset()
		stateVarLabels.forEach(l => l.reset())
		costLabels.forEach(l => l.reset())
		codeTransform.reset()
	}}>
		<!-- ═══════════════════════════════════════════════════
		     LAYOUT: 3-panel grid that morphs between phases
		     Left: state×time chart (hidden in 'code' phase)
		     Right-top: code editor (full-screen in 'code' phase, small otherwise)
		     Right-bottom: variables or terminal panel
		     ═══════════════════════════════════════════════════ -->
		<div class="relative h-full w-full overflow-hidden">

			<!-- ── Heading overlay (visible only in 'code' phase) ── -->
			<div
				class="absolute z-20 transition-all duration-500 pointer-events-none"
				style="
					top: 18%;
					left: 5rem;
					opacity: {showHeading ? 1 : 0};
					transform: translateY({showHeading ? 0 : -20}px);
				"
			>
				<h2 class="text-left text-8xl font-bold text-black">How do you debug this?</h2>
			</div>

			<!-- ── State×Time Chart (left region) ── -->
			<div
				class="absolute top-0 left-0 bottom-0 transition-all duration-700"
				style="
					width: {phase === 'code' ? '0%' : phase === 'chart' || phase === 'autopsy' ? '100%' : '64%'};
					opacity: {phase === 'code' ? 0 : 1};
				"
			>
				<div class="relative flex h-full items-center justify-center overflow-hidden">
					<svg viewBox="0 0 900 520" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
						<!-- Plot background -->
						<rect x="100" y="40" width="720" height="420" fill="white" />

						<!-- Step 1: Breakpoint — animated vertical slice -->
						{#if stateTimeStep === 1}
							<rect x={bpX.x - 12} y="40" width="24" height="420" fill="#1E40AF"
								style="opacity: 0; animation: appear 0.3s ease-out 0ms forwards" />
						{/if}

						<!-- (no dots at print section start) -->

						<!-- Step 5–7: Print — row 1 dots (with per-row lines) -->
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

						<!-- Step 7: Print — row 2 dots (with per-row lines) -->
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

						<!-- Step 10: Print — zigzag interleaved line connecting dots in execution order -->
						{#if stateTimeStep === 10}
							{#each printDotsInterleaved as [cx, cy], i}
								{#if i > 0}
									<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
										stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
										style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
								{/if}
								<circle {cx} {cy} r="6" fill="#991B1B"
									style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
							{/each}
						{/if}

						<!-- (autopsy bars removed — now on comparison slide) -->

						<!-- Axes (fade when a label is in title position) -->
						<g opacity={axisFade.axisOpacity}>
							<line x1="100" y1="40" x2="100" y2="460" stroke="black" stroke-width="2.5" />
							<polygon points="100,33 94,47 106,47" fill="black" />
							<line x1="100" y1="460" x2="836" y2="460" stroke="black" stroke-width="2.5" />
							<polygon points="843,460 829,454 829,466" fill="black" />
						</g>

						<!-- Axis labels (tweened) -->
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

						<!-- State variable labels along Y-axis -->
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

						<!-- Cost value labels along X-axis -->
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

					<!-- Code overlay for axis build-up (state-vars / cost highlighting) -->
					{#if showAxisCode}
						<div class="absolute flex items-center justify-center gap-4" style="pointer-events: none; width: 75%; left: 12.5%;">
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

					<!-- Technique label (top-right of chart area during 3-panel, or top-right of full area) -->
					{#if stateTimeStep >= 1}
						<div class="absolute left-[4%] top-[6%] rounded-md bg-white/85 px-4 py-2 text-left">
							{#if stateTimeStep === 1}
								<p class="text-5xl font-bold text-[#1E40AF]">breakpoint debugger</p>
								<p class="text-3xl text-gray-500">all state · one moment</p>
							{/if}
							{#if stateTimeStep >= 2 && stateTimeStep <= 10}
								<p class="text-5xl font-bold text-[#1E40AF]">print debugging</p>
								<p class="text-3xl text-gray-500">some state · many moments</p>
							{/if}
						</div>
					{/if}
				</div>
			</div>

			<!-- ── Right panels region (code + variables/terminal) ── -->
			<div
				class="absolute top-0 bottom-0 flex flex-col gap-3 p-3 transition-all duration-700"
				style="
					right: 0;
					width: {phase === 'code' ? '100%' : phase === 'chart' ? '50%' : '36%'};
					padding: {phase === 'code' ? '30% 5rem 3rem' : '0.75rem'};
				"
			>
				<!-- ── Code editor panel ── -->
				<div
					class="transition-all duration-700 overflow-hidden"
					style="
						flex: {phase === 'breakpoint' || phase === 'print' ? '1 1 50%' : 'none'};
						opacity: {phase === 'autopsy' ? 0 : codeTransform.opacity};
						transform: scale({phase === 'code' ? 1 : phase === 'chart' ? 0.5 : 1});
						transform-origin: top right;
						min-height: 0;
					"
				>
					{#if phase === 'code'}
						<!-- In code phase, show a full-size Code component with syntax highlighting -->
						<div class="rounded-xl border border-gray-200 bg-gray-50 p-6 shadow-sm overflow-hidden text-left">
							<Code
								bind:this={code}
								lang="python"
								theme="github-light"
								code={codeInitial}
								options={{ duration: 400, stagger: 0, lineNumbers: true, containerStyle: false, enhanceMatching: true, splitTokens: true }}
								class="text-5xl"
							/>
						</div>
					{:else}
						<!-- In chart/breakpoint/print phases, show CodeOverlay -->
						<CodeOverlay
							lines={unifiedCodeLines}
							highlightLine={unifiedHighlightLine}
							accentLines={unifiedAccentLines}
							markers={unifiedMarkers}
							instant={instantHighlight}
						/>
					{/if}
				</div>

				<!-- ── Bottom-right panel: Variables pane or Terminal ── -->
				<div
					class="transition-all duration-500 overflow-hidden"
					style="
						flex: {rightPanel !== 'none' ? '1 1 50%' : '0 0 0px'};
						opacity: {rightPanel !== 'none' ? 1 : 0};
						min-height: 0;
					"
				>
					{#if rightPanel === 'variables'}
						<VariablesPane
							variables={tr.breakpointSnapshots[bpDebuggerIteration]}
							style="height: 100%"
						/>
					{:else if rightPanel === 'terminal'}
						<div
							class="rounded-xl border border-gray-800 bg-gray-900 p-4 font-mono text-xl leading-relaxed text-green-400 text-left overflow-y-auto h-full"
						>
							<p class="text-gray-400 text-lg mb-2">Terminal</p>
							{#each printTerminalLines as line}
								<p>{line}</p>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		</div>

		<!-- ════════════════════════════════════════════════════
		     Phase 1: Code presentation (no actions needed for initial display)
		     ════════════════════════════════════════════════════ -->

		<!-- A0: Transition from 'code' phase → 'chart' phase
		     Shrink code to top-right corner, reveal axes -->
		<Action
			do={async () => {
				showHeading = false
				await sleep(300)
				phase = 'chart'
			}}
			undo={async () => {
				phase = 'code'
				await sleep(300)
				showHeading = true
			}}
		/>

		<!-- ════════════════════════════════════════════════════
		     Phase 2: Axis build-up (code small in corner)
		     ════════════════════════════════════════════════════ -->

		<!-- A1: Fly "program state" to title position -->
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

		<!-- A2: Show code overlay on chart, highlight state variables -->
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

		<!-- A2b: Distribute state variable names along Y-axis -->
		<Action
			do={async () => {
				showStateVarLabels = true
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

		<!-- A4: Fly "time" to title position -->
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

		<!-- A5: Show code overlay (highlight cost) + cost terminal -->
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

		<!-- A5b: Distribute cost values along X-axis -->
		<Action
			do={async () => {
				showCostLabels = true
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
		     Phase 3: Breakpoint debugging (3-panel layout)
		     ════════════════════════════════════════════════════ -->

		<!-- Enter breakpoint mode: switch to 3-panel, show bar + breakpoint marker + variables -->
		<Action
			do={async () => {
				phase = 'breakpoint'
				stateTimeStep = 1
				rightPanel = 'variables'
				bpDebuggerHighlightLine = COST_LINE_IDX
				bpDebuggerIteration = 0
			}}
			undo={async () => {
				phase = 'chart'
				stateTimeStep = 0
				rightPanel = 'none'
				bpDebuggerHighlightLine = -1
				bpDebuggerIteration = 0
				bpX.reset()
			}}
		/>

		<!-- Breakpoint: one slow "Continue" -->
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

		<!-- Breakpoint: fast-forward remaining iterations -->
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

		<!-- ════════════════════════════════════════════════════
		     Phase 4: Print debugging (seamless transition from breakpoint)
		     Keep the 3-panel layout, swap variables→terminal, remove breakpoint marker
		     ════════════════════════════════════════════════════ -->

		<!-- Transition: breakpoint → print. Maintain code editor, animate bar→dot -->
		<Action
			do={async () => {
				phase = 'print'
				stateTimeStep = 2
				rightPanel = 'terminal'
				printTerminalLines = []
				bpDebuggerHighlightLine = -1
				printCodeVersion = 0
				printDebuggerHighlightLine = -1
			}}
			undo={async () => {
				phase = 'breakpoint'
				stateTimeStep = 1
				rightPanel = 'variables'
				bpDebuggerHighlightLine = COST_LINE_IDX
				bpDebuggerIteration = Math.min(tr.breakpointXPositions.length, 8) - 1
				printCodeVersion = 0
				printDebuggerHighlightLine = -1
			}}
		/>

		<!-- Print: add print to first condition -->
		<Action
			do={async () => {
				printCodeVersion = 1; stateTimeStep = 4
				unifiedAccentLines = tr.codeVariants.printV1.printLines
				await sleep(800)
				unifiedAccentLines = []
			}}
			undo={() => { printCodeVersion = 0; stateTimeStep = 2; unifiedAccentLines = [] }}
		/>

		<!-- Print V1: one slow iteration with terminal output -->
		<Action
			do={async () => {
				stateTimeStep = 5
				printDotsVisibleRow1 = 0
				for (const line of printExecPathV1[0]) {
					printDebuggerHighlightLine = line
					if (line === FIRST_PRINT_LINE) {
						printDotsVisibleRow1 += 1
						// Add terminal line
						const outputs = tr.traces.printV1[0].printOutputs
						const out = outputs[printDotsVisibleRow1 - 1]
						if (out) printTerminalLines = [...printTerminalLines, out.text]
					}
					await sleep(SLOW_LINE_DELAY)
				}
			}}
			undo={() => {
				stateTimeStep = 4
				printDotsVisibleRow1 = 0
				printDebuggerHighlightLine = -1
				printTerminalLines = []
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
							const outputs = tr.traces.printV1[iter].printOutputs
							const out = outputs.find(o => o.line === FIRST_PRINT_LINE)
							if (out) printTerminalLines = [...printTerminalLines, out.text]
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
				// Restore terminal to just first iteration output
				const out = tr.traces.printV1[0].printOutputs[0]
				printTerminalLines = out ? [out.text] : []
			}}
		/>

		<!-- Print: add second print, clear dots/terminal -->
		<Action
			do={async () => {
				printCodeVersion = 2
				stateTimeStep = 6; printTerminalLines = []; printDotsVisibleRow1 = 0; printDotsVisibleRow2 = 0
				unifiedAccentLines = tr.codeVariants.printV2.printLines
				await sleep(800)
				unifiedAccentLines = []
			}}
			undo={() => {
				printCodeVersion = 1; stateTimeStep = 5
				printDotsVisibleRow1 = tr.printDots.row1.length
				printDotsVisibleRow2 = 0
				unifiedAccentLines = []
				const lines: string[] = []
				for (const t of tr.traces.printV1) {
					for (const p of t.printOutputs) lines.push(p.text)
				}
				printTerminalLines = lines
			}}
		/>

		<!-- Print V2: slow first iteration -->
		<Action
			do={async () => {
				stateTimeStep = 7
				for (const line of printExecPathV2[0]) {
					printDebuggerHighlightLine = line
					if (line === FIRST_PRINT_LINE) {
						printDotsVisibleRow1 += 1
						const out = tr.traces.printV2[0].printOutputs.find(o => o.line === FIRST_PRINT_LINE)
						if (out) printTerminalLines = [...printTerminalLines, out.text]
					}
					if (line === SECOND_PRINT_LINE) {
						printDotsVisibleRow2 += 1
						const out = tr.traces.printV2[0].printOutputs.find(o => o.line === SECOND_PRINT_LINE)
						if (out) printTerminalLines = [...printTerminalLines, out.text]
					}
					await sleep(SLOW_LINE_DELAY)
				}
			}}
			undo={() => {
				stateTimeStep = 6
				printDotsVisibleRow1 = 0
				printDotsVisibleRow2 = 0
				printDebuggerHighlightLine = -1
				printTerminalLines = []
			}}
		/>

		<!-- Print V2: fast-forward remaining iterations (interleaved output) -->
		<Action
			do={async () => {
				instantHighlight = true
				for (let iter = 1; iter < printExecPathV2.length; iter++) {
					for (const line of printExecPathV2[iter]) {
						printDebuggerHighlightLine = line
						if (line === FIRST_PRINT_LINE) {
							printDotsVisibleRow1 += 1
							const out = tr.traces.printV2[iter].printOutputs.find(o => o.line === FIRST_PRINT_LINE)
							if (out) printTerminalLines = [...printTerminalLines, out.text]
						}
						if (line === SECOND_PRINT_LINE) {
							printDotsVisibleRow2 += 1
							const out = tr.traces.printV2[iter].printOutputs.find(o => o.line === SECOND_PRINT_LINE)
							if (out) printTerminalLines = [...printTerminalLines, out.text]
						}
						await sleep(FAST_LINE_DELAY)
					}
				}
				printDebuggerHighlightLine = -1
				instantHighlight = false
			}}
			undo={() => {
				instantHighlight = false
				printDotsVisibleRow1 = printExecPathV2[0].includes(FIRST_PRINT_LINE) ? 1 : 0
				printDotsVisibleRow2 = printExecPathV2[0].includes(SECOND_PRINT_LINE) ? 1 : 0
				printDebuggerHighlightLine = -1
				// Restore to just first iteration's interleaved output
				const lines: string[] = []
				for (const p of tr.traces.printV2[0].printOutputs) lines.push(p.text)
				printTerminalLines = lines
			}}
		/>

		<!-- Print V2: show zigzag interleaved line connecting dots in execution order -->
		<Action
			do={() => { stateTimeStep = 10 }}
			undo={() => { stateTimeStep = 7 }}
		/>

		<!-- (Autopsy phase moved to later comparison slide) -->

		<Notes>
			This slide combines the code example with the state×time conceptual diagram.
			Start by showing the code and asking "How do you debug this?" Then transition
			to the state×time space, explain the axes, and walk through each debugging
			technique as a different sampling pattern in the 3-panel layout.
		</Notes>
	</Slide>

	<!-- Slide: Formative study — too much / too little information -->
	<Slide class="h-full" in={() => { showTooLittle = false }}>
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
			<Action do={() => { showTooLittle = true }} undo={() => { showTooLittle = false }} />
			<div class="flex flex-col gap-6 transition-opacity duration-400" style="opacity: {showTooLittle ? 1 : 0}">
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

	<!-- Slide: Why are they in tension? -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Why are they in tension?</h2>
			<ul class="flex flex-col gap-6 pl-6 text-5xl text-black list-disc">
				<li>Current debuggers <span class="text-[#0000FF]">couple</span> collecting execution data and analyzing it</li>
				<li>Current debuggers lack affordances for <span class="text-[#0000FF]">transforming and comprehending</span> execution data</li>
			</ul>
		</div>
		<Notes>
			There's nothing you can do with print debugging output besides browsing it and performing text search on it.
			Print debugging is "preregistering" your analysis.
			On the other hand, interactive debugging with a breakpoint debugger is almost the opposite: it forces you to continually make decisions about what data to collect next.
			You're constantly switching between deciding where to go next and analyzing what you can now see.

			On the analysis side, neither has strong affordances for reasoning about whole-program execution, which I'll get into in a bit.
			First, let's examine what better collection could look like.
		</Notes>
	</Slide>

	<!-- Slide: State×time comparison — blank → breakpoint → print → autopsy -->
	<Slide class="h-full" in={() => { compChartStep = 0 }}>
		<div class="flex h-full flex-col items-center justify-center gap-4 px-12">
			<svg viewBox="0 0 900 520" width="80%" preserveAspectRatio="xMidYMid meet">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="white" stroke="#e5e7eb" stroke-width="1" />

				<!-- Y-axis label -->
				<text x="50" y="250" text-anchor="middle" font-family="Lato, sans-serif" font-size="36"
					fill="black" transform="rotate(-90 50 250)">program state</text>

				<!-- X-axis label -->
				<text x="460" y="500" text-anchor="middle" font-family="Lato, sans-serif" font-size="36"
					fill="black">time</text>

				<!-- Step 1: Breakpoint — single vertical bar -->
				{#if compChartStep === 1}
					<rect x={tr.breakpointXPositions[3] - 12} y="40" width="24" height="420" fill="#1E40AF"
						style="opacity: 0; animation: appear 0.5s ease-out forwards" />
					<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
						fill="#1E40AF" font-weight="bold"
						style="opacity: 0; animation: appear 0.5s ease-out 0.3s forwards">breakpoint debugger</text>
				{/if}

				<!-- Step 2: Print — zigzag interleaved (both rows) -->
				{#if compChartStep === 2}
					{#each printDotsInterleaved as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
								style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B"
							style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
					{/each}
					<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
						fill="#991B1B" font-weight="bold"
						style="opacity: 0; animation: appear 0.5s ease-out 0.3s forwards">print debugging</text>
				{/if}

				<!-- Steps 3–5: Autopsy build-up -->
				{#if compChartStep >= 3}
					<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
						fill="#1E40AF" font-weight="bold"
						style="font-family: var(--r-code-font); opacity: 0; animation: appear 0.5s ease-out forwards">autopsy</text>

					<!-- Step 5: bars (rendered first so dots paint on top) -->
					{#if compChartStep >= 5}
						{#each autopsySlices as x, i}
							<rect x={x - 12} y="40" width="24" height="420" fill="#1E40AF" rx="4" fill-opacity="0.35"
								style="opacity: 0; animation: appear 0.15s ease-out {i * 60}ms forwards" />
						{/each}
					{/if}

					<!-- Step 3+: zigzag interleaved line + dots -->
					{#each printDotsInterleaved as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
								style={compChartStep === 3 ? `opacity: 0; animation: appear 0.1s ease-out ${i * 30}ms forwards` : ''} />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B"
							style={compChartStep === 3 ? `opacity: 0; animation: appear 0.1s ease-out ${i * 30}ms forwards` : ''} />
					{/each}

					<!-- Step 4+: horizontal per-row lines -->
					{#if compChartStep >= 4}
						{#each printDotsRow1 as [cx, cy], i}
							{#if i > 0}
								<line x1={printDotsRow1[i-1][0]} y1={printDotsRow1[i-1][1]} x2={cx} y2={cy}
									stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
									style={compChartStep === 4 ? `opacity: 0; animation: appear 0.15s ease-out ${i * 30}ms forwards` : ''} />
							{/if}
						{/each}
						{#each printDotsRow2 as [cx, cy], i}
							{#if i > 0}
								<line x1={printDotsRow2[i-1][0]} y1={printDotsRow2[i-1][1]} x2={cx} y2={cy}
									stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
									style={compChartStep === 4 ? `opacity: 0; animation: appear 0.15s ease-out ${i * 30}ms forwards` : ''} />
							{/if}
						{/each}
					{/if}
				{/if}
			</svg>
		</div>

		<!-- Actions: step through each visualization -->
		<Action do={() => { compChartStep = 1 }} undo={() => { compChartStep = 0 }} />
		<Action do={() => { compChartStep = 2 }} undo={() => { compChartStep = 1 }} />
		<Action do={() => { compChartStep = 3 }} undo={() => { compChartStep = 2 }} />
		<Action do={() => { compChartStep = 4 }} undo={() => { compChartStep = 3 }} />
		<Action do={() => { compChartStep = 5 }} undo={() => { compChartStep = 4 }} />

		<Notes>
			Show the same state×time chart from before, but now just as a quick comparison.
			Breakpoint: all state, one moment. Print: some state, many moments. Autopsy: all state, many moments.
		</Notes>
	</Slide>

	<!-- Slide: autopsy intro — import autopsy -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">
				<span
					class="bg-[#0000FF] px-2 py-1 text-white"
					style="font-family: var(--r-code-font)"
				>autopsy</span>
			</h2>
			<div class="rounded-xl border border-gray-200 bg-gray-50 p-8 shadow-sm text-left">
				<Code
					lang="python"
					theme="github-light"
					code={`import autopsy

...

autopsy.log("checkpoint", order, total)`}
					options={{ lineNumbers: false, containerStyle: false }}
					class="text-5xl"
				/>
			</div>
			<div class="rounded-lg border-2 border-dashed border-amber-400 bg-amber-50 px-6 py-4 mt-4">
				<p class="text-3xl text-amber-800"><strong>TODO:</strong> Need to explain call stack capture — <code>autopsy.log()</code> captures passed arguments + full stack trace (all frames, all local variables at each frame)</p>
			</div>
		</div>
		<Notes>
			Introduce the autopsy tool: a Python tracing library. The key insight is that a single log call
			captures far more than what you explicitly pass — it grabs the entire call stack with all local
			variables at every frame. This is the "collect more" side of the design.
		</Notes>
	</Slide>

	<!-- Slide: Principle 3c — better affordances for analysis -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Affordances for analysis</h2>
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

	<!-- Slide: Looping analysis animation (talk-over slide) -->
	<Slide class="h-full" in={() => { stopLoop(); loopMode = 'none'; loopHighlightLine = -1; loopTerminalLines = []; loopPrintDotsR1 = 0; loopPrintDotsR2 = 0; loopBpX.reset() }}>
		<div class="relative h-full w-full overflow-hidden">
			<!-- Left: state×time chart -->
			<div
				class="absolute top-0 left-0 bottom-0 transition-all duration-500"
				style="width: {loopMode === 'none' ? '100%' : '64%'}; opacity: {loopMode === 'none' ? 0.3 : 1}"
			>
				<div class="relative flex h-full items-center justify-center overflow-hidden">
					<svg viewBox="0 0 900 520" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
						<rect x="100" y="40" width="720" height="420" fill="white" />

						<!-- Axes -->
						<line x1="140" y1="40" x2="140" y2="420" stroke="black" stroke-width="2" />
						<line x1="140" y1="420" x2="780" y2="420" stroke="black" stroke-width="2" />
						<text x="50" y="250" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
							fill="black" transform="rotate(-90 50 250)">program state</text>
						<text x="460" y="480" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
							fill="black">time</text>

						<!-- Breakpoint mode: animated vertical bar -->
						{#if loopMode === 'breakpoint'}
							<rect x={loopBpX.x - 12} y="40" width="24" height="420" fill="#1E40AF"
								style="opacity: 0; animation: appear 0.3s ease-out forwards" />
						{/if}

						<!-- Print mode: dots -->
						{#if loopMode === 'print'}
							{#each printDotsInterleaved as [cx, cy], i}
								{#if i > 0 && i < loopPrintDotsR1 + loopPrintDotsR2}
									{@const prevIdx = i - 1}
									<line x1={printDotsInterleaved[prevIdx][0]} y1={printDotsInterleaved[prevIdx][1]} x2={cx} y2={cy}
										stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
								{/if}
								{#if i < loopPrintDotsR1 + loopPrintDotsR2}
									<circle {cx} {cy} r="6" fill="#991B1B" />
								{/if}
							{/each}
						{/if}
					</svg>

					<!-- Technique label -->
					{#if loopMode !== 'none'}
						<div class="absolute left-[4%] top-[6%] rounded-md bg-white/85 px-4 py-2 text-left">
							{#if loopMode === 'breakpoint'}
								<p class="text-4xl font-bold text-[#1E40AF]">breakpoint debugger</p>
								<p class="text-2xl text-gray-500">all state · one moment</p>
							{:else}
								<p class="text-4xl font-bold text-[#1E40AF]">print debugging</p>
								<p class="text-2xl text-gray-500">some state · many moments</p>
							{/if}
						</div>
					{/if}
				</div>
			</div>

			<!-- Right panels -->
			<div
				class="absolute top-0 bottom-0 right-0 flex flex-col gap-3 p-3 transition-all duration-500"
				style="width: {loopMode === 'none' ? '0%' : '36%'}; opacity: {loopMode === 'none' ? 0 : 1}"
			>
				<!-- Code editor -->
				<div class="flex-1 min-h-0 overflow-hidden">
					<CodeOverlay
						lines={loopMode === 'print' ? tr.codeVariants.printV2.lines : tr.codeVariants.base.lines}
						highlightLine={loopHighlightLine}
						markers={loopMode === 'breakpoint' ? [{ line: COST_LINE_IDX, type: 'breakpoint' }] : []}
					/>
				</div>

				<!-- Bottom panel: variables or terminal -->
				<div class="flex-1 min-h-0 overflow-hidden">
					{#if loopMode === 'breakpoint'}
						<VariablesPane
							variables={loopVars}
							style="height: 100%"
						/>
					{:else if loopMode === 'print'}
						<div class="rounded-xl border border-gray-800 bg-gray-900 p-4 font-mono text-xl leading-relaxed text-green-400 text-left overflow-y-auto h-full">
							<p class="text-gray-400 text-lg mb-2">Terminal</p>
							{#each loopTerminalLines as line}
								<p>{line}</p>
							{/each}
						</div>
					{/if}
				</div>
			</div>

			<!-- Center text when no mode active -->
			{#if loopMode === 'none'}
				<div class="absolute inset-0 flex items-center justify-center">
					<h2 class="text-7xl font-bold text-gray-400">Affordances for analysis</h2>
				</div>
			{/if}
		</div>

		<Action
			do={() => { stopLoop(); loopMode = 'breakpoint'; loopVars = tr.breakpointSnapshots[0]; runBreakpointLoop() }}
			undo={() => { stopLoop(); loopMode = 'none'; loopHighlightLine = -1 }}
		/>
		<Action
			do={() => { stopLoop(); loopMode = 'print'; loopHighlightLine = -1; loopTerminalLines = []; loopPrintDotsR1 = 0; loopPrintDotsR2 = 0; runPrintLoop() }}
			undo={() => { stopLoop(); loopMode = 'breakpoint'; loopVars = tr.breakpointSnapshots[0]; runBreakpointLoop() }}
		/>

		<Notes>
			Talk over this slide about affordances for analysis.
			The looping animations show how current tools force you to step through execution one item at a time,
			with no way to see patterns across the full execution.
		</Notes>
	</Slide>

	<!-- Slide: Principle 3d — connection back to code -->
	 <!--
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
	-->

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
