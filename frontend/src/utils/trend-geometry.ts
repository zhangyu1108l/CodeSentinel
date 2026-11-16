export interface ChartPoint {
  index: number
  x: number
  y: number
}

export interface ChartTick {
  index: number
  x: number
}

export interface ChartAxisTick {
  value: number
  y: number
}

export interface TrendGeometry {
  width: number
  height: number
  plotLeft: number
  plotTop: number
  plotRight: number
  baselineY: number
  axisMax: number
  reviewPoints: ChartPoint[]
  findingPoints: ChartPoint[]
  xTicks: ChartTick[]
  yTicks: ChartAxisTick[]
}

export interface MultiSeriesGeometry {
  width: number
  height: number
  plotLeft: number
  plotTop: number
  plotRight: number
  baselineY: number
  axisMax: number
  /** Positioned points for every input series, in input order. */
  seriesPoints: ChartPoint[][]
  xTicks: ChartTick[]
  yTicks: ChartAxisTick[]
}

export interface TrendGeometryOptions {
  width?: number
  height?: number
  paddingLeft?: number
  paddingRight?: number
  paddingTop?: number
  paddingBottom?: number
  maxXTicks?: number
}

const DEFAULT_WIDTH = 720
const DEFAULT_HEIGHT = 260
const DEFAULT_PADDING_LEFT = 46
const DEFAULT_PADDING_RIGHT = 18
const DEFAULT_PADDING_TOP = 18
const DEFAULT_PADDING_BOTTOM = 36
const DEFAULT_MAX_X_TICKS = 8

/**
 * Rounds an axis maximum up to a readable value. A minimum axis of 4 keeps
 * small integer counts from producing duplicate rounded grid labels.
 */
export function niceAxisMax(value: number): number {
  if (!Number.isFinite(value) || value <= 0) {
    return 4
  }
  const target = Math.max(4, value)
  if (target <= 4) {
    return 4
  }
  const magnitude = 10 ** Math.floor(Math.log10(target))
  const normalized = target / magnitude
  let nice = 10
  if (normalized <= 1) {
    nice = 1
  } else if (normalized <= 2) {
    nice = 2
  } else if (normalized <= 5) {
    nice = 5
  }
  return nice * magnitude
}

/**
 * Selects evenly spaced x-axis tick indexes, always including the first and
 * last point. This keeps 30-day trends readable on narrow screens.
 */
export function sampleTickIndexes(count: number, maxTicks: number): number[] {
  if (count <= 0 || maxTicks <= 0) {
    return []
  }
  if (count === 1 || maxTicks === 1) {
    return [0]
  }
  const tickCount = Math.min(count, maxTicks)
  const indexes: number[] = []
  for (let tick = 0; tick < tickCount; tick += 1) {
    const index = Math.round((tick * (count - 1)) / (tickCount - 1))
    if (indexes[indexes.length - 1] !== index) {
      indexes.push(index)
    }
  }
  return indexes
}

/** Builds an SVG `M`/`L` path from already positioned points. */
export function buildLinePath(points: ChartPoint[]): string {
  if (points.length === 0) {
    return ''
  }
  return points
    .map(
      (point, index) =>
        `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`,
    )
    .join(' ')
}

/** Builds a closed area path down to the chart baseline. */
export function buildAreaPath(
  points: ChartPoint[],
  baselineY: number,
): string {
  if (points.length === 0) {
    return ''
  }
  const first = points[0]
  const last = points[points.length - 1]
  if (!first || !last) {
    return ''
  }
  return `${buildLinePath(points)} L ${last.x.toFixed(2)} ${baselineY.toFixed(
    2,
  )} L ${first.x.toFixed(2)} ${baselineY.toFixed(2)} Z`
}

/**
 * Computes SVG coordinates for both trend series.
 *
 * - `n = 0` returns empty series without dividing by zero.
 * - `n = 1` places the single point at the horizontal centre.
 * - all-zero data plots on the baseline instead of producing `NaN`.
 */
