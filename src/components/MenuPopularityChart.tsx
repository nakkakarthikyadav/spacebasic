/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface MealData {
  category: string;
  count: number;
  color: string;
}

export default function MenuPopularityChart() {
  const chartRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    const svgElement = chartRef.current;
    if (!svgElement) return;

    // Clear previous chart
    d3.select(svgElement).selectAll("*").remove();

    const data: MealData[] = [
      { category: 'Non-Veg', count: 14, color: '#4f46e5' },   // Indigo-600
      { category: 'Eggitarian', count: 8, color: '#0ea5e9' },  // Sky-500
      { category: 'Veg (Fallback)', count: 4, color: '#10b981' } // Emerald-500
    ];

    const width = 450;
    const height = 280;
    const margin = { top: 20, right: 30, bottom: 40, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgElement)
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('width', '100%')
      .attr('height', '100%')
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // X scale
    const x = d3.scaleBand()
      .domain(data.map(d => d.category))
      .range([0, innerWidth])
      .padding(0.4);

    // Y scale
    const y = d3.scaleLinear()
      .domain([0, 16])
      .nice()
      .range([innerHeight, 0]);

    // Add X axis
    svg.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
      .attr('font-size', '11px')
      .attr('fill', '#64748b');

    // Add Y axis
    svg.append('g')
      .call(d3.axisLeft(y).ticks(4))
      .selectAll('text')
      .attr('font-size', '11px')
      .attr('fill', '#64748b');

    // Add grid lines
    svg.append('g')
      .attr('class', 'grid')
      .attr('opacity', 0.1)
      .call(d3.axisLeft(y).ticks(4).tickSize(-innerWidth).tickFormat(() => ''));

    // Tooltip div
    const tooltip = d3.select('body').selectAll('.d3-tooltip').data([0]).join('div')
      .attr('class', 'd3-tooltip')
      .style('position', 'absolute')
      .style('visibility', 'hidden')
      .style('background', '#0f172a')
      .style('color', '#fff')
      .style('padding', '6px 10px')
      .style('border-radius', '6px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('box-shadow', '0 4px 6px -1px rgb(0 0 0 / 0.1)');

    // Add bars with animation
    svg.selectAll('.bar')
      .data(data)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', d => x(d.category) || 0)
      .attr('width', x.bandwidth())
      .attr('y', innerHeight)
      .attr('height', 0)
      .attr('fill', d => d.color)
      .attr('rx', 6)
      .on('mouseover', (event, d) => {
        tooltip.style('visibility', 'visible')
          .text(`${d.category}: ${d.count} meals chosen`);
      })
      .on('mousemove', (event) => {
        tooltip.style('top', `${event.pageY - 35}px`)
          .style('left', `${event.pageX + 10}px`);
      })
      .on('mouseout', () => {
        tooltip.style('visibility', 'hidden');
      })
      .transition()
      .duration(800)
      .attr('y', d => y(d.count))
      .attr('height', d => innerHeight - y(d.count));

    // Add value labels on top of bars
    svg.selectAll('.label')
      .data(data)
      .enter()
      .append('text')
      .attr('class', 'label')
      .attr('x', d => (x(d.category) || 0) + x.bandwidth() / 2)
      .attr('y', d => y(d.count) - 8)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('font-weight', '600')
      .attr('fill', '#334155')
      .text(d => `${d.count} days`);

  }, []);

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-slate-900">Menu Popularity (Past 30 Days)</h3>
          <p className="text-xs text-slate-500 mt-0.5">Frequency distribution of auto-booked meal preferences</p>
        </div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
          <span className="w-2 h-2 rounded-full bg-indigo-600"></span>
          <span>Total 26 Working Days</span>
        </div>
      </div>
      
      <div className="w-full h-[280px] flex items-center justify-center">
        <svg ref={chartRef}></svg>
      </div>
    </div>
  );
}
