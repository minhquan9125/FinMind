import { FACTS, formatFact } from "./financials.js";

function FinancialTrend({ periods, metric, title, teal = false }) {
  const values = periods.map((period) => {
    const fact = period.facts?.[metric];
    const confirmedUnit =
      fact?.unit === "VND" || fact?.unit === "SOURCE_NATIVE";
    return confirmedUnit &&
      fact.value != null &&
      Number.isFinite(Number(fact.value))
      ? Number(fact.value) / 1e9
      : null;
  });
  const actual = values.filter((value) => value !== null);
  const min = Math.min(0, ...actual),
    max = Math.max(0, ...actual);
  const scale = (value) => 115 - ((value - min) / (max - min || 1)) * 100;
  const baseline = scale(0),
    width = 300 / Math.max(1, periods.length);
  return (
    <section className={`approved-financial-trend ${teal ? "teal" : ""}`}>
      <h3>{title}</h3>
      <p>Theo kỳ báo cáo · Tỷ đồng</p>
      {actual.length ? (
        <svg
          viewBox="0 0 340 160"
          role="img"
          aria-label={`${title} theo ${periods.length} kỳ báo cáo, đơn vị tỷ đồng`}
        >
          <line x1="15" x2="325" y1={baseline} y2={baseline} stroke="#e7edf5" />
          {periods.map((period, index) => {
            const value = values[index],
              x = 20 + (index + 0.5) * width;
            return (
              <g key={period.period}>
                <title>
                  {period.label || period.period}:{" "}
                  {value === null
                    ? "Chưa có số liệu cùng đơn vị"
                    : formatFact(period.facts[metric], "money")}
                </title>
                {value !== null && (
                  <rect
                    x={x - Math.min(16, width * 0.3)}
                    y={Math.min(baseline, scale(value))}
                    width={Math.min(32, width * 0.6)}
                    height={Math.max(1, Math.abs(baseline - scale(value)))}
                    rx="3"
                    fill={teal ? "#13a28f" : "#2d7dec"}
                  />
                )}
                <text
                  x={x}
                  y={
                    value === null
                      ? 70
                      : value >= 0
                        ? Math.max(10, scale(value) - 6)
                        : Math.min(128, scale(value) + 10)
                  }
                  textAnchor="middle"
                  fontSize="8"
                  fill="#73839a"
                >
                  {value === null
                    ? "—"
                    : value.toLocaleString("vi-VN", {
                        maximumFractionDigits: 0,
                      })}
                </text>
                <text
                  x={x}
                  y="148"
                  textAnchor="middle"
                  fontSize="8"
                  fill="#8a97a9"
                >
                  {period.period.replace("-YEAR", "")}
                </text>
              </g>
            );
          })}
        </svg>
      ) : (
        <p className="approved-financial-no-data">
          Chưa có số liệu cùng đơn vị để vẽ biểu đồ.
        </p>
      )}
    </section>
  );
}

export default function CompanyFinancialSummary({ company, selected }) {
  if (!selected) return null;
  const annual = selected.period.endsWith("YEAR");
  const periods = (company.periods || [])
    .filter(
      (period) =>
        period.period.endsWith("YEAR") === annual &&
        period.period <= selected.period,
    )
    .sort((a, b) => a.period.localeCompare(b.period))
    .slice(-6);
  return (
    <>
      <div className="approved-financial-kpis">
        {["revenue", "netProfit", "totalAssets", "roe"].map((key) => {
          const fact = FACTS.find((item) => item.key === key);
          return (
            <div className="approved-financial-kpi" key={key}>
              <span>
                {key === "revenue"
                  ? "Doanh thu / Thu nhập hoạt động"
                  : fact.label}
              </span>
              <strong>{formatFact(selected.facts?.[key], fact.kind)}</strong>
              <small>{selected.label || selected.period}</small>
            </div>
          );
        })}
      </div>
      <div className="approved-financial-trends">
        <FinancialTrend
          title="Doanh thu / Thu nhập hoạt động"
          metric="revenue"
          periods={periods}
        />
        <FinancialTrend
          title="Lợi nhuận sau thuế"
          metric="netProfit"
          periods={periods}
          teal
        />
      </div>
    </>
  );
}
