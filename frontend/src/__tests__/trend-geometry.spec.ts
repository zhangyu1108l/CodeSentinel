import { describe, expect, it } from 'vitest'

import {
  buildAreaPath,
  buildLinePath,
  buildMultiSeriesGeometry,
  buildTrendGeometry,
  niceAxisMax,
  sampleTickIndexes,
} from '@/utils/trend-geometry'

describe('trend geometry', () => {
  it('rounds axis maxima to readable values with a minimum of 4', () => {
    expect(niceAxisMax(0)).toBe(4)
    expect(niceAxisMax(-2)).toBe(4)
    expect(niceAxisMax(1)).toBe(4)
    expect(niceAxisMax(3)).toBe(4)
    expect(niceAxisMax(4)).toBe(4)
    expect(niceAxisMax(5)).toBe(5)
    expect(niceAxisMax(6)).toBe(10)
    expect(niceAxisMax(9)).toBe(10)
    expect(niceAxisMax(19)).toBe(20)
    expect(niceAxisMax(45)).toBe(50)
    expect(niceAxisMax(48)).toBe(50)
    expect(niceAxisMax(100)).toBe(100)
    expect(niceAxisMax(Number.NaN)).toBe(4)
  })

  it('samples evenly spaced ticks and keeps both endpoints', () => {
    expect(sampleTickIndexes(0, 8)).toEqual([])
    expect(sampleTickIndexes(30, 8)).toEqual([0, 4, 8, 12, 17, 21, 25, 29])
    expect(sampleTickIndexes(30, 4)).toEqual([0, 10, 19, 29])
    expect(sampleTickIndexes(1, 8)).toEqual([0])
    expect(sampleTickIndexes(2, 8)).toEqual([0, 1])
    expect(sampleTickIndexes(5, 0)).toEqual([])
  })

  it('returns safe empty geometry for no points', () => {
    const geometry = buildTrendGeometry([], [])

    expect(geometry.reviewPoints).toEqual([])
    expect(geometry.findingPoints).toEqual([])
    expect(geometry.xTicks).toEqual([])
    expect(Number.isNaN(geometry.baselineY)).toBe(false)
    expect(buildLinePath(geometry.reviewPoints)).toBe('')
    expect(buildAreaPath(geometry.reviewPoints, geometry.baselineY)).toBe('')
  })

  it('centres a single point instead of dividing by zero', () => {
    const geometry = buildTrendGeometry([1], [45])

    expect(geometry.reviewPoints).toHaveLength(1)
    expect(geometry.findingPoints).toHaveLength(1)
    expect(geometry.reviewPoints[0]?.x).toBe(
      (geometry.plotLeft + geometry.plotRight) / 2,
    )
    expect(geometry.reviewPoints[0]?.y).toBeGreaterThan(geometry.plotTop)
    expect(geometry.reviewPoints[0]?.y).toBeLessThan(geometry.baselineY)
    expect(geometry.findingPoints[0]?.y).toBeLessThan(
      geometry.reviewPoints[0]?.y ?? 0,
    )
    expect(geometry.xTicks).toEqual([
      {
        index: 0,
        x: (geometry.plotLeft + geometry.plotRight) / 2,
      },
    ])
  })

  it('plots all-zero data on the baseline with a readable axis', () => {
    const geometry = buildTrendGeometry([0, 0, 0], [0, 0, 0])

    expect(geometry.axisMax).toBe(4)
    for (const point of [
      ...geometry.reviewPoints,
      ...geometry.findingPoints,
    ]) {
      expect(point.y).toBe(geometry.baselineY)
      expect(Number.isFinite(point.x)).toBe(true)
    }
    expect(geometry.yTicks.map((tick) => tick.value)).toEqual([4, 3, 2, 1, 0])
  })

  it('keeps normal points inside the plot area', () => {
    const geometry = buildTrendGeometry(
      [1, 2, 3, 4],
      [0, 10, 20, 30],
      { width: 400, height: 200, paddingLeft: 40, paddingRight: 20 },
    )

    for (const point of [
      ...geometry.reviewPoints,
      ...geometry.findingPoints,
    ]) {
      expect(point.x).toBeGreaterThanOrEqual(geometry.plotLeft)
      expect(point.x).toBeLessThanOrEqual(geometry.plotRight)
      expect(point.y).toBeGreaterThanOrEqual(geometry.plotTop)
      expect(point.y).toBeLessThanOrEqual(geometry.baselineY)
    }

    expect(geometry.reviewPoints[0]?.x).toBe(geometry.plotLeft)
    expect(geometry.reviewPoints[3]?.x).toBe(geometry.plotRight)
    expect(geometry.findingPoints[0]?.y).toBe(geometry.baselineY)
    expect(geometry.findingPoints[3]?.y).toBeGreaterThan(geometry.plotTop)
    expect(geometry.findingPoints[3]?.y).toBeLessThan(geometry.baselineY)
  })

  it('builds line and closed area paths from positioned points', () => {
    const geometry = buildTrendGeometry([1, 2], [1, 2])
    const line = buildLinePath(geometry.reviewPoints)
    const area = buildAreaPath(geometry.reviewPoints, geometry.baselineY)

    expect(line.startsWith('M ')).toBe(true)
    expect(line).toContain(' L ')
    expect(area.startsWith(line)).toBe(true)
    expect(area.endsWith('Z')).toBe(true)
  })
})

