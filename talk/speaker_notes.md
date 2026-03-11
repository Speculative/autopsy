# Speaker Notes

## Title (Slide 1)
Hello! I'm Jeff, a PhD student at Penn, and today I'm excited to tell you about
Data-oriented Debugging, which is a new approach for thinking about the debugging process and debugging tools,
and about autopsy, a new debugger that implements some of these ideas.

## Why I Care About Debugging (Slide 2)
Just to introduce where I'm coming from with debugging.
I used to be a senior software engineer in the industry, where I worked on auth, notifications, client/server sync.
All things that are procedural, highly stateful, highly complex, prone to bugs, and really annoying to debug.
And in all that time I was one of those programmers who always used print statements to debug.
But I found the debugging tools at my disposal unsatisfying.

## How do you debug this? / State×Time Chart / Debugging Techniques (Slide 3)
Let's start with an example to illustrate what I see are some issues with current debuggers.
You're working on an online retail payment processing pipeline.
It does some conventional things retailers do, such as giving a discount on bulk orders, and free shipping on orders above a certain cost.

You've maybe already spotted the bug: sometimes a customer will get a discount for a bulk order and that'll take away what was previously going to be their free shipping, which isn't a good experience.
Let's say that this in the real code base this is hard to spot: maybe the logic is distributed across multiple functions, or there's a bunch of stuff in between these lines.
This is a pretty common issue: the logic looks reasonable locally, but produces unreasonable results when composed.

---

We're going to analyze how a programmer might use different debuggers to understand this problem.
But first I need to introduce this visualization I call the state-time chart, which we'll use to understand what different debuggers can do.
First, let me give you some intuition about how this chart works.

---

On the vertical axis we have all state across all scopes of the program.

---

In our toy example this is all of the fields of the item and the cart.

---

Imagine these various pieces of the program state distributed at different locations along the vertical axis.

---

Next, the horizontal axis represents time. Really it's discretized by the program counter.

---

As each statement in the program executes, computation happens. Take item price here -- as we process each item we calculate a price for it.

---

For a certain row across the chart, a particular variable is taking on different values, with increasing time as we move to the right.

---

Okay that's the state-time chart. Let's use it to understand how a debugger works.

---

Breakpoint debugging pauses execution at a particular point in time.
When paused, you have access to arbitrary state at every frame of the call stack, which is shown in the variables panel in the bottom right.

---

When I press continue, the program runs until it hits the breakpoint again, and I can see all of the state everywhere at this new moment.

This can be great! It leaves you flexible and doesn't require you to predict in advance what state will be relevant to your debugging.

---

And as I continue to use my breakpoint debugger, I'm proceeding through a sequence of stack traces, each of which is a complete vertical slice of state, but at a different point in time.

So I like that I can see all of the state and know that it's all related because it's all from the same moment in time, but I have to keep track of the history of how I got to this point in my head, and I have to decide when to pause and inspect state.

---

Next, let's examine print debugging.

---

When I add a print statement to the code,

---

when execution runs over the print statement, I get a log entry in my terminal, shown in the bottom right, that shows me the values of some variables that I choose at that moment in time.

---

As the entire program executes, I get a bunch of logs in my terminal, each corresponding to a particular value taken on by a specific part of the program state.
Each of these dots represents a particular log entry, which you can think of as storing that particular state-time value.
They're arranged horizontally because they all represent state pulled from the same place in the code.

---

Now, if I add a second print line

---

as the program executes, I get logs whenever one of these print statements executes.

---

And when the whole program executes, I get logs from both print statements, extracting different states from different times.
Programmers often insert multiple print statement probes in their code, precisely because, in contrast to breakpoints, it helps them understand sequences of events.

But recall the blue bars of the breakpoint debugger. You no longer have access to complete information about each moment in time.

And also, where I put my print statements and how the program actually executes determines how the information I get is displayed to me.
I don't have two neat, separated rows of logs. I have this zigzag interleaving of them.
This helps me in situations where I want to understand the history of execution, but it makes it hard to understand the execution in any other way besides chronologically.

## Too Much / Too Little Information (Slide 4)
We conducted interviews with 12 experienced industry software engineers to understand their debugging practices and why they preferred certain tools and techniques.
One major theme that emerged was that their debugging strategies often involved this active negotiation with collecting and viewing information about execution.

Sometimes they worried about collecting too much. One participant told us that unnecessary information could cause them to lose out on the meaningful thing that would help them understand the bug.

Another participant said that a poorly placed breakpoint could disrupt their workflow if it was hit a lot.

---

On the other hand, they also worried about not having enough information to understand their bugs. They felt this more acutely the longer it took to get new debugging data.

## Two information needs in tension (Slide 5)
This negotiation process puts these two instincts in tension. On the one hand, I'm inclined to collect more information because it'll help me make sense of the problem.
But on the other hand, I worry that if I collect too much, I won't even be able understand what I'm looking at.

Needing to navigate this tension seems to me like incidental complexity of current debuggers, rather than an inherent part of debugging.

