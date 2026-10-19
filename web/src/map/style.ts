import type { ExpressionSpecification, LayerSpecification, Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';
import { token } from './tokens';

const empty = (): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features: [] });

// Widths grow linearly from zoom 13 to zoom 16.
const width = (a: number, b: number): ExpressionSpecification => ['interpolate', ['linear'], ['zoom'], 13, a, 16, b];
const cls = (...names: string[]): ExpressionSpecification => ['in', ['get', 'road_class'], ['literal', names]];
const kind = (k: string): ExpressionSpecification => ['==', ['get', 'kind'], k];

export function buildStyle(): StyleSpecification {
  const ink = token('--ink');
  const ink2 = token('--ink-2');
  const ink3 = token('--ink-3');
  const paper = token('--paper');
  const line = token('--line');
  const lime = token('--lime');
  const signal = token('--signal');
  const rain = token('--risk-rain');
  const air = token('--risk-air');
  const event = token('--risk-event');

  const round = { 'line-cap': 'round', 'line-join': 'round' } as const;
  const layers: LayerSpecification[] = [
    { id: 'background', type: 'background', paint: { 'background-color': token('--cream') } },
    {
      id: 'risk-fill', type: 'fill', source: 'risk',
      paint: {
        'fill-color': ['match', ['get', 'kind'], 'rain', rain, 'air', air, event],
        'fill-opacity': ['match', ['get', 'kind'], 'rain', 0.35, 'air', 0.35, 0.3],
      },
    },
    { id: 'risk-hatch', type: 'fill', source: 'risk', filter: kind('rain'), paint: { 'fill-pattern': 'mm-hatch' } },
    { id: 'risk-dots', type: 'fill', source: 'risk', filter: kind('air'), paint: { 'fill-pattern': 'mm-dots' } },
    {
      id: 'risk-outline', type: 'line', source: 'risk', filter: kind('event'),
      paint: { 'line-color': ink, 'line-width': 1.5, 'line-dasharray': [2, 2] },
    },
    {
      id: 'roads-minor', type: 'line', source: 'roads', filter: cls('residential', 'unclassified', 'service'),
      layout: round, paint: { 'line-color': line, 'line-width': width(1.5, 4) },
    },
    {
      id: 'roads-casing', type: 'line', source: 'roads', filter: cls('trunk', 'primary'),
      layout: round, paint: { 'line-color': ink2, 'line-width': width(5, 12) },
    },
    {
      id: 'roads-casing-minor', type: 'line', source: 'roads', filter: cls('secondary', 'tertiary'),
      layout: round, paint: { 'line-color': ink3, 'line-width': width(3.5, 9) },
    },
    {
      id: 'roads-fill', type: 'line', source: 'roads', filter: cls('trunk', 'primary'),
      layout: round, paint: { 'line-color': paper, 'line-width': width(3.5, 10) },
    },
    {
      id: 'roads-fill-minor', type: 'line', source: 'roads', filter: cls('secondary', 'tertiary'),
      layout: round, paint: { 'line-color': paper, 'line-width': width(2, 7) },
    },
    {
      id: 'protected', type: 'line', source: 'roads', filter: ['==', ['get', 'protected'], true],
      paint: { 'line-color': ink, 'line-width': 2, 'line-dasharray': [2, 1.5] },
    },
    {
      id: 'works-selected-ink', type: 'line', source: 'works', filter: ['==', ['get', 'selected'], true],
      layout: round, paint: { 'line-color': ink, 'line-width': width(13, 21) },
    },
    {
      id: 'works-selected', type: 'line', source: 'works', filter: ['==', ['get', 'selected'], true],
      layout: round, paint: { 'line-color': lime, 'line-width': width(10, 18) },
    },
    { id: 'works-casing', type: 'line', source: 'works', layout: round, paint: { 'line-color': paper, 'line-width': width(6, 12) } },
    {
      id: 'works', type: 'line', source: 'works', layout: round,
      paint: { 'line-color': ['get', 'color'], 'line-width': width(3.5, 8), 'line-opacity': ['case', ['get', 'faded'], 0.45, 1] },
    },
    {
      id: 'works-shared', type: 'line', source: 'works', filter: ['has', 'second_color'],
      paint: { 'line-color': ['get', 'second_color'], 'line-width': width(3.5, 8), 'line-dasharray': [1.5, 1.5] },
    },
    {
      id: 'clashes', type: 'circle', source: 'clashes',
      paint: { 'circle-radius': 7, 'circle-color': signal, 'circle-stroke-color': paper, 'circle-stroke-width': 2 },
    },
  ];

  return {
    version: 8,
    sources: {
      roads: { type: 'geojson', data: empty() },
      works: { type: 'geojson', data: empty() },
      risk: { type: 'geojson', data: empty() },
      clashes: { type: 'geojson', data: empty() },
    },
    layers,
  };
}

// 8×8 patterns for the rain and air areas.
export function addPatterns(map: MapLibreMap): void {
  const make = (draw: (ctx: CanvasRenderingContext2D) => void): ImageData => {
    const canvas = document.createElement('canvas');
    canvas.width = 8;
    canvas.height = 8;
    const ctx = canvas.getContext('2d')!;
    draw(ctx);
    return ctx.getImageData(0, 0, 8, 8);
  };
  const hatch = make((ctx) => {
    ctx.strokeStyle = token('--risk-rain');
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (const o of [-8, 0, 8]) {
      ctx.moveTo(o, 8 + 0);
      ctx.lineTo(o + 8, 0);
    }
    ctx.stroke();
  });
  const dots = make((ctx) => {
    ctx.fillStyle = token('--risk-air');
    ctx.beginPath();
    ctx.arc(4, 4, 1, 0, Math.PI * 2);
    ctx.fill();
  });
  if (!map.hasImage('mm-hatch')) map.addImage('mm-hatch', hatch);
  if (!map.hasImage('mm-dots')) map.addImage('mm-dots', dots);
}