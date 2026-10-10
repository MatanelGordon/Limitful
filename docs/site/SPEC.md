# Limitful Documentation Site Specification

Limitful's documentation site is the static, language-aware product and reference
experience for the five native libraries, generated from language-specific
Markdown that is also the exact machine-readable source of truth.

## Status and ownership

This document is the canonical owner of the documentation site's product,
content, routing, offline, search, versioning, accessibility, and repository
requirements. It specifies the site to build; it does not select a framework or
hosting provider.

The library is still in the design stage. No language binding, benchmark
implementation, or site implementation exists yet.

## Goals

The site must be:

- beautiful and convincing as a product-marketing experience;
- extremely fast and responsive, both in interaction and across screen sizes;
- installable as a Progressive Web App;
- useful to developers through clear explanations, examples, and playgrounds;
- directly readable by models from the same Markdown humans see; and
- designed for Generative Engine Optimization so answer engines can understand,
  cite, and recommend Limitful.

## Non-goals

The site does not include:

- competitor comparison pages;
- an aggregate `llms-full.txt`;
- a documentation MCP server;
- analytics, tracking, or cookies;
- translated prose beyond English;
- a light theme; or
- server-side search.

## Information architecture and routes

### Global language selection

The site has one global selector for C#, TypeScript/JavaScript, Rust, Go, and
Python. A selected language changes the content, code, API names, versions, and
language-specific details throughout the language-prefixed site tree.

Language is part of the URL. The JavaScript/TypeScript tree uses the source's
`/js/` prefix, for example `/js/probe.html`. The other four languages have their
own corresponding prefixes.

Switching languages preserves the current page when an equivalent page exists:
switching from `/js/rate-controller` to Rust opens the Rust
`rate-controller` page, not the Rust front page.

The bare `/` route is language-agnostic. It sells the product without selecting
a language.

### Per-language site trees

Each language prefix is a separate fork of the documentation experience. It has:

- its own getting-started front page;
- language-specific utility, concept, API, question, and playground content;
- independently retained package-version documentation;
- its own changelog; and
- links to the package-to-behavior-spec compatibility table.

Every published content page also has a `.md` variant containing the exact
Markdown source used to generate the human-facing page. The exact serving
mechanism is not specified.

## Required page types

Every page includes:

1. a one-sentence, self-contained definition at the top; and
2. schema.org structured data describing the software library, applicable
   package and behavior-spec versions, and programming language.

### Getting-started page

**Purpose:** get a developer using the selected language binding quickly.

Required sections:

- the language's installation command;
- one minimal working example; and
- links to each utility.

### Utility or concept page

**Purpose:** explain one Limitful utility or one cross-cutting concept in the
selected language.

Required sections:

- what the utility or concept does;
- when to use it;
- language-specific examples and API names;
- relevant behavior, defaults, and constraints from the canonical library spec;
- links to related utility, concept, and API pages; and
- one playground for that exact utility and language.

### API reference page

**Purpose:** document the selected package's public API precisely.

Required sections:

- every exported class or equivalent public type;
- every exported method or function;
- every exported option; and
- the package version and behavior-spec version to which the reference applies.

API references are handwritten Markdown. Future per-language CI checks compare
the public package API and the reference in both directions and fail when code is
undocumented or documentation names an API that is no longer exported. This
specification does not choose the extraction or comparison tool.

### Question / GEO page

**Purpose:** answer a real developer question in a form useful to humans and
answer engines.

Required sections:

- a first sentence that directly answers the question;
- an explanation of how Limitful addresses it;
- a language-specific example; and
- links to the relevant utility, concept, API, and playground pages.

Examples of the intended question class include limiting concurrency around
`Promise.all` and batching asynchronous calls in C#. These pages are not
competitor comparison pages.

### Changelog page

**Purpose:** record changes to one language package independently of the others.

Required sections:

- package versions in that language;
- changes belonging to each version; and
- the behavior-spec version implemented by each package version.

### Package-to-spec compatibility page

**Purpose:** show which independently versioned package release implements which
behavior-spec version.

Required sections:

- one row per relevant language package version;
- the corresponding behavior-spec version; and
- enough retained history to understand older supported documentation.

## Homepage

The language-agnostic homepage follows this rough order:

1. a concise pitch with strong claims about Limitful;
2. an interactive visual simulation of load leveling; and
3. reproducible benchmark results.

The order is directional rather than a rigid layout prescription.

### Interactive simulation

The homepage demo is an animated visual simulation, not execution of a real
Limitful binding. It shows each submitted item and when that item is processed.

The user controls are:

- incoming flood size;
- concurrency limit; and
- naive versus Limitful mode.

No additional controls are required by this specification. Reduced-motion
preferences calm or pause the animation.

## Benchmarks

Each language presents a before-and-after comparison between Limitful and the
exact naive baseline developers commonly use:

| Language | Naive baseline |
| --- | --- |
| TypeScript/JavaScript | `Promise.all` |
| C# | `Task.WhenAll` |
| Rust | `join_all` |
| Go | one goroutine per job with a `WaitGroup` |
| Python | `asyncio.gather` |

Each comparison reports:

- thread count;
- CPU usage; and
- memory usage.

The benchmark code lives in the same project so readers can reproduce the
results. This specification does not choose benchmark environments, datasets,
budgets, result values, or repository paths.

## Content pipeline and model access

Each page is authored as five separate Markdown sources, one per language. A
page is not one source file containing language tabs or conditional blocks.

Markdown generates the human-facing page and is its exact source of truth. The
published `.md` variant therefore contains exactly the content represented by
the page rather than a separately maintained model summary.