describe('multi-series trend geometry', () => {
  it('derives the axis maximum from every series', () => {
    const geometry = buildMultiSeriesGeometry([
      [1, 2, 3],
      [0, 40, 0],
      [0, 0, 0],
    ])

    expect(geometry.axisMax).toBe(50)
    expect(geometry.seriesPoints).toHaveLength(3)
    expect(geometry.seriesPoints[1]?.[1]?.y).toBeLessThan(
      geometry.seriesPoints[0]?.[2]?.y ?? 0,
    )
  })

  it('keeps all-zero series on the baseline with axisMax 4', () => {
    const geometry = buildMultiSeriesGeometry([
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
    ])

    expect(geometry.axisMax).toBe(4)
    for (const series of geometry.seriesPoints) {
      for (const point of series) {
        expect(point.y).toBe(geometry.baselineY)
        expect(Number.isFinite(point.x)).toBe(true)
      }
    }
  })

  it('centres a single point shared by every series', () => {
    const geometry = buildMultiSeriesGeometry([[1], [2], [3], [0], [4]])

    const centre = (geometry.plotLeft + geometry.plotRight) / 2
    for (const series of geometry.seriesPoints) {
      expect(series).toHaveLength(1)
      expect(series[0]?.x).toBe(centre)
    }
    expect(geometry.xTicks).toEqual([{ index: 0, x: centre }])
  })

  it('returns safe empty geometry without NaN for no series or empty series', () => {
    const noSeries = buildMultiSeriesGeometry([])
    const emptySeries = buildMultiSeriesGeometry([[], [], []])

    expect(noSeries.seriesPoints).toEqual([])
    expect(emptySeries.seriesPoints).toEqual([[], [], []])

    for (const geometry of [noSeries, emptySeries]) {
      expect(geometry.xTicks).toEqual([])
      expect(Number.isFinite(geometry.baselineY)).toBe(true)
      expect(Number.isNaN(geometry.axisMax)).toBe(false)
    }
  })

  it('samples x-ticks with the shared sampling algorithm', () => {
    const values = Array.from({ length: 30 }, (_, index) => index)
    const geometry = buildMultiSeriesGeometry([values, values, values])
    const expectedIndexes = sampleTickIndexes(30, 8)

    expect(geometry.xTicks.map((tick) => tick.index)).toEqual(expectedIndexes)
    for (const series of geometry.seriesPoints) {
      expect(series.map((point) => point.x)).toEqual(
        geometry.seriesPoints[0]?.map((point) => point.x),
      )
    }
  })

  it('truncates unequal series to the shortest shared bucket count', () => {
    const geometry = buildMultiSeriesGeometry([
      [1, 2, 3],
      [1, 2],
      [1, 2, 3, 4],
    ])

    expect(geometry.seriesPoints.map((series) => series.length)).toEqual([
      2, 2, 2,
    ])
  })
})
