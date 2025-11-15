"""ASCII trend plotting for compliance scores."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db.models import ComplianceScore


def plot_ascii_trend(scores: list[ComplianceScore], width: int = 50, height: int = 10) -> str:
    """
    Generate an ASCII sparkline/trend visualization of compliance scores.
    
    Args:
        scores: List of ComplianceScore records (ordered by time, oldest first)
        width: Width of the plot in characters
        height: Height of the plot in lines
        
    Returns:
        Multi-line string containing the ASCII plot
    """
    if not scores:
        return "No scores to plot."
    
    # Extract score values (reverse to show oldest to newest left to right)
    score_values = [s.overall_score for s in scores]
    
    if len(score_values) == 1:
        # Single point - just show the value
        return f"Score: {score_values[0]:.1f}"
    
    # Normalize scores to 0-height range
    min_score = min(score_values)
    max_score = max(score_values)
    score_range = max_score - min_score if max_score > min_score else 1.0
    
    # Map scores to plot coordinates
    plot_data = []
    for score in score_values:
        # Normalize to 0-1 range
        normalized = (score - min_score) / score_range
        # Map to 0-(height-1) range
        y = int(normalized * (height - 1))
        plot_data.append(y)
    
    # Create a grid
    grid = [[" " for _ in range(len(plot_data))] for _ in range(height)]
    
    # Plot points
    for x, y in enumerate(plot_data):
        grid[height - 1 - y][x] = "●"
    
    # Connect points with lines
    for x in range(len(plot_data) - 1):
        y1 = height - 1 - plot_data[x]
        y2 = height - 1 - plot_data[x + 1]
        
        if y1 == y2:
            # Horizontal line
            grid[y1][x] = "─"
        elif y1 < y2:
            # Upward line
            for y in range(y1, y2 + 1):
                if y == y1:
                    grid[y][x] = "╱"
                elif y == y2:
                    grid[y][x + 1] = "╱"
                else:
                    grid[y][x] = "│"
        else:
            # Downward line
            for y in range(y2, y1 + 1):
                if y == y1:
                    grid[y][x] = "╲"
                elif y == y2:
                    grid[y][x + 1] = "╲"
                else:
                    grid[y][x] = "│"
    
    # Build output
    lines = []
    lines.append(f"Score Trend (Range: {min_score:.1f} - {max_score:.1f})")
    lines.append("")
    
    # Add Y-axis labels
    for i in range(height):
        y_value = max_score - (i / (height - 1)) * score_range if height > 1 else max_score
        label = f"{y_value:5.1f} │"
        line = "".join(grid[i])
        lines.append(f"{label} {line}")
    
    # Add X-axis
    lines.append("      └" + "─" * len(plot_data))
    
    # Add score values below
    score_line = "       "
    for score in score_values:
        score_line += f"{score:.0f} "
    lines.append(score_line)
    
    return "\n".join(lines)


def format_score_table(scores: list[ComplianceScore]) -> str:
    """
    Format compliance scores as a simple table.
    
    Args:
        scores: List of ComplianceScore records
        
    Returns:
        Formatted table string
    """
    if not scores:
        return "No scores available."
    
    lines = []
    lines.append("Date       | Score  | RED | YELLOW | GREEN | Total")
    lines.append("-----------|--------|-----|--------|-------|------")
    
    for score in scores:
        date_str = score.created_at.strftime("%Y-%m-%d") if score.created_at else "N/A"
        lines.append(
            f"{date_str} | {score.overall_score:6.2f} | {score.red_count:3d} | "
            f"{score.yellow_count:6d} | {score.green_count:5d} | {score.total_flags:5d}"
        )
    
    return "\n".join(lines)

