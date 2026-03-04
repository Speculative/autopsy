# Data-Oriented Debugging with autopsy — PLATEAU '26 Talk Outline

**Total time: 14 minutes**
**Audience: HCI-interested PL researchers**

---

## Section 1: Debugging is about checking mental models against execution data (3 min)

### Slide 1: Title slide
- Title: Data-Oriented Debugging with autopsy
- Authors: Jeffrey Tao, Xiaorui Liu, Ryan Marcus, Andrew Head
- Venue: PLATEAU '26

### Slide 2: What is debugging, really?
- Programmers form mental models of how their code works
- Debugging = checking those models against what the program actually does
- The only way to check is by looking at execution data
- Notes: All 12 formative study participants described their process this way. This is well-supported in the literature (Siegmund et al. "scientific debugging," Alaboudi & LaToza's hypothesis generation/testing). Frame this as: debugging is not primarily about *finding* the right code — it's about *understanding* execution.

### Slide 3: The state × time space
- Diagram: 2D plot. Vertical axis = program state (variables, call stacks, etc.). Horizontal axis = time (execution steps).
- A program execution fills this entire space. Without tools, all of this data is generated and thrown away as the program runs.
- Notes: This is the core conceptual diagram of the talk. Return to it when discussing each tool. The key provocation: your program already produces all the data you need to find the bug. Your tools just throw most of it away.

### Slide 4: Current tools are impoverished projections
- Breakpoint debugging: a vertical slice. All state at one point in time. Step to move to another point. Comparisons across time must happen in your head.
- Print debugging: scattered points. Some state at many points in time. Fixed presentation (sequential text). What you see is locked in at collection time.
- Omniscient/time-travel debugging: same vertical slice, but you can step backward. Still one point in time at a time. (Wang & LaToza: no significant productivity improvement over conventional breakpoints.)
- Notes: The point is not that these tools are bad — they're useful. The point is that they're limited projections of the full state×time space, and those limitations have consequences.

---

## Section 2: Evidence — what programmers actually struggle with (3 min)

### Slide 5: Formative study overview
- 12 professional software engineers, 3–11 years experience
- 30-minute semi-structured interviews about debugging practices
- Thematic analysis through a data-oriented debugging lens
- Notes: Recruited from personal networks and internal company postings. 4 companies, 8 from one company. Mix of print-preferred (7), breakpoint-preferred (2), and both (3). Keep this slide brief — the findings matter more than the method.

### Slide 6: The coupling problem
- Core finding: current tools tightly couple data collection and data analysis.
- Breakpoints: you collect and analyze simultaneously. You're inspecting state while also deciding where to go next.
- Print statements: you plan collection upfront, then analyze output. But if the output is wrong, you go back to collection and rerun.
- Quote from P5 about anticipating everything needed to avoid 2-hour redeployment cycles.
- Notes: P5: "what all could I need, and then add everything in the logs, and then analyze it later...Because if I miss one thing, I have to wait 2 hours." This is the central tension the whole talk builds on. The coupling is what makes both tools frustrating in different ways.

### Slide 7: The information management tension
- Programmers want to collect more data (to avoid regret of missing something)
- But they also fear being overwhelmed by too much output
- They lack tools to manage the data once collected — so they manage it by collecting less
- P3: worrying about "burning up log files with unnecessary information"
- P7: using a notepad to keep track of log output because there's too much to hold in their head
- P10: breakpoints on hot code paths "drive me crazy"
- Notes: This is a direct consequence of coupling. If you had tools to filter/sort/query after the fact, you wouldn't need to be so careful about what you collect. P4 had a strategy of printing both nested fields (for scanning) AND full objects (to avoid regret) — a workaround for the lack of post-hoc analysis tools. Multiple participants also discussed adding string tags to logs for filtering — a manual approximation of structured querying.

### Slide 8: Production debugging already solved this
- Industry shifted from text logs → structured logging → query tools (Splunk, Datadog, ELK stack)
- Production debugging treats logs as a queryable dataset
- Local debugging is decades behind: still text on a terminal
- Notes: This is a one-slide point but it's important. It shows the transition the talk is arguing for has already happened in a related domain. The audience should be asking "why hasn't this happened for local debugging too?"

---

## Section 3: Data-oriented debugging as a framework (2 min)

### Slide 9: The core proposal — decouple collection from analysis
- Data-oriented debugging: treat execution data as a structured dataset and give programmers data tools to work with it
- Decouple when/what you collect from how you analyze it
- Key shift: move programmer intentionality from collection to analysis
- Notes: This is the thesis slide. Keep it crisp. The "intentionality" framing: with current tools, the intentional act is deciding what to log or where to set a breakpoint. With data-oriented debugging, the intentional act is deciding how to query, filter, sort, and visualize the data you already have.

### Slide 10: Design principles
- Make collection easy: minimize friction of capturing execution data
- Manage abundant data: provide tools for filtering, transforming, and querying — don't force programmers to manage volume by collecting less
- Support exploration: help programmers characterize execution before narrowing to specific hypotheses
- Support model confirmation: present execution data in ways that make it easy to compare against mental models
- Connect back to code: link analysis results to the code that produced them
- Notes: These are derived from the formative study. Don't dwell on each one — they'll be illustrated in the demo. The key message is that these are design principles for a *class* of tools, not just for autopsy specifically.

---

## Section 4: autopsy demo / walkthrough (5 min)

Notes: This section should be either a live demo or a rehearsed walkthrough with screenshots. Live demo is more engaging but riskier for time. Recommend a hybrid: pre-recorded or scripted walkthrough with the real tool, narrated live. Use the shipping cost motivating example from the paper (adapted to current feature set) or a new example if the current one better showcases the expanded features.

### Slide 11: autopsy overview
- Three components: Python tracing library, web viewer, VS Code extension
- `import autopsy` / `autopsy.log("label", var1, var2)` — captures passed arguments + full stack trace (all frames, all variables)
- Notes: Emphasize: the log call is intentional (you choose where to probe), but what gets captured goes far beyond what you explicitly asked for. This is the first step of decoupling — collection gives you more than you requested.

### Slide 12: Demo — the problem setup
- Introduce the motivating example and the codebase
- Show the bug symptoms
- Notes: Keep this brief. The audience needs just enough context to follow the debugging process. The point of the demo is not the bug — it's the *workflow*.

### Slide 13: Demo — streams view + computed columns
- Show logs from one call site as a structured table
- Add a computed column from a stack variable that wasn't explicitly logged
- Key point: "retroactive print debugging" — no rerun needed
- Notes: This is the single most important feature to demonstrate. It directly shows decoupling: you collected data at one point, and now you're expanding what you can see from that data without going back to collection. Emphasize: in print debugging, realizing you need another variable means editing code and rerunning. Here, it's a drag-and-drop.

### Slide 14: Demo — sorting, filtering, cross-time comparison
- Sort by a column to group related entries
- Filter to a subset of interest
- Show how patterns across many executions become visible in the table
- Notes: This is the "data tools" part. Sorting and filtering are simple but they enable seeing patterns that are invisible in sequential log output. Point out that time is always a secondary sort dimension, so within groups you still see temporal ordering.

### Slide 15: Demo — navigation between views
- Click a row in streams → jump to its location in history (sequential context)
- Click a row in history → jump to its stream (cross-time context)
- Inspect the full call stack from any row
- Notes: This demonstrates "connect back to code" and the ability to shift between analytical lenses on the same data. The navigation between streams and history is how autopsy supports both "what happened at this code location across time?" and "what happened around this moment in execution?"

### Slide 16: Demo — identifying the bug
- Walk through how the data tools led to identifying the root cause
- Show the moment where comparing stack traces across rows reveals the state mutation
- Notes: Land the demo by connecting back to the model-checking framing. The programmer had a mental model, the data tools made it easy to find where reality diverged, and the full stack traces let them trace back to the code.

---

## Section 5: Future vision and closing (1 min)

### Slide 17: Where this goes
- Current limitation: programmer manually places log statements. This is partly intentional (log placement = hypothesis expression) but also a scalability constraint.
- Future: full execution capture → all state at all time → intentionality moves entirely to analysis
- Agentic coding angle: LLM coding assistants currently debug via print statements (text in, text out). What if the agent could query a full execution dataset instead?
- Ongoing validation: controlled lab study comparing static logs vs. autopsy's interactive data manipulation
- Notes: Don't oversell the agentic angle — it's speculative. But it's a good hook for this audience and it shows the framework has implications beyond the current tool. The lab study is in progress; mention it to signal that empirical validation is coming but isn't the focus of this talk.

### Slide 18: Closing slide
- Recap: Debugging = checking mental models against execution data. Current tools couple collection and analysis. Data-oriented debugging decouples them. autopsy demonstrates this.
- Link to tool / paper / contact info