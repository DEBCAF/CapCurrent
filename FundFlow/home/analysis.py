from datetime import datetime, date, timedelta
from typing import Iterable, List, Dict, Optional

try: # tries to import modules, but if it fails then none 
    import pandas as pd
    from scipy.stats import linregress
except Exception:
    pd = None
    linregress = None

from home.db_models import GroupTransaction, Group, Goal, GroupGoal, SavingChanges, User
import math

from pandas import Series

# Convert a list of transaction to a daily pandas series
def _to_dataframe(transactions: Iterable[Dict]) -> Optional[Series]:
    if pd is None: # prevents errors 
        return None
    # Convert a list of transactions to DataFrame
    df = pd.DataFrame(transactions)
    if df.empty: # if no data, return empty series
        return pd.Series(dtype=float)

    if 'date' not in df or 'amount' not in df:
        raise ValueError("transactions must include 'date' and 'amount' keys")

    # handles timezone
    df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert(None)

    # Sum per day
    daily = df.set_index('date').sort_index()['amount'].resample('D').sum()

    # Fill missing days with 0
    daily = daily.asfreq('D', fill_value=0.0)

    return daily

# Calculate rate per day from transactions
def rate_per_day(transactions: Iterable[Dict], lookback_days: int = 90) -> Optional[float]:
    # Infer daily rate from transactions
    daily = _to_dataframe(transactions)
    if daily is None or len(daily) == 0:
        return None
    # Get recent data within lookback period
    recent = daily.last(f'{lookback_days}D')
    if len(recent) == 0:
        return None

    # Multiple ways are used to find the rate, and the first valid one is returned
    
    # exponential weighted moving average with 14 smoothing amount: newer data gets more weight
    ewma_rate = recent.ewm(span=14).mean().iloc[-1]

    # weekly robust median
    weekly = recent.resample('W').sum() # sample weekly
    weekly_median_rate = weekly.median() / 7.0

    # regression slope
    slope_val = None
    # checks if have enough data points
    if linregress is not None and len(recent) > 5:
        # finding slope of cumulative sum which is a mostly increasing function
        cumsum = recent.cumsum()
        # converting dates into day offsets for regression
        x = (cumsum.index - cumsum.index[0]).days.values
        # y axis are the cumulative sums
        y = cumsum.values
        # perform linear regression
        slope, *_ = linregress(x, y)
        slope_val = slope
        
    # if only one data point, then smooth it out over a week
    if len(recent) == 1:
        return float(ewma_rate / 7.0)
    # if few deta points, then use weekly median 
    elif 1 < len(recent) <= 7:
        return float(weekly_median_rate)
    # if a lot of data points, then use regression
    if len(recent) >= 100:
        return float(slope_val)
    
    # chooses the first valid rate otherwise
    for r in (ewma_rate, weekly_median_rate, slope_val):
        if r is not None:
            return float(r)
    return None

def estimate_eta(remaining_amount: float, rate_per_day: Optional[float]) -> Optional[date]:
    # prevent division ballooning to a huge number if daily rate is tiny
    if rate_per_day is None or rate_per_day < 0.001:
        return None

    # calculate days needed
    days = math.ceil(remaining_amount / rate_per_day)
    return date.today() + timedelta(days=days)

def rate_breakdown(rate_per_day: Optional[float]) -> Dict[str, Optional[float]]:
    if rate_per_day is None:
        return {"per_day": None, "per_week": None, "per_month": None}
    # calculate weekly and monthly rates
    return {
        "per_day": rate_per_day,
        "per_week": rate_per_day * 7.0,
        "per_month": rate_per_day * 30.0,
    }

def required_rate(remaining_amount: float, days: int) -> Optional[float]:
    if days <= 0:
        return None
    return remaining_amount / float(days)

def group_transactions_as_movements(group_id: int, approved_only: bool = True) -> List[Dict]:
    # load group transactions, no need for goals since approved goals trigger transactions
    q = GroupTransaction.query.filter_by(group_id=group_id)
    if approved_only: # only approved transactions
        q = q.filter_by(status='approved')
    movements: List[Dict] = []
    # iterate through transactions and convert to movement format
    for tx in q.order_by(GroupTransaction.occurred_at.asc()).all():
        movements.append({
            "date": tx.occurred_at,
            "amount": float(tx.amount),
            "id": tx.id,
        })
    # sort by date just in case
    try:
        movements.sort(key=lambda m: m.get('date'))
    except Exception:
        pass

    return movements

