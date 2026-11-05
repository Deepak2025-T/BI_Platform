/**
 * "Download PDF": printing a report so the sheet looks like the screen.
 *
 * Charts are drawn on a canvas whose size is fixed in pixels when it is drawn. The browser cannot
 * reflow a canvas the way it reflows text, so a chart printed straight from the screen keeps its
 * on-screen width and runs off the edge of the paper. So before the print dialog opens, the page is
 * laid out at the width of a printed sheet (body.printing, see app.css), every chart is redrawn at
 * that width, and the page is put back afterwards.
 */

import * as echarts from "echarts/core";

/** One animation frame, so the browser applies the new width before anything measures it. */
const frame = () => new Promise<void>((done) => requestAnimationFrame(() => done()));

function resizeCharts() {
  // echarts-for-react marks the element it drew into with this attribute.
  document.querySelectorAll<HTMLElement>("[_echarts_instance_]").forEach((el) => {
    try {
      echarts.getInstanceByDom(el)?.resize();
    } catch {
      /* A chart that has already been disposed is nothing to worry about. */
    }
  });
}

export async function printReport() {
  document.body.classList.add("printing");
  try {
    await frame();
    await frame();
    resizeCharts();
    await frame();
    window.print();
  } finally {
    document.body.classList.remove("printing");
    await frame();
    resizeCharts();  // back to the width of the screen
  }
}