export function buildTrendGeometry(
  reviewValues: number[],
  findingValues: number[],
  options: TrendGeometryOptions = {},
): TrendGeometry {
  const width = options.width ?? DEFAULT_WIDTH
  const height = options.height ?? DEFAULT_HEIGHT
  const plotLeft = options.paddingLeft ?? DEFAULT_PADDING_LEFT
  const plotRight =
    width - (options.paddingRight ?? DEFAULT_PADDING_RIGHT)
  const plotTop = options.paddingTop ?? DEFAULT_PADDING_TOP
  const baselineY =
    height - (options.paddingBottom ?? DEFAULT_PADDING_BOTTOM)
  const plotWidth = Math.max(0, plotRight - plotLeft)
  const plotHeight = Math.max(0, baselineY - plotTop)
  const maxXTicks = options.maxXTicks ?? DEFAULT_MAX_X_TICKS

  const pointCount = Math.min(reviewValues.length, findingValues.length)
  const allValues = [
    ...reviewValues.slice(0, pointCount),
    ...findingValues.slice(0, pointCount),
  ]
  const axisMax = niceAxisMax(Math.max(0, ...allValues))

  const xFor = (index: number): number => {
    if (pointCount <= 0) {
      return plotLeft
    }
    if (pointCount === 1) {
      return plotLeft + plotWidth / 2
    }
    return plotLeft + (index * plotWidth) / (pointCount - 1)
  }

  const yFor = (value: number): number => {
    if (axisMax <= 0) {
      return baselineY
    }
    const ratio = Math.min(1, Math.max(0, value / axisMax))
    return baselineY - ratio * plotHeight
  }

  const toPoints = (values: number[]): ChartPoint[] =>
    values.slice(0, pointCount).map((value, index) => ({
      index,
      x: xFor(index),
      y: yFor(value),
    }))

  const xTicks = sampleTickIndexes(pointCount, maxXTicks).map((index) => ({
    index,
    x: xFor(index),
  }))

  const yTicks = [1, 0.75, 0.5, 0.25, 0].map((ratio) => {
    const value = axisMax * ratio
    return {
      value,
      y: baselineY - ratio * plotHeight,
    }
  })

  return {
    width,
    height,
    plotLeft,
    plotTop,
    plotRight,
    baselineY,
    axisMax,
    reviewPoints: toPoints(reviewValues),
    findingPoints: toPoints(findingValues),
    xTicks,
    yTicks,
  }
}

/**
 * Computes SVG coordinates for an arbitrary number of series sharing one
 * x-axis and one y-axis.
 *
 * The series are truncated to the shortest input so every line spans the same
 * buckets. `n = 0` returns empty series without dividing by zero, `n = 1`
 * centres the single point, and all-zero data plots on the baseline with the
 * same minimum axis maximum as `buildTrendGeometry`.
 */
export function buildMultiSeriesGeometry(
  seriesValues: number[][],
  options: TrendGeometryOptions = {},
): MultiSeriesGeometry {
  const width = options.width ?? DEFAULT_WIDTH
  const height = options.height ?? DEFAULT_HEIGHT
  const plotLeft = options.paddingLeft ?? DEFAULT_PADDING_LEFT
  const plotRight =
    width - (options.paddingRight ?? DEFAULT_PADDING_RIGHT)
  const plotTop = options.paddingTop ?? DEFAULT_PADDING_TOP
  const baselineY =
    height - (options.paddingBottom ?? DEFAULT_PADDING_BOTTOM)
  const plotWidth = Math.max(0, plotRight - plotLeft)
  const plotHeight = Math.max(0, baselineY - plotTop)
  const maxXTicks = options.maxXTicks ?? DEFAULT_MAX_X_TICKS

  const pointCount =
    seriesValues.length === 0
      ? 0
      : Math.min(...seriesValues.map((values) => values.length))
  const axisMax = niceAxisMax(
    Math.max(0, ...seriesValues.flatMap((values) => values.slice(0, pointCount))),
  )

  const xFor = (index: number): number => {
    if (pointCount <= 0) {
      return plotLeft
    }
    if (pointCount === 1) {
      return plotLeft + plotWidth / 2
    }
    return plotLeft + (index * plotWidth) / (pointCount - 1)
  }

  const yFor = (value: number): number => {
    if (axisMax <= 0) {
      return baselineY
    }
    const ratio = Math.min(1, Math.max(0, value / axisMax))
    return baselineY - ratio * plotHeight
  }

  const xTicks = sampleTickIndexes(pointCount, maxXTicks).map((index) => ({
    index,
    x: xFor(index),
  }))

  const yTicks = [1, 0.75, 0.5, 0.25, 0].map((ratio) => {
    const value = axisMax * ratio
    return {
      value,
      y: baselineY - ratio * plotHeight,
    }
  })

  return {
    width,
    height,
    plotLeft,
    plotTop,
    plotRight,
    baselineY,
    axisMax,
    seriesPoints: seriesValues.map((values) =>
      values.slice(0, pointCount).map((value, index) => ({
        index,
        x: xFor(index),
        y: yFor(value),
      })),
    ),
    xTicks,
    yTicks,
  }
}