def user_transactions_as_movements(user: User) -> List[Dict]:
    # load user saving changes as movements
    q = SavingChanges.query.filter_by(user_id=user.id)
    movements: List[Dict] = []
    # iterate through saving changes and convert to movement format
    for sc in q.order_by(SavingChanges.date_time.asc()).all():
        movements.append({
            "date": sc.date_time,
            "amount": float(sc.amount),
            "id": sc.id
        })
    return movements

def analyse_group(group: Group, goals: Iterable[GroupGoal], group_balance: float) -> Dict[int, Dict[str, Optional[float]]]:
    # get transaction movements of group
    tx = group_transactions_as_movements(group.id, approved_only=True)
    # calculate rate per day
    rate = rate_per_day(tx)
    # creating a dictionary of results for each goal
    results: Dict[int, Dict[str, Optional[float]]] = {}
    for g in goals:
        # calculates the remaining amount needed to complete 
        remaining = max(0.0, float(g.target_amount) - float(group_balance))
        # calculates estimated data of completion 
        eta = estimate_eta(remaining, rate)
        # gets the rate breakdown
        rb = rate_breakdown(rate)
        days = 30
        deadline_passed = False
        try: # tries to get the deadline if not then default 30 days 
            if getattr(g, 'deadline', None):
                dl = g.deadline
                if isinstance(dl, datetime):
                    dl_date = dl.date()
                else:
                    dl_date = dl
                days_left = (dl_date - date.today()).days
                if days_left is None:
                    days = 30
                    deadline_passed = False
                elif days_left < 0:
                    # deadline has passed: mark and fall back to 30-day required rate
                    days = 30
                    deadline_passed = True
                else:
                    days = max(1, days_left)
                    deadline_passed = False
        except Exception:
            days = 30
            deadline_passed = False
        # calculates the required rate daily to complete the goal in time
        required_daily = required_rate(remaining, days)
        # creates new dictionary for each goal containing the analysis  
        results[g.id] = {
            "remaining": remaining,
            "rate_per_day": rb["per_day"],
            "rate_per_week": rb["per_week"],
            "rate_per_month": rb["per_month"],
            "eta_ts": None if eta is None else eta.isoformat(),
            "required_daily": required_daily,
            "deadline_passed": deadline_passed,
            "progress_percent": (group_balance / g.target_amount * 100) if g.target_amount > 0 else 0
        }
    return results

def analyse_user(user: User, goals: Iterable[Goal], current_savings: float) -> Dict[int, Dict[str, Optional[float]]]:
    # get changes in savings as movements
    tx = user_transactions_as_movements(user)
    # calculate rate per day 
    rate = rate_per_day(tx)
    # creating a dictionary of results for each goal
    results: Dict[int, Dict[str, Optional[float]]] = {}
    for g in goals:
        # calculates the remaining amount needed to complete 
        remaining = max(0.0, float(g.target_amount) - float(current_savings))
        # calculates estimated data of completion 
        eta = estimate_eta(remaining, rate)
        # gets the rate breakdown
        rb = rate_breakdown(rate)
        days = 30
        deadline_passed = False
        try: # tries to get the deadline if not then default 30 days 
            if getattr(g, 'deadline', None):
                dl = g.deadline
                if isinstance(dl, datetime):
                    dl_date = dl.date()
                else:
                    dl_date = dl
                days_left = (dl_date - date.today()).days
                if days_left is None:
                    days = 30
                    deadline_passed = False
                elif days_left < 0:
                    days = 30
                    deadline_passed = True
                else:
                    days = max(1, days_left)
                    deadline_passed = False
        except Exception:
            days = 30
            deadline_passed = False
        # calculates the required rate daily to complete the goal in time
        required_daily = required_rate(remaining, days)
        # creates new dictionary for each goal containing the analysis  
        results[g.id] = {
            "remaining": remaining,
            "rate_per_day": rb["per_day"],
            "rate_per_week": rb["per_week"],
            "rate_per_month": rb["per_month"],
            "eta_ts": None if eta is None else eta.isoformat(),
            "required_daily": required_daily,
            "deadline_passed": deadline_passed,
            "progress_percent": (current_savings / g.target_amount * 100) if g.target_amount > 0 else 0
        }
    return results

