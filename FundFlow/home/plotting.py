from io import BytesIO
from typing import Optional
import matplotlib.dates as mdates

try: # tries to import modules, but if it fails then none 
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except Exception:
    plt = None

from pandas import Series

# generates a cumulative savings graph from a transaction series
def plot_cumulative_savings(daily_series: Optional[Series], title: str = "Cumulative Savings") -> Optional[bytes]:
    # prevents errors from null 
    if plt is None:
        return None
    if daily_series is None or len(daily_series) == 0:
        return None
    
    # catches errors if they occur 
    try:
        # gets a series of cumulative sums
        cumsum = daily_series.cumsum()
        # creates a figure and axis for plotting
        fig, ax = plt.subplots(figsize=(10, 5))
        # plotting the dates (index) on the y axis and the cumulative sums (values) on the x axis
        ax.plot(cumsum.index, cumsum.values, linewidth=2, color='#000080')
        # shading under the line with slight transparency
        ax.fill_between(cumsum.index, cumsum.values, alpha=0.3, color='#000080')
        # setting the title (default Cumulative Savings)
        ax.set_title(title, fontsize=14, fontweight='bold')
        # labelling the x and y axes 
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Savings')
        # adding a grid 
        ax.grid(True, alpha=0.3)
        
        # adjusting layout to fit format 
        fig.tight_layout()
        # setting specific points where the dates are displayed to prevent overlap
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        
        # saving the figure to a bytes buffer
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=100)
        buffer.seek(0)
        plt.close(fig)
        
        return buffer.getvalue()
    
    except Exception as e:
        # notifies user of any errors
        print(f"Error plotting cumulative savings: {e}")
        plt.close('all')
        return None

# generates a daily change graph from a transaction series
def plot_daily_change(daily_series: Optional[Series], title: str = "Daily Changes") -> Optional[bytes]:
    # prevents errors from null 
    if plt is None:
        return None
    if daily_series is None or len(daily_series) == 0:
        return None
    
    # catches errors if they occur 
    try:
        # creates a figure and axis for plotting
        fig, ax = plt.subplots(figsize=(10, 5))
        
        # colour positive and negative bars differently
        colours = ['#00A36C' if x > 0 else '#c41e3a' for x in daily_series.values]
        # using bar chart since discreet daily changes
        ax.bar(daily_series.index, daily_series.values, color=colours)
        # setting the title (default Daily Changes)
        ax.set_title(title, fontsize=14, fontweight='bold')
        # labelling the x and y axes
        ax.set_xlabel('Date')
        ax.set_ylabel('Daily Change')
        # adding a horizontal line on the x axis for reference if the graph goes up and down
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        # adding a grid
        ax.grid(True, alpha=0.3, axis='y')
        
        # adjusting layout to fit format
        fig.tight_layout()
        # setting specific points where the dates are displayed to prevent overlap
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        
        # saving the figure to a bytes buffer
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=100)
        buffer.seek(0)
        plt.close(fig)
        return buffer.getvalue()
    
    except Exception as e:
        # notifies user of any errors
        print(f"Error plotting daily change: {e}")
        plt.close('all')
        return None