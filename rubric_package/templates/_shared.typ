// Rubric shared functions — included in every generated document
// Override: copy to ~/.config/rubric/templates/_shared.typ and edit freely.

#let movement(title) = {
  v(8pt)
  align(center, text(weight: "bold", size: 1.2em, smallcaps(title)))
  v(4pt)
}

#let hymnref(ref, title) = {
  strong(ref)
  h(0.3em)
  emph(title)
}

#let ldr(content) = { strong(content); linebreak() }
#let ppl(content) = { strong(content); linebreak() }

#let sverse(num, content) = {
  super(str(num))
  h(0.25em)
  content
  linebreak()
}

#let scripture(content) = block(
  inset: (left: 1.5em),
  above: 4pt,
  below: 4pt,
  content,
)

#let leader-note(content) = block(
  fill: rgb("#fff0f0"),
  inset: (left: 10pt, right: 10pt, top: 6pt, bottom: 6pt),
  radius: 4pt,
  above: 4pt,
  below: 4pt,
  text(size: 0.9em, fill: rgb("#b91c1c"), style: "italic", content),
)

// Rubric note: leader instructions — red italic, manuscript only (stripped from bulletin)
#let rubric-note(content) = block(
  fill: rgb("#fff0f0"),
  inset: (left: 10pt, right: 10pt, top: 6pt, bottom: 6pt),
  radius: 4pt,
  above: 4pt,
  below: 4pt,
  text(size: 0.9em, fill: rgb("#b91c1c"), style: "italic", content),
)

// Element heading: bold small-caps with a thin rule below
#show heading.where(level: 3): it => {
  v(6pt, weak: true)
  text(weight: "bold", smallcaps(it.body))
  v(1pt, weak: true)
  line(length: 100%, stroke: 0.4pt + luma(160))
  v(4pt, weak: true)
}

// Movement heading: centred bold larger text
#show heading.where(level: 2): it => {
  v(8pt, weak: true)
  align(center, text(size: 1.1em, weight: "bold", it.body))
  v(4pt, weak: true)
}