The site root exposes `llms.txt`, a concise plain-text map of the documentation
for AI tools. The site does not publish `llms-full.txt` and does not provide a
documentation MCP server.

## Progressive Web App and offline behavior

The site is installable as a PWA. After the first visit, the language-agnostic
homepage and documentation for all five languages are available offline.

Cache-first instant repeat visits are not included, and there is no "new version
available" prompt. The cache/update algorithm and the resulting offline payload
size are not specified.

## Search

A Cmd+K / Ctrl+K command palette is available throughout the site.

Search:

- covers all five language trees;
- runs entirely in the browser and sends no server request;
- ships its index with the static site;
- caches that index for offline use; and
- opens every result offline after the first-visit offline content is available.

## GEO and structured data

The site supports Generative Engine Optimization through:

- real developer-question pages;
- a direct answer in the first sentence, followed by the Limitful solution;
- a self-contained one-sentence definition at the top of every page; and
- schema.org structured data on every page describing the library, versions,
  and programming language.

The site does not create competitor comparison pages.

## Playgrounds

Every utility or instructional page has one ready-made playground for exactly
that page's utility and language. An embedded experience is preferred over a
link-only experience.

Replit iframe viability is explicitly **Open** and must be tested against the
real service before implementation is committed. If Replit cannot embed an
editable project:

- TypeScript/JavaScript may use StackBlitz or CodeSandbox;
- C# may use .NET Fiddle;
- Python may use an in-browser Python environment; and
- Rust and Go may use outbound links where no suitable embed exists.

The page still provides a usable link when embedding is unavailable.

## Versioning

Older documentation remains available.

Each language package and its documentation are versioned independently. A
bugfix in one binding releases a new version of that package only; other package
versions do not change.

The shared Markdown behavior specification has a separate version. Every package
release states which behavior-spec version it implements, and the site publishes
a compatibility table mapping package versions to behavior-spec versions.

A behavior change increments the behavior-spec version. Each language binding
adopts that version on its own schedule. This specification does not define
SemVer policy, URL grammar for retained versions, an initial version, or the
algorithm used to maintain the compatibility table.

## Visual direction

The visual direction is dark-only, glowing, and product-marketing oriented, in
the style of Linear and Raycast. This specification intentionally does not choose
fonts, colors, tokens, spacing scales, or breakpoints.

## Privacy, language, and accessibility

- The site is fully static.
- It has no analytics, tracking, or cookies.
- Prose is English only.
- It meets WCAG 2.2 AA.
- Text and controls maintain readable contrast within the dark visual direction.
- All navigation and interactions, including the command palette, are keyboard
  accessible.
- The site respects the system reduced-motion preference.

## Repository and deployment requirements

The site source, its Markdown, the benchmark code, and the future five native
packages live in the same monorepo. A package or behavior change and its
documentation change can therefore land in the same pull request.

The site is fully static and may be deployed to any static host. The framework
and hosting provider are undecided.

At the requirement level, the repository must contain:

- the site implementation;
- the five language-specific Markdown content sets; and
- reproducible benchmark code.

This document does not prescribe exact directories beyond its own canonical
location, `docs/site/SPEC.md`.

## Acceptance checklist

- [ ] The bare `/` homepage is language-agnostic and follows the pitch,
      simulation, benchmark order.
- [ ] The simulation visually shows every item and processing event and exposes
      flood size, concurrency, and naive/Limitful controls.
- [ ] A global five-language selector preserves the equivalent page when
      switching languages.
- [ ] Language-specific content is served under language-prefixed URLs,
      including the `/js/` tree.
- [ ] Every language tree has a getting-started front page and changelog.
- [ ] Required page types exist with the specified sections.
- [ ] Every page begins with a standalone definition and includes applicable
      schema.org structured data.
- [ ] Each content page is generated from its own language-specific Markdown
      source and has an exact `.md` variant.
- [ ] Root `llms.txt` maps the documentation; no `llms-full.txt` or docs MCP is
      shipped.
- [ ] One exact-utility, exact-language playground is available per applicable
      page, embedded where viable and linked otherwise.
- [ ] Each language benchmark compares Limitful with its specified naive
      baseline and reports thread count, CPU, and memory.
- [ ] Benchmark code is reproducible from the monorepo.
- [ ] The PWA is installable and makes the homepage and all five language trees
      available offline after the first visit.
- [ ] Cmd+K / Ctrl+K search is available everywhere, covers all languages, makes
      no server request, and works offline.
- [ ] Old package documentation is retained and package-to-spec compatibility is
      visible.
- [ ] API references are handwritten Markdown and the future drift check is
      defined bidirectionally without selecting a tool.
- [ ] The result is fully static, dark-only, English-only, and free of analytics,
      tracking, and cookies.
- [ ] The result meets WCAG 2.2 AA contrast and keyboard requirements and
      respects reduced motion.
- [ ] Site source, Markdown, benchmark code, and future packages remain in the
      same monorepo.

## Issues to resolve

These items are intentionally not silently resolved:

| Item | Status |
| --- | --- |
| Site framework | Undecided implementation choice |
| Static hosting provider | Undecided implementation choice |
| Replit iframe viability and the required per-language fallback | **Open product item** |
| Language bindings and benchmark implementations | Do not exist yet |
| Mechanics for independent package versions and behavior-spec versions | Not specified |
| Offline payload size and update/cache algorithm for all five language trees | Not specified |
| Exact mechanism that serves each `.md` page variant | Not specified |
