<script lang="ts">
	import { Presentation, Slide, Notes, Action, Code } from '@animotion/core'
	import { tween, all } from '@animotion/motion'
	import { onMount } from 'svelte'
	import { AlertTriangle, CircleUserRound, Info } from '@lucide/svelte'
	import { trace } from '$lib/tracing'
	import CodeOverlay from '$lib/components/CodeOverlay.svelte'
	import VariablesPane from '$lib/components/VariablesPane.svelte'

	// ── Configurable parameters ──
	const SEED = 2
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
		'    if item.qty >= 10:',
		'        item.price *= 0.9',
		'        print("Price", item.price, item.qty)',
		'    ...',
		'    if item.total() > 35:',
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

	// ── Constants ──
	const COST_LINE_IDX = 2
	const FIRST_PRINT_LINE = tr.codeVariants.printV1.printLines[0]
	const SECOND_PRINT_LINE = tr.codeVariants.printV2.printLines[1]

	const printExecPathV1 = tr.traces.printV1.map((t) => t.path)
	const printExecPathV2 = tr.traces.printV2.map((t) => t.path)

	const baseLineCount = tr.codeVariants.base.lines.length
	function bpContinuePath(): number[] {
		const path: number[] = []
		for (let i = COST_LINE_IDX; i < baseLineCount; i++) path.push(i)
		for (let i = 0; i <= COST_LINE_IDX; i++) path.push(i)
		return path
	}
	const bpHighlightPath = bpContinuePath()

	function sleep(ms: number, signal?: AbortSignal) {
		return new Promise<void>((resolve) => {
			const id = setTimeout(resolve, ms)
			signal?.addEventListener('abort', () => { clearTimeout(id); resolve() })
		})
	}

	// In dev, serve iframed HTML via /__raw/ to bypass Vite's HMR injection
	const iframBase = import.meta.env.DEV ? '/__raw' : ''

	// ── Static data ──
	const stateVarNames = tr.stateVarNames
	const stateVarTargetY = stateVarNames.map((_, i) =>
		110 + (i / (stateVarNames.length - 1)) * 320
	)
	const costValues = tr.costValues
	const costLabelTargetX = costValues.map((_, i) =>
		110 + (i / Math.max(costValues.length - 1, 1)) * 700
	)
	const printDotsRow1 = tr.printDots.row1
	const printDotsRow2 = tr.printDots.row2
	const printDotsRow1Indices = tr.printDots.row1Indices
	const printDotsRow2Indices = tr.printDots.row2Indices
	const autopsySlices = tr.autopsySliceXPositions

	const printDotsInterleaved: [number, number][] = (() => {
		const seq: [number, number][] = []
		let r1 = 0, r2 = 0
		for (const t of tr.traces.printV2) {
			const hitsFirst = t.printOutputs.some(o => o.line === tr.codeVariants.printV2.printLines[0])
			const hitsSecond = t.printOutputs.some(o => o.line === tr.codeVariants.printV2.printLines[1])
			if (hitsFirst && r1 < printDotsRow1.length) { seq.push(printDotsRow1[r1]); r1++ }
			if (hitsSecond && r2 < printDotsRow2.length) { seq.push(printDotsRow2[r2]); r2++ }
		}
		return seq
	})()

	// ── Pre-computed terminal lines for each relevant step ──
	const terminalLinesV1Iter0: string[] = tr.traces.printV1[0].printOutputs.map(o => o.text)
	const terminalLinesV1All: string[] = tr.traces.printV1.flatMap(t => t.printOutputs.map(o => o.text))
	const terminalLinesV2Iter0: string[] = tr.traces.printV2[0].printOutputs.map(o => o.text)
	const terminalLinesV2All: string[] = tr.traces.printV2.flatMap(t => t.printOutputs.map(o => o.text))

	const maxBpIter = Math.min(tr.breakpointXPositions.length, 8) - 1

	// ── Tweens (kept as objects, targets set by $effect) ──
	const psLabel = tween({ x: 50, y: 250, rotate: -90, fontSize: 36 }, { duration: 600 })
	const tLabel = tween({ x: 460, y: 500, rotate: 0, fontSize: 36 }, { duration: 600 })
	const axisFade = tween({ codeOpacity: 0, terminalOpacity: 0, axisOpacity: 1 }, { duration: 400 })
	const stateVarLabels = stateVarNames.map(() =>
		tween({ x: 460, y: 250, opacity: 0, fontSize: 36 }, { duration: 500 })
	)
	const costLabels = costValues.map(() =>
		tween({ x: 460, y: 250, rotate: 0, opacity: 0, fontSize: 36 }, { duration: 500 })
	)
	const bpX = tween({ x: tr.breakpointXPositions[0] ?? 200 })
	const codeTransform = tween({ scale: 1, opacity: 1 }, { duration: 500 })

	// ── Step-driven state for the merged slide ──
	type Phase = 'code' | 'chart' | 'breakpoint' | 'print' | 'autopsy'
	const TOTAL_STEPS = 21  // steps 0-20

	let chartStep = $state(0)

	// ── Mutable state (set by applySnapshot / progressive animations) ──
	let phase = $state<Phase>('code')
	let showHeading = $state(true)
	let titleLabel = $state<'none' | 'state' | 'time'>('none')
	let showAxisCode = $state(false)
	let axisCodeHighlight = $state<'state-vars' | 'cost' | null>(null)
	let showCostTerminal = $state(false)
	let showStateVarLabels = $state(false)
	let showCostLabels = $state(false)
	let rightPanel = $state<'none' | 'variables' | 'terminal'>('none')
	let stateTimeStep = $state(0)
	let printCodeVersion = $state(0)
	let bpDebuggerHighlightLine = $state(-1)
	let bpDebuggerIteration = $state(0)
	let printDebuggerHighlightLine = $state(-1)
	let instantHighlight = $state(false)
	let printDotsVisibleRow1 = $state(0)
	let printDotsVisibleRow2 = $state(0)
	let autopsyVisibleCount = $state(0)
	let unifiedAccentLines = $state<number[]>([])
	let printTerminalLines = $state<string[]>([])
	let terminalEl = $state<HTMLDivElement>()

	$effect(() => {
		printTerminalLines;  // track dependency
		if (terminalEl) {
			// Use tick to wait for DOM update, then scroll
			requestAnimationFrame(() => {
				terminalEl!.scrollTop = terminalEl!.scrollHeight
			})
		}
	})

	// ── Derived state ──
	let unifiedCodeLines = $derived(
		[...(printCodeVersion === 0 ? tr.codeVariants.base.lines
		: printCodeVersion === 1 ? tr.codeVariants.printV1.lines
		: tr.codeVariants.printV2.lines)]
	)
	let unifiedMarkers = $derived(
		phase === 'breakpoint'
			? [{ line: COST_LINE_IDX, type: 'breakpoint' as const }]
			: []
	)
	let unifiedHighlightLine = $derived(
		phase === 'breakpoint' ? bpDebuggerHighlightLine : printDebuggerHighlightLine
	)

	// ── Snapshot type ──
	interface StepSnapshot {
		phase: Phase
		showHeading: boolean
		titleLabel: 'none' | 'state' | 'time'
		showAxisCode: boolean
		axisCodeHighlight: 'state-vars' | 'cost' | null
		showCostTerminal: boolean
		showStateVarLabels: boolean
		showCostLabels: boolean
		rightPanel: 'none' | 'variables' | 'terminal'
		stateTimeStep: number
		printCodeVersion: number
		bpDebuggerHighlightLine: number
		bpDebuggerIteration: number
		printDebuggerHighlightLine: number
		instantHighlight: boolean
		printDotsVisibleRow1: number
		printDotsVisibleRow2: number
		printTerminalLines: string[]
		unifiedAccentLines: number[]
		psLabel: { x: number; y: number; rotate: number; fontSize: number }
		tLabel: { x: number; y: number; rotate?: number; fontSize: number }
		axisFade: { codeOpacity: number; terminalOpacity: number; axisOpacity: number }
		stateVarLabelTargets: Array<{ x: number; y: number; opacity: number }>
		costLabelTargets: Array<{ x: number; y: number; rotate: number; opacity: number }>
		bpX: number
	}

	// Default tween positions
	const PS_AXIS = { x: 50, y: 250, rotate: -90, fontSize: 36 }
	const PS_TITLE = { x: 460, y: 60, rotate: 0, fontSize: 72 }
	const T_AXIS = { x: 460, y: 500, fontSize: 36 }
	const T_TITLE = { x: 460, y: 60, fontSize: 72 }
	const FADE_NORMAL = { codeOpacity: 0, terminalOpacity: 0, axisOpacity: 1 }
	const FADE_DIM = { codeOpacity: 0, terminalOpacity: 0, axisOpacity: 0.15 }
	const SVL_HIDDEN = stateVarNames.map(() => ({ x: 460, y: 250, opacity: 0 }))
	const SVL_VISIBLE = stateVarNames.map((_, i) => ({ x: 140, y: stateVarTargetY[i], opacity: 1 }))
	const CL_HIDDEN = costValues.map(() => ({ x: 460, y: 250, rotate: 0, opacity: 0 }))
	const CL_VISIBLE = costValues.map((_, i) => ({ x: costLabelTargetX[i], y: 430, rotate: -90, opacity: 1 }))

	const BASE: StepSnapshot = {
		phase: 'code', showHeading: true, titleLabel: 'none',
		showAxisCode: false, axisCodeHighlight: null, showCostTerminal: false,
		showStateVarLabels: false, showCostLabels: false,
		rightPanel: 'none', stateTimeStep: 0, printCodeVersion: 0,
		bpDebuggerHighlightLine: -1, bpDebuggerIteration: 0,
		printDebuggerHighlightLine: -1, instantHighlight: false,
		printDotsVisibleRow1: 0, printDotsVisibleRow2: 0,
		printTerminalLines: [], unifiedAccentLines: [],
		psLabel: PS_AXIS, tLabel: T_AXIS, axisFade: FADE_NORMAL,
		stateVarLabelTargets: SVL_HIDDEN, costLabelTargets: CL_HIDDEN,
		bpX: tr.breakpointXPositions[0] ?? 200,
	}

	function s(overrides: Partial<StepSnapshot>): StepSnapshot {
		return { ...BASE, ...overrides }
	}

	// Count dots in first iteration of print V1
	const v1Iter0Dots = printExecPathV1[0].filter(l => l === FIRST_PRINT_LINE).length
	// Count dots in first iteration of print V2
	const v2Iter0DotsR1 = printExecPathV2[0].filter(l => l === FIRST_PRINT_LINE).length
	const v2Iter0DotsR2 = printExecPathV2[0].filter(l => l === SECOND_PRINT_LINE).length

	const STEPS: StepSnapshot[] = [
		// 0: code phase
		s({}),
		// 1: chart phase (axes appear)
		s({ phase: 'chart', showHeading: false }),
		// 2: "program state" flies to title
		s({ phase: 'chart', showHeading: false, titleLabel: 'state',
			psLabel: PS_TITLE, axisFade: FADE_DIM }),
		// 3: code overlay, state-vars highlighted
		s({ phase: 'chart', showHeading: false, titleLabel: 'state',
			psLabel: PS_TITLE, axisFade: { ...FADE_DIM, codeOpacity: 1 },
			showAxisCode: true, axisCodeHighlight: 'state-vars' }),
		// 4: state var labels distributed on Y-axis
		s({ phase: 'chart', showHeading: false, titleLabel: 'state',
			psLabel: PS_TITLE, axisFade: FADE_DIM,
			showStateVarLabels: true, stateVarLabelTargets: SVL_VISIBLE }),
		// 5: labels fade, "program state" back to axis
		s({ phase: 'chart', showHeading: false,
			showStateVarLabels: true, stateVarLabelTargets: SVL_HIDDEN }),
		// 6: "time" flies to title
		s({ phase: 'chart', showHeading: false, titleLabel: 'time',
			tLabel: T_TITLE, axisFade: FADE_DIM }),
		// 7: cost code + terminal overlay
		s({ phase: 'chart', showHeading: false, titleLabel: 'time',
			tLabel: T_TITLE, axisFade: { ...FADE_DIM, codeOpacity: 1, terminalOpacity: 1 },
			showAxisCode: true, axisCodeHighlight: 'cost', showCostTerminal: true }),
		// 8: cost labels distributed on X-axis
		s({ phase: 'chart', showHeading: false, titleLabel: 'time',
			tLabel: T_TITLE, axisFade: FADE_DIM,
			showCostLabels: true, costLabelTargets: CL_VISIBLE }),
		// 9: labels fade, "time" back to axis
		s({ phase: 'chart', showHeading: false,
			showCostLabels: true, costLabelTargets: CL_HIDDEN }),
		// 10: breakpoint mode
		s({ phase: 'breakpoint', showHeading: false, stateTimeStep: 1,
			rightPanel: 'variables', bpDebuggerHighlightLine: COST_LINE_IDX,
			bpDebuggerIteration: 0, bpX: tr.breakpointXPositions[0] ?? 200 }),
		// 11: one slow "Continue" (end state: iteration 1)
		s({ phase: 'breakpoint', showHeading: false, stateTimeStep: 1,
			rightPanel: 'variables', bpDebuggerHighlightLine: COST_LINE_IDX,
			bpDebuggerIteration: 1, bpX: tr.breakpointXPositions[1] ?? 420 }),
		// 12: fast-forward remaining iterations
		s({ phase: 'breakpoint', showHeading: false, stateTimeStep: 1,
			rightPanel: 'variables', bpDebuggerHighlightLine: COST_LINE_IDX,
			bpDebuggerIteration: maxBpIter, bpX: tr.breakpointXPositions[maxBpIter] ?? 700 }),
		// 13: transition to print
		s({ phase: 'print', showHeading: false, stateTimeStep: 2,
			rightPanel: 'terminal' }),
		// 14: add first print statement
		s({ phase: 'print', showHeading: false, stateTimeStep: 4,
			rightPanel: 'terminal', printCodeVersion: 1 }),
		// 15: V1 slow first iteration done
		s({ phase: 'print', showHeading: false, stateTimeStep: 5,
			rightPanel: 'terminal', printCodeVersion: 1,
			printDotsVisibleRow1: v1Iter0Dots,
			printTerminalLines: terminalLinesV1Iter0 }),
		// 16: V1 fast-forward done
		s({ phase: 'print', showHeading: false, stateTimeStep: 5,
			rightPanel: 'terminal', printCodeVersion: 1,
			printDotsVisibleRow1: printDotsRow1.length,
			printTerminalLines: terminalLinesV1All }),
		// 17: add second print, clear dots/terminal
		s({ phase: 'print', showHeading: false, stateTimeStep: 6,
			rightPanel: 'terminal', printCodeVersion: 2 }),
		// 18: V2 slow first iteration done
		s({ phase: 'print', showHeading: false, stateTimeStep: 7,
			rightPanel: 'terminal', printCodeVersion: 2,
			printDotsVisibleRow1: v2Iter0DotsR1, printDotsVisibleRow2: v2Iter0DotsR2,
			printTerminalLines: terminalLinesV2Iter0 }),
		// 19: V2 fast-forward done
		s({ phase: 'print', showHeading: false, stateTimeStep: 7,
			rightPanel: 'terminal', printCodeVersion: 2,
			printDotsVisibleRow1: printDotsRow1.length, printDotsVisibleRow2: printDotsRow2.length,
			printTerminalLines: terminalLinesV2All }),
		// 20: zigzag interleaved line
		s({ phase: 'print', showHeading: false, stateTimeStep: 10,
			rightPanel: 'terminal', printCodeVersion: 2,
			printDotsVisibleRow1: printDotsRow1.length, printDotsVisibleRow2: printDotsRow2.length,
			printTerminalLines: terminalLinesV2All }),
		// 21: autopsy — blue vertical bars
		s({ phase: 'autopsy', showHeading: false, stateTimeStep: 11 }),
	]

	// ── Apply a snapshot to all mutable state + tweens ──
	function applySnapshot(snap: StepSnapshot, skipAnim: boolean) {
		phase = snap.phase
		showHeading = snap.showHeading
		titleLabel = snap.titleLabel
		showAxisCode = snap.showAxisCode
		axisCodeHighlight = snap.axisCodeHighlight
		showCostTerminal = snap.showCostTerminal
		showStateVarLabels = snap.showStateVarLabels
		showCostLabels = snap.showCostLabels
		rightPanel = snap.rightPanel
		stateTimeStep = snap.stateTimeStep
		printCodeVersion = snap.printCodeVersion
		bpDebuggerHighlightLine = snap.bpDebuggerHighlightLine
		bpDebuggerIteration = snap.bpDebuggerIteration
		printDebuggerHighlightLine = snap.printDebuggerHighlightLine
		instantHighlight = snap.instantHighlight
		printDotsVisibleRow1 = snap.printDotsVisibleRow1
		printDotsVisibleRow2 = snap.printDotsVisibleRow2
		printTerminalLines = snap.printTerminalLines
		unifiedAccentLines = snap.unifiedAccentLines
		autopsyVisibleCount = 0

		const opts = skipAnim ? { duration: 0 } : {}
		psLabel.to(snap.psLabel, opts)
		tLabel.to({ ...snap.tLabel, rotate: snap.tLabel.rotate ?? 0 }, opts)
		axisFade.to(snap.axisFade, opts)
		bpX.to({ x: snap.bpX }, opts)

		snap.stateVarLabelTargets.forEach((t, i) => {
			stateVarLabels[i].to({ ...t, fontSize: 36 }, opts)
		})
		snap.costLabelTargets.forEach((t, i) => {
			costLabels[i].to({ ...t, fontSize: 36 }, opts)
		})
	}

	// ── Progressive animations for steps that have line-by-line playback ──
	const STEP_ANIMATIONS: Partial<Record<number, (signal: AbortSignal) => Promise<void>>> = {
		// Step 11: one slow breakpoint "Continue"
		11: async (signal) => {
			// Start from step 10's end state
			bpDebuggerHighlightLine = COST_LINE_IDX
			bpDebuggerIteration = 0
			bpX.to({ x: tr.breakpointXPositions[0] ?? 200 }, { duration: 0 })
			const barDuration = bpHighlightPath.length * SLOW_LINE_DELAY
			await all(
				bpX.to({ x: tr.breakpointXPositions[1] ?? 420 }, { duration: barDuration }),
				(async () => {
					for (const line of bpHighlightPath) {
						if (signal.aborted) return
						bpDebuggerHighlightLine = line
						await sleep(SLOW_LINE_DELAY, signal)
					}
					bpDebuggerIteration = 1
				})(),
			)
		},
		// Step 12: fast-forward remaining breakpoint iterations
		12: async (signal) => {
			instantHighlight = true
			bpDebuggerIteration = 1
			bpX.to({ x: tr.breakpointXPositions[1] ?? 420 }, { duration: 0 })
			const maxIter = Math.min(tr.breakpointXPositions.length, 8)
			for (let iter = 2; iter < maxIter; iter++) {
				if (signal.aborted) break
				const barDuration = bpHighlightPath.length * FAST_LINE_DELAY
				await all(
					bpX.to({ x: tr.breakpointXPositions[iter] }, { duration: barDuration }),
					(async () => {
						for (const line of bpHighlightPath) {
							if (signal.aborted) return
							bpDebuggerHighlightLine = line
							await sleep(FAST_LINE_DELAY, signal)
						}
						bpDebuggerIteration = iter
					})(),
				)
			}
			instantHighlight = false
		},
		// Step 14: flash accent lines when print is added
		14: async (signal) => {
			unifiedAccentLines = tr.codeVariants.printV1.printLines
			await sleep(800, signal)
			if (!signal.aborted) unifiedAccentLines = []
		},
		// Step 15: V1 slow first iteration
		15: async (signal) => {
			printDotsVisibleRow1 = 0
			printTerminalLines = []
			for (const line of printExecPathV1[0]) {
				if (signal.aborted) return
				printDebuggerHighlightLine = line
				if (line === FIRST_PRINT_LINE) {
					printDotsVisibleRow1 += 1
					const out = tr.traces.printV1[0].printOutputs[printDotsVisibleRow1 - 1]
					if (out) printTerminalLines = [...printTerminalLines, out.text]
				}
				await sleep(SLOW_LINE_DELAY, signal)
			}
		},
		// Step 16: V1 fast-forward remaining iterations
		16: async (signal) => {
			instantHighlight = true
			// Start from end of step 15
			printDotsVisibleRow1 = v1Iter0Dots
			printTerminalLines = [...terminalLinesV1Iter0]
			for (let iter = 1; iter < printExecPathV1.length; iter++) {
				for (const line of printExecPathV1[iter]) {
					if (signal.aborted) { instantHighlight = false; return }
					printDebuggerHighlightLine = line
					if (line === FIRST_PRINT_LINE) {
						printDotsVisibleRow1 += 1
						const out = tr.traces.printV1[iter].printOutputs.find(o => o.line === FIRST_PRINT_LINE)
						if (out) printTerminalLines = [...printTerminalLines, out.text]
					}
					await sleep(FAST_LINE_DELAY, signal)
				}
			}
			printDebuggerHighlightLine = -1
			instantHighlight = false
		},
		// Step 17: flash accent lines when second print is added
		17: async (signal) => {
			unifiedAccentLines = tr.codeVariants.printV2.printLines
			await sleep(800, signal)
			if (!signal.aborted) unifiedAccentLines = []
		},
		// Step 18: V2 slow first iteration
		18: async (signal) => {
			printDotsVisibleRow1 = 0
			printDotsVisibleRow2 = 0
			printTerminalLines = []
			for (const line of printExecPathV2[0]) {
				if (signal.aborted) return
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
				await sleep(SLOW_LINE_DELAY, signal)
			}
		},
		// Step 19: V2 fast-forward remaining iterations
		19: async (signal) => {
			instantHighlight = true
			printDotsVisibleRow1 = v2Iter0DotsR1
			printDotsVisibleRow2 = v2Iter0DotsR2
			printTerminalLines = [...terminalLinesV2Iter0]
			for (let iter = 1; iter < printExecPathV2.length; iter++) {
				for (const line of printExecPathV2[iter]) {
					if (signal.aborted) { instantHighlight = false; return }
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
					await sleep(FAST_LINE_DELAY, signal)
				}
			}
			printDebuggerHighlightLine = -1
			instantHighlight = false
		},
	}

	// ── Apply step: called directly from Actions and slide entry ──
	let chartAbort: AbortController | null = null
	let chartReady = $state(false)

	function applyStep(step: number, skipAnim: boolean) {
		// Cancel any running progressive animation
		chartAbort?.abort()
		chartAbort = null

		const snap = STEPS[step]
		if (!snap) return

		// During initial restore (before slide is ready), always skip animations
		const effectiveSkip = skipAnim || !chartReady
		applySnapshot(snap, effectiveSkip)

		if (!effectiveSkip && STEP_ANIMATIONS[step]) {
			const ac = new AbortController()
			chartAbort = ac
			STEP_ANIMATIONS[step]!(ac.signal).then(() => {
				// Ensure we land on exact end state after animation completes
				if (!ac.signal.aborted) applySnapshot(snap, true)
			})
		}
	}

	// Mark chart as ready after initial action replay completes
	onMount(() => {
		requestAnimationFrame(() => { chartReady = true })
	})

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
				loopBpX.to({ x: tr.breakpointXPositions[iter] })
				loopBpIteration = iter
				loopVars = tr.breakpointSnapshots[iter]
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
			if (!cancelled) await sleep(500)
		}
	}

	// ── Comparison chart (post-tension slide) ──
	let compChartStep = $state(0)
	let affordChartStep = $state(0)
	let computedColStep = $state(0)
	let groupFilterStep = $state(0)

	// ── Grouping & filtering: free_shipping True/False dots ──
	const freeShippingY = printDotsRow2.length > 0 ? printDotsRow2[0][1] : 307
	const freeShipTrueIndices = new Set(printDotsRow2Indices)
	const groupFilterDots: { x: number; isTrue: boolean; idx: number }[] = autopsySlices.map((x, i) => ({
		x,
		isTrue: freeShipTrueIndices.has(i),
		idx: i,
	}))
	const trueDots = groupFilterDots.filter(d => d.isTrue)
	const falseDots = groupFilterDots.filter(d => !d.isTrue)
	// Redistributed positions for true dots (evenly spaced between first and last true dot positions)
	const trueFirstX = trueDots.length > 0 ? trueDots[0].x : 110
	const trueLastX = trueDots.length > 0 ? trueDots[trueDots.length - 1].x : 810
	const trueRedistributed = trueDots.map((_, i) => trueFirstX + (i / Math.max(trueDots.length - 1, 1)) * (trueLastX - trueFirstX))

	// ── Computed columns: total() row below price ──
	// Price row Y and total() row Y (offset below price)
	const priceRowY = printDotsRow1.length > 0 ? printDotsRow1[0][1] : 307
	const totalRowY = Math.min(priceRowY + 80, 400) // 80px below price, clamped
	const middlePriceDotIdx = Math.floor(printDotsRow1.length / 2)
	// total() dots share x-positions with price dots
	const totalDots: [number, number][] = printDotsRow1.map(([x]) => [x, totalRowY])

	// ── Video elements ──
	let vidStackTrace: HTMLVideoElement
	let vidStreams: HTMLVideoElement
	let vidStepping: HTMLVideoElement
	let vidComputed: HTMLVideoElement
	let vidAggFilter: HTMLVideoElement

	function restartVideo(el: HTMLVideoElement) {
		if (!el) return
		el.currentTime = 0
		el.playbackRate = 1.5
		el.play()
	}

	// ── Step debugging random walk ──
	let stepDebugIdx = $state(0)
	let stepDebugPlaying = $state(false)
	let stepDebugTimer: ReturnType<typeof setTimeout> | null = null

	// Pre-compute a random-walk sequence of indices into printDotsInterleaved
	const stepDebugSequence: number[] = (() => {
		const seq: number[] = [0]
		let pos = 0
		const maxIdx = printDotsInterleaved.length - 1
		let forward = true
		while (pos < maxIdx) {
			if (forward) {
				const steps = 3 + Math.floor(Math.random() * 5) // 2–4
				for (let s = 0; s < steps && pos < maxIdx; s++) {
					pos++
					seq.push(pos)
				}
			} else {
				const steps = 1 + Math.floor(Math.random() * 3) // 0–2
				for (let s = 0; s < steps && pos > 0; s++) {
					pos--
					seq.push(pos)
				}
			}
			forward = !forward
		}
		return seq
	})()

	function startStepDebug() {
		if (stepDebugPlaying) return
		stepDebugPlaying = true
		stepDebugAdvance()
	}

	function stopStepDebug() {
		stepDebugPlaying = false
		if (stepDebugTimer) { clearTimeout(stepDebugTimer); stepDebugTimer = null }
	}

	function stepDebugAdvance() {
		if (!stepDebugPlaying) return
		if (stepDebugIdx < stepDebugSequence.length - 1) {
			stepDebugIdx++
			stepDebugTimer = setTimeout(stepDebugAdvance, 400)
		} else {
			stepDebugPlaying = false
		}
	}
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
		<Notes>
			Hello! I'm Jeff, a PhD student at Penn, and today I'm excited to tell you about
			Data-oriented Debugging, which is a new approach for thinking about the debugging process and debugging tools,
			and about autopsy, a new debugger that implements some of these ideas.
		</Notes>
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
			Just to introduce where I'm coming from with debugging.
			I used to be a senior software engineer in the industry, where I worked on auth, notifications, client/server sync.
			All things that are procedural, highly stateful, highly complex, prone to bugs, and really annoying to debug.
			And in all that time I was one of those programmers who always used print statements to debug.
			But I found the debugging tools at my disposal unsatisfying.
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
		const cf = document.querySelector('.current-fragment')
		if (!cf) {
			chartStep = 0
			applyStep(0, true)
		}
	}}>
		<!-- ═══════════════════════════════════════════════════
		     LAYOUT: 3-panel grid that morphs between phases
		     Left: state×time chart (hidden in 'code' phase)
		     Right-top: code editor (full-screen in 'code' phase, small otherwise)
		     Right-bottom: variables or terminal panel
		     ═══════════════════════════════════════════════════ -->
		<div class="relative h-full w-full overflow-hidden">

				<!-- ── State×Time Chart (left region) ── -->
			<div
				class="absolute top-0 left-0 bottom-0 transition-all duration-700"
				style="
					width: {phase === 'code' ? '0%' : phase === 'chart' || phase === 'autopsy' ? '100%' : '58%'};
					opacity: {phase === 'code' ? 0 : 1};
				"
			>
				<div class="relative flex h-full items-center justify-center overflow-hidden">
					<svg viewBox="0 0 900 520" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
						<!-- Plot background -->
						<rect x="100" y="40" width="720" height="420" fill="white" />

						<!-- Step 1: Breakpoint — animated vertical slice -->
						<g visibility={stateTimeStep === 1 ? 'visible' : 'hidden'}>
							<rect x={bpX.x - 12} y="40" width="24" height="420" fill="#1E40AF"
								style="opacity: 0; animation: appear 0.3s ease-out 0ms forwards" />
						</g>

						<!-- Step 5–7: Print — row 1 dots (with per-row lines) -->
						<g visibility={stateTimeStep >= 5 && stateTimeStep <= 7 ? 'visible' : 'hidden'}>
							{#each printDotsRow1.slice(0, printDotsVisibleRow1) as [cx, cy], i}
								{#if i > 0}
									<line x1={printDotsRow1[i-1][0]} y1={printDotsRow1[i-1][1]} x2={cx} y2={cy}
										stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
								{/if}
								<circle {cx} {cy} r="6" fill="#991B1B"
									style="opacity: 0; animation: appear 0.15s ease-out 0ms forwards" />
							{/each}
						</g>

						<!-- Step 7: Print — row 2 dots (with per-row lines) -->
						<g visibility={stateTimeStep === 7 ? 'visible' : 'hidden'}>
							{#each printDotsRow2.slice(0, printDotsVisibleRow2) as [cx, cy], i}
								{#if i > 0}
									<line x1={printDotsRow2[i-1][0]} y1={printDotsRow2[i-1][1]} x2={cx} y2={cy}
										stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
								{/if}
								<circle {cx} {cy} r="6" fill="#991B1B"
									style="opacity: 0; animation: appear 0.15s ease-out 0ms forwards" />
							{/each}
						</g>

						<!-- Step 10: Print — zigzag interleaved line connecting dots in execution order -->
						<g visibility={stateTimeStep === 10 ? 'visible' : 'hidden'}>
							{#each printDotsInterleaved as [cx, cy], i}
								{#if i > 0}
									<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
										stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
										style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
								{/if}
								<circle {cx} {cy} r="6" fill="#991B1B"
									style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
							{/each}
						</g>

						<!-- Row labels for print dots -->
						{#if printDotsRow1.length > 0}
							<text x={printDotsRow1[0][0]} y={printDotsRow1[0][1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#991B1B"
								visibility={stateTimeStep >= 5 ? 'visible' : 'hidden'}>price</text>
						{/if}
						{#if printDotsRow2.length > 0}
							<text x={printDotsRow2[0][0]} y={printDotsRow2[0][1] - 14} font-family="var(--r-code-font)" font-size="20" fill="#991B1B"
								visibility={stateTimeStep >= 7 ? 'visible' : 'hidden'}>free_shipping</text>
						{/if}

						<!-- Autopsy vertical bars -->
						<g visibility={stateTimeStep >= 11 ? 'visible' : 'hidden'}>
							{#each autopsySlices as x, i}
								<rect x={x - 12} y="40" width="24" height="420" fill="#1E40AF" rx="4" fill-opacity="0.20"
									style="opacity: 0; animation: appear 0.15s ease-out {i * 60}ms forwards" />
							{/each}
						</g>

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
						<g visibility={showStateVarLabels ? 'visible' : 'hidden'}>
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
						</g>

						<!-- Cost value labels along X-axis -->
						<g visibility={showCostLabels ? 'visible' : 'hidden'}>
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
						</g>
					</svg>

					<!-- Code overlay for axis build-up (state-vars / cost highlighting) -->
					<div class="absolute flex items-stretch justify-center gap-4"
						style="pointer-events: none; width: 75%; left: 12.5%; display: {showAxisCode ? 'flex' : 'none'};"
					>
						<div
							class="rounded-xl border border-gray-200 bg-white/95 px-8 py-6 shadow-xl"
							style="flex: 2 1 0; opacity: {axisFade.codeOpacity}"
						>
							<pre class="text-5xl leading-relaxed font-mono text-gray-800"><span class="text-gray-500">for </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">item</span><span class="text-gray-500"> in </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">cart</span><span class="text-gray-500">:</span>
<span class="text-gray-500">    if </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">item.qty</span><span class="text-gray-500"> >= 10:</span>
<span class="text-gray-500">        </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' || axisCodeHighlight === 'cost' ? 'bg-yellow-200' : 'bg-transparent'}">item.price</span><span class="text-gray-500"> *= 0.9</span>
<span class="text-gray-500">    ...</span>
<span class="text-gray-500">    if </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' || axisCodeHighlight === 'cost' ? 'bg-yellow-200' : 'bg-transparent'}">item.total()</span><span class="text-gray-500"> &gt; 35:</span>
<span class="text-gray-500">        </span><span class="rounded px-0.5 transition-colors duration-300 {axisCodeHighlight === 'state-vars' ? 'bg-yellow-200' : 'bg-transparent'}">item.free_shipping</span><span class="text-gray-500"> = True</span></pre>
						</div>
						<div
							class="rounded-xl border border-gray-800 bg-gray-900 px-5 py-4 font-mono text-2xl leading-relaxed text-green-400 overflow-y-auto text-left"
							style="flex: 1 1 0; opacity: {axisFade.terminalOpacity}; display: {showCostTerminal ? 'block' : 'none'}"
						>
							{#each terminalLines as [label, value]}
								<p>{label} <span class="text-white">{value}</span></p>
							{/each}
						</div>
					</div>

					<!-- Technique label (top-right of chart area during 3-panel, or top-right of full area) -->
					<div class="absolute left-[4%] top-[6%] rounded-md bg-white/85 px-4 py-2 text-left"
						style="display: {stateTimeStep >= 1 ? 'block' : 'none'}"
					>
						<p class="text-5xl font-bold text-[#1E40AF]"
							style="display: {stateTimeStep === 1 ? 'block' : 'none'}"
						>breakpoint debugger</p>
						<p class="text-3xl text-gray-500"
							style="display: {stateTimeStep === 1 ? 'block' : 'none'}"
						>all state · one moment</p>
						<p class="text-5xl font-bold text-[#1E40AF]"
							style="display: {stateTimeStep >= 2 && stateTimeStep <= 10 ? 'block' : 'none'}"
						>print debugging</p>
						<p class="text-3xl text-gray-500"
							style="display: {stateTimeStep >= 2 && stateTimeStep <= 10 ? 'block' : 'none'}"
						>some state · many moments</p>
					</div>
				</div>
			</div>

			<!-- ── Right panels region (code + variables/terminal) ── -->
			<div
				class="absolute top-0 bottom-0 flex flex-col transition-all duration-700"
				class:justify-center={phase === 'code'}
				class:gap-8={phase === 'code'}
				class:gap-3={phase !== 'code'}
				style="
					right: 0;
					width: {phase === 'code' ? '100%' : phase === 'chart' ? '50%' : '42%'};
					padding: {phase === 'code' ? '4rem 5rem' : '0.75rem'};
				"
			>
				<!-- ── Heading (moves with panel, then slides off top) ── -->
				<div
					class="transition-all duration-700"
					style="
						opacity: {showHeading ? 1 : 0};
						transform: translateY({showHeading ? 0 : -200}px);
						max-height: {showHeading ? '10rem' : '0'};
					"
				>
					<h2 class="text-left text-8xl font-bold text-black whitespace-nowrap">How do you debug this?</h2>
				</div>

				<!-- ── Code editor panel ── -->
				<div
					class="overflow-hidden"
					style="
						flex: {phase === 'breakpoint' || phase === 'print' ? '1 1 0' : 'none'};
						opacity: {phase === 'autopsy' ? 0 : codeTransform.opacity};
						transform: scale({phase === 'code' ? 1 : phase === 'chart' ? 0.5 : 1});
						transform-origin: top right;
						min-height: 0;
						transition: opacity 700ms, transform 700ms;
					"
				>
					<!-- In code phase, show a full-size Code component with syntax highlighting -->
					<div class="rounded-xl border border-gray-200 bg-gray-50 p-6 shadow-sm overflow-hidden text-left"
						style="display: {phase === 'code' ? 'block' : 'none'}"
					>
						<Code
							bind:this={code}
							lang="python"
							theme="github-light"
							code={codeInitial}
							options={{ duration: 400, stagger: 0, lineNumbers: true, containerStyle: false, enhanceMatching: true, splitTokens: true }}
							class="text-5xl"
						/>
					</div>
					<!-- In chart/breakpoint/print phases, show CodeOverlay -->
					<div style="display: {phase !== 'code' ? 'contents' : 'none'}">
						<CodeOverlay
							lines={unifiedCodeLines}
							highlightLine={unifiedHighlightLine}
							accentLines={unifiedAccentLines}
							markers={unifiedMarkers}
							instant={instantHighlight}
						/>
					</div>
				</div>

				<!-- ── Bottom-right panel: Variables pane or Terminal ── -->
				<div
					class="overflow-hidden"
					style="
						flex: {rightPanel !== 'none' ? '1 1 0' : '0 0 0px'};
						opacity: {rightPanel !== 'none' ? 1 : 0};
						min-height: 0;
						transition: opacity 500ms;
					"
				>
					<div style="display: {rightPanel === 'variables' ? 'contents' : 'none'}">
						<VariablesPane
							variables={tr.breakpointSnapshots[bpDebuggerIteration]}
							style="height: 100%"
						/>
					</div>
					<div
						bind:this={terminalEl}
						class="rounded-xl border border-gray-800 bg-gray-900 p-4 font-mono text-xl leading-relaxed text-green-400 text-left overflow-y-auto h-full"
						style="display: {rightPanel === 'terminal' ? 'block' : 'none'}"
					>
						<p class="text-gray-400 text-lg mb-2">Terminal</p>
						{#each printTerminalLines as line}
							<p>{line}</p>
						{/each}
					</div>
				</div>
			</div>
		</div>

		<!-- ════════════════════════════════════════════════════
		     Step-driven Actions: each just increments/decrements chartStep
		     ════════════════════════════════════════════════════ -->
		{#each { length: TOTAL_STEPS - 1 } as _, i}
			<Action
				do={() => { chartStep = i + 1; applyStep(i + 1, false) }}
				undo={() => { chartStep = i; applyStep(i, false) }}
			/>
		{/each}

		<Notes>
			<p>
				Let's start with an example to illustrate what I see are some issues with current debuggers.
				You're working on an online retail payment processing pipeline.
				It does some conventional things retailers do, such as giving a discount on bulk orders, and free shipping on orders above a certain cost.
			</p>

			<p>
				You've maybe already spotted the bug: sometimes a customer will get a discount for a bulk order and that'll take away what was previously going to be their free shipping, which isn't a good experience.
				This is a toy example, but it represents a pretty common issue: the logic looks reasonable locally, but produces unreasonable results when composed.
			</p>

			<hr>

			We're going to analyze how a programmer might use different debuggers to understand this problem.
			But first I need to introduce this visualization I call the state-time chart, which we'll use to understand what different debuggers can do.
			First, let me give you some intuition about how this chart works.

			<hr>

			On the vertical axis we have all state across all scopes of the program.

			<hr>

			In our toy example this is all of the fields of the item and the cart.

			<hr>

			Imagine these various pieces of the program state distributed at different locations along the vertical axis.

			<hr>

			Next, the horizontal axis represents time. Really it's discretized by the program counter.

			<hr>

			As each statement in the program executes, computation happens. Take item price here -- as we process each item we calculate a price for it.

			<hr>

			For a certain row across the chart, a particular variable is taking on different values, with increasing time as we move to the right.

			<hr>

			Okay that's the state-time chart. Let's use it to understand how a debugger works.

			<hr>

			Breakpoint debugging pauses execution at a particular point in time.
			When paused, you have access to arbitrary state at every frame of the call stack, which is shown in the variables panel in the bottom right.

			<hr>

			When I press continue, the program runs until it hits the breakpoint again, and I can see all of the state everywhere at this new moment.

			This can be great! It leaves you flexible and doesn't require you to predict in advance what state will be relevant to your debugging.

			<hr>

			And as I continue to use my breakpoint debugger, I'm proceeding through a sequence of stack traces, each of which is a complete vertical slice of state, but at a different point in time.

			So I like that I can see all of the state and know that it's all related because it's all from the same moment in time, but I have to keep track of the history of how I got to this point in my head, and I have to decide when to pause and inspect state.

			<hr>
			
			Next, let's examine print debugging. 

			<hr>

			When I add a print statement to the code,

			<hr>

			when execution runs over the print statement, I get a log entry in my terminal, shown in the bottom right, that shows me the values of some variables that I choose at that moment in time.

			<hr>

			As the entire program executes, I get a bunch of logs in my terminal, each corresponding to a particular value taken on by a specific part of the program state.
			Each of these dots represents a particular log entry, which you can think of as storing that particular state-time value.
			They're arranged horizontally because they all represent state pulled from the same place in the code.

			<hr>

			Now, if I add a second print line

			<hr>

			as the program executes, I get logs whenever one of these print statements executes.

			<hr>

			And when the whole program executes, I get logs from both print statements, extracting different states from different times.
			Programmers often insert multiple print statement probes in their code, precisely because, in contrast to breakpoints, it helps them understand sequences of events.

			But recall the blue bars of the breakpoint debugger. You no longer have access to complete information about each moment in time.

			<br>

			And also, where I put my print statements and how the program actually executes determines how the information I get is displayed to me.
			I don't have two neat, separated rows of logs. I have this zigzag interleaving of them.
			This helps me in situations where I want to understand the history of execution, but it makes it hard to understand the execution in any other way besides chronologically.


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
			<p>
				We conducted interviews with 12 experienced industry software engineers to understand their debugging practices and why they preferred certain tools and techniques.
				One major theme that emerged was that their debugging strategies often involved this active negotiation with collecting and viewing information about execution.
			</p>

			<p>
				Sometimes they worried about collecting too much. One participant told us that unnecessary information could cause them to lose out on the meaningful thing that would help them understand the bug.
			</p>

			<p>
				Another participant said that a poorly placed breakpoint could disrupt their workflow if it was hit a lot.
			</p>

			<hr>

			<p>On the other hand, they also worried about not having enough information to understand their bugs. They felt this more acutely the longer it took to get new debugging data.</p>
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
		<Notes>
			<p>
				This negotiation process puts these two instincts in tension. On the one hand, I'm inclined to collect more information because it'll help me make sense of the problem.
				But on the other hand, I worry that if I collect too much, I won't even be able understand what I'm looking at.
			</p>

			<p>Needing to navigate this tension seems to me like incidental complexity of current debuggers, rather than an inherent part of debugging.</p>

			<p>
				I'm a databases person. When I hear this tension, my instinct is that I should be able to collect everything and that I should have good analysis tools that let me manage all of that data.
			</p>
		</Notes>
	</Slide>

	<!-- Slide: Why are they in tension? -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-8 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Why are they in tension?</h2>
			<ul class="flex flex-col gap-6 pl-6 text-5xl text-black list-disc">
				<li>Current debuggers <span class="text-[#0000FF]">couple collecting</span> execution data <span class="text-[#0000FF]">and analyzing</span> it</li>
				<li>Current debuggers lack affordances for <span class="text-[#0000FF]">transforming and comprehending</span> execution data</li>
			</ul>
		</div>
		<Notes>
			<p>But where is this tension coming from in current debuggers? Well, the design of both debugging tools couples collection and analysis.</p>

			<p>
				There's nothing you can do with print debugging output besides browsing it and performing text search on it.
				And your print statements fix output, forcing you to see only what you've logged, but also forcing you to see everything you've logged.
			</p>
			<p>
				On the other hand, interactive debugging with a breakpoint debugger is almost the opposite: it forces you to continually make decisions about what data to collect next.
				You're constantly switching between deciding where to go next and analyzing what you can now see.
			</p>

			On the analysis side, neither has affordances to aid your reasoning beyond just showing you the data. I'll get back to that in a minute.
			First, let's examine what better collection could look like.
		</Notes>
	</Slide>

	<!-- Slide: State×time comparison — breakpoint → print → autopsy -->
	<Slide class="h-full" in={() => { compChartStep = 0 }}>
		<div class="flex h-full flex-col items-center justify-center gap-4 px-12">
			<h2 class="w-[80%] text-left text-7xl font-bold text-black">Collection</h2>
			<svg viewBox="0 0 900 520" width="80%" preserveAspectRatio="xMidYMid meet">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="white" stroke="#e5e7eb" stroke-width="1" />

				<!-- Y-axis label -->
				<text x="50" y="250" text-anchor="middle" font-family="Lato, sans-serif" font-size="36"
					fill="black" transform="rotate(-90 50 250)">program state</text>

				<!-- X-axis label -->
				<text x="460" y="500" text-anchor="middle" font-family="Lato, sans-serif" font-size="36"
					fill="black">time</text>

				<!-- Step 0: Breakpoint — single vertical bar (visible on enter) -->
				{#if compChartStep === 0}
					<rect x={tr.breakpointXPositions[3] - 12} y="40" width="24" height="420" fill="#1E40AF" />
					<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
						fill="#1E40AF" font-weight="bold">breakpoint debugger</text>
				{/if}

				<!-- Step 1: Breakpoint fades out, print fades in simultaneously -->
				{#if compChartStep === 1}
					<rect x={tr.breakpointXPositions[3] - 12} y="40" width="24" height="420" fill="#1E40AF"
						style="animation: disappear 0.4s ease-out forwards" />
					<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
						fill="#1E40AF" font-weight="bold"
						style="animation: disappear 0.4s ease-out forwards">breakpoint debugger</text>

					{#each printDotsInterleaved as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
								style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B"
							style="opacity: 0; animation: appear 0.1s ease-out {i * 30}ms forwards" />
					{/each}
					{#if printDotsRow1.length > 0}
						<text x={printDotsRow1[0][0]} y={printDotsRow1[0][1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#991B1B"
							style="opacity: 0; animation: appear 0.3s ease-out forwards">price</text>
					{/if}
					{#if printDotsRow2.length > 0}
						<text x={printDotsRow2[0][0]} y={printDotsRow2[0][1] - 14} font-family="var(--r-code-font)" font-size="20" fill="#991B1B"
							style="opacity: 0; animation: appear 0.3s ease-out forwards">free_shipping</text>
					{/if}
					<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
						fill="#991B1B" font-weight="bold"
						style="opacity: 0; animation: appear 0.5s ease-out 0.3s forwards">print debugging</text>
				{/if}

				<!-- Step 2: Autopsy — retain print dots (no animation), add blue bars -->
				{#if compChartStep === 2}
					<!-- Blue vertical bars (animated) -->
					{#each autopsySlices as x, i}
						<rect x={x - 12} y="40" width="24" height="420" fill="#1E40AF" rx="4" fill-opacity="0.20"
							style="opacity: 0; animation: appear 0.15s ease-out {i * 60}ms forwards" />
					{/each}

					<!-- Print dots retained (static) -->
					{#each printDotsInterleaved as [cx, cy], i}
						{#if i > 0}
							<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
						{/if}
						<circle {cx} {cy} r="6" fill="#991B1B" />
					{/each}

					<!-- Row labels (static) -->
					{#if printDotsRow1.length > 0}
						<text x={printDotsRow1[0][0]} y={printDotsRow1[0][1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">price</text>
					{/if}
					{#if printDotsRow2.length > 0}
						<text x={printDotsRow2[0][0]} y={printDotsRow2[0][1] - 14} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">free_shipping</text>
					{/if}

					<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
						fill="#1E40AF" font-weight="bold"
						style="font-family: var(--r-code-font); opacity: 0; animation: appear 0.5s ease-out forwards">autopsy</text>
				{/if}
			</svg>
		</div>

		<Action do={() => { compChartStep = 1 }} undo={() => { compChartStep = 0 }} />
		<Action do={() => { compChartStep = 2 }} undo={() => { compChartStep = 1 }} />

		<Notes>
			So we saw that breakpoints let you see all of the state at one particular moment in time.

			<hr>

			And print statements let you see particular pieces of state across many moments in time, and in order.

			<hr>

			Well, from a pure data collection perspective, it sure would be nice to get all state at all moments in time.
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
			<p><span class="font-mono">autopsy.log()</span> calls capture <span class="text-[#0000FF]">full stack traces</span></p>
		</div>
		<Notes>
			<p>
			This is exactly what we designed autopsy to do. The first part of autopsy is a python debugging library.
			The way you use it to instrument code looks a lot like print debugging: you just import log from autopsy and sprinkle calls to log throughout your code base.
			</p>

			<p>
			The interesting extra bit is that it captures full stack traces, not just the expressions you pass it.
			Here, a full stack trace means every stack frame, and every variable in every stack frame. This is all of the information you get when paused on a breakpoint.
			</p>
		</Notes>
	</Slide>

	<!-- Slide: Call stack in History view -->
	<Slide class="h-full" in={() => restartVideo(vidStackTrace)}>
		<div class="flex h-full flex-col items-center justify-center">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video bind:this={vidStackTrace} src="/stack_trace.mp4" loop muted playsinline style="width: 90%; border-radius: 0.5rem; box-shadow: 0 4px 24px rgba(0,0,0,0.15);"></video>
		</div>
		<Notes>
			And so, one view of the autopsy interface is like your chronological print statement output,
			except that you can click on any log entry and see the full stack trace for that moment in time, just like you would see if you were paused at a breakpoint.

			It gives you all of the data you asked for, and more on demand.
		</Notes>
	</Slide>

	<!-- Slide: Affordances — Print → table revelation -->
	<Slide class="h-full">
		<div class="flex h-full flex-col items-center justify-center gap-8 px-20 py-12">
			<div class="flex items-center justify-center gap-6">
				<div class="flex flex-col items-center gap-2">
					<img src="js_console.png" alt="JavaScript console output" class="rounded-lg shadow-lg" style="max-height: 55vh;" />
					<p class="text-2xl text-gray-500">Print Output</p>
				</div>
				<svg width="80" height="60" viewBox="0 0 80 60" class="shrink-0">
					<defs>
						<marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
							<polygon points="0 0, 10 3.5, 0 7" fill="#374151" />
						</marker>
					</defs>
					<line x1="5" y1="30" x2="65" y2="30" stroke="#374151" stroke-width="3" marker-end="url(#arrowhead)" />
				</svg>
				<div class="flex flex-col items-center gap-2">
					<img src="pandas.png" alt="Pandas DataFrame output" class="rounded-lg shadow-lg" style="max-height: 55vh;" />
					<p class="text-2xl text-gray-500">DataFrame?</p>
				</div>
			</div>
		</div>
		<Notes>
			Next, on to analysis affordances.

			This project was partially born from me looking at the JavaScript console, looking at how different logs were separated by lines,
			and thinking to myself, "Isn't this a table? Shouldn't I be able to do more things with this?" which is when I began to see my debugging logs as a dataset in themselves,
			where I had previously been thinking of them as the end of where tooling could help me.
		</Notes>
	</Slide>

	<!-- Slide: Autopsy state×time chart — analysis affordances preview -->
	<Slide class="h-full" in={() => { affordChartStep = 0 }}>
		<div class="flex h-full flex-col items-center justify-center gap-4 px-12">
			<h2 class="w-[80%] text-left text-7xl font-bold text-black">Affordances — Streams</h2>
			<svg viewBox="0 0 900 520" width="80%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="white" />

				<!-- Autopsy vertical bars (static) -->
				{#each autopsySlices as x, i}
					<rect x={x - 12} y="40" width="24" height="420" fill="#1E40AF" rx="4" fill-opacity="0.20" />
				{/each}

				<!-- Red horizontal bars (animated in on step 1) -->
				{#if affordChartStep >= 1}
					{#if printDotsRow1.length > 0}
						<rect x="100" y={printDotsRow1[0][1] - 12} width="720" height="24" fill="#991B1B" rx="4" fill-opacity="0.20"
							style={affordChartStep === 1 ? 'opacity: 0; animation: appear 0.15s ease-out forwards' : ''} />
					{/if}
					{#if printDotsRow2.length > 0}
						<rect x="100" y={printDotsRow2[0][1] - 12} width="720" height="24" fill="#991B1B" rx="4" fill-opacity="0.20"
							style={affordChartStep === 1 ? 'opacity: 0; animation: appear 0.15s ease-out 60ms forwards' : ''} />
					{/if}
				{/if}

				<!-- Print dots (both rows, interleaved with lines) -->
				{#each printDotsInterleaved as [cx, cy], i}
					{#if i > 0}
						<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
							stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
					{/if}
					<circle {cx} {cy} r="6" fill="#991B1B" />
				{/each}

				<!-- Row labels -->
				{#if printDotsRow1.length > 0}
					<text x={printDotsRow1[0][0]} y={printDotsRow1[0][1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">price</text>
				{/if}
				{#if printDotsRow2.length > 0}
					<text x={printDotsRow2[0][0]} y={printDotsRow2[0][1] - 14} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">free_shipping</text>
				{/if}

				<!-- Axes -->
				<line x1="100" y1="40" x2="100" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="100,33 94,47 106,47" fill="black" />
				<line x1="100" y1="460" x2="836" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="843,460 829,454 829,466" fill="black" />

				<!-- Axis labels -->
				<text x="50" y="250" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black" transform="rotate(-90 50 250)">program state</text>
				<text x="460" y="500" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black">time</text>

				<!-- Title -->
				<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="#1E40AF" font-weight="bold"
					style="font-family: var(--r-code-font)">autopsy</text>
			</svg>
		</div>
		<Action do={() => { affordChartStep = 1 }} undo={() => { affordChartStep = 0 }} />
		<Notes>
			To start, we briefly hit upon this ordering problem of only being able to see logs chronologically.
			One obvious affordance is letting you isolate the logs from different places in your code.
		</Notes>
	</Slide>

	<!-- Slide: Video — Streams -->
	<Slide class="h-full" in={() => restartVideo(vidStreams)}>
		<div class="flex h-full flex-col items-center justify-center">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video bind:this={vidStreams} src="/streams.mp4" loop muted playsinline style="width: 90%; border-radius: 0.5rem; box-shadow: 0 4px 24px rgba(0,0,0,0.15);"></video>
		</div>
		<Notes>
			By default, autopsy shows you this chronological view.
			But if you switch to this Streams view, they're separated by statement, letting you see all of the logs produced at a particular point in your code.
			And since all of those logs have the same set of arguments, they're presented in a table view, which has some nice properties we're about to see.
		</Notes>
	</Slide>

	<!-- Slide: Affordances — "Step" Debugging -->
	<Slide class="h-full" in={() => { stopStepDebug(); stepDebugIdx = 0 }}>
		<div class="flex h-full flex-col items-center justify-center gap-4 px-12">
			<h2 class="w-[80%] text-left text-7xl font-bold text-black">Affordances — "Step" Debugging</h2>
			<svg viewBox="0 0 900 520" width="80%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="white" />

				<!-- Single blue bar behind current dot -->
				<rect x={printDotsInterleaved[stepDebugSequence[stepDebugIdx]][0] - 12} y="40" width="24" height="420" fill="#1E40AF" rx="4" fill-opacity="0.20"
					style="transition: x 0.2s ease-out" />

				<!-- Print dots with lines -->
				{#each printDotsInterleaved as [cx, cy], i}
					{#if i > 0}
						<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
							stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
					{/if}
					<circle cx={cx} cy={cy} r="6" fill="#991B1B"
						style="transform-origin: {cx}px {cy}px; transform: scale({i === stepDebugSequence[stepDebugIdx] ? 1.7 : 1}); transition: transform 0.2s ease-out" />
				{/each}

				<!-- Row labels -->
				{#if printDotsRow1.length > 0}
					<text x={printDotsRow1[0][0]} y={printDotsRow1[0][1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">price</text>
				{/if}
				{#if printDotsRow2.length > 0}
					<text x={printDotsRow2[0][0]} y={printDotsRow2[0][1] - 14} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">free_shipping</text>
				{/if}

				<!-- Axes -->
				<line x1="100" y1="40" x2="100" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="100,33 94,47 106,47" fill="black" />
				<line x1="100" y1="460" x2="836" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="843,460 829,454 829,466" fill="black" />

				<!-- Axis labels -->
				<text x="50" y="250" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black" transform="rotate(-90 50 250)">program state</text>
				<text x="460" y="500" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black">time</text>

				<!-- Title -->
				<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="#1E40AF" font-weight="bold"
					style="font-family: var(--r-code-font)">autopsy</text>
			</svg>
		</div>
		<Action do={() => { startStepDebug() }} undo={() => { stopStepDebug(); stepDebugIdx = 0 }} />
		<Notes>
			<p>
				So autopsy can replace print debugging, and goes beyond it. But what about breakpoint debugging?
				We tried to give it a similar treatment for stepping. You should be able to follow along with the order that things were captured in.
			</p>

			<p>
				At each point, we can show you the same information the breakpoint debugger would have shown you, because we're capturing the full stack trace.
				And since this is all post-hoc analysis of captured logs, we can do the omniscient debugging thing of letting you step forwards and backwards and jump to arbitrary points.
			</p>
		</Notes>
	</Slide>

	<!-- Slide: Video — Step Debugging -->
	<Slide class="h-full" in={() => restartVideo(vidStepping)}>
		<div class="flex h-full flex-col items-center justify-center">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video bind:this={vidStepping} src="/stepping.mp4" loop muted playsinline style="width: 90%; border-radius: 0.5rem; box-shadow: 0 4px 24px rgba(0,0,0,0.15);"></video>
		</div>
		<Notes>
			<p>
				So here, next to any log in autopsy, I can click on this "Show in code" button, which gives me a code lens above the corresponding log statement.
				Then, I can click these buttons to step forwards and backwards through the logs.
				If I have multiple log statements, the view will jump around to them.
				And like I said, since I have the full stack trace, I can click on the log to see all of the information that a breakpoint debugger would have shown me.
			</p>

			<p>The one glaring difference is that this doesn't give me the same stepping experience as breakpoints since it only works when I have log statements. We'll get back to that at the end.</p>
		</Notes>
	</Slide>

	<!-- Slide: Affordances — Computed Columns -->
	<Slide class="h-full" in={() => { computedColStep = 0 }}>
		<div class="flex h-full flex-col items-center justify-center gap-4 px-12">
			<h2 class="w-[80%] text-left text-7xl font-bold text-black">Affordances — Computed Columns</h2>
			<svg viewBox="0 0 900 520" width="80%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="white" />

				<!-- Autopsy vertical bars (static) -->
				{#each autopsySlices as x, i}
					<rect x={x - 12} y="40" width="24" height="420" fill="#1E40AF" rx="4" fill-opacity="0.20" />
				{/each}

				<!-- Red horizontal bars for price and free_shipping (static, from Streams) -->
				{#if printDotsRow1.length > 0}
					<rect x="100" y={printDotsRow1[0][1] - 12} width="720" height="24" fill="#991B1B" rx="4" fill-opacity="0.20" />
				{/if}
				{#if printDotsRow2.length > 0}
					<rect x="100" y={printDotsRow2[0][1] - 12} width="720" height="24" fill="#991B1B" rx="4" fill-opacity="0.20" />
				{/if}

				<!-- Step 2: total() horizontal bar (animated) -->
				{#if computedColStep >= 2}
					<rect x="100" y={totalRowY - 12} width="720" height="24" fill="#991B1B" rx="4" fill-opacity="0.20"
						style="opacity: 0; animation: appear 0.3s ease-out forwards" />
				{/if}

				<!-- Print dots (both rows, interleaved with lines) -->
				{#each printDotsInterleaved as [cx, cy], i}
					{#if i > 0}
						<line x1={printDotsInterleaved[i-1][0]} y1={printDotsInterleaved[i-1][1]} x2={cx} y2={cy}
							stroke="#991B1B" stroke-width="2.5" stroke-linecap="round" />
					{/if}
					<circle {cx} {cy} r="6" fill="#991B1B" />
				{/each}

				<!-- Step 1: Highlight middle price dot + arrow to single total() dot -->
				{#if computedColStep >= 1}
					{@const midDot = printDotsRow1[middlePriceDotIdx]}
					{@const midTotal = totalDots[middlePriceDotIdx]}
					<!-- Highlight ring on middle price dot -->
					<circle cx={midDot[0]} cy={midDot[1]} r="12" fill="none" stroke="#991B1B" stroke-width="2"
						style="opacity: 0; animation: appear 0.3s ease-out forwards" />
					<!-- Arrow down to total dot -->
					<line x1={midDot[0]} y1={midDot[1] + 12} x2={midTotal[0]} y2={midTotal[1] - 8}
						stroke="#1E40AF" stroke-width="2" stroke-dasharray="4 3"
						marker-end="url(#arrowBlue)"
						style="opacity: 0; animation: appear 0.3s ease-out 0.2s forwards" />
					<!-- total() dot -->
					<circle cx={midTotal[0]} cy={midTotal[1]} r="6" fill="#1E40AF"
						style="opacity: 0; animation: appear 0.3s ease-out 0.3s forwards" />
					<!-- total() label (step 1 only, next to middle dot) -->
					{#if computedColStep === 1}
						<text x={midTotal[0]} y={midTotal[1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#1E40AF"
							style="opacity: 0; animation: appear 0.3s ease-out 0.4s forwards">total()</text>
					{/if}
				{/if}

				<!-- Step 2: All arrows + total dots + label aligned with leftmost -->
				{#if computedColStep >= 2}
					{#each printDotsRow1 as [px, py], i}
						{#if i !== middlePriceDotIdx}
							<line x1={px} y1={py + 8} x2={totalDots[i][0]} y2={totalDots[i][1] - 8}
								stroke="#1E40AF" stroke-width="2" stroke-dasharray="4 3"
								marker-end="url(#arrowBlue)"
								style="opacity: 0; animation: appear 0.2s ease-out {i * 40}ms forwards" />
							<circle cx={totalDots[i][0]} cy={totalDots[i][1]} r="6" fill="#1E40AF"
								style="opacity: 0; animation: appear 0.2s ease-out {i * 40 + 100}ms forwards" />
						{/if}
					{/each}
					<text x={totalDots[0][0]} y={totalDots[0][1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#1E40AF"
						style="opacity: 0; animation: appear 0.3s ease-out forwards">total()</text>
				{/if}

				<!-- Row labels -->
				{#if printDotsRow1.length > 0}
					<text x={printDotsRow1[0][0]} y={printDotsRow1[0][1] + 28} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">price</text>
				{/if}
				{#if printDotsRow2.length > 0}
					<text x={printDotsRow2[0][0]} y={printDotsRow2[0][1] - 14} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">free_shipping</text>
				{/if}

				<!-- Axes -->
				<line x1="100" y1="40" x2="100" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="100,33 94,47 106,47" fill="black" />
				<line x1="100" y1="460" x2="836" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="843,460 829,454 829,466" fill="black" />

				<!-- Axis labels -->
				<text x="50" y="250" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black" transform="rotate(-90 50 250)">program state</text>
				<text x="460" y="500" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black">time</text>

				<!-- Title -->
				<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="#1E40AF" font-weight="bold"
					style="font-family: var(--r-code-font)">autopsy</text>

				<!-- Arrow marker definition -->
				<defs>
					<marker id="arrowBlue" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
						<path d="M0,0 L8,4 L0,8 Z" fill="#1E40AF" />
					</marker>
				</defs>
			</svg>
		</div>
		<Action do={() => { computedColStep = 1 }} undo={() => { computedColStep = 0 }} />
		<Action do={() => { computedColStep = 2 }} undo={() => { computedColStep = 1 }} />
		<Notes>
			
			Well now that I've captured all of this extra context at each log line, it seems like I could do more with it.
			To help with the problem of not having logged the right things, you can now decide that you want to see this other state alongside what you're already seeing.

			<hr>

			To do so, you reach into that stack trace that you've captured for this log and pull out the relevant bit of state

			<hr>

			And then your tool projects that for every log you have.
			
		</Notes>
	</Slide>

	<!-- Slide: Video — Computed Columns -->
	<Slide class="h-full" in={() => restartVideo(vidComputed)}>
		<div class="flex h-full flex-col items-center justify-center">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video bind:this={vidComputed} src="/computed.mp4" loop muted playsinline style="width: 90%; border-radius: 0.5rem; box-shadow: 0 4px 24px rgba(0,0,0,0.15);"></video>
		</div>
		<Notes>
			<p>
				So here's me doing that in autopsy. When I'm looking at this table, I can open the call stack and pull out other relevant state to create a new column.
			</p>

			<p>
				I can also compute arbitrary python expressions over the captured call stack and project it into a new column, like the total being the quantity times the price.
			</p>

			<p>
				And just like that, I can enrich my logs with new information on demand.
			</p>
		</Notes>
	</Slide>

	<!-- Slide: Affordances — Grouping & Filtering -->
	<Slide class="h-full" in={() => { groupFilterStep = 0 }}>
		<div class="flex h-full flex-col items-center justify-center gap-4 px-12">
			<h2 class="w-[80%] text-left text-7xl font-bold text-black">Affordances — Grouping & Filtering</h2>
			<svg viewBox="0 0 900 520" width="80%" preserveAspectRatio="xMidYMid meet" style="overflow: visible">
				<!-- Plot background -->
				<rect x="100" y="40" width="720" height="420" fill="white" />

				<!-- Connecting lines (rendered first so dots are on top) -->
				{#if groupFilterStep < 2}
					{#each groupFilterDots as dot, i}
						{#if i > 0}
							<line
								x1={groupFilterDots[i - 1].x} y1={freeShippingY}
								x2={dot.x} y2={freeShippingY}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
							/>
						{/if}
					{/each}
				{:else}
					<!-- After filtering: lines between consecutive true dots -->
					{#each trueDots as _, i}
						{#if i > 0}
							<line
								x1={trueRedistributed[i - 1]} y1={freeShippingY}
								x2={trueRedistributed[i]} y2={freeShippingY}
								stroke="#991B1B" stroke-width="2.5" stroke-linecap="round"
								style="opacity: 0; animation: appear 0.3s ease-out 0.4s forwards"
							/>
						{/if}
					{/each}
				{/if}

				<!-- All dots: blue for True, orange for False -->
				{#each groupFilterDots as dot, i}
					{@const isSelected = groupFilterStep >= 1 && dot.isTrue}
					{@const isDiscarded = groupFilterStep >= 2 && !dot.isTrue}
					{@const redistIdx = dot.isTrue ? trueDots.indexOf(dot) : -1}
					{@const targetX = groupFilterStep >= 2 && dot.isTrue ? trueRedistributed[redistIdx] : dot.x}
					<circle
						cx={targetX}
						cy={freeShippingY}
						r={isSelected ? 10 : 8}
						fill={dot.isTrue ? '#1E40AF' : '#EA580C'}
						stroke={isSelected ? '#1E40AF' : 'none'}
						stroke-width={isSelected ? 3 : 0}
						style="
							transition: cx 0.6s ease-out, r 0.3s ease-out, opacity 0.4s ease-out, transform 0.4s ease-out;
							opacity: {isDiscarded ? 0 : 1};
							transform-origin: {dot.x}px {freeShippingY}px;
							transform: {isDiscarded ? 'translateY(80px) scale(0.3)' : 'none'};
						"
					/>
					<!-- Selection ring for step 1 -->
					{#if isSelected && groupFilterStep < 2}
						<circle cx={dot.x} cy={freeShippingY} r="16" fill="none" stroke="#1E40AF" stroke-width="2" stroke-dasharray="4 3"
							style="opacity: 0; animation: appear 0.3s ease-out {i * 30}ms forwards" />
					{/if}
				{/each}

				<!-- Row label -->
				<text x={autopsySlices[0]} y={freeShippingY + 32} font-family="var(--r-code-font)" font-size="20" fill="#991B1B">free_shipping</text>

				<!-- Legend -->
				<circle cx="620" cy="70" r="8" fill="#1E40AF" />
				<text x="636" y="76" font-family="var(--r-code-font)" font-size="18" fill="#1E40AF">True</text>
				<circle cx="710" cy="70" r="8" fill="#EA580C" />
				<text x="726" y="76" font-family="var(--r-code-font)" font-size="18" fill="#EA580C">False</text>

				<!-- Axes -->
				<line x1="100" y1="40" x2="100" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="100,33 94,47 106,47" fill="black" />
				<line x1="100" y1="460" x2="836" y2="460" stroke="black" stroke-width="2.5" />
				<polygon points="843,460 829,454 829,466" fill="black" />

				<!-- Axis labels -->
				<text x="50" y="250" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black" transform="rotate(-90 50 250)">program state</text>
				<text x="460" y="500" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="black">time</text>

				<!-- Title -->
				<text x="460" y="25" text-anchor="middle" font-family="Lato, sans-serif" font-size="28"
					fill="#1E40AF" font-weight="bold"
					style="font-family: var(--r-code-font)">autopsy</text>
			</svg>
		</div>
		<Action do={() => { groupFilterStep = 1 }} undo={() => { groupFilterStep = 0 }} />
		<Action do={() => { groupFilterStep = 2 }} undo={() => { groupFilterStep = 1 }} />
		<Notes>
			Last affordance I'll talk about today: ways of getting overviews of the logs and customizing your view.

			<hr>

			To make certain comparisons easier, or to narrow my focus to an interesting subset of the data, I should be able to say that I only care about logs with a particular characteristic.
			So I should be able to select only the stuff I care about...

			<hr>

			...and then change my view of the logs to just those logs.
		</Notes>
	</Slide>

	<!-- Slide: Video — Grouping & Filtering -->
	<Slide class="h-full" in={() => restartVideo(vidAggFilter)}>
		<div class="flex h-full flex-col items-center justify-center">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video bind:this={vidAggFilter} src="/agg_filter.mp4" loop muted playsinline style="width: 90%; border-radius: 0.5rem; box-shadow: 0 4px 24px rgba(0,0,0,0.15);"></video>
		</div>
		<Notes>
			<p>So in autopsy, next to each column header is a filter icon.</p>

			<p>
				I can see distributions of values, letting me easily understand properties of the captured data in aggregate.
				Is this the right distribution of values for this variable? Are there values in here that I don't expect?
			</p>

			<p>And then I can go and say "oh I only care to see when free_shipping was True". This also cross-filters my chronological view.</p>
		</Notes>
	</Slide>

	<!-- Slide: Principle 3c — better affordances for analysis -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Future Work</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Starting tomorrow: controlled lab study vs. print/breakpoints</li>
				<li>Capture all statements, no <span class="font-mono">autopsy.log()</span> calls</li>
				<li>More complex queries ("Pairs of logs where X happened, then Y")</li>
				<li>Comparisons across multiple executions ("How did my change affect the execution?")</li>
				<li>Letting LLMs query the dataset, both for agentic loops and explanations</li>
			</ul>
		</div>
		<Notes>
			<p>Up next for this project, well as soon as I get back from PLATEAU I'm running a user study on this.</p>
			<p>We'd also like to work on efficient capture and capture all statements automatically.</p>
			<p>I've only covered most most basic queries, I think you could do much more with this data.</p>
			<p>Being able to make a code change and diff the traces could be really powerful as well.</p>
			<p>And lastly, I think letting coding agents query the dataset might be interesting, both for the agent coding loop and for creating explanations for humans.</p>
		</Notes>
	</Slide>

	<!-- Slide 18: Closing -->
	<Slide class="h-full">
		<div class="flex h-full flex-col justify-center gap-6 px-20 py-16 text-left">
			<h2 class="text-8xl font-bold text-black">Data-oriented debugging <br>
				with <span
					class="mt-2 inline-block bg-[#0000FF] px-3 py-1 text-white"
					style="font-family: var(--r-code-font)"
				>autopsy</span>
			</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Separate collection and analysis</li>
				<li>New analysis affordances over captured data</li>
			</ul>
			<h2 class="text-8xl font-bold text-black">Discussion</h2>
			<ul class="flex flex-col gap-3 pl-6 text-5xl text-black list-disc">
				<li>Any questions you would want to ask participants of my study?</li>
				<li>Is this the right way to think about debugging tools?</li>
				<li>Other things you can imagine doing with full traces?</li>
			</ul>
		</div>
		<Notes>
			So that's data-oriented debugging and autopsy.
			For discussion, I'd like to emphasize this first question especially:
			I'm running a study starting tomorrow, so if there are any questions you think I should be asking participants, please let me know!
		</Notes>
	</Slide>
</Presentation>
