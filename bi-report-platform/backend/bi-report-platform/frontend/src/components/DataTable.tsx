import type { NumberFormat, QueryResult } from "../api/types";
import { money } from "../lib/format";
import { monthTotals } from "../lib/report";

export default function DataTable({ result, fmt }: { result: QueryResult; fmt: NumberFormat }) {
  const totals = monthTotals(result);
  const grand = totals.reduce((a, b) => a + b, 0);
  return (
    <div className="table-scroll">
      <table className="table num">
        <thead>
          <tr>
            <th scope="col">Region</th>
            {result.months.map((m) => <th scope="col" key={m} className="r">{m}</th>)}
            <th scope="col" className="r">Total</th>
          </tr>
        </thead>
        <tbody>
          {result.regions.map((reg) => (
            <tr key={reg}>
              <th scope="row">{reg}</th>
              {result.series[reg].map((v, i) => <td key={i} className="r">{money(v, fmt)}</td>)}
              <td className="r strong">{money(result.series[reg].reduce((a, b) => a + b, 0), fmt)}</td>
            </tr>
          ))}
          {result.regions.length > 1 && (
            <tr className="total-row">
              <th scope="row">All regions</th>
              {totals.map((v, i) => <td key={i} className="r">{money(v, fmt)}</td>)}
              <td className="r strong">{money(grand, fmt)}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
