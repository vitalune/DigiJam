---
title: Text Highlighter
date: 2025-02-11
description: A text highlighter that mimics the effect of a human-drawn marker stroke.
author: pratiyank
published: true
---

<ComponentPreview name="highlighter-demo" />

## Installation

<Tabs defaultValue="cli">

<TabsList>
  <TabsTrigger value="cli">CLI</TabsTrigger>
  <TabsTrigger value="manual">Manual</TabsTrigger>
</TabsList>
<TabsContent value="cli">

```bash
npx shadcn@latest add @magicui/highlighter
```

</TabsContent>

<TabsContent value="manual">

<Steps>

<Step>Copy and paste the following code into your project.</Step>

```tsx
"use client"

import { useEffect, useRef } from "react"
import type React from "react"
import { useInView } from "motion/react"
import { annotate } from "rough-notation"
import { type RoughAnnotation } from "rough-notation/lib/model"

type AnnotationAction =
  | "highlight"
  | "underline"
  | "box"
  | "circle"
  | "strike-through"
  | "crossed-off"
  | "bracket"

interface HighlighterProps {
  children: React.ReactNode
  action?: AnnotationAction
  color?: string
  strokeWidth?: number
  animationDuration?: number
  iterations?: number
  padding?: number
  multiline?: boolean
  isView?: boolean
}

export function Highlighter({
  children,
  action = "highlight",
  color = "#ffd1dc",
  strokeWidth = 1.5,
  animationDuration = 600,
  iterations = 2,
  padding = 2,
  multiline = true,
  isView = false,
}: HighlighterProps) {
  const elementRef = useRef<HTMLSpanElement>(null)
  const annotationRef = useRef<RoughAnnotation | null>(null)

  const isInView = useInView(elementRef, {
    once: true,
    margin: "-10%",
  })

  // If isView is false, always show. If isView is true, wait for inView
  const shouldShow = !isView || isInView

  useEffect(() => {
    if (!shouldShow) return

    const element = elementRef.current
    if (!element) return

    const annotationConfig = {
      type: action,
      color,
      strokeWidth,
      animationDuration,
      iterations,
      padding,
      multiline,
    }

    const annotation = annotate(element, annotationConfig)

    annotationRef.current = annotation
    annotationRef.current.show()

    const resizeObserver = new ResizeObserver(() => {
      annotation.hide()
      annotation.show()
    })

    resizeObserver.observe(element)
    resizeObserver.observe(document.body)

    return () => {
      if (element) {
        annotate(element, { type: action }).remove()
        resizeObserver.disconnect()
      }
    }
  }, [
    shouldShow,
    action,
    color,
    strokeWidth,
    animationDuration,
    iterations,
    padding,
    multiline,
  ])

  return (
    <span ref={elementRef} className="relative inline-block bg-transparent">
      {children}
    </span>
  )
}

```

</Steps>

</TabsContent>

</Tabs>

## Usage

```tsx showLineNumbers
import { Highlighter } from "@/components/ui/highlighter"
```

```tsx showLineNumbers
<p>
  The{" "}
  <Highlighter action="underline" color="#FF9800">
    Magic UI Highlighter
  </Highlighter>{" "}
  makes important{" "}
  <Highlighter action="highlight" color="#87CEFA">
    text stand out
  </Highlighter>{" "}
  effortlessly.
</p>
```

## Props

Here's the updated props table with units specified for the numerical values:

| Prop                | Type                                                                                                | Default       | Description                                                                  |
| ------------------- | --------------------------------------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------- |
| `children`          | `React.ReactNode`                                                                                   | Required      | The content to be highlighted/annotated.                                     |
| `color`             | `string`                                                                                            | `"#ffd1dc"`   | The color of the highlight.                                                  |
| `action`            | `"highlight" \| "circle" \| "box" \| "bracket" \| "crossed-off" \| "strike-through" \| "underline"` | `"highlight"` | The type of annotation effect to apply.                                      |
| `strokeWidth`       | `number`                                                                                            | `1.5px`       | The width of the annotation stroke.                                          |
| `animationDuration` | `number`                                                                                            | `500ms`       | Duration of the animation in milliseconds.                                   |
| `iterations`        | `number`                                                                                            | `2`           | Number of times to draw the annotation (adds a sketchy effect when > 1).     |
| `padding`           | `number`                                                                                            | `2px`         | Padding between the element and the annotation.                              |
| `multiline`         | `boolean`                                                                                           | `true`        | Whether to annotate across multiple lines or treat content as a single line. |
| `isView`            | `boolean`                                                                                           | `false`       | Controls whether the animation starts only when the element enters viewport. |

## Credits

- Credit to [@pratiyank](https://github.com/Pratiyankkumar) for this component!