I'm a databases person. When I hear this tension, my instinct is that I should be able to collect everything and that I should have good analysis tools that let me manage all of that data.

## Why are they in tension? (Slide 6)
But where is this tension coming from in current debuggers? Well, the design of both debugging tools couples collection and analysis.

There's nothing you can do with print debugging output besides browsing it and performing text search on it.
And your print statements fix output, forcing you to see only what you've logged, but also forcing you to see everything you've logged.

On the other hand, interactive debugging with a breakpoint debugger is almost the opposite: it forces you to continually make decisions about what data to collect next.
You're constantly switching between deciding where to go next and analyzing what you can now see.

On the analysis side, neither has affordances to aid your reasoning beyond just showing you the data. I'll get back to that in a minute.
First, let's examine what better collection could look like.

## Collection — State×Time Comparison (Slide 7)
So we saw that breakpoints let you see all of the state at one particular moment in time.

---

And print statements let you see particular pieces of state across many moments in time, and in order.

---

Well, from a pure data collection perspective, it sure would be nice to get all state at all moments in time.

## autopsy intro (Slide 8)
This is exactly what we designed autopsy to do. The first part of autopsy is a python debugging library.
The way you use it to instrument code looks a lot like print debugging: you just import log from autopsy and sprinkle calls to log throughout your code base.

The interesting extra bit is that it captures full stack traces, not just the expressions you pass it.
Here, a full stack trace means every stack frame, and every variable in every stack frame. This is all of the information you get when paused on a breakpoint.

## Call Stack in History View (Slide 9)
And so, one view of the autopsy interface is like your chronological print statement output,
except that you can click on any log entry and see the full stack trace for that moment in time, just like you would see if you were paused at a breakpoint.

It gives you all of the data you asked for, and more on demand.

## Print → Table Revelation (Slide 10)
Next, on to analysis affordances.

This project was partially born from me looking at the JavaScript console, looking at how different logs were separated by lines,
and thinking to myself, "Isn't this a table? Shouldn't I be able to do more things with this?" which is when I began to see my debugging logs as a dataset in themselves,
where I had previously been thinking of them as the end of where tooling could help me.

## Affordances — Streams (Slide 11)
To start, we briefly hit upon this ordering problem of only being able to see logs chronologically.
One obvious affordance is letting you isolate the logs from different places in your code.

## Streams Video (Slide 12)
By default, autopsy shows you this chronological view.
But if you switch to this Streams view, they're separated by statement, letting you see all of the logs produced at a particular point in your code.
And since all of those logs have the same set of arguments, they're presented in a table view, which has some nice properties we're about to see.

## Affordances — "Step" Debugging (Slide 13)
So autopsy can replace print debugging, and goes beyond it. But what about breakpoint debugging?
We tried to give it a similar treatment for stepping. You should be able to follow along with the order that things were captured in.

At each point, we can show you the same information the breakpoint debugger would have shown you, because we're capturing the full stack trace.
And since this is all post-hoc analysis of captured logs, we can do the omniscient debugging thing of letting you step forwards and backwards and jump to arbitrary points.

## Step Debugging Video (Slide 14)
So here, next to any log in autopsy, I can click on this "Show in code" button, which gives me a code lens above the corresponding log statement.
Then, I can click these buttons to step forwards and backwards through the logs.
If I have multiple log statements, the view will jump around to them.
And like I said, since I have the full stack trace, I can click on the log to see all of the information that a breakpoint debugger would have shown me.

The one glaring difference is that this doesn't give me the same stepping experience as breakpoints since it only works when I have log statements. We'll get back to that at the end.

## Affordances — Computed Columns (Slide 15)
Well now that I've captured all of this extra context at each log line, it seems like I could do more with it.
To help with the problem of not having logged the right things, you can now decide that you want to see this other state alongside what you're already seeing.

---

To do so, you reach into that stack trace that you've captured for this log and pull out the relevant bit of state

---

And then your tool projects that for every log you have.

## Computed Columns Video (Slide 16)
So here's me doing that in autopsy. When I'm looking at this table, I can open the call stack, find the relevant part of the stack trace,
and drag it to the header of the log table to create a new column.

And just like that, I can enrich my logs with new information on demand.

## Affordances — Grouping & Filtering (Slide 17)
Last affordance I'll talk about today: ways of getting overviews of the logs and customizing your view.

---

To make certain comparisons easier, or to narrow my focus to an interesting subset of the data, I should be able to say that I only care about logs with a particular characteristic.
So I should be able to select only the stuff I care about...

---

...and then change my view of the logs to just those logs.

## Grouping & Filtering Video (Slide 18)
So in autopsy, next to each column header is a filter icon.

For primitive values, there are visualizations of the distribution of values.
This lets me easily understand properties of the captured data in aggregate. Is this the right distribution of values for this variable? Are there values in here that I don't expect?

And then I can go and say "oh I only care to see when free_shipping was True"

## Future Work (Slide 19)
This is where I'll briefly talk about future work, including capturing everything.

## Closing (Slide 20)
*(No speaker notes)*
