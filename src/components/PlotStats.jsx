// src/components/PlotStats.jsx
import './PlotStats.css';

export default function PlotStats({ buffer, pvName }) {
  if (!buffer || buffer.getPointCount() === 0) {
    return (
      <div className="plot-stats">
        <div className="stat-item">
          <span className="stat-label">Waiting for data...</span>
        </div>
      </div>
    );
  }

  const data = buffer.getData();
  const values = data.y;
  
  const current = values[values.length - 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const avg = values.reduce((a, b) => a + b, 0) / values.length;

  return (
    <div className="plot-stats">
      <div className="stat-item">
        <span className="stat-label">Current</span>
        <span className="stat-value">{current.toExponential(2)}</span>
      </div>
      <div className="stat-item">
        <span className="stat-label">Min</span>
        <span className="stat-value">{min.toExponential(2)}</span>
      </div>
      <div className="stat-item">
        <span className="stat-label">Max</span>
        <span className="stat-value">{max.toExponential(2)}</span>
      </div>
      <div className="stat-item">
        <span className="stat-label">Avg</span>
        <span className="stat-value">{avg.toExponential(2)}</span>
      </div>
      <div className="stat-item">
        <span className="stat-label">Points</span>
        <span className="stat-value">{values.length}</span>
      </div>
    </div>
  );
}
